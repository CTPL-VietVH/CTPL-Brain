"""T2.7 promote (b) — the write order, proven by crashing between the two
stores, and what the crash now leaves behind.

S6 (07 Mục 6) puts the gate at the vector store: *"Cổng chặn nằm ở KHO
VECTOR."* Deletion removes the vector first so nothing findable ever points at
a missing profile; writing runs that backwards, so the last thing to happen is
the thing that makes the document findable. The order itself is asserted from
INSIDE the failing writer: when Qdrant is reached, PostgreSQL must already
hold the profile.

⚠️ **What this file used to assert, and why it changed (VEC-1, 25/9/2026).**
Until the incident it ended with *"the profile is already committed"* and
called that state harmless — invisible to every query, pointing at nothing
missing. It is not harmless. The fingerprint index reads the `document` table
directly, so the surviving profile makes the NEXT upload of the same file come
back as `duplicate`, naming a document no question can reach. So the promote
now undoes its own write, and this case asserts the undo: both stores end up
not knowing the document, and the original failure is what comes out.

`discard` still never ran, so the entry is still in the buffer — a retry has
something to pick up, which is the whole reason it is last.
"""

from __future__ import annotations

import pytest
from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.promotion import InMemoryVectorStoreWriter, promote_approved_ingestion
from schema.chunk import Chunk

from .conftest import (
    EMBEDDING_BATCH_SIZE,
    SATURATION_EPSILON,
    SATURATION_ROUNDS,
    SCAN_PAIR_BUDGET,
    SCAN_TIME_BUDGET,
    FakeBgeM3,
    buffer_a_document,
    make_scope,
    vector_deleter_for,
)


class QdrantIsDown(Exception):
    pass


class FailingVectorStoreWriter:
    """Qdrant unreachable at exactly the moment the gate would open.

    It looks the profile up on its way down, so the assertion about ORDER is
    made at the only instant it can be made: after step 4, before step 5 has
    had any effect.
    """

    def __init__(self, profile_store, document_id: str) -> None:
        self._profile_store = profile_store
        self._document_id = document_id
        self.profile_present_when_called: bool | None = None

    def write(self, chunks: list[Chunk]) -> None:
        self.profile_present_when_called = (
            self._profile_store.get_document(self._document_id) is not None
        )
        raise QdrantIsDown("connection refused")


def test_profile_lands_before_the_vector_gate_opens(tmp_path, profile_store) -> None:
    store = profile_store
    buffer = InMemoryPreApprovalBuffer()
    vectors = InMemoryVectorStoreWriter()
    entry = buffer_a_document(tmp_path, buffer=buffer, fingerprint_index=store)
    writer = FailingVectorStoreWriter(store, "doc-promote-1")

    with pytest.raises(QdrantIsDown):
        promote_approved_ingestion(
            entry,
            profile_store=store,
            profile_deleter=store,
            buffer=buffer,
            vector_writer=writer,
            vector_deleter=vector_deleter_for(vectors),
            embedding_model=FakeBgeM3(),
            embedding_batch_size=EMBEDDING_BATCH_SIZE,
            relation_scope=make_scope(),
            relation_document_source=store,
            saturation_epsilon=SATURATION_EPSILON,
            saturation_rounds=SATURATION_ROUNDS,
            scan_pair_budget=SCAN_PAIR_BUDGET,
            scan_time_budget=SCAN_TIME_BUDGET,
        )

    # The order, observed from inside the vector step: PostgreSQL came first.
    assert writer.profile_present_when_called is True

    # …and then the failure took it back. Nothing findable, nothing to trip
    # over on the next upload of the same bytes.
    assert store.get_document("doc-promote-1") is None
    assert store.documents() == []
    assert store.relations() == []

    # The working area still holds the entry — `discard` is last on purpose.
    assert buffer.get("doc-promote-1") is not None
