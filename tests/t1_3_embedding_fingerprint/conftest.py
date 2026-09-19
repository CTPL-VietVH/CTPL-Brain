"""Nền chung cho test T1.3 — chèn `packages/` vào sys.path, kết nối Postgres và
Qdrant THẬT trên máy dev, giống hệt `tests/t0_1_stores/conftest.py`.

Hai điều cố ý ở đây:

1. **Không có giá trị mặc định trong mã** cho tham số kết nối — thiếu `.env`
   hoặc thiếu một khoá `CBRAIN_*` thì `pytest.fail` ngay, nêu rõ tên khoá.
2. **Bảng `embedding_models` / `embedding_model_collections` là hạ tầng dùng
   chung LÂU DÀI**, không phải bảng thăm dò riêng của T0.1 — nên fixture ở
   đây CHỈ tạo bảng (`CREATE TABLE IF NOT EXISTS`, DDL lấy từ hằng số export
   trong `schema.embedding_registry`, không hard-code lại SQL) và mỗi test tự
   xoá đúng NHỮNG DÒNG mình tạo ra sau khi chạy xong — không `DROP TABLE`.
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
        # DDL THẬT của module code — test không hard-code lại SQL của mình.
        conn.execute(EMBEDDING_MODELS_TABLE_DDL)
        conn.execute(EMBEDDING_MODEL_COLLECTIONS_TABLE_DDL)
        yield conn


@pytest.fixture(scope="session")
def qdrant(_env: None) -> QdrantClient:
    host = _require("CBRAIN_QDRANT_HOST")
    port = int(_require("CBRAIN_QDRANT_HTTP_PORT"))
    client = QdrantClient(host=host, port=port)
    client.get_collections()  # nổ sớm nếu kho chưa chạy
    return client


@pytest.fixture
def probe_collection(qdrant: QdrantClient):
    """Một collection Qdrant dùng một lần, xoá sạch sau mỗi ca thử."""
    created: list[str] = []

    def _make(name_hint: str, *, size: int, distance: models.Distance = models.Distance.COSINE) -> str:
        name = f"t1_3_{name_hint}_{uuid.uuid4().hex[:8]}"
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
    """Sổ ghi những dòng catalog test này tự tạo, để dọn đúng CHÚNG sau khi
    xong — không đụng gì tới dữ liệu catalog khác đã có sẵn trên máy, và
    KHÔNG bao giờ `DROP TABLE` (bảng là hạ tầng dùng chung lâu dài).

    Dùng: `created_models, created_collections = catalog_rows`, rồi
    `.append(...)` mỗi khi gọi `register_embedding_model` /
    `set_active_embedding_model_for_collection` thành công.

    Thứ tự xoá: bảng con (`embedding_model_collections`) trước, bảng cha
    (`embedding_models`) sau — đúng chiều khoá ngoại.
    """
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
