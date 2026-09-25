"""T2.4b — mandatory acceptance suite: `extract_document_number` /
`extract_title` against the 21 real files in `data/test-corpus-vn-admin/`
(same corpus as `GROUND_TRUTH_HIEU_LUC` in T2.4).

Acceptance bar (task T2.4b work-order, spec item 5):
  - doc_number: 0 WRONG values are allowed (a value that was filled in but
    disagrees with the answer key) — an empty string is never counted as
    wrong, only as missing coverage, which is reported but not gated.
  - title: no percentage bar. Reported as match / wrong / empty against
    `GROUND_TRUTH_TITLE_DOC_NUMBER`, with ONE hard assertion: never a case of
    picking up the title of a document CITED inside this one instead of this
    document's own title.

Written in English per CLAUDE.md Section 0 #4 (new code for this task).
"""

from __future__ import annotations

import re

from ingestion.labeling import extract_document_number, extract_title

from .conftest import GROUND_TRUTH_TITLE_DOC_NUMBER


def _normalized_document_number(raw: str) -> str:
    """Same normalization `packages/ingestion/relations.py` applies before
    using `doc_number` as the explicit-citation join key — comparing through
    it here is what the work-order means by "khớp đáp án sau khi qua
    _normalized_document_number"."""
    return re.sub(r"\s+", "", raw).upper()


def _normalized_title(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip().casefold()


def test_doc_number_has_zero_wrong_values_on_the_21_file_corpus(corpus_extracted_texts):
    wrong: list[str] = []
    empty: list[str] = []

    for path, expected_doc_number, _expected_title in GROUND_TRUTH_TITLE_DOC_NUMBER:
        extracted_text = corpus_extracted_texts[path]
        actual = extract_document_number(extracted_text).doc_number

        if actual == "":
            empty.append(path)
            continue
        if _normalized_document_number(actual) != _normalized_document_number(
            expected_doc_number
        ):
            wrong.append(f"{path}: expected={expected_doc_number!r} actual={actual!r}")

    total = len(GROUND_TRUTH_TITLE_DOC_NUMBER)
    coverage = total - len(empty)
    assert wrong == [], (
        f"doc_number must have ZERO wrong values (task T2.4b: THÀ TRỐNG CÒN "
        f"HƠN SAI) — got {len(wrong)}/{total} wrong:\n" + "\n".join(wrong)
    )
    print(f"\ndoc_number coverage: {coverage}/{total} (empty: {empty})")


def test_title_match_wrong_empty_report_on_the_21_file_corpus(corpus_extracted_texts):
    matched: list[str] = []
    wrong: list[str] = []
    empty: list[str] = []

    for path, _expected_doc_number, expected_title in GROUND_TRUTH_TITLE_DOC_NUMBER:
        extracted_text = corpus_extracted_texts[path]
        actual_title = extract_title(extracted_text).title

        if actual_title == "":
            empty.append(path)
        elif _normalized_title(actual_title) == _normalized_title(expected_title):
            matched.append(path)
        else:
            wrong.append(f"{path}: expected={expected_title!r} actual={actual_title!r}")

    total = len(GROUND_TRUTH_TITLE_DOC_NUMBER)
    print(
        f"\ntitle report — matched: {len(matched)}/{total}, "
        f"wrong: {len(wrong)}, empty: {len(empty)} ({empty})"
    )
    if wrong:
        print("wrong:\n" + "\n".join(wrong))


def test_title_never_picks_up_a_cited_documents_title_instead_of_its_own(
    corpus_extracted_texts,
):
    """Hard requirement (spec item 5): "0 ca lấy nhầm tên văn bản được dẫn
    chiếu." Every real file in the corpus opens with "Căn cứ <cited law> ..."
    recitals naming OTHER documents by their own type + subject — if the
    title extractor ever wandered past the front-matter window, it would
    start picking those up instead. Cross-check: the returned title, when
    non-empty, must never equal (casefold) another row's title in this same
    corpus — a cited document's title would otherwise look exactly like a
    genuine hit for the WRONG row."""
    titles_in_corpus = {
        _normalized_title(title) for _p, _d, title in GROUND_TRUTH_TITLE_DOC_NUMBER
    }

    for path, _expected_doc_number, expected_title in GROUND_TRUTH_TITLE_DOC_NUMBER:
        extracted_text = corpus_extracted_texts[path]
        actual_title = extract_title(extracted_text).title
        if actual_title == "":
            continue
        normalized_actual = _normalized_title(actual_title)
        normalized_expected = _normalized_title(expected_title)
        if normalized_actual != normalized_expected:
            assert normalized_actual not in (titles_in_corpus - {normalized_expected}), (
                f"{path}: extracted title matches ANOTHER document's title "
                f"in the corpus instead of its own — looks like a cited-"
                f"document mix-up: {actual_title!r}"
            )
