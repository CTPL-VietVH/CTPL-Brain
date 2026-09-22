"""T2.7 promote (b) — the write order, proven by crashing between the two
stores.

S6 (07 Mục 6) puts the gate at the vector store: *"Cổng chặn nằm ở KHO
VECTOR."* Deletion removes the vector first so nothing findable ever points at
a missing profile; writing runs that backwards, so the last thing to happen is
the thing that makes the document findable.

Crashing the Qdrant write leaves the harmless intermediate state — a profile
nobody can find, pointing at nothing missing. The opposite order would leave
findable chunks whose profile does not exist, the dangling pointer S6 exists
to prevent.

And `discard` has not run, so the entry is still in the buffer for the retry.
"""

from __future__ import annotations

import pytest
from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.promotion import InMemorySharedProfileStore, promote_approved_ingestion
from schema.chunk import Chunk

from .conftest import (
    SATURATION_EPSILON,
    SATURATION_ROUNDS,
    SCAN_PAIR_BUDGET,
    SCAN_TIME_BUDGET,
    FakeBgeM3,
    buffer_a_document,
    make_scope,
)


class QdrantIsDown(Exception):
    pass


class FailingVectorStoreWriter:
    """Qdrant unreachable at exactly the moment the gate would open."""

    def write(self, chunks: list[Chunk]) -> None:
        raise QdrantIsDown("connection refused")


def test_profile_lands_before_the_vector_gate_opens(tmp_path) -> None:
    store = InMemorySharedProfileStore()
    buffer = InMemoryPreApprovalBuffer()
    entry = buffer_a_document(tmp_path, buffer=buffer, fingerprint_index=store)

    with pytest.raises(QdrantIsDown):
        promote_approved_ingestion(
            entry,
            profile_store=store,
            buffer=buffer,
            vector_writer=FailingVectorStoreWriter(),
            embedding_model=FakeBgeM3(),
            relation_scope=make_scope(),
            relation_document_source=store,
            saturation_epsilon=SATURATION_EPSILON,
            saturation_rounds=SATURATION_ROUNDS,
            scan_pair_budget=SCAN_PAIR_BUDGET,
            scan_time_budget=SCAN_TIME_BUDGET,
        )

    # The profile is already committed: PostgreSQL came first.
    assert store.get_document("doc-promote-1") is not None
    # Nothing is findable, so the half-done state is invisible rather than wrong.
    # And the working area still holds the entry — `discard` is last on purpose.
    assert buffer.get("doc-promote-1") is not None
