"""Nền chung cho test T2.1 — chèn `packages/` vào sys.path để import
`ingestion.*` và `schema.*`, cùng cách `tests/t1_1_schema/conftest.py` làm.

──────────────────────────────────────────────────────────────────────────
KHO-PG-A — `fingerprint_index` tham số hoá InMemory / PostgreSQL
──────────────────────────────────────────────────────────────────────────

`fingerprint_index` giờ chạy trên CẢ HAI cài đặt của `intake.FingerprintIndex`:
`InMemoryFingerprintIndex` (không đổi) và `ingestion.pg_document_stores.
PgDocumentStore` (mới — packages/ingestion/pg_document_stores.py). Mọi hàm
`test_*` nhận `fingerprint_index` qua fixture này tự động chạy hai lần, không
cần sửa thân hàm — đúng yêu cầu "tham số hoá ... không viết lại hành vi mong
đợi lần hai".

`space_registry` GIỮ NGUYÊN InMemory — `packages/ingestion/space_registry.py`
thuộc phạm vi KHO-PG-B (chạy song song), work-order này không được đụng vào.

Nhánh "pg" đòi `.env` (biến `CBRAIN_PG_*`) và một PostgreSQL đang chạy — thiếu
một trong hai thì `pytest.fail` ngay, KHÔNG skip im lặng. Nhánh "memory"
không chạm gì tới Postgres, nên không bị ảnh hưởng khi `.env`/kho vắng mặt.

Mỗi ca thử "pg" chạy trong một kết nối RIÊNG, không tự động commit
(`autocommit` mặc định `False` của psycopg) — cả bài test coi như một giao
dịch ngoài cùng, `conn.rollback()` ở cuối fixture xoá sạch mọi thứ ca đó ghi.
`PgDocumentStore.write_document_and_relations` tự mở `with connection.
transaction():` bên trong — psycopg nhận ra giao dịch ngoài đã mở sẵn nên
dùng SAVEPOINT lồng vào, không xung đột với cơ chế rollback-mỗi-ca-thử này.
"""

from __future__ import annotations

import os
import pathlib
import sys
from datetime import date, datetime, timezone

import psycopg
import pytest
from dotenv import load_dotenv

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from ingestion.intake import IntakeRequest, InMemoryFingerprintIndex  # noqa: E402
from ingestion.pg_document_stores import PgDocumentStore  # noqa: E402
from ingestion.space_registry import InMemorySpaceRegistry  # noqa: E402
from schema.document import DateSource  # noqa: E402
from schema.store_schema import SHARED_STORE_DDL  # noqa: E402

#: Mọi Space mà các ca thử T2.1 dùng tới. T2.11 (docs/10 §4.0) đặt một cổng
#: chặn ở `decide_intake`: `space_id` phải đã đăng ký và đang dùng. Các ca ở
#: đây nói về trùng lặp và chuỗi phiên bản, không nói về cổng đó — nên chúng
#: chạy trong một sổ đăng ký đã có sẵn cả hai Space. Chính cổng đó được kiểm
#: ở `tests/t2_11_space_registry/`.
SPACES_USED_BY_THESE_CASES = ("space-a", "space-b")


# --------------------------------------------------------------------------- #
# Kết nối PostgreSQL — CHỈ dựng khi một ca thử thật sự xin nhánh "pg" (qua
# `request.getfixturevalue` bên dưới), nên nhánh "memory" không bao giờ đòi
# `.env` hay một Postgres đang chạy.
# --------------------------------------------------------------------------- #


def _require(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        pytest.fail(
            f"Thiếu khoá cấu hình '{name}'. Không có giá trị mặc định trong mã — "
            f"chép .env.example thành .env và điền."
        )
    return value


@pytest.fixture(scope="session")
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
def _pg_schema_ready(pg_dsn: str) -> None:
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        for statement in SHARED_STORE_DDL:
            conn.execute(statement)


@pytest.fixture
def pg_connection(pg_dsn: str, _pg_schema_ready: None):
    """Một kết nối riêng cho một ca thử, luôn ROLLBACK ở cuối — dù ca thử qua
    hay trượt — nên không có dữ liệu nào của một ca thử "pg" sống sót sang ca
    kế tiếp.

    `psycopg.Rollback`, raise BÊN TRONG khối `with conn.transaction():`, là
    cách psycopg3 tài liệu hoá để buộc rollback một giao dịch mà KHÔNG cho
    lỗi đó thoát ra ngoài — quan trọng vì gọi `conn.rollback()` sau khi khối
    `with` đã tự COMMIT (hành vi thật của `Connection.transaction()` khi nó
    là khối giao dịch NGOÀI CÙNG — không có `BEGIN` nào mở sẵn trước đó dù
    `autocommit=False`) sẽ không xoá được gì — đã kiểm chứng bằng tay trước
    khi chốt cách này. Đặt khối `with conn.transaction():` ở NGOÀI (bên trong
    fixture này), lời gọi `with self._connection.transaction():` bên trong
    `PgDocumentStore`/`PgDeletionLog` sẽ tự lồng thành SAVEPOINT thay vì tự
    COMMIT — psycopg3 phát hiện đã có một khối giao dịch mở và không tạo
    khối gốc thứ hai.
    """
    with psycopg.connect(pg_dsn) as conn:
        with conn.transaction():
            yield conn
            raise psycopg.Rollback


@pytest.fixture(params=["memory", "pg"], ids=["memory", "pg"])
def fingerprint_index(request: pytest.FixtureRequest):
    if request.param == "pg":
        pg_connection = request.getfixturevalue("pg_connection")
        return PgDocumentStore(connection=pg_connection)
    return InMemoryFingerprintIndex()


@pytest.fixture
def space_registry() -> InMemorySpaceRegistry:
    registry = InMemorySpaceRegistry()
    for space_id in SPACES_USED_BY_THESE_CASES:
        registry.register(space_id)
    return registry


def make_request(
    *,
    document_id: str,
    space_id: str,
    content_fingerprint: str,
    tenant_id: str = "tenant-1",
    declared_previous_version=None,
) -> IntakeRequest:
    """Dựng một `IntakeRequest` hợp lệ tối thiểu — các trường không liên quan
    tới quyết định trùng lặp/bản mới được điền giá trị cố định vô hại.

    `ingested_at` mang `tzinfo=UTC` (không còn naive) để vòng ghi-đọc qua
    PostgreSQL (cột `timestamptz`) trả về đúng cùng một thời điểm — naive so
    aware qua `==` luôn `False` dù cùng một khắc giờ.
    """
    return IntakeRequest(
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        title="Quyết định về việc ban hành quy chế",
        doc_number="15/2024/QĐ-TGĐ",
        issued_date=date(2024, 1, 10),
        issued_date_source=DateSource.EXTRACTED,
        effective_date=date(2024, 2, 1),
        effective_date_source=DateSource.CONFIRMED,
        ingested_at=datetime(2024, 1, 12, 9, 0, tzinfo=timezone.utc),
        source_format="pdf",
        content_fingerprint=content_fingerprint,
        extracted_text="Toàn văn ở đây.",
        declared_previous_version=declared_previous_version,
    )
