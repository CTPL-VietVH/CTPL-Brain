"""T2.6 (h) — every produced `Relation` carries a valid, unique `relation_id`
(uuid4, same precedent as `version_chain_id` in `ingestion/intake.py`), and
starts `approval_state=PENDING` even though its `origin` is already "chắc
chắn" (`07` Mục 2.3, DX1) — 06 Mục 5.3: certainty fast-tracks approval, it
does not skip it. Only `origin=MANAGER_ASSIGNED` links start at APPROVED,
and this module never produces that origin.
"""

from __future__ import annotations

import uuid

from ingestion.relations import detect_explicit_relations
from schema.relation import ApprovalState

from .conftest import make_document


def test_relation_id_is_a_valid_and_unique_uuid4():
    citing = make_document(
        document_id="doc-citing",
        doc_number="10/2020/TT-BLĐTBXH",
        extracted_text=(
            "Căn cứ Nghị định số 14/2017/NĐ-CP ngày 17 tháng 02 năm 2017 của Chính phủ.\n"
            "(Kèm theo Nghị định số 20/2021/NĐ-CP ngày 05 tháng 01 năm 2021 của Chính phủ)"
        ),
    )
    cited_reference = make_document(
        document_id="doc-cited-reference",
        doc_number="14/2017/NĐ-CP",
        extracted_text="Toàn văn.",
    )
    cited_attachment = make_document(
        document_id="doc-cited-attachment",
        doc_number="20/2021/NĐ-CP",
        extracted_text="Toàn văn.",
    )

    relations = detect_explicit_relations([citing, cited_reference, cited_attachment])

    assert len(relations) == 2
    relation_ids = {relation.relation_id for relation in relations}
    assert len(relation_ids) == 2
    for relation_id in relation_ids:
        assert uuid.UUID(relation_id).version == 4

    for relation in relations:
        assert relation.approval_state == ApprovalState.PENDING
