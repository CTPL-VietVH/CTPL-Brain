"""T2.6 (o) — a three-version chain (same subject, strictly increasing
issue dates) yields every later→earlier pair, not just adjacent ones
(module docstring: deliberate — each pair is scored independently, Manager
approval is where redundant suggestions get rejected). Also checks the
`Relation` invariants shared with `detect_explicit_relations`
(`relation_id` uuid4, `approval_state=PENDING`) hold for
`detect_inferred_amendment_relations` too.
"""

from __future__ import annotations

import uuid
from datetime import date

from ingestion.relations import detect_inferred_amendment_relations
from schema.relation import ApprovalState, RelationOrigin

from .conftest import make_document


def test_three_version_chain_produces_all_three_later_to_earlier_pairs():
    v1 = make_document(
        document_id="doc-v1",
        doc_number="1/2004/NĐ-CP",
        extracted_text="Bản v1.",
        issued_date=date(2004, 4, 8),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )
    v2 = make_document(
        document_id="doc-v2",
        doc_number="2/2012/NĐ-CP",
        extracted_text="Bản v2.",
        issued_date=date(2012, 6, 1),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )
    v3 = make_document(
        document_id="doc-v3",
        doc_number="3/2020/NĐ-CP",
        extracted_text="Bản v3.",
        issued_date=date(2020, 3, 5),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )

    relations = detect_inferred_amendment_relations([v1, v2, v3])

    pairs = {(relation.from_document_id, relation.to_document_id) for relation in relations}
    assert pairs == {
        ("doc-v2", "doc-v1"),
        ("doc-v3", "doc-v2"),
        ("doc-v3", "doc-v1"),
    }

    relation_ids = [relation.relation_id for relation in relations]
    assert len(set(relation_ids)) == len(relation_ids)
    for relation_id in relation_ids:
        assert uuid.UUID(relation_id).version == 4
    for relation in relations:
        assert relation.approval_state == ApprovalState.PENDING
        assert relation.origin == RelationOrigin.MACHINE_INFERRED
        assert relation.confidence is not None
