"""T2.6 (h) — a `(from, to, type)` triple comes back exactly ONCE, however
many rounds re-examine the pair that produced it (work-order: *"khử trùng
theo (from_document_id, to_document_id, relation_type)"*).

The candidate found in round 1 stays inside the accumulated scan set for
every later round, so a scan that merged results naively would hand the
caller three copies of the same link and three Manager approval tasks for
one relationship.
"""

from __future__ import annotations

from .conftest import CITATION_110, DOC_NUMBER_110, ISSUED_110, StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)


def test_a_relation_is_not_duplicated_across_rounds(document_source_factory) -> None:
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
        space_id="space-child",
    )
    in_parent = make_document(
        document_id="in-parent",
        doc_number="01/2019/QĐ-UBND",
        space_id="space-parent",
    )
    in_grandparent = make_document(
        document_id="in-grandparent",
        doc_number="02/2019/QĐ-UBND",
        space_id="space-grandparent",
    )

    result = scan_relations_for_new_document(
        new_document,
        scope=InMemorySpaceScanScope(
            [
                InMemorySpace(space_id="space-grandparent"),
                InMemorySpace(
                    space_id="space-parent",
                    parent_space_id="space-grandparent",
                    inherits_from_parent=True,
                ),
                InMemorySpace(
                    space_id="space-child",
                    parent_space_id="space-parent",
                    inherits_from_parent=True,
                ),
            ]
        ),
        document_source=document_source_factory(
            [new_document, cited, in_parent, in_grandparent]
        ),
        saturation_epsilon=0.01,
        saturation_rounds=3,
        scan_pair_budget=100,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    assert result.rounds_run >= 3, "the pair must survive more than one round to prove anything"
    assert len(result.relations) == 1
    keys = {
        (relation.from_document_id, relation.to_document_id, relation.relation_type)
        for relation in result.relations
    }
    assert len(keys) == len(result.relations)
