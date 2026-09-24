"""T2.6 (b) — the scan does NOT stop at one Space: it widens one hop per
round through the INHERITING Space tree and finds a relation that only
becomes visible after the hop (PO decision 22/9/2026; 06 Mục 5.3 *"mở rộng
dần"*).
"""

from __future__ import annotations

from .conftest import CITATION_110, DOC_NUMBER_110, ISSUED_110, StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)
from schema.document import RelationsScanState
from schema.relation import RelationType


def test_scope_widens_to_an_inheriting_parent_space(document_source_factory) -> None:
    new_document = make_document(
        document_id="new",
        doc_number="30/2020/NĐ-CP",
        extracted_text=CITATION_110,
        space_id="space-child",
    )
    cited = make_document(
        document_id="cited",
        doc_number=DOC_NUMBER_110,
        issued_date=ISSUED_110,
        space_id="space-parent",
    )

    result = scan_relations_for_new_document(
        new_document,
        scope=InMemorySpaceScanScope(
            [
                InMemorySpace(space_id="space-parent"),
                InMemorySpace(
                    space_id="space-child",
                    parent_space_id="space-parent",
                    inherits_from_parent=True,
                ),
            ]
        ),
        document_source=document_source_factory([new_document, cited]),
        saturation_epsilon=0.01,
        saturation_rounds=3,
        scan_pair_budget=100,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    assert [relation.relation_type for relation in result.relations] == [RelationType.REFERENCES]
    assert result.relations[0].to_document_id == "cited"
    # Round 1 saw only `space-child` (nothing new there but the document
    # itself); the pair only existed once the parent was pulled in.
    assert result.rounds_run >= 2
    assert result.pairs_compared == 1
    # Round 3 found the scope at its fixed point with nothing new — scope
    # exhausted, which is the cost ceiling (PO 22/9/2026, E1), and the idle
    # round had already saturated.
    assert result.recommended_scan_state is RelationsScanState.STOPPED
