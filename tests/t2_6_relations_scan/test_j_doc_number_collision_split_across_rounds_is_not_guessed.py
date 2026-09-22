"""T2.6 (j) — the ambiguity guard of `detect_explicit_relations` ("more than
one candidate shares that `doc_number` → guess nothing") must hold across
the WHOLE scan, not merely within one round.

This is the failure the round loop could most easily introduce: feeding the
detector one round's newcomers at a time, a collision whose two halves live
in different Spaces would never be visible to it, and round 1's confident
link toward the wrong half would survive untouched — a REFERENCES pointing
at a document the text never meant, with no signal that anything was
ambiguous. NT2 accepts a miss here; it does not accept a guess.
"""

from __future__ import annotations

from .conftest import CITATION_110, DOC_NUMBER_110, ISSUED_110, StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceDocumentSource,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)


def test_doc_number_collision_split_across_rounds_is_not_guessed() -> None:
    new_document = make_document(
        document_id="new",
        doc_number="30/2020/NĐ-CP",
        extracted_text=CITATION_110,
        space_id="space-child",
    )
    same_number_in_child = make_document(
        document_id="cited-in-child",
        doc_number=DOC_NUMBER_110,
        issued_date=ISSUED_110,
        space_id="space-child",
    )
    same_number_in_parent = make_document(
        document_id="cited-in-parent",
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
        document_source=InMemorySpaceDocumentSource(
            [new_document, same_number_in_child, same_number_in_parent]
        ),
        saturation_epsilon=0.01,
        saturation_rounds=3,
        scan_pair_budget=100,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    assert result.pairs_compared == 2, "both halves of the collision must have been compared"
    assert result.relations == []
