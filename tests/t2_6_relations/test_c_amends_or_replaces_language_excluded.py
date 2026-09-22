"""T2.6 (c) — AMENDS_OR_REPLACES language must NOT surface as REFERENCES.

Work-order note (PO, 22/9/2026): the pair `110-2004-nd-cp.docx` /
`30_2020_ND_CP.docx` is real — 30_2020's "Điều 37. Hiệu lực thi hành" names
110-2004 by number — but the sentence is amendment/repeal language
("hết hiệu lực"), not a plain citation. It belongs to AMENDS_OR_REPLACES
(a later work-order, K3, `06` Mục 5.3), and `detect_explicit_relations` here
must produce NOTHING for it — silently guessing REFERENCES would be worse
than the accepted miss (NT2).

Quote is verbatim from `data/test-corpus-vn-admin/phap-che-tuan-thu/30_2020_ND_CP.docx`,
Điều 37 (the run of spaces between "định" and "số" is in the source file).
"""

from __future__ import annotations

from ingestion.relations import detect_explicit_relations

from .conftest import make_document

REAL_REPEAL_SENTENCE = (
    "Nghị định này có hiệu lực thi hành kể từ ngày ký. Nghị định                              "
    "số 110/2004/NĐ-CP ngày 08 tháng 4 năm 2004 của Chính phủ về công tác văn thư và Nghị định "
    "số 09/2010/NĐ-CP ngày 08 tháng 02 năm 2010 của Chính phủ sửa đổi, bổ sung một số điều của "
    "Nghị định số 110/2004/NĐ-CP ngày 08 tháng 4 năm 2004 của Chính phủ về công tác văn thư hết "
    "hiệu lực từ ngày Nghị định này có hiệu lực pháp luật."
)


def test_real_repeal_sentence_naming_another_document_by_number_produces_no_relation():
    later_document = make_document(
        document_id="doc-30-2020-nd-cp",
        doc_number="30/2020/NĐ-CP",
        extracted_text=REAL_REPEAL_SENTENCE,
    )
    repealed_document = make_document(
        document_id="doc-110-2004-nd-cp",
        doc_number="110/2004/NĐ-CP",
        extracted_text="Toàn văn Nghị định 110/2004/NĐ-CP.",
    )

    assert detect_explicit_relations([later_document, repealed_document]) == []


def test_cited_clause_starting_with_can_cu_but_carrying_amendment_wording_is_still_excluded():
    """Defense-in-depth: even if "Căn cứ" DID directly precede the citation
    (it never does in the real corpus for this pair — see test above), the
    amendment-vocabulary guard on its own must still block it.
    """
    citing = make_document(
        document_id="doc-adversarial",
        doc_number="99/2099/NĐ-CP",
        extracted_text=(
            "Căn cứ Nghị định số 110/2004/NĐ-CP ngày 08 tháng 4 năm 2004 của Chính phủ "
            "đã được sửa đổi, bổ sung;"
        ),
    )
    cited = make_document(
        document_id="doc-110-2004-nd-cp",
        doc_number="110/2004/NĐ-CP",
        extracted_text="Toàn văn Nghị định 110/2004/NĐ-CP.",
    )

    assert detect_explicit_relations([citing, cited]) == []
