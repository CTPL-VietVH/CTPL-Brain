"""T2.6 (m) — subject-overlap gate: empty `subject_entities` on either side,
or two non-empty lists that share nothing after normalization, both mean K3
has no basis to reason from — no candidate, no guess (work-order: "Không
suy luận khi thiếu subject_entities... không đoán").
"""

from __future__ import annotations

from datetime import date

from ingestion.relations import detect_inferred_amendment_relations

from .conftest import make_document


def test_empty_subject_entities_on_either_side_blocks_the_candidate():
    later = make_document(
        document_id="doc-later",
        doc_number="2/2020/NĐ-CP",
        extracted_text="Bản mới.",
        issued_date=date(2020, 3, 5),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )
    earlier_no_subject = make_document(
        document_id="doc-earlier",
        doc_number="1/2004/NĐ-CP",
        extracted_text="Bản cũ, chưa gợi ý được đối tượng.",
        issued_date=date(2004, 4, 8),
        subject_entities=[],
    )

    assert detect_inferred_amendment_relations([later, earlier_no_subject]) == []


def test_non_overlapping_subject_entities_block_the_candidate():
    later = make_document(
        document_id="doc-later",
        doc_number="2/2020/NĐ-CP",
        extracted_text="Bản mới.",
        issued_date=date(2020, 3, 5),
        subject_entities=["VỀ QUẢN LÝ TÀI SẢN CÔNG"],
    )
    earlier = make_document(
        document_id="doc-earlier",
        doc_number="1/2004/NĐ-CP",
        extracted_text="Bản cũ, chủ đề khác hẳn.",
        issued_date=date(2004, 4, 8),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )

    assert detect_inferred_amendment_relations([later, earlier]) == []
