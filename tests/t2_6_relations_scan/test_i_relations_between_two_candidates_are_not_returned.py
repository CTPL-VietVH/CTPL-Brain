"""T2.6 (i) — this is the scan of ONE new document (06 Mục 5.5: *"Tái cơ
cấu quan hệ ... ngay khi có tài liệu mới vào kho ... mở rộng dần từ Space
chứa nó"*). Two OLD documents citing each other is not this document's
business: each of them had its own scan when it arrived.

Both detectors in `relations.py` compare every pair inside the list they are
given, so without the filter this scan would quietly re-propose the whole
Space's internal link graph on every ingestion.
"""

from __future__ import annotations

from .conftest import CITATION_110, DOC_NUMBER_110, ISSUED_110, StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceDocumentSource,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)


def test_relations_between_two_candidates_are_not_returned() -> None:
    new_document = make_document(
        document_id="new",
        doc_number="30/2020/NĐ-CP",
        extracted_text="Văn bản này không dẫn chiếu văn bản nào.",
    )
    citing_candidate = make_document(
        document_id="citing-candidate",
        doc_number="99/2019/QĐ-UBND",
        extracted_text=CITATION_110,
    )
    cited_candidate = make_document(
        document_id="cited-candidate",
        doc_number=DOC_NUMBER_110,
        issued_date=ISSUED_110,
    )

    result = scan_relations_for_new_document(
        new_document,
        scope=InMemorySpaceScanScope([InMemorySpace(space_id="space-own")]),
        document_source=InMemorySpaceDocumentSource(
            [new_document, citing_candidate, cited_candidate]
        ),
        saturation_epsilon=0.01,
        saturation_rounds=3,
        scan_pair_budget=100,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    # The candidate→candidate REFERENCES is real, and belongs to that
    # candidate's own scan — not to this one.
    assert result.relations == []
    assert result.pairs_compared == 2
