"""T2.6 (a) — the scan starts at the Space holding the new document (06 Mục
5.3: *"bắt đầu từ Space chứa tài liệu"*) and turns a citation found there
into a REFERENCES relation, with the CHỐT direction (`07` Mục 2.3).
"""

from __future__ import annotations

from .conftest import CITATION_110, DOC_NUMBER_110, ISSUED_110, StubClock, make_document
from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceDocumentSource,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)
from schema.relation import RelationType


def test_first_round_scans_the_documents_own_space() -> None:
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
        scan_pair_budget=100,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    assert [
        (relation.from_document_id, relation.to_document_id, relation.relation_type)
        for relation in result.relations
    ] == [("new", "cited", RelationType.REFERENCES)]
    assert result.pairs_compared == 1
