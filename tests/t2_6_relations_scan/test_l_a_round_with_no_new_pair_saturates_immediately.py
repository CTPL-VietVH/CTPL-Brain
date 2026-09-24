"""T2.6 (l) — a round that compares ZERO new pairs counts as saturated at
once, instead of spending `saturation_rounds` no-op rounds to reach the same
conclusion (work-order: *"Nếu vòng đó có 0 cặp mới (đã hết Space để mở
rộng), coi là bão hoà ngay"*).

Also the division-by-zero guard: "tỷ lệ phát hiện quan hệ mới" has pairs in
its denominator, and this round has none.
"""

from __future__ import annotations

from .conftest import CITATION_110, StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)
from schema.document import RelationsScanState


def test_a_round_with_no_new_pair_saturates_immediately(document_source_factory) -> None:
    lonely_document = make_document(
        document_id="new",
        doc_number="30/2020/NĐ-CP",
        extracted_text=CITATION_110,
    )

    result = scan_relations_for_new_document(
        lonely_document,
        scope=InMemorySpaceScanScope([InMemorySpace(space_id="space-own")]),
        document_source=document_source_factory([lonely_document]),
        saturation_epsilon=0.01,
        saturation_rounds=3,
        scan_pair_budget=100,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    assert result.pairs_compared == 0
    assert result.relations == []
    # One round, not one + `saturation_rounds`.
    assert result.rounds_run == 1
    # Saturated on that one round, and the scope was exhausted on it too, so
    # both S8 conditions hold (E1) — a document alone in its Space is DONE
    # being compared, not perpetually "chưa đối chiếu xong".
    assert result.recommended_scan_state is RelationsScanState.STOPPED
