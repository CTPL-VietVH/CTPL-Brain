"""T2.6 (b) — ATTACHMENT detected from a real "kèm theo ... số ..." opening,
with the CHỐT direction (`07` Mục 2.3): `from` = the appendix, `to` = the
main document.

Quote is verbatim from
`data/test-corpus-vn-admin/nhan-su/nghi-dinh-145-2020-huong-dan-thi-hanh-dieu-kien-lao-dong-va-quan-he-lao-dong.docx`
(the "Phụ lục III" opening line). In the real file this heading sits inside
the SAME document it names — a self-citation, excluded (see test_g). Here it
stands in for the realistic case of that appendix having been uploaded as
its OWN, separate `Document` — the exact phrase an appendix file would open
with either way.
"""

from __future__ import annotations

from datetime import date

from ingestion.relations import detect_explicit_relations
from schema.relation import ApprovalState, RelationOrigin, RelationType

from .conftest import make_document

ATTACHMENT_OPENING = (
    "Phụ lục III\n(Kèm theo Nghị định số 145/2020/NĐ-CP ngày 14 tháng 12 năm 2020 của Chính phủ)"
)


def test_attachment_relation_points_from_appendix_to_main_document():
    appendix = make_document(
        document_id="doc-phu-luc-iii",
        doc_number="Phụ lục III/145/2020/NĐ-CP",
        extracted_text=ATTACHMENT_OPENING,
    )
    main_document = make_document(
        document_id="doc-nghi-dinh-145-2020",
        doc_number="145/2020/NĐ-CP",
        extracted_text="Toàn văn Nghị định 145/2020/NĐ-CP.",
        issued_date=date(2020, 12, 14),
    )

    relations = detect_explicit_relations([appendix, main_document])

    assert len(relations) == 1
    relation = relations[0]
    assert relation.from_document_id == "doc-phu-luc-iii"
    assert relation.to_document_id == "doc-nghi-dinh-145-2020"
    assert relation.relation_type == RelationType.ATTACHMENT
    assert relation.origin == RelationOrigin.MACHINE_READ_EXPLICIT_REFERENCE
    assert relation.approval_state == ApprovalState.PENDING
    assert relation.confidence == 1.0  # 0.7 base + 0.2 matching date + 0.1 authority
