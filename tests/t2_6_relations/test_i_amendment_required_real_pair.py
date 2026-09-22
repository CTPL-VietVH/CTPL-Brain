"""T2.6 (i) — K3 REQUIRED case (work-order): `110-2004-nd-cp.docx` and
`30_2020_ND_CP.docx` share a subject with NO explicit citation between them
(Điều 37 of 30_2020 only names 110-2004 in repeal language, excluded from
REFERENCES by test_c) — `detect_inferred_amendment_relations` is the ONLY
detector that should link this pair.

Values below are exactly what the real pipeline produces — verified by
running `extract_subject_entities()` / `goi_y_nhan()` / `trich_ngay_ky()`
directly on both files before writing this test:

  110-2004-nd-cp.docx: subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
                        category_labels=["NGHỊ ĐỊNH"], issued_date=2004-04-08
  30_2020_ND_CP.docx:  subject_entities=["Về công tác văn thư"],
                        category_labels=["NGHỊ ĐỊNH"], issued_date=2020-03-05

Note the case difference on `subject_entities` — this is real, not a typo
planted for the test, and it's exactly why the gate normalizes before
comparing (work-order: "khác HOA/thường, phải chuẩn hoá mới khớp").
"""

from __future__ import annotations

from datetime import date

from ingestion.relations import detect_explicit_relations, detect_inferred_amendment_relations
from schema.relation import ApprovalState, RelationOrigin, RelationType

from .conftest import make_document


def _real_pair():
    earlier = make_document(
        document_id="doc-110-2004-nd-cp",
        doc_number="110/2004/NĐ-CP",
        extracted_text="Toàn văn Nghị định 110/2004/NĐ-CP về công tác văn thư.",
        issued_date=date(2004, 4, 8),
        subject_entities=["VỀ CÔNG TÁC VĂN THƯ"],
        category_labels=["NGHỊ ĐỊNH"],
    )
    later = make_document(
        document_id="doc-30-2020-nd-cp",
        doc_number="30/2020/NĐ-CP",
        extracted_text="Toàn văn Nghị định 30/2020/NĐ-CP về công tác văn thư.",
        issued_date=date(2020, 3, 5),
        subject_entities=["Về công tác văn thư"],
        category_labels=["NGHỊ ĐỊNH"],
    )
    return earlier, later


def test_real_pair_produces_amends_or_replaces_from_later_to_earlier():
    earlier, later = _real_pair()

    relations = detect_inferred_amendment_relations([earlier, later])

    assert len(relations) == 1
    relation = relations[0]
    assert relation.from_document_id == "doc-30-2020-nd-cp"
    assert relation.to_document_id == "doc-110-2004-nd-cp"
    assert relation.relation_type == RelationType.AMENDS_OR_REPLACES
    assert relation.origin == RelationOrigin.MACHINE_INFERRED
    assert relation.approval_state == ApprovalState.PENDING
    assert relation.confidence == 1.0  # 0.5 subject + 0.3 type + 0.2 date, all satisfied


def test_explicit_detector_stays_empty_on_the_same_pair_cross_check():
    """The two detectors must not step on each other: this pair has no
    plain citation clause (only repeal language, excluded — test_c), so
    `detect_explicit_relations` must return nothing for it, same as before
    K3 existed.
    """
    earlier, later = _real_pair()

    assert detect_explicit_relations([earlier, later]) == []
