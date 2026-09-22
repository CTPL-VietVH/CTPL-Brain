"""T2.6 (k) — date-order gate: equal `issued_date` (or the reverse
ordering) must NOT produce a candidate — work-order: "nếu bằng nhau...
KHÔNG tạo ứng viên", no guessing which one came first.
"""

from __future__ import annotations

from datetime import date

from ingestion.relations import detect_inferred_amendment_relations

from .conftest import make_document


def test_equal_issued_dates_produce_no_candidate_in_either_direction():
    document_a = make_document(
        document_id="doc-a",
        doc_number="1/2020/QĐ-X",
        extracted_text="Bản A.",
        issued_date=date(2020, 5, 1),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )
    document_b = make_document(
        document_id="doc-b",
        doc_number="2/2020/QĐ-X",
        extracted_text="Bản B.",
        issued_date=date(2020, 5, 1),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )

    assert detect_inferred_amendment_relations([document_a, document_b]) == []


def test_only_the_later_to_earlier_direction_is_produced_not_both():
    earlier = make_document(
        document_id="doc-earlier",
        doc_number="1/2004/NĐ-CP",
        extracted_text="Bản cũ.",
        issued_date=date(2004, 4, 8),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )
    later = make_document(
        document_id="doc-later",
        doc_number="2/2020/NĐ-CP",
        extracted_text="Bản mới.",
        issued_date=date(2020, 3, 5),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )

    relations = detect_inferred_amendment_relations([earlier, later])

    assert len(relations) == 1
    assert (relations[0].from_document_id, relations[0].to_document_id) == ("doc-later", "doc-earlier")
