"""T2.6 (f) — only when saturation AND the cost ceiling hold TOGETHER does
the scan recommend `STOPPED` (07 S8: *"Chỉ khi cả hai cùng thoả,
`relations_scan_state` mới được chuyển sang đã dừng"*).

Compare with test (e), where the very same ceiling was reached but the
saturation streak was not — the outer relationship between the two
conditions is "and", never "or".
"""

from __future__ import annotations

from .conftest import StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceDocumentSource,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)
from schema.document import RelationsScanState


def test_both_s8_conditions_together_give_stopped() -> None:
    new_document = make_document(document_id="new", doc_number="30/2020/NĐ-CP")
    unrelated_first = make_document(document_id="filler-1", doc_number="01/2019/QĐ-UBND")
    unrelated_second = make_document(document_id="filler-2", doc_number="02/2019/QĐ-UBND")

    result = scan_relations_for_new_document(
        new_document,
        scope=InMemorySpaceScanScope([InMemorySpace(space_id="space-own")]),
        document_source=InMemorySpaceDocumentSource(
            [new_document, unrelated_first, unrelated_second]
        ),
        # Yield of round 1 is 0/2 = 0.0, below the threshold, and one such
        # round is already a full streak.
        saturation_epsilon=0.5,
        saturation_rounds=1,
        scan_pair_budget=2,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    assert result.pairs_compared == 2
    assert result.recommended_scan_state is RelationsScanState.STOPPED
