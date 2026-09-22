"""T2.6 (e) — hitting the cost ceiling WITHOUT saturating leaves the
document at `EXPANDING`: 07 S8 — *"trần chi phí một mình thì dừng khi hết
tiền chứ không phải khi đã đủ"*. The answer keeps saying "chưa đối chiếu
xong", and `config/ingestion.yaml`'s own misconfiguration hint for
`scan_time_budget` ("Tài liệu mới lâu ngày vẫn mang nhãn 'chưa đối chiếu
xong' → nới") is exactly this situation being observed from outside.
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


def test_ceiling_before_saturation_stays_expanding() -> None:
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

    result = scan_relations_for_new_document(
        new_document,
        scope=InMemorySpaceScanScope([InMemorySpace(space_id="space-own")]),
        document_source=InMemorySpaceDocumentSource([new_document, cited]),
        saturation_epsilon=0.01,
        saturation_rounds=3,
        # One pair of budget: the round that finds the relation is also the
        # round that exhausts the budget, so the yield never had a chance to
        # fall below `saturation_epsilon` for three consecutive rounds.
        scan_pair_budget=1,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    assert result.pairs_compared == 1
    assert len(result.relations) == 1
    assert result.recommended_scan_state is RelationsScanState.EXPANDING
