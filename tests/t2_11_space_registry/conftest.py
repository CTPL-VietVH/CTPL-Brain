"""Shared fixtures for T2.11 (Space register + Space deletion) — inserts
`packages/` and `tests/` into `sys.path`, the first for `ingestion.*` /
`schema.*` and the second for `fault_injection`.

No live PostgreSQL and no live Qdrant, same as every other Nhóm 2 folder. The
in-memory stores come from the modules that already own them — `promotion.py`
for the profile and vector stores, `deletion.py` for their deleting halves,
`pre_approval_buffer.py` for the staging area — so a test acts on ONE world,
exactly as a deployment does. Separate stand-ins would let a Space deletion
"pass" against data the ingestion path never wrote.

──────────────────────────────────────────────────────────────────────────
The world these cases share
──────────────────────────────────────────────────────────────────────────

    space-doomed  (registered, IN_USE)      space-keeper  (registered, IN_USE)
    ├─ doc-doomed-1  ──amends──► doc-doomed-2       └─ doc-twin
    ├─ doc-doomed-2                                     ▲
    ├─ doc-doomed-3  ──references────────────────────────┘
    └─ [buffer] doc-buffered   (pre-approval, never promoted)

`doc-twin` carries the SAME `content_fingerprint` as `doc-doomed-1` — a
byte-identical copy of one file uploaded into two Spaces, which 06 Mục 5.7
makes two separate documents. It is the tripwire for docs/10 §4.0's first
anti-mistake rule: selecting what to delete by fingerprint instead of by
`space_id` would take it too, silently.

The `doc-doomed-3 → doc-twin` link crosses the Space boundary on purpose: 06
Mục 5.6 removes the links OF a deleted document, and that must not be read as
permission to touch the document at the far end.

Every fixture is function-scoped: each case builds its own world.
"""

from __future__ import annotations

import os
import pathlib
import sys
from datetime import date, datetime, timezone

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from ingestion.deletion import (  # noqa: E402
    InMemoryBackgroundCleanup,
    InMemoryDeletableProfileStore,
    InMemoryDeletionLog,
    InMemoryVectorStoreDeleter,
)
from ingestion.pg_queue_stores import PgSpaceRegistry  # noqa: E402
from ingestion.pre_approval_buffer import (  # noqa: E402
    BufferedIngestion,
    InMemoryPreApprovalBuffer,
)
from ingestion.promotion import (  # noqa: E402
    InMemorySharedProfileStore,
    InMemoryVectorStoreWriter,
)
from ingestion.space_registry import InMemorySpaceRegistry  # noqa: E402
from schema.chunk import Chunk  # noqa: E402
from schema.document import DateSource, Document  # noqa: E402
from schema.relation import (  # noqa: E402
    ApprovalState,
    Relation,
    RelationOrigin,
    RelationType,
)
from schema.store_schema import SPACE_REGISTRY_TABLE, SPACE_REGISTRY_TABLE_DDL  # noqa: E402

# --------------------------------------------------------------------------- #
# KHO-PG-B — `space_registry_factory`, parametrized over InMemory and the real
# PostgreSQL table, so the SAME test body proves the SAME behaviour on both
# (task KHO-PG-B-hang-doi-dang-ky-vung-dem). PostgreSQL is only connected to
# when the `postgresql` param actually runs — an InMemory-param test case
# never touches the network, and a missing/unreachable store FAILS the
# `postgresql` case loudly rather than skipping it silently.
# --------------------------------------------------------------------------- #


def _require_pg_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        pytest.fail(
            f"Missing config key '{name}'. No default in code — copy .env.example "
            f"to .env and fill it in before running the postgresql-parametrized case."
        )
    return value


def _pg_dsn() -> str:
    host = _require_pg_env("CBRAIN_PG_HOST")
    port = _require_pg_env("CBRAIN_PG_PORT")
    database = _require_pg_env("CBRAIN_PG_DATABASE")
    user = _require_pg_env("CBRAIN_PG_USER")
    password = os.environ.get("CBRAIN_PG_PASSWORD") or ""
    auth = f"{user}:{password}" if password else user
    return f"postgresql://{auth}@{host}:{port}/{database}"


@pytest.fixture(scope="session")
def _pg_connection():
    """One real connection for the whole session, only opened the first time
    a `postgresql`-param test actually asks for it."""
    import psycopg
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    with psycopg.connect(_pg_dsn(), autocommit=True) as connection:
        connection.execute(SPACE_REGISTRY_TABLE_DDL)
        yield connection


@pytest.fixture(params=["in_memory", "postgresql"])
def space_registry_factory(request):
    """A zero-argument callable that returns a FRESH `SpaceRegistry`.

    `in_memory` never imports psycopg or reads `.env` — the InMemory half of
    this suite keeps working with no PostgreSQL running at all, exactly as it
    did before this task. `postgresql` connects to the real table, deletes
    any rows a previous run of THESE tests left behind (the space_ids this
    file uses are constants, e.g. `DOOMED_SPACE`/`KEEPER_SPACE`, not random
    per-run ids), and cleans up again afterwards.
    """
    if request.param == "in_memory":
        yield InMemorySpaceRegistry
        return

    connection = request.getfixturevalue("_pg_connection")
    connection.execute(f"DELETE FROM {SPACE_REGISTRY_TABLE}")
    yield lambda: PgSpaceRegistry(connection)
    connection.execute(f"DELETE FROM {SPACE_REGISTRY_TABLE}")

DOOMED_SPACE = "space-doomed"
KEEPER_SPACE = "space-keeper"

INGESTED_AT = datetime(2026, 9, 23, 15, 0)
DELETED_AT = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)

#: The fingerprint `doc-doomed-1` and `doc-twin` share — one file, two Spaces.
SHARED_FINGERPRINT = "fingerprint-identical-upload"

# Real Vietnamese text: `span_start`/`span_end` count Unicode characters, and
# a corpus of plain ASCII would not notice if they ever stopped.
BODY = "Điều 1. Phạm vi điều chỉnh. Quyết định này quy định về công tác văn thư."

DELETION_REASON = "Phòng Nhân sự giải thể, Space không còn chủ"
DELETED_BY = "manager-lan"


def make_document(
    *,
    document_id: str,
    space_id: str,
    content_fingerprint: str | None = None,
) -> Document:
    return Document(
        document_id=document_id,
        space_id=space_id,
        tenant_id="tenant-1",
        title="Quyết định về công tác văn thư",
        doc_number="15/2021/QĐ-BNV",
        issued_date=date(2021, 3, 1),
        issued_date_source=DateSource.EXTRACTED,
        effective_date=date(2021, 4, 1),
        effective_date_source=DateSource.EXTRACTED,
        ingested_at=INGESTED_AT,
        source_format="docx",
        content_fingerprint=content_fingerprint or f"fingerprint-{document_id}",
        extracted_text=BODY,
        version_chain_id=f"chain-{document_id}",
        version_ordinal=1,
    )


def make_chunk(
    *, chunk_id: str, document: Document, span: tuple[int, int], embedded: bool = True
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=document.document_id,
        space_id=document.space_id,
        tenant_id=document.tenant_id,
        structure_path=["Điều 1"],
        span_start=span[0],
        span_end=span[1],
        structure_block_start=span[0],
        structure_block_end=span[1],
        # A buffered chunk carries NO vector — GĐ6 has not run for it, and
        # `InMemoryPreApprovalBuffer` refuses one that does (T2.7).
        embedding=[0.1, 0.2, 0.3, 0.4] if embedded else [],
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
    """One deployment's worth of stores — see the module docstring for the map."""

    def __init__(self) -> None:
        inner = InMemorySharedProfileStore()
        self.vector_writer = InMemoryVectorStoreWriter()
        self.buffer = InMemoryPreApprovalBuffer()
        self.registry = InMemorySpaceRegistry()

        self.registry.register(DOOMED_SPACE)
        self.registry.register(KEEPER_SPACE)

        self.doomed_documents = [
            make_document(
                document_id="doc-doomed-1",
                space_id=DOOMED_SPACE,
                content_fingerprint=SHARED_FINGERPRINT,
            ),
            make_document(document_id="doc-doomed-2", space_id=DOOMED_SPACE),
            make_document(document_id="doc-doomed-3", space_id=DOOMED_SPACE),
        ]
        # Same bytes as `doc-doomed-1`, different Space — a different document
        # (06 Mục 5.7), and the one that must survive.
        self.twin = make_document(
            document_id="doc-twin",
            space_id=KEEPER_SPACE,
            content_fingerprint=SHARED_FINGERPRINT,
        )

        for document in (*self.doomed_documents, self.twin):
            inner.write_document_and_relations(document=document, relations=[])

        inner.write_document_and_relations(
            document=self.doomed_documents[0],
            relations=[
                make_relation(
                    relation_id="rel-inside",
                    from_document_id="doc-doomed-1",
                    to_document_id="doc-doomed-2",
                ),
                # Crosses the Space boundary: deleting `doc-doomed-3` removes
                # this link, and must leave `doc-twin` itself untouched.
                make_relation(
                    relation_id="rel-crossing",
                    from_document_id="doc-doomed-3",
                    to_document_id="doc-twin",
                ),
            ],
        )

        for document in (*self.doomed_documents, self.twin):
            self.vector_writer.write(
                [
                    make_chunk(
                        chunk_id=f"chunk-{document.document_id}-1",
                        document=document,
                        span=(0, 28),
                    ),
                    make_chunk(
                        chunk_id=f"chunk-{document.document_id}-2",
                        document=document,
                        span=(28, 72),
                    ),
                ]
            )

        # The fourth document of the doomed Space: still in the pre-approval
        # buffer, in no shared store, waiting for a Manager who will never
        # come (06 Mục 5.6: *"cùng tài liệu còn trong vùng đệm tiền kiểm"*).
        self.buffered_document = make_document(
            document_id="doc-buffered", space_id=DOOMED_SPACE
        )
        self.buffer.put(
            BufferedIngestion(
                document=self.buffered_document,
                buffered_at=INGESTED_AT,
                chunks=[
                    make_chunk(
                        chunk_id="chunk-doc-buffered-1",
                        document=self.buffered_document,
                        span=(0, 28),
                        embedded=False,
                    )
                ],
            )
        )
        # A buffered entry in the OTHER Space, to prove the buffer sweep is
        # scoped the same way the document sweep is.
        self.kept_buffered_document = make_document(
            document_id="doc-buffered-keeper", space_id=KEEPER_SPACE
        )
        self.buffer.put(
            BufferedIngestion(
                document=self.kept_buffered_document,
                buffered_at=INGESTED_AT,
                chunks=[],
            )
        )

        self.inner_store = inner
        self.profile_store = InMemoryDeletableProfileStore(inner)
        self.vector_store = InMemoryVectorStoreDeleter(self.vector_writer)
        self.cleanup = InMemoryBackgroundCleanup()
        self.log = InMemoryDeletionLog()

    # -- inspection ------------------------------------------------------ #

    def point_ids(self) -> set[str]:
        return set(self.vector_writer.points)

    def document_ids(self) -> set[str]:
        return {document.document_id for document in self.inner_store.documents()}

    def relation_ids(self) -> set[str]:
        return {relation.relation_id for relation in self.inner_store.relations()}

    def buffered_ids(self) -> set[str]:
        return {
            entry.document.document_id
            for entry in (
                *self.buffer.list_in_space(DOOMED_SPACE),
                *self.buffer.list_in_space(KEEPER_SPACE),
            )
        }

    def snapshot(self) -> tuple[set[str], set[str], set[str], set[str]]:
        """Every store that must converge, in one comparable value."""
        return (
            self.point_ids(),
            self.document_ids(),
            self.relation_ids(),
            self.buffered_ids(),
        )


@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def space_deletion_kwargs(world: World) -> dict:
    """The call every deletion case makes, minus whichever port it wraps in a
    fault.

    `document_source` and `profile_store` are the SAME object: in a real
    deployment both are the `document` table, and modelling them as two would
    hide the fact that a purge removes a document from the worklist as well.
    """
    return {
        "reason": DELETION_REASON,
        "deleted_by": DELETED_BY,
        "space_registry": world.registry,
        "document_source": world.profile_store,
        "profile_store": world.profile_store,
        "vector_store": world.vector_store,
        "background_cleanup": world.cleanup,
        "deletion_log": world.log,
        "pre_approval_buffer": world.buffer,
        "clock": lambda: DELETED_AT,
    }
