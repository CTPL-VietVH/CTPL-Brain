"""Shared fixtures for T2.6 (relation scan orchestration) tests — inserts
`packages/` into `sys.path` to import `ingestion.*` and `schema.*`, same as
`tests/t2_6_relations/conftest.py`.

──────────────────────────────────────────────────────────────────────────
KHO-PG-A — `document_source_factory` tham số hoá InMemory / PostgreSQL
──────────────────────────────────────────────────────────────────────────

`SpaceDocumentSource` (relations_scan.py) giờ có hai cài đặt: `InMemorySpace
DocumentSource` (không đổi) và `ingestion.pg_document_stores.PgDocumentStore`
(mới). `document_source_factory` là một callable `[Document] -> SpaceDocument
Source` tham số hoá theo cả hai — mỗi file test chỉ đổi
`InMemorySpaceDocumentSource([...])` thành `document_source_factory([...])`,
không đổi gì khác.

`scope` (`SpaceScanScope`, cây Space) KHÔNG thuộc phạm vi work-order này —
06 Mục 5.3/`10` Mục 4.0 nói cây Space là dữ liệu của Backend, Ingestion chỉ
đọc tươi mỗi lần, không có bảng nào để "cài PostgreSQL" cho nó — nên
`InMemorySpaceScanScope`/`UnavailableSpaceScanScope` giữ nguyên trong mọi
ca thử, kể cả nhánh "pg".

Cùng cơ chế kết nối/rollback-mỗi-ca-thử như `tests/t2_1_intake/conftest.py`
— xem docstring của `pg_connection` ở đó để biết vì sao phải
`with conn.transaction(): ... raise psycopg.Rollback` thay vì chỉ
`conn.rollback()`.
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

from ingestion.pg_document_stores import PgDocumentStore  # noqa: E402
from ingestion.relations_scan import InMemorySpaceDocumentSource  # noqa: E402
from schema.document import DateSource, Document  # noqa: E402
from schema.store_schema import SHARED_STORE_DDL  # noqa: E402

# A real Vietnamese administrative citation clause — same shape as the one
# in `data/test-corpus-vn-admin/phap-che-tuan-thu/30_2020_ND_CP.docx`, with
# the amendment vocabulary deliberately absent so it stays a REFERENCES.
CITATION_110 = (
    "Căn cứ Nghị định số 110/2004/NĐ-CP ngày 08 tháng 4 năm 2004 "
    "của Chính phủ về công tác văn thư;"
)
DOC_NUMBER_110 = "110/2004/NĐ-CP"
ISSUED_110 = date(2004, 4, 8)


def make_document(
    *,
    document_id: str,
    doc_number: str,
    extracted_text: str = "Văn bản không dẫn chiếu văn bản nào.",
    space_id: str = "space-own",
    tenant_id: str = "tenant-1",
    title: str = "Văn bản thử",
    issued_date: date = date(2020, 1, 1),
    issued_date_source: DateSource = DateSource.EXTRACTED,
    subject_entities: list[str] | None = None,
    category_labels: list[str] | None = None,
) -> Document:
    """A minimally-filled `Document` — every field outside the explicit
    parameters is fixed to a value irrelevant to `ingestion.relations_scan`.

    `subject_entities` defaults to empty, which GATES OFF K3
    (`detect_inferred_amendment_relations`): a test that wants an inferred
    AMENDS_OR_REPLACES must set it on both documents on purpose.

    `ingested_at` mang `tzinfo=UTC` (KHO-PG-A) — vòng ghi-đọc qua PostgreSQL
    (cột `timestamptz`) trả về đúng cùng một thời điểm; naive so aware qua
    `==` luôn `False` dù cùng một khắc giờ.
    """
    return Document(
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        title=title,
        doc_number=doc_number,
        issued_date=issued_date,
        issued_date_source=issued_date_source,
        effective_date=issued_date,
        effective_date_source=issued_date_source,
        ingested_at=datetime(2026, 9, 22, 11, 0, tzinfo=timezone.utc),
        source_format="docx",
        content_fingerprint=f"fp-{document_id}",
        extracted_text=extracted_text,
        version_chain_id=f"chain-{document_id}",
        version_ordinal=1,
        subject_entities=subject_entities if subject_entities is not None else [],
        category_labels=category_labels if category_labels is not None else [],
    )


class StubClock:
    """A clock that only moves when a test moves it — the whole reason
    `scan_relations_for_new_document` takes `clock` instead of calling
    `time.monotonic` itself (no test may need to wait ten real minutes to
    exercise `scan_time_budget`).

    Returns `readings` in order, then repeats the last one forever.
    """

    def __init__(self, readings: list[float]) -> None:
        self._readings = list(readings)
        self.calls = 0

    def __call__(self) -> float:
        index = min(self.calls, len(self._readings) - 1)
        self.calls += 1
        return self._readings[index]


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
    """Xem docstring của cùng fixture ở `tests/t2_1_intake/conftest.py` —
    `psycopg.Rollback` bên trong `with conn.transaction():` là cách bắt buộc
    rollback thật; `conn.rollback()` đơn thuần KHÔNG xoá được gì vì
    `Connection.transaction()` là khối giao dịch NGOÀI CÙNG nếu gọi nó mà
    chưa có `BEGIN` nào mở sẵn — nó tự COMMIT khi thoát bình thường."""
    with psycopg.connect(pg_dsn) as conn:
        with conn.transaction():
            yield conn
            raise psycopg.Rollback


@pytest.fixture(params=["memory", "pg"], ids=["memory", "pg"])
def document_source_factory(request: pytest.FixtureRequest):
    """`[Document] -> SpaceDocumentSource`, tham số hoá theo cả hai cài đặt."""
    if request.param == "pg":
        pg_connection = request.getfixturevalue("pg_connection")
        store = PgDocumentStore(connection=pg_connection)

        def _make_pg(documents: list[Document]):
            for document in documents:
                store.register(document)
            return store

        return _make_pg

    def _make_memory(documents: list[Document]):
        return InMemorySpaceDocumentSource(documents)

    return _make_memory
