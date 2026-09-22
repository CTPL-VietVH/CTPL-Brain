"""T2.6 (f) — a document citing the same target document twice is ONE
relationship, not two.
"""

from __future__ import annotations

from ingestion.relations import detect_explicit_relations

from .conftest import make_document


def test_two_citations_to_the_same_target_produce_a_single_relation():
    citing = make_document(
        document_id="doc-citing",
        doc_number="10/2020/TT-BLĐTBXH",
        extracted_text=(
            "Căn cứ Nghị định số 14/2017/NĐ-CP ngày 17 tháng 02 năm 2017 của Chính phủ.\n"
            "Điều 1. Nhắc lại: xem thêm Căn cứ Nghị định số 14/2017/NĐ-CP ngày 17 tháng 02 "
            "năm 2017 của Chính phủ về thẩm quyền liên quan."
        ),
    )
    cited = make_document(
        document_id="doc-cited",
        doc_number="14/2017/NĐ-CP",
        extracted_text="Toàn văn.",
    )

    relations = detect_explicit_relations([citing, cited])

    assert len(relations) == 1
    assert relations[0].to_document_id == "doc-cited"
