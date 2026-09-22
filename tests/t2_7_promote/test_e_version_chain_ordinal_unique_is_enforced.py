"""T2.7 promote (e) — `(version_chain_id, version_ordinal)` is refused at the
STORAGE layer, which is the half 08 dòng 210 insists on: *"cần ÍT NHẤT hai
unique constraint tầng lưu trữ, không chỉ kiểm tra ở tầng ứng dụng."*

Recomputing the ordinal at promote time (test d) narrows the window; it cannot
close it, because two promotes can read the same `max` before either writes.
This constraint is what makes one of them lose instead of both winning —
T2.1-E2's race condition.
"""

from __future__ import annotations

import pytest
from ingestion.promotion import InMemorySharedProfileStore, VersionChainOrdinalConflictError

from .conftest import make_stored_document


def test_version_chain_ordinal_unique_is_enforced() -> None:
    store = InMemorySharedProfileStore()
    store.register(
        make_stored_document(
            document_id="doc-a",
            version_chain_id="chain-1",
            version_ordinal=2,
            content_fingerprint="fp-a",
        )
    )

    # A second writer that read `max = 1` before the first one committed.
    with pytest.raises(VersionChainOrdinalConflictError):
        store.register(
            make_stored_document(
                document_id="doc-b",
                version_chain_id="chain-1",
                version_ordinal=2,
                content_fingerprint="fp-b",
            )
        )

    assert len(store.documents()) == 1


def test_a_different_chain_may_reuse_the_same_ordinal() -> None:
    """The constraint is on the PAIR — every chain has its own ordinal 1."""
    store = InMemorySharedProfileStore()
    store.register(
        make_stored_document(
            document_id="doc-a",
            version_chain_id="chain-1",
            version_ordinal=1,
            content_fingerprint="fp-a",
        )
    )
    store.register(
        make_stored_document(
            document_id="doc-b",
            version_chain_id="chain-2",
            version_ordinal=1,
            content_fingerprint="fp-b",
        )
    )
    assert len(store.documents()) == 2
