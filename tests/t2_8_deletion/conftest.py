"""Shared fixtures for T2.8 (permanent deletion) — inserts `packages/` and
`tests/` into `sys.path`, the first for `ingestion.*`/`schema.*` and the
second for `fault_injection`.

No live PostgreSQL and no live Qdrant, same as every other Nhóm 2 folder.
The in-memory stores come from `promotion.py` wherever they already exist, so
a test that promotes a document and then deletes it acts on ONE store — two
stand-ins would let a delete "pass" against data the promote never wrote.

Every fixture is function-scoped: each case builds its own world and no case
can inherit state from the one before it.
"""

from __future__ import annotations

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
from ingestion.promotion import (  # noqa: E402
    InMemorySharedProfileStore,
    InMemoryVectorStoreWriter,
)
from schema.chunk import Chunk  # noqa: E402
from schema.document import DateSource, Document  # noqa: E402
from schema.relation import ApprovalState, Relation, RelationOrigin, RelationType  # noqa: E402

INGESTED_AT = datetime(2026, 9, 22, 15, 0)
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
    needs: the one being deleted, and a neighbour that must survive it."""

    def __init__(self) -> None:
        inner = InMemorySharedProfileStore()
        self.vector_writer = InMemoryVectorStoreWriter()

        self.doomed = make_document(document_id="doc-doomed")
        self.neighbour = make_document(document_id="doc-neighbour", space_id="space-hr")
        self.bystander = make_document(document_id="doc-bystander", space_id="space-it")

        for document in (self.doomed, self.neighbour, self.bystander):
            inner.write_document_and_relations(document=document, relations=[])

        # One link out of the doomed document, one INTO it, and one that has
        # nothing to do with it.
        inner.write_document_and_relations(
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

    def snapshot(self) -> tuple[set[str], set[str], set[str]]:
        """Everything that must converge, in one comparable value."""
        return (self.point_ids(), self.document_ids(), self.relation_ids())


@pytest.fixture
def world() -> World:
    return World()


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
