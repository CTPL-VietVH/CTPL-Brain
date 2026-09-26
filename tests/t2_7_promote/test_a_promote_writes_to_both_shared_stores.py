"""T2.7 promote (a) — the whole arc: a document invisible to every store while
it waits, then present in both the moment a Manager approves.

08 dòng 206: *"Manager duyệt xong mới chạy nốt và ghi ra ba kho."* The
before-state is T2.7's own acceptance criterion; asserting it here too is what
makes the after-state mean something.
"""

from __future__ import annotations

from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.promotion import (
    InMemoryVectorStoreWriter,
    promote_approved_ingestion,
)
from schema.document import RelationsScanState

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


def test_promote_writes_to_both_shared_stores(tmp_path, profile_store) -> None:
    store = profile_store  # the official `document` + `relation`
    vectors = InMemoryVectorStoreWriter()  # Qdrant
    buffer = InMemoryPreApprovalBuffer()

    entry = buffer_a_document(tmp_path, buffer=buffer, fingerprint_index=store)

    # --- before approval: nothing anywhere -------------------------------
    assert store.documents() == []
    assert vectors.count() == 0

    result = promote_approved_ingestion(
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

    # --- after approval: present in both, gone from the working area -----
    stored = store.get_document("doc-promote-1")
    assert stored is not None
    assert stored.title == entry.document.title
    assert stored.extracted_text == entry.document.extracted_text
    assert stored.category_labels == entry.document.category_labels

    assert vectors.count() == len(entry.chunks) > 0
    for chunk in result.chunks:
        assert chunk.embedding, "GĐ6 must have filled every vector"

    assert buffer.get("doc-promote-1") is None, "the working area is released last"

    # GĐ7 ran, and its recommendation is what landed on the profile — the
    # scan itself never persists (T2.6).
    assert stored.relations_scan_state in set(RelationsScanState)
    assert stored.relations_scan_state is result.document.relations_scan_state
