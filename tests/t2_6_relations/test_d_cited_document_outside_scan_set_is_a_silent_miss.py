"""T2.6 (d) — citing a document that is NOT in the same scan-set list
produces no relation and no error (NT2: a phán đoán that finds nothing is
an accepted miss, not a failure).
"""

from __future__ import annotations

from ingestion.relations import detect_explicit_relations

from .conftest import make_document


def test_citation_to_a_document_absent_from_the_list_yields_nothing():
    citing = make_document(
        document_id="doc-thong-tu-10-2020",
        doc_number="10/2020/TT-BLĐTBXH",
        extracted_text=(
            "Căn cứ Nghị định số 14/2017/NĐ-CP ngày 17 tháng 02 năm 2017 của Chính phủ "
            "quy định chức năng, nhiệm vụ, quyền hạn."
        ),
    )

    assert detect_explicit_relations([citing]) == []
