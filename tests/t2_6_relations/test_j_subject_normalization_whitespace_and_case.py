"""T2.6 (j) — subject-entity matching normalizes BOTH case and internal
whitespace before comparing (work-order gate: "uppercase + gộp khoảng
trắng"). Synthetic beyond the real pair in test_i, to isolate whitespace
collapsing on its own (the real pair only exercises the case difference).
"""

from __future__ import annotations

from datetime import date

from ingestion.relations import detect_inferred_amendment_relations

from .conftest import make_document


def test_extra_internal_whitespace_and_case_both_normalize_to_a_match():
    earlier = make_document(
        document_id="doc-earlier",
        doc_number="1/2019/QĐ-X",
        extracted_text="Bản gốc.",
        issued_date=date(2019, 1, 1),
        subject_entities=["về  công tác   văn thư"],
    )
    later = make_document(
        document_id="doc-later",
        doc_number="2/2021/QĐ-X",
        extracted_text="Bản sửa đổi.",
        issued_date=date(2021, 1, 1),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )

    relations = detect_inferred_amendment_relations([earlier, later])

    assert len(relations) == 1
    assert relations[0].from_document_id == "doc-later"
    assert relations[0].to_document_id == "doc-earlier"
