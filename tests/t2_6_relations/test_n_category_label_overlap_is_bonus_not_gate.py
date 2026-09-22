"""T2.6 (n) — `category_labels` overlap is a confidence BONUS, not a gate
(work-order: explicitly "không phải điều kiện gate"). A candidate with
matching subject + later date but NO shared type label still produces a
relation — at the lower end of the confidence scale, not rejected outright.
"""

from __future__ import annotations

from datetime import date

from ingestion.relations import detect_inferred_amendment_relations

from .conftest import make_document


def test_candidate_without_shared_category_label_still_produces_a_relation_at_lower_confidence():
    earlier = make_document(
        document_id="doc-earlier",
        doc_number="1/2004/NĐ-CP",
        extracted_text="Bản cũ.",
        issued_date=date(2004, 4, 8),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
        category_labels=["NGHỊ ĐỊNH"],
    )
    later_different_type = make_document(
        document_id="doc-later",
        doc_number="2/2020/QĐ-CP",
        extracted_text="Bản mới, loại văn bản khác.",
        issued_date=date(2020, 3, 5),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
        category_labels=["QUYẾT ĐỊNH"],
    )

    relations = detect_inferred_amendment_relations([earlier, later_different_type])

    assert len(relations) == 1
    assert relations[0].confidence == 0.7  # 0.5 subject + 0.2 date, no 0.3 type bonus


def test_candidate_with_shared_category_label_gets_the_full_bonus():
    earlier = make_document(
        document_id="doc-earlier",
        doc_number="1/2004/NĐ-CP",
        extracted_text="Bản cũ.",
        issued_date=date(2004, 4, 8),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
        category_labels=["NGHỊ ĐỊNH"],
    )
    later_same_type = make_document(
        document_id="doc-later",
        doc_number="2/2020/NĐ-CP",
        extracted_text="Bản mới, cùng loại văn bản.",
        issued_date=date(2020, 3, 5),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
        category_labels=["NGHỊ ĐỊNH"],
    )

    relations = detect_inferred_amendment_relations([earlier, later_same_type])

    assert len(relations) == 1
    assert relations[0].confidence == 1.0
