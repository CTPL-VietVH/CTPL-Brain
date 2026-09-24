"""Shared fixtures for T2.8 (permanent deletion) — inserts `packages/` and
`tests/` into `sys.path`, the first for `ingestion.*`/`schema.*` and the
second for `fault_injection`.

No live Qdrant, in every case — `InMemoryVectorStoreWriter`/`InMemoryVector
StoreDeleter` stand in for the collection regardless of which
`profile_store`/`deletion_log` backing a case runs against (Qdrant is outside
KHO-PG-A's scope; `document`/`relation`/`deletion_log` are the tables this
work order gives a real PostgreSQL implementation to). The stores come from
`promotion.py`/`deletion.py`/`pg_document_stores.py` wherever they already
exist, so a test that promotes a document and then deletes it acts on ONE
store — two stand-ins would let a delete "pass" against data the promote
never wrote.

Every fixture is function-scoped: each case builds its own world and no case
can inherit state from the one before it.

──────────────────────────────────────────────────────────────────────────
KHO-PG-A — `world` tham số hoá InMemory / PostgreSQL
──────────────────────────────────────────────────────────────────────────

`World` giờ nhận `profile_store` / `deletion_log` / `background_cleanup` đã
dựng sẵn từ bên ngoài thay vì tự tạo InMemory bên trong `__init__` — và
`world` là fixture tham số hoá theo hai cách dựng: `InMemoryDeletableProfile
Store(InMemorySharedProfileStore())` + `InMemoryDeletionLog` +
`InMemoryBackgroundCleanup` (không đổi), hoặc `PgDocumentStore` +
`PgDeletionLog` + `PgBackgroundCleanup` (mới — `ingestion.pg_document_stores`)
trên một kết nối PostgreSQL THẬT. TOÀN BỘ 18 file test dưới thư mục này chạy
qua `world`/`deletion_kwargs`, nên không file test nào cần sửa — đúng "tham
số hoá ... không viết lại hành vi mong đợi lần hai", kể cả các ca cắt tiến
trình (`fault_injection.crash_before`/`crash_after` bọc trong suốt bất kỳ
đối tượng nào, InMemory hay Pg).

`PgBackgroundCleanup` không có bảng riêng (xem docstring trong `pg_document_
stores.py`) nên `document_source`/`world.cleanup` khi chạy nhánh "pg" chỉ là
một đối tượng ghi nhớ lời gọi trong tiến trình — hành vi giống hệt
`InMemoryBackgroundCleanup`.
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
sys.path.insert(0, str(REPO_ROOT / "tests"))

from ingestion.deletion import (  # noqa: E402
    InMemoryBackgroundCleanup,
    InMemoryDeletableProfileStore,
    InMemoryDeletionLog,
    InMemoryVectorStoreDeleter,
)
from ingestion.pg_document_stores import (  # noqa: E402
    PgBackgroundCleanup,
    PgDeletionLog,
    PgDocumentStore,
)
from ingestion.promotion import (  # noqa: E402
    InMemorySharedProfileStore,
    InMemoryVectorStoreWriter,
)
from schema.chunk import Chunk  # noqa: E402
from schema.document import DateSource, Document  # noqa: E402
from schema.relation import ApprovalState, Relation, RelationOrigin, RelationType  # noqa: E402
from schema.store_schema import SHARED_STORE_DDL  # noqa: E402

# `tzinfo=UTC` (KHO-PG-A) — vòng ghi-đọc qua PostgreSQL (cột `timestamptz`)
# trả về đúng cùng một thời điểm; naive so aware qua `==` luôn `False` dù
# cùng một khắc giờ.
INGESTED_AT = datetime(2026, 9, 22, 15, 0, tzinfo=timezone.utc)
DELETED_AT = datetime(2026, 9, 22, 16, 0, tzinfo=timezone.utc)

# Real Vietnamese text: `span_start`/`span_end` count Unicode characters, and
# a test corpus of plain ASCII would not notice if they ever stopped.
BODY = "Điều 1. Phạm vi điều chỉnh. Quyết định này quy định về công tác văn thư."


def make_document(
    *,
    document_id: str,
    space_id: str = "space-hr",
    tenant_id: str = "tenant-1",
    doc_number: str = "15/2021/QĐ-BNV",
    title: str = "Quyết định về công tác văn thư",
    extracted_text: str = BODY,
    content_fingerprint: str | None = None,
) -> Document:
    return Document(
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        title=title,
        doc_number=doc_number,
        issued_date=date(2021, 3, 1),
        issued_date_source=DateSource.EXTRACTED,
        effective_date=date(2021, 4, 1),
        effective_date_source=DateSource.EXTRACTED,
        ingested_at=INGESTED_AT,
        source_format="docx",
        content_fingerprint=content_fingerprint or f"fingerprint-{document_id}",
        extracted_text=extracted_text,
        version_chain_id=f"chain-{document_id}",
        version_ordinal=1,
    )


def make_chunk(*, chunk_id: str, document: Document, span: tuple[int, int]) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=document.document_id,
        space_id=document.space_id,
        tenant_id=document.tenant_id,
        structure_path=["Điều 1"],
        span_start=span[0],
        span_end=span[1],
        embedding=[0.1, 0.2, 0.3, 0.4],
    )


def make_relation(
    *, relation_id: str, from_document_id: str, to_document_id: str
) -> Relation:
    return Relation(
        relation_id=relation_id,
        from_document_id=from_document_id,
        to_document_id=to_document_id,
        relation_type=RelationType.REFERENCES,
        origin=RelationOrigin.MACHINE_READ_EXPLICIT_REFERENCE,
        approval_state=ApprovalState.PENDING,
    )


class World:
    """One deployment's worth of stores, plus the two documents every case
    needs: the one being deleted, and a neighbour that must survive it.

    `profile_store`/`deletion_log`/`background_cleanup` arrive ALREADY BUILT
    (KHO-PG-A) — `World` no longer chooses InMemory for itself, so the same
    class serves both parametrizations of the `world` fixture below.
    """

    def __init__(self, *, profile_store, deletion_log, background_cleanup) -> None:
        self.vector_writer = InMemoryVectorStoreWriter()

        self.doomed = make_document(document_id="doc-doomed")
        self.neighbour = make_document(document_id="doc-neighbour", space_id="space-hr")
        self.bystander = make_document(document_id="doc-bystander", space_id="space-it")

        for document in (self.doomed, self.neighbour, self.bystander):
            profile_store.write_document_and_relations(document=document, relations=[])

        # One link out of the doomed document, one INTO it, and one that has
        # nothing to do with it.
        profile_store.write_document_and_relations(
            document=self.doomed,
            relations=[
                make_relation(
                    relation_id="rel-out",
                    from_document_id="doc-doomed",
                    to_document_id="doc-neighbour",
                ),
                make_relation(
                    relation_id="rel-in",
                    from_document_id="doc-neighbour",
                    to_document_id="doc-doomed",
                ),
                make_relation(
                    relation_id="rel-elsewhere",
                    from_document_id="doc-neighbour",
                    to_document_id="doc-bystander",
                ),
            ],
        )

        self.vector_writer.write(
            [
                make_chunk(chunk_id="chunk-doomed-1", document=self.doomed, span=(0, 28)),
                make_chunk(chunk_id="chunk-doomed-2", document=self.doomed, span=(28, 72)),
                make_chunk(
                    chunk_id="chunk-neighbour-1", document=self.neighbour, span=(0, 28)
                ),
            ]
        )

        self.profile_store = profile_store
        self.vector_store = InMemoryVectorStoreDeleter(self.vector_writer)
        self.cleanup = background_cleanup
        self.log = deletion_log

    # -- inspection ------------------------------------------------------ #

    def point_ids(self) -> set[str]:
        return set(self.vector_writer.points)

    def document_ids(self) -> set[str]:
        return {document.document_id for document in self.profile_store.documents()}

    def relation_ids(self) -> set[str]:
        return {relation.relation_id for relation in self.profile_store.relations()}

    def snapshot(self) -> tuple[set[str], set[str], set[str]]:
        """Everything that must converge, in one comparable value."""
        return (self.point_ids(), self.document_ids(), self.relation_ids())


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
def world(request: pytest.FixtureRequest) -> World:
    if request.param == "pg":
        pg_connection = request.getfixturevalue("pg_connection")
        return World(
            profile_store=PgDocumentStore(connection=pg_connection),
            deletion_log=PgDeletionLog(connection=pg_connection),
            background_cleanup=PgBackgroundCleanup(),
        )
    return World(
        profile_store=InMemoryDeletableProfileStore(InMemorySharedProfileStore()),
        deletion_log=InMemoryDeletionLog(),
        background_cleanup=InMemoryBackgroundCleanup(),
    )


def pop_document_without_trace(world: World, document_id: str) -> None:
    """Test-only escape hatch for `test_m`'s T4 "no evidence at all" case: a
    document row gone with no `deletion_log` line — a state this module's own
    API can never produce, only a raw store poke can.

    Dispatches on which backing `world.profile_store` is (duck-typed on
    `InMemoryDeletableProfileStore`'s `_inner` attribute), mirroring the
    InMemory side's own `store._documents.pop(...)` reach-into-internals —
    the PostgreSQL side reaches into `._connection` for the same reason.
    On PostgreSQL the `DELETE` may also cascade any relations touching the
    document (`schema/store_schema.py`'s `ON DELETE CASCADE`); `test_m`
    asserts nothing about relations afterwards, so this is harmless either
    way.
    """
    profile_store = world.profile_store
    if hasattr(profile_store, "_inner"):
        del profile_store._inner._documents[document_id]
        return
    from schema.store_schema import DOCUMENT_TABLE

    doc_id_field = Document.__dataclass_fields__["document_id"].name
    profile_store._connection.execute(
        f"DELETE FROM {DOCUMENT_TABLE} WHERE {doc_id_field} = %s", (document_id,)
    )


@pytest.fixture
def deletion_kwargs(world: World) -> dict:
    """The call every case makes, minus whichever port it wraps in a fault.

    `space_id` matches `world.doomed` (and `world.neighbour`, which shares
    the same Space) — the T4 check (docs/10 §1) must pass for every case that
    is not itself testing T4, so this fixture is the one place that value
    lives.
    """
    return {
        "space_id": "space-hr",
        "deleted_by": "manager-lan",
        "reason": "Người upload đưa nhầm file của khách hàng khác",
        "profile_store": world.profile_store,
        "vector_store": world.vector_store,
        "background_cleanup": world.cleanup,
        "deletion_log": world.log,
        "clock": lambda: DELETED_AT,
    }
