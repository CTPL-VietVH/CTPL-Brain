"""T2.6 (c) — expansion is CUT at a private (`riêng`) branch: a document
sitting in a non-inheriting child Space is never compared, however citable
it looks (06 line 33 / line 72: *"quyền chảy một chiều xuống ... và cắt tại
nhánh riêng"*; PO decision 22/9/2026 makes that same cut the scan boundary).

The cut is the DEFAULT, not an opt-in: 06 line 32 — *"Khi tạo Space mới mà
không chỉ định thì mặc định là riêng."*
"""

from __future__ import annotations

from .conftest import CITATION_110, DOC_NUMBER_110, ISSUED_110, StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceDocumentSource,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)


def test_private_branch_cuts_the_expansion() -> None:
    new_document = make_document(
        document_id="new",
        doc_number="30/2020/NĐ-CP",
        extracted_text=CITATION_110,
        space_id="space-parent",
    )
    cited_behind_the_cut = make_document(
        document_id="cited",
        doc_number=DOC_NUMBER_110,
        issued_date=ISSUED_110,
        space_id="space-private-child",
    )

    result = scan_relations_for_new_document(
        new_document,
        scope=InMemorySpaceScanScope(
            [
                InMemorySpace(space_id="space-parent"),
                InMemorySpace(
                    space_id="space-private-child",
                    parent_space_id="space-parent",
                    # `inherits_from_parent` left at its default False — the
                    # branch cut.
                ),
            ]
        ),
        document_source=InMemorySpaceDocumentSource([new_document, cited_behind_the_cut]),
        saturation_epsilon=0.01,
        saturation_rounds=3,
        scan_pair_budget=100,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    assert result.relations == []
    assert result.pairs_compared == 0
