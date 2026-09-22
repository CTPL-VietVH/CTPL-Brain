"""T2.6 (g) — a document citing its OWN `doc_number` produces no relation
(no self-loop). This is the real, ordinary shape in the corpus: an appendix
embedded in the same file it names, e.g.
`data/test-corpus-vn-admin/nhan-su/nghi-dinh-145-2020-huong-dan-thi-hanh-dieu-kien-lao-dong-va-quan-he-lao-dong.docx`
itself contains "(Kèm theo Nghị định số 145/2020/NĐ-CP ngày 14 tháng 12 năm
2020 của Chính phủ)" — a self-citation, not a link to a separate attachment
document (contrast with test_b, where the SAME phrase names a document
other than itself).
"""

from __future__ import annotations

from ingestion.relations import detect_explicit_relations

from .conftest import make_document


def test_document_citing_its_own_doc_number_yields_no_relation():
    document = make_document(
        document_id="doc-nghi-dinh-145-2020",
        doc_number="145/2020/NĐ-CP",
        extracted_text=(
            "Phụ lục III\n(Kèm theo Nghị định số 145/2020/NĐ-CP ngày 14 tháng 12 năm 2020 "
            "của Chính phủ)"
        ),
    )

    assert detect_explicit_relations([document]) == []
