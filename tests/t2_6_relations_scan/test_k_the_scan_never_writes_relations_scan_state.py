"""T2.6 (k) — the scan RECOMMENDS a `relations_scan_state`; it never writes
one. Same shape as every other module under `packages/ingestion/`: the
machine proposes, a caller decides what to persist.

Asserted on the case where the recommendation differs from what the
document already carries — otherwise the test would pass on a module that
does write.
"""

from __future__ import annotations

from .conftest import StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)
from schema.document import RelationsScanState


def test_the_scan_never_writes_relations_scan_state(document_source_factory) -> None:
    new_document = make_document(document_id="new", doc_number="30/2020/NĐ-CP")
    unrelated_first = make_document(document_id="filler-1", doc_number="01/2019/QĐ-UBND")
    unrelated_second = make_document(document_id="filler-2", doc_number="02/2019/QĐ-UBND")
    assert new_document.relations_scan_state is RelationsScanState.EXPANDING

    result = scan_relations_for_new_document(
        new_document,
        scope=InMemorySpaceScanScope([InMemorySpace(space_id="space-own")]),
        document_source=document_source_factory(
            [new_document, unrelated_first, unrelated_second]
        ),
        saturation_epsilon=0.5,
        saturation_rounds=1,
        scan_pair_budget=2,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    assert result.recommended_scan_state is RelationsScanState.STOPPED
    assert new_document.relations_scan_state is RelationsScanState.EXPANDING
