"""T2.6 (m) — the E1 case (PO decision 22/9/2026). When the Space scope
reaches its fixed point (`expand` returns its argument unchanged — 06 Mục
5.3: *"mở rộng dần cho tới khi xác định không nên mở thêm"*) and the round
brought no newcomer, the scan ends AND counts that as the cost ceiling, so
both S8 conditions hold and the recommendation is `STOPPED`.

Two things are being pinned here, and they are separate:

- **The exit.** Without it, a literal reading of S8 would keep looping —
  every round a no-op — purely to let `scan_time_budget` elapse, so a small
  corpus would spend ten minutes of wall clock learning nothing. The frozen
  `StubClock` below makes that a hang rather than a slow pass, and
  `rounds_run` pins the exit to the first idle round.
- **The state.** Reading condition 2 as pairs-or-time ONLY made `STOPPED`
  unreachable for any kho smaller than the budget: this scan saturates after
  a single pair and never approaches 100 pairs or 10 minutes, so the
  document would have carried "chưa đối chiếu xong" forever despite having
  compared everything in reach. Scope exhaustion IS the ceiling — there is
  no pair left to spend budget on.

The contrast is test (e): same ceiling reached, but by spend and before
saturating, and that one stays `EXPANDING` — *"dừng khi hết tiền chứ không
phải khi đã đủ"*.
"""

from __future__ import annotations

from .conftest import CITATION_110, DOC_NUMBER_110, ISSUED_110, StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceDocumentSource,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)
from schema.document import RelationsScanState


def test_a_fixed_point_scope_ends_the_scan_without_burning_the_clock() -> None:
    new_document = make_document(
        document_id="new",
        doc_number="30/2020/NĐ-CP",
        extracted_text=CITATION_110,
    )
    cited = make_document(
        document_id="cited",
        doc_number=DOC_NUMBER_110,
        issued_date=ISSUED_110,
    )
    # Never advances: any exit that depended on time passing would hang here.
    clock = StubClock([0.0])

    result = scan_relations_for_new_document(
        new_document,
        scope=InMemorySpaceScanScope([InMemorySpace(space_id="space-own")]),
        document_source=InMemorySpaceDocumentSource([new_document, cited]),
        saturation_epsilon=0.01,
        saturation_rounds=3,
        scan_pair_budget=100,
        scan_time_budget=10.0,
        clock=clock,
    )

    # Round 1 compared the one candidate; round 2 found nothing new and ended.
    assert result.rounds_run == 2
    assert result.pairs_compared == 1
    # Neither spend ceiling was anywhere near reached — scope exhaustion is
    # what satisfied condition 2.
    assert result.pairs_compared < 100
    assert result.recommended_scan_state is RelationsScanState.STOPPED
