"""T2.7 promote (g) — profile and relations are written in ONE transaction, and
a refusal leaves the store exactly as it was.

07 Mục 2 dòng 65 is what makes this possible: *"hai bước xoá quan hệ và hồ sơ
nằm chung một cơ sở dữ liệu nên thành MỘT GIAO DỊCH NGUYÊN KHỐI — ranh giới duy
nhất còn thiếu giao dịch chung là giữa Qdrant và PostgreSQL."* Writing has the
same shape, and the ordering inside the transaction is fixed: the document row
first, because every relation row carries a foreign key to it.
"""

from __future__ import annotations

import pytest
from ingestion.promotion import UnknownRelationEndpointError
from schema.relation import ApprovalState, Relation, RelationOrigin, RelationType

from .conftest import make_stored_document


def test_a_relation_to_an_unknown_document_is_refused_and_changes_nothing(profile_store) -> None:
    store = profile_store
    document = make_stored_document(
        document_id="doc-new",
        version_chain_id="chain-new",
        version_ordinal=1,
        content_fingerprint="fp-new",
    )

    with pytest.raises(UnknownRelationEndpointError):
        store.write_document_and_relations(
            document=document,
            relations=[
                Relation(
                    relation_id="rel-1",
                    from_document_id="doc-new",
                    to_document_id="doc-that-does-not-exist",
                    relation_type=RelationType.REFERENCES,
                    origin=RelationOrigin.MACHINE_READ_EXPLICIT_REFERENCE,
                    approval_state=ApprovalState.PENDING,
                    confidence=0.9,
                )
            ],
        )

    # The document did NOT land: one transaction, all or nothing.
    assert store.get_document("doc-new") is None
    assert store.relations() == []


def test_a_relation_to_the_document_being_written_is_accepted(profile_store) -> None:
    """The FK is satisfied inside the transaction — the document row goes in
    before the relation rows, so a self-referencing write is legal."""
    store = profile_store
    store.register(
        make_stored_document(
            document_id="doc-old",
            version_chain_id="chain-old",
            version_ordinal=1,
            content_fingerprint="fp-old",
        )
    )
    document = make_stored_document(
        document_id="doc-new",
        version_chain_id="chain-new",
        version_ordinal=1,
        content_fingerprint="fp-new",
    )

    store.write_document_and_relations(
        document=document,
        relations=[
            Relation(
                relation_id="rel-1",
                from_document_id="doc-new",  # not in the store until this call
                to_document_id="doc-old",
                relation_type=RelationType.AMENDS_OR_REPLACES,
                origin=RelationOrigin.MACHINE_INFERRED,
                approval_state=ApprovalState.PENDING,
                confidence=0.8,
            )
        ],
    )

    assert store.get_document("doc-new") is not None
    assert len(store.relations()) == 1
