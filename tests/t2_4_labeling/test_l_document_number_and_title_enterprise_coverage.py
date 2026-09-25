"""T2.4b — coverage-only report on the 15 real enterprise PDFs in
`data/eval-corpus-enterprise/` (spec item 5: "chỉ báo tỷ lệ phủ, không đáp
án" — no answer key exists for this corpus, so nothing here is graded).

This corpus is mostly Nội quy / Quy chế / Quy trình / user manuals — none of
which carry a "NGHỊ ĐỊNH"/"LUẬT"/"THÔNG TƯ"/"BỘ LUẬT" front-matter anchor, so
LOW coverage here is an expected, honest result of "thà trống còn hơn sai"
(task T2.4b PO chốt), not a defect — `extract_document_number` correctly
refuses rather than guessing at, for instance, the "Kèm theo Quyết định số:
..." citation that several of these files open with (that number belongs to
the decision THIS document is an attachment to, not to this document).

Written in English per CLAUDE.md Section 0 #4 (new code for this task).
"""

from __future__ import annotations

from ingestion.labeling import extract_document_number, extract_title

from .conftest import ENTERPRISE_CORPUS_RELATIVE_PATHS


def test_coverage_report_on_the_15_enterprise_pdfs(enterprise_corpus_extracted_texts):
    doc_number_hits: list[str] = []
    title_hits: list[str] = []

    for relative_path in ENTERPRISE_CORPUS_RELATIVE_PATHS:
        extracted_text = enterprise_corpus_extracted_texts[relative_path]
        if extract_document_number(extracted_text).doc_number:
            doc_number_hits.append(relative_path)
        if extract_title(extracted_text).title:
            title_hits.append(relative_path)

    total = len(ENTERPRISE_CORPUS_RELATIVE_PATHS)
    print(
        f"\nenterprise coverage — doc_number: {len(doc_number_hits)}/{total} "
        f"{doc_number_hits}, title: {len(title_hits)}/{total} {title_hits}"
    )


def test_kem_theo_citation_is_not_mistaken_for_this_documents_own_number(
    enterprise_corpus_extracted_texts,
):
    """`noi-quy-lao-dong-truong-dai-hoc-phan-thiet.pdf` opens with "(Kèm
    theo Quyết định số: 18/QĐ-ĐHPT ngày 08 tháng 01 năm 2021 của Hiệu trưởng
    ...)" — that number names the DECISION this Nội quy is an attachment to,
    not this document's own number. No "NGHỊ ĐỊNH"/"LUẬT"/"THÔNG TƯ"/"BỘ
    LUẬT" front-matter line exists here to bound the search window, so the
    extractor must refuse entirely rather than grab this citation."""
    path = "hanh-chinh/noi-quy-lao-dong-truong-dai-hoc-phan-thiet.pdf"
    extracted_text = enterprise_corpus_extracted_texts[path]
    result = extract_document_number(extracted_text)
    assert result.doc_number == "", (
        f"expected no confident doc_number (no front-matter anchor to bound "
        f"the search), got {result.doc_number!r} — likely picked up the "
        f"'Kèm theo Quyết định số: ...' citation instead of this document's "
        f"own number"
    )
