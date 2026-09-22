"""T2.6 (a) — REFERENCES detected from a real "Căn cứ ... số ..." citation,
with the CHỐT direction (`07` Mục 2.3): `from` = citing document, `to` =
cited document.

Quote is verbatim from `data/test-corpus-vn-admin/nhan-su/10_2020_TT-BLDTBXH_454406.docx`
line 6 (Thông tư 10/2020/TT-BLĐTBXH citing Nghị định 14/2017/NĐ-CP).
"""

from __future__ import annotations

from datetime import date

from ingestion.relations import detect_explicit_relations
from schema.relation import ApprovalState, RelationOrigin, RelationType

from .conftest import make_document

CITING_TEXT = (
    "Căn cứ Nghị định số 14/2017/NĐ-CP ngày 17 tháng 02 năm 2017 của Chính phủ "
    "quy định chức năng, nhiệm vụ, quyền hạn và cơ cấu tổ chức của Bộ Lao động "
    "– Thương binh và Xã hội;"
)


def test_reference_relation_points_from_citing_document_to_cited_document():
    citing = make_document(
        document_id="doc-thong-tu-10-2020",
        doc_number="10/2020/TT-BLĐTBXH",
        extracted_text=CITING_TEXT,
    )
    cited = make_document(
        document_id="doc-nghi-dinh-14-2017",
        doc_number="14/2017/NĐ-CP",
        extracted_text="Toàn văn Nghị định 14/2017/NĐ-CP.",
        issued_date=date(2017, 2, 17),
    )

    relations = detect_explicit_relations([citing, cited])

    assert len(relations) == 1
    relation = relations[0]
    assert relation.from_document_id == "doc-thong-tu-10-2020"
    assert relation.to_document_id == "doc-nghi-dinh-14-2017"
    assert relation.relation_type == RelationType.REFERENCES
    assert relation.origin == RelationOrigin.MACHINE_READ_EXPLICIT_REFERENCE
    assert relation.approval_state == ApprovalState.PENDING


def test_reference_confidence_gets_corroboration_bonus_for_matching_date_and_authority():
    citing = make_document(
        document_id="doc-thong-tu-10-2020",
        doc_number="10/2020/TT-BLĐTBXH",
        extracted_text=CITING_TEXT,
    )
    cited_with_matching_date = make_document(
        document_id="doc-nghi-dinh-14-2017",
        doc_number="14/2017/NĐ-CP",
        extracted_text="Toàn văn Nghị định 14/2017/NĐ-CP.",
        issued_date=date(2017, 2, 17),
    )
    cited_with_different_date = make_document(
        document_id="doc-nghi-dinh-14-2017-b",
        doc_number="14/2017/NĐ-CP-B",
        extracted_text="Toàn văn khác.",
        issued_date=date(1999, 1, 1),
    )

    relations_with_match = detect_explicit_relations([citing, cited_with_matching_date])
    assert relations_with_match[0].confidence == 1.0  # 0.7 base + 0.2 date + 0.1 authority

    citing_b = make_document(
        document_id="doc-thong-tu-10-2020-b",
        doc_number="10/2020/TT-BLĐTBXH-B",
        extracted_text=CITING_TEXT.replace("14/2017/NĐ-CP", "14/2017/NĐ-CP-B"),
    )
    relations_without_date_match = detect_explicit_relations([citing_b, cited_with_different_date])
    assert relations_without_date_match[0].confidence == 0.8  # 0.7 base + 0.1 authority only
