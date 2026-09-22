"""T2.7 promote (f) — `(space_id, content_fingerprint)` is unique only among
ACTIVE documents.

The constraint 08 dòng 210 asks for cannot be a plain UNIQUE. T2.1 deliberately
allows a re-upload into a Space that already holds a `removed_as_wrong` twin:
PO chốt Phương án A (21/9) made *"removed_as_wrong coi như không tồn tại"* a
principle that runs through the whole of `intake.py`, and `decide_intake`
creates a new document rather than reporting a duplicate in that case.

A plain constraint would refuse that legitimate re-upload — silently turning a
recovery path into a dead end. Hence the PARTIAL index, `WHERE NOT
removed_as_wrong`, and both halves are tested here.
"""

from __future__ import annotations

import dataclasses

import pytest
from ingestion.promotion import DuplicateActiveFingerprintError, InMemorySharedProfileStore

from .conftest import make_stored_document


def test_two_active_documents_may_not_share_a_fingerprint_in_one_space() -> None:
    store = InMemorySharedProfileStore()
    store.register(
        make_stored_document(
            document_id="doc-a",
            version_chain_id="chain-a",
            version_ordinal=1,
            content_fingerprint="fp-same",
        )
    )

    with pytest.raises(DuplicateActiveFingerprintError):
        store.register(
            make_stored_document(
                document_id="doc-b",
                version_chain_id="chain-b",
                version_ordinal=1,
                content_fingerprint="fp-same",
            )
        )


def test_a_removed_twin_does_not_block_a_re_upload() -> None:
    store = InMemorySharedProfileStore()
    removed = make_stored_document(
        document_id="doc-a",
        version_chain_id="chain-a",
        version_ordinal=1,
        content_fingerprint="fp-same",
        removed_as_wrong=True,
    )
    store.register(removed)

    store.register(
        make_stored_document(
            document_id="doc-b",
            version_chain_id="chain-b",
            version_ordinal=1,
            content_fingerprint="fp-same",
        )
    )
    assert len(store.documents()) == 2


def test_the_same_fingerprint_in_another_space_is_fine() -> None:
    """06 Mục 5.7: *"Trùng khít, khác Space → hợp lệ, không cảnh báo"* — the
    constraint is scoped to one Space, not to the tenant."""
    store = InMemorySharedProfileStore()
    first = make_stored_document(
        document_id="doc-a",
        version_chain_id="chain-a",
        version_ordinal=1,
        content_fingerprint="fp-same",
    )
    store.register(first)
    store.register(
        dataclasses.replace(
            first,
            document_id="doc-b",
            space_id="space-other",
            version_chain_id="chain-b",
        )
    )
    assert len(store.documents()) == 2
