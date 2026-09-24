"""T2.6 (n) — one scan carries BOTH proposal sources of 06 Mục 5.3 in a
single result: the explicit citation read off the text, and K3's inferred
amendment (*"cùng đối tượng được nói tới + cùng loại văn bản + ngày ban hành
sau"*), which exists precisely because *"quyết định nhân sự mới thường không
nhắc quyết định cũ"*.

The two `origin` values stay distinct — `MACHINE_READ_EXPLICIT_REFERENCE` is
in DX1's "chắc chắn" set, `MACHINE_INFERRED` is not (07 Mục 2.3) — so
merging the two detectors must not flatten them.
"""

from __future__ import annotations

from datetime import date

from ingestion.relations_scan import (
    InMemorySpace,
    InMemorySpaceScanScope,
    scan_relations_for_new_document,
)
from schema.relation import RelationOrigin, RelationType

from .conftest import CITATION_110, DOC_NUMBER_110, ISSUED_110, StubClock, make_document


def test_both_detectors_contribute_to_one_result(document_source_factory) -> None:
    new_document = make_document(
        document_id="new",
        doc_number="30/2020/NĐ-CP",
        extracted_text=CITATION_110,
        issued_date=date(2020, 3, 5),
        subject_entities=["Ban Giám đốc Công ty"],
        category_labels=["Quyết định"],
    )
    cited = make_document(
        document_id="cited",
        doc_number=DOC_NUMBER_110,
        issued_date=ISSUED_110,
    )
    superseded = make_document(
        document_id="superseded",
        doc_number="05/2018/QĐ-TCT",
        issued_date=date(2018, 6, 1),
        subject_entities=["ban giám đốc công ty"],
        category_labels=["Quyết định"],
    )

    result = scan_relations_for_new_document(
        new_document,
        scope=InMemorySpaceScanScope([InMemorySpace(space_id="space-own")]),
        document_source=document_source_factory([new_document, cited, superseded]),
        saturation_epsilon=0.01,
        saturation_rounds=3,
        scan_pair_budget=100,
        scan_time_budget=10.0,
        clock=StubClock([0.0]),
    )

    by_type = {relation.relation_type: relation for relation in result.relations}
    assert set(by_type) == {RelationType.REFERENCES, RelationType.AMENDS_OR_REPLACES}

    reference = by_type[RelationType.REFERENCES]
    assert (reference.from_document_id, reference.to_document_id) == ("new", "cited")
    assert reference.origin is RelationOrigin.MACHINE_READ_EXPLICIT_REFERENCE

    amendment = by_type[RelationType.AMENDS_OR_REPLACES]
    assert (amendment.from_document_id, amendment.to_document_id) == ("new", "superseded")
    assert amendment.origin is RelationOrigin.MACHINE_INFERRED
