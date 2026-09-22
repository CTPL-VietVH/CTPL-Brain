"""T2.6 (e) — two documents in the scan set sharing the same `doc_number`
makes a citation ambiguous. The detector must not guess which one is meant
— no relation, for either candidate.
"""

from __future__ import annotations

from ingestion.relations import detect_explicit_relations

from .conftest import make_document


def test_two_documents_sharing_a_doc_number_are_not_guessed_between():
    citing = make_document(
        document_id="doc-citing",
        doc_number="10/2020/TT-BLĐTBXH",
        extracted_text=(
            "Căn cứ Nghị định số 14/2017/NĐ-CP ngày 17 tháng 02 năm 2017 của Chính phủ "
            "quy định chức năng, nhiệm vụ, quyền hạn."
        ),
    )
    candidate_one = make_document(
        document_id="doc-candidate-1",
        doc_number="14/2017/NĐ-CP",
        extracted_text="Bản A.",
    )
    candidate_two = make_document(
        document_id="doc-candidate-2",
        doc_number="14/2017/NĐ-CP",
        extracted_text="Bản B — cùng số hiệu, khác định danh.",
    )

    assert detect_explicit_relations([citing, candidate_one, candidate_two]) == []
