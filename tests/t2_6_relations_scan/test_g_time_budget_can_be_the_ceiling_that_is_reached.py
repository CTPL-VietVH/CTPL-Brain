"""T2.6 (g) — the cost ceiling's INNER "or" (07 S8: *"tối đa N cặp đối
chiếu, hoặc T thời gian"*): elapsed time alone can satisfy condition (2),
with the pair budget nowhere near spent.

Time is read through the injected `clock`, never `time.monotonic` directly —
otherwise proving anything about a ten-minute budget would take ten minutes.
"""

from __future__ import annotations

from .conftest import StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)
from schema.document import RelationsScanState


def test_time_budget_can_be_the_ceiling_that_is_reached(document_source_factory) -> None:
    new_document = make_document(document_id="new", doc_number="30/2020/NĐ-CP")
    unrelated_first = make_document(document_id="filler-1", doc_number="01/2019/QĐ-UBND")
    unrelated_second = make_document(document_id="filler-2", doc_number="02/2019/QĐ-UBND")

    # Start of the scan reads 0.0; the first round boundary reads 100.0 —
    # past a one-minute budget, without a second of real waiting.
    clock = StubClock([0.0, 100.0])

    result = scan_relations_for_new_document(
        new_document,
        scope=InMemorySpaceScanScope([InMemorySpace(space_id="space-own")]),
        document_source=document_source_factory(
            [new_document, unrelated_first, unrelated_second]
        ),
        saturation_epsilon=0.5,
        saturation_rounds=1,
        scan_pair_budget=1000,
        scan_time_budget=1.0,
        clock=clock,
    )

    assert result.recommended_scan_state is RelationsScanState.STOPPED
    # The pair budget was never close to spent — time was the trigger.
    assert result.pairs_compared == 2
    assert clock.calls >= 2
