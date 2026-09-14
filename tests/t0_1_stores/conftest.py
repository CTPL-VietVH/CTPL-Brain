"""Nền chung cho bằng chứng nghiệm thu T0.1.

Hai điều cố ý ở đây:

1. **Không có giá trị mặc định trong mã.** Thiếu một khoá kết nối thì dừng ngay
   kèm tên khoá, không "đoán localhost". Đây là cùng hình dạng với quy tắc
   CLAUDE.md Mục 4 quy tắc 2 — dựng thói quen từ Nhóm 0 để tới T1.2 không phải
   sửa lại nếp.

2. **Bảng thăm dò nằm trong schema riêng `t0_1_probe`.** T0.1 chứng minh KHO
   LÀM ĐƯỢC GÌ, không phải chốt tên trường — tên trường là việc của T1.1 và
   phải định nghĩa đúng một lần trong `packages/schema/`. Đặt bảng thăm dò ở
   schema riêng với tên riêng để không ai nhầm nó là hợp đồng dữ liệu.
"""

from __future__ import annotations

import os
import pathlib
import uuid

import psycopg
import pytest
from dotenv import load_dotenv
from qdrant_client import QdrantClient

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PROBE_SCHEMA = "t0_1_probe"

# Chiều vector dùng cho bảng thăm dò. Soi theo BGE-M3 (1024) để phép thử phản
# ánh đúng khối lượng thật, nhưng đây KHÔNG phải `embedding_dim` của nhóm cấu
# hình hợp đồng — khoá đó có nhà ở T1.2, không phải ở đây.
PROBE_VECTOR_SIZE = 1024


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
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {PROBE_SCHEMA}")
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
    """Một collection dùng một lần, xoá sạch sau mỗi ca thử."""
    created: list[str] = []

    def _make(name_hint: str, **kwargs) -> str:
        name = f"t0_1_{name_hint}_{uuid.uuid4().hex[:8]}"
        from qdrant_client import models

        qdrant.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=kwargs.pop("size", PROBE_VECTOR_SIZE),
                distance=kwargs.pop("distance", models.Distance.COSINE),
            ),
            **kwargs,
        )
        created.append(name)
        return name

    yield _make

    for name in created:
        qdrant.delete_collection(collection_name=name)
