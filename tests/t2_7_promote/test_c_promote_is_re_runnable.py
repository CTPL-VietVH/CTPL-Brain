"""T2.7 promote (c) — re-running a promote converges instead of duplicating.

The Qdrant↔PostgreSQL boundary has no shared transaction — 07 Mục 2 calls it
*"ranh giới duy nhất còn thiếu giao dịch chung"* — and S6's answer to that for
deletion is the same answer here: *"mỗi bước phải làm lại được mà không hỏng
thêm."* 08 T2.8 turns it into an acceptance condition in so many words:
running the command twice must not error and must not change the result.

The ordinal is the sharp edge: recomputing `max + 1` on every attempt would
walk the document one slot further down its own chain each time it is retried.
"""

from __future__ import annotations

from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.promotion import (
    InMemoryVectorStoreWriter,
    promote_approved_ingestion,
)

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


def _promote(entry, store, buffer, vectors):
    return promote_approved_ingestion(
        entry,
        profile_store=store,
        profile_deleter=store,
        buffer=buffer,
        vector_writer=vectors,
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


def test_promote_is_re_runnable(tmp_path, profile_store) -> None:
    store = profile_store
    vectors = InMemoryVectorStoreWriter()
    buffer = InMemoryPreApprovalBuffer()
    entry = buffer_a_document(tmp_path, buffer=buffer, fingerprint_index=store)

    first = _promote(entry, store, buffer, vectors)
    documents_after_first = len(store.documents())
    vectors_after_first = vectors.count()
    relations_after_first = len(store.relations())

    second = _promote(entry, store, buffer, vectors)

    assert second.document.version_ordinal == first.document.version_ordinal
    assert second.version_ordinal_was_recomputed is False
    assert len(store.documents()) == documents_after_first == 1
    assert vectors.count() == vectors_after_first
    assert len(store.relations()) == relations_after_first
