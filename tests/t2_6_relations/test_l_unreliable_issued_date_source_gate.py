"""T2.6 (l) — a document whose `issued_date_source` is
`DEFAULT_INGESTION_DATE` (06 Mục 6.4: nobody actually knows the real issue
date) must be excluded from the date-order gate even though its
`issued_date` field still holds a placeholder value that would otherwise
compare as "later".
"""

from __future__ import annotations

from datetime import date

from ingestion.relations import detect_inferred_amendment_relations
from schema.document import DateSource

from .conftest import make_document


def test_unreliable_issued_date_on_the_later_side_blocks_the_candidate():
    earlier = make_document(
        document_id="doc-earlier",
        doc_number="1/2004/NĐ-CP",
        extracted_text="Bản cũ.",
        issued_date=date(2004, 4, 8),
        issued_date_source=DateSource.EXTRACTED,
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )
    later_but_unreliable = make_document(
        document_id="doc-later",
        doc_number="2/2026/NĐ-CP",
        extracted_text="Bản mới nhưng ngày không trích được.",
        issued_date=date(2026, 1, 1),  # ingestion-date placeholder, not a real signal
        issued_date_source=DateSource.DEFAULT_INGESTION_DATE,
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )

    assert detect_inferred_amendment_relations([earlier, later_but_unreliable]) == []


def test_unreliable_issued_date_on_the_earlier_side_also_blocks_the_candidate():
    earlier_but_unreliable = make_document(
        document_id="doc-earlier",
        doc_number="1/2004/NĐ-CP",
        extracted_text="Bản cũ, ngày không trích được.",
        issued_date=date(2004, 4, 8),
        issued_date_source=DateSource.DEFAULT_INGESTION_DATE,
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )
    later = make_document(
        document_id="doc-later",
        doc_number="2/2020/NĐ-CP",
        extracted_text="Bản mới.",
        issued_date=date(2020, 3, 5),
        issued_date_source=DateSource.EXTRACTED,
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
    )

    assert detect_inferred_amendment_relations([earlier_but_unreliable, later]) == []
