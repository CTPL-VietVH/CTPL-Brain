"""Nền chung cho test T2.5 — chèn `packages/` vào sys.path, nạp model BGE-M3
THẬT (giống `tests/t0_2_embedding/conftest.py`), và kết nối Postgres/Qdrant
THẬT trên máy dev (giống `tests/t1_3_embedding_fingerprint/conftest.py`).

Không mock model lẫn kho — task T2.5 cho phép gọi thật, đúng cách đã verify.
"""

from __future__ import annotations

import os
import pathlib
import sys
import uuid

import psycopg
import pytest
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from schema.embedding_registry import (  # noqa: E402
    EMBEDDING_MODEL_COLLECTIONS_TABLE,
    EMBEDDING_MODEL_COLLECTIONS_TABLE_DDL,
    EMBEDDING_MODELS_TABLE,
    EMBEDDING_MODELS_TABLE_DDL,
)

MODEL_HOME = REPO_ROOT / ".runtime" / "models"
CONTRACT_PATH = REPO_ROOT / "config" / "contract.yaml"

DOC_ID = "doc-t2-5-1"
SPACE_ID = "space-t2-5-1"
TENANT_ID = "tenant-t2-5-1"

# Một Khoản hành chính VN viết dài như ngoài đời — tái dùng đúng văn bản
# `tests/t0_2_embedding/test_bge_m3_contract.py` đã verify hành vi trần ngữ
# cảnh trên đó, để không phải chứng minh lại từ đầu văn bản nào "đủ dài".
KHOAN_DAI = (
    "Điều 12. Trình tự, thủ tục xử lý vi phạm trong hoạt động đấu thầu\n"
    "1. Khi phát hiện hành vi vi phạm quy định của pháp luật về đấu thầu, "
    "người có thẩm quyền hoặc chủ đầu tư có trách nhiệm tạm dừng ngay các "
    "hoạt động có liên quan và lập biên bản ghi nhận sự việc, trong đó nêu "
    "rõ thời điểm phát hiện, nội dung vi phạm, tổ chức và cá nhân có liên "
    "quan, cùng các tài liệu, chứng cứ kèm theo. "
)


def _require(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        pytest.fail(
            f"Thiếu khoá cấu hình '{name}'. Không có giá trị mặc định trong mã — "
            f"chép .env.example thành .env và điền."
        )
    return value


@pytest.fixture(scope="session", autouse=True)
def _env() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        pytest.fail(f"Thiếu {env_file}. Chạy: cp .env.example .env")
    load_dotenv(env_file)


@pytest.fixture(scope="session")
def model():
    """Nạp BGE-M3 từ đĩa cục bộ MỘT LẦN cho cả phiên test — đúng cách
    `tests/t0_2_embedding/conftest.py` đã verify, KHÔNG tự chế lại."""
    os.environ["HF_HOME"] = str(MODEL_HOME)
    os.environ["HF_HUB_OFFLINE"] = "1"

    from sentence_transformers import SentenceTransformer

    if not MODEL_HOME.exists():
        pytest.fail(f"Chưa tải mô hình về {MODEL_HOME}. Xem tests/t0_2_embedding/README.md")
    return SentenceTransformer("BAAI/bge-m3")


@pytest.fixture(scope="session")
def pg_dsn(_env: None) -> str:
    host = _require("CBRAIN_PG_HOST")
    port = _require("CBRAIN_PG_PORT")
    db = _require("CBRAIN_PG_DATABASE")
    user = _require("CBRAIN_PG_USER")
    password = os.environ.get("CBRAIN_PG_PASSWORD") or ""
    auth = f"{user}:{password}" if password else user
    return f"postgresql://{auth}@{host}:{port}/{db}"


@pytest.fixture(scope="session")
def pg(pg_dsn: str):
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(EMBEDDING_MODELS_TABLE_DDL)
        conn.execute(EMBEDDING_MODEL_COLLECTIONS_TABLE_DDL)
        yield conn


@pytest.fixture(scope="session")
def qdrant(_env: None) -> QdrantClient:
    host = _require("CBRAIN_QDRANT_HOST")
    port = int(_require("CBRAIN_QDRANT_HTTP_PORT"))
    client = QdrantClient(host=host, port=port)
    client.get_collections()
    return client


@pytest.fixture
def probe_collection(qdrant: QdrantClient):
    """Một collection Qdrant dùng một lần, xoá sạch sau mỗi ca thử."""
    created: list[str] = []

    def _make(name_hint: str, *, size: int, distance: models.Distance = models.Distance.COSINE) -> str:
        name = f"t2_5_{name_hint}_{uuid.uuid4().hex[:8]}"
        qdrant.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=size, distance=distance),
        )
        created.append(name)
        return name

    yield _make

    for name in created:
        qdrant.delete_collection(collection_name=name)


@pytest.fixture
def catalog_rows(pg):
    """Sổ ghi dòng catalog test này tự tạo — dọn đúng CHÚNG, không đụng dữ
    liệu khác, không bao giờ `DROP TABLE` (cùng khuôn `tests/t1_3_.../conftest.py`)."""
    created_models: list[tuple[str, str]] = []
    created_collections: list[str] = []

    yield created_models, created_collections

    for collection_name in created_collections:
        pg.execute(
            f"DELETE FROM {EMBEDDING_MODEL_COLLECTIONS_TABLE} WHERE collection_name = %s",
            (collection_name,),
        )
    for model_name, model_version in created_models:
        pg.execute(
            f"DELETE FROM {EMBEDDING_MODELS_TABLE} WHERE model_name = %s AND model_version = %s",
            (model_name, model_version),
        )


@pytest.fixture
def stamped_collection(qdrant, pg, probe_collection, catalog_rows):
    """Một collection Qdrant MỚI, đã đóng dấu active đúng model/version khớp
    `config/contract.yaml` thật (BAAI/bge-m3, 1024 chiều, cosine) — dùng cho
    mọi test cần `ghi_vao_qdrant` chạy trọn qua bước kiểm con dấu."""
    from schema.embedding_registry import (
        register_embedding_model,
        set_active_embedding_model_for_collection,
    )

    created_models, created_collections = catalog_rows
    name = probe_collection("stamped", size=1024, distance=models.Distance.COSINE)

    register_embedding_model(
        pg_connection=pg, model_name="BAAI/bge-m3", model_version="v1", embedding_dim=1024
    )
    created_models.append(("BAAI/bge-m3", "v1"))
    set_active_embedding_model_for_collection(
        pg_connection=pg, collection_name=name, model_name="BAAI/bge-m3", model_version="v1"
    )
    created_collections.append(name)
    return name
