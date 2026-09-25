"""T2.7 promote (d) — the ordinal assigned when the entry entered the buffer is
provisional and is thrown away.

An approval can sit for an unbounded time while the chain keeps growing.
Carrying the buffered ordinal forward would let two pending uploads both
promote as ordinal 2 — T2.1-E2's race walking back in through the approval
door, which is exactly the hole 08 dòng 210 was written to close.
"""

from __future__ import annotations

from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.promotion import (
    InMemoryVectorStoreWriter,
    promote_approved_ingestion,
)

from .conftest import (
    SATURATION_EPSILON,
    SATURATION_ROUNDS,
    SCAN_PAIR_BUDGET,
    SCAN_TIME_BUDGET,
    FakeBgeM3,
    buffer_a_document,
    make_scope,
    vector_deleter_for,
    make_stored_document,
)


def test_version_ordinal_is_recomputed_at_promote_time(tmp_path, profile_store) -> None:
    store = profile_store
    vectors = InMemoryVectorStoreWriter()
    buffer = InMemoryPreApprovalBuffer()
    entry = buffer_a_document(tmp_path, buffer=buffer, fingerprint_index=store)

    # The entry was buffered as the start of its own chain...
    chain = entry.document.version_chain_id
    assert entry.document.version_ordinal == 1

    # ...and while it waited, two versions of that chain were published.
    for ordinal in (1, 2):
        store.register(
            make_stored_document(
                document_id=f"doc-chain-{ordinal}",
                version_chain_id=chain,
                version_ordinal=ordinal,
                content_fingerprint=f"fp-chain-{ordinal}",
            )
        )

    result = promote_approved_ingestion(
        entry,
        profile_store=store,
        profile_deleter=store,
        buffer=buffer,
        vector_writer=vectors,
        vector_deleter=vector_deleter_for(vectors),
        embedding_model=FakeBgeM3(),
        relation_scope=make_scope(),
        relation_document_source=store,
        saturation_epsilon=SATURATION_EPSILON,
        saturation_rounds=SATURATION_ROUNDS,
        scan_pair_budget=SCAN_PAIR_BUDGET,
        scan_time_budget=SCAN_TIME_BUDGET,
    )

    assert result.version_ordinal_was_recomputed is True
    assert result.document.version_ordinal == 3
    assert store.get_document("doc-promote-1").version_ordinal == 3
    # The buffered object itself is untouched — the promote builds a new one.
    assert entry.document.version_ordinal == 1
