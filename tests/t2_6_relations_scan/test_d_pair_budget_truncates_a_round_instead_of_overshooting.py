"""T2.6 (d) — `scan_pair_budget` is a CEILING, not a quota: a round is cut
short at the budget rather than allowed to overshoot it (07 Mục 3.2: *"trần
số cặp đối chiếu"* per document).

The citable document is placed LAST on purpose — proving the truncation
really stops the comparison rather than merely stopping the counter.
"""

from __future__ import annotations

from .conftest import CITATION_110, DOC_NUMBER_110, ISSUED_110, StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceDocumentSource,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)


def test_pair_budget_truncates_a_round_instead_of_overshooting() -> None:
    new_document = make_document(
        document_id="new",
        doc_number="30/2020/NĐ-CP",
        extracted_text=CITATION_110,
    )
    unrelated_first = make_document(document_id="filler-1", doc_number="01/2019/QĐ-UBND")
    unrelated_second = make_document(document_id="filler-2", doc_number="02/2019/QĐ-UBND")
    cited = make_document(
        document_id="cited",
        doc_number=DOC_NUMBER_110,
        issued_date=ISSUED_110,
    )

    result = scan_relations_for_new_document(
        new_document,
        scope=InMemorySpaceScanScope([InMemorySpace(space_id="space-own")]),
        document_source=InMemorySpaceDocumentSource(
            [new_document, unrelated_first, unrelated_second, cited]
        ),
        saturation_epsilon=0.01,
        saturation_rounds=3,
        scan_pair_budget=2,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    assert result.pairs_compared == 2
    assert result.relations == []
