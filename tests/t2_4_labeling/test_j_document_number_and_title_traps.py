"""T2.4b — `extract_document_number` / `extract_title`, one test per named
trap from the work-order (packages/ingestion/labeling.py).

Written in English per CLAUDE.md Section 0 #4 (new code for this task, not a
rename of the existing Vietnamese-named test files in this directory — same
convention already used in test_i_subject_entities.py).
"""

from __future__ import annotations

import dataclasses

from ingestion import labeling
from ingestion.labeling import (
    DocNumberSuggestion,
    TitleSuggestion,
    extract_document_number,
    extract_title,
)

# ---------------------------------------------------------------------------
# Trap 1 — "Căn cứ Nghị định số …": a citation TO another document, inside a
# "Căn cứ" recital, must never be read as THIS document's own number. The
# front-matter window ends at the first "Căn cứ" line, so the citation's
# number is never even reached.
# ---------------------------------------------------------------------------
DOC_WITH_CITATION_IN_RECITALS = """CHÍNH PHỦ Số: 30/2020/NĐ-CP | CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

NGHỊ ĐỊNH
Về công tác văn thư

Căn cứ Nghị định số 48/2008/NĐ-CP ngày 17 tháng 4 năm 2008 của Chính phủ;
Chính phủ ban hành Nghị định về công tác văn thư."""


def test_trap_citation_inside_can_cu_recital_is_not_read_as_own_number():
    result = extract_document_number(DOC_WITH_CITATION_IN_RECITALS)
    assert result.doc_number == "30/2020/NĐ-CP"


# ---------------------------------------------------------------------------
# Trap 2 — the number of a document this Luật REPLACES, mentioned near the
# END of the text, must not leak into doc_number either. Trivially true by
# construction (the window never reads past the front matter), but pinned
# explicitly since the work-order calls it out as its own named trap.
# ---------------------------------------------------------------------------
DOC_WHOSE_TAIL_CITES_A_REPLACED_LAW = """QUỐC HỘI Luật số: 59/2020/QH14 | CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

LUẬT
DOANH NGHIỆP

Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;
Quốc hội ban hành Luật Doanh nghiệp.

Điều 1. Phạm vi điều chỉnh
Luật này quy định về việc thành lập, tổ chức quản lý doanh nghiệp.

Điều 220. Hiệu lực thi hành
Luật này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2021 và thay thế
Luật Doanh nghiệp số 68/2014/QH13."""


def test_trap_replaced_law_number_at_the_tail_is_not_picked_up():
    result = extract_document_number(DOC_WHOSE_TAIL_CITES_A_REPLACED_LAW)
    assert result.doc_number == "59/2020/QH14"


# ---------------------------------------------------------------------------
# Trap 3a — "Luật số:".
# ---------------------------------------------------------------------------
def test_trap_luat_so_prefix():
    text = "QUỐC HỘI Luật số: 88/2015/QH13 | CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n\nLUẬT\nKẾ TOÁN\n\nCăn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;"
    result = extract_document_number(text)
    assert result.doc_number == "88/2015/QH13"


# ---------------------------------------------------------------------------
# Trap 3b — "Bộ luật số:".
# ---------------------------------------------------------------------------
def test_trap_bo_luat_so_prefix():
    text = "QUỐC HỘI Bộ luật số: 45/2019/QH14 | CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n\nBỘ LUẬT\nLAO ĐỘNG\n\nCăn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;"
    result = extract_document_number(text)
    assert result.doc_number == "45/2019/QH14"


# ---------------------------------------------------------------------------
# Trap 4 — the issuing-body abbreviation runs flush against "Số:" with no
# space or line break (real file: 110-2004-nd-cp.docx, "CHÍNH
# PHỦ––––Số: 110/2004/NĐ-CP"). No line-start anchor may be required.
# ---------------------------------------------------------------------------
def test_trap_authority_name_glued_to_so_prefix():
    text = "CHÍNH PHỦ––––Số: 110/2004/NĐ-CP | CỘNG HÒA XÃ HỘI CHỦ NGHIÃ VIỆT NAM\n\nNGHỊ ĐỊNH\nVỀ CÔNG TÁC VĂN THƯ\n\nCăn cứ Luật Tổ chức Chính phủ ngày 25 tháng 12 năm 2001;"
    result = extract_document_number(text)
    assert result.doc_number == "110/2004/NĐ-CP"


# ---------------------------------------------------------------------------
# Trap 5 — lower-cased "số:" (observed OCR artifact, real file:
# tt-200-btc-22-12-2014.pdf: "số: 200/2014/TT-BTC").
# ---------------------------------------------------------------------------
def test_trap_lowercase_so_prefix_from_ocr():
    text = "Bộ TÀI CHÍNH CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐỘC lập - Tự do - Hạnh phúc\nsố: 200/2014/TT-BTC Hà Nội, ngày 22 tháng 12 năm 2014\nTHÔNG TƯ\nHướng dẫn Chế độ kế toán Doanh nghiệp\nCăn cứ Luật Kế toán ngày 17 tháng 06 năm 2003;"
    result = extract_document_number(text)
    assert result.doc_number == "200/2014/TT-BTC"


# ---------------------------------------------------------------------------
# Trap 6 — a trích yếu that wraps across several physical lines (a manual
# mid-sentence line-wrap, not a new paragraph): continuation lines are
# recognized by starting lower-case, and joined with a SINGLE space (real
# file: 168.2024.NĐ.CP.docx).
# ---------------------------------------------------------------------------
DOC_WITH_MULTILINE_SUBJECT_CLAUSE = """CHÍNH PHỦ | CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Số: 168/2024/NĐ-CP | Hà Nội, ngày 26 tháng 12 năm 2024

NGHỊ ĐỊNH
Quy định xử phạt vi phạm hành chính về trật tự, an toàn giao thông
trong lĩnh vực giao thông đường bộ; trừ điểm,
phục hồi điểm giấy phép lái xe
Căn cứ Luật Tổ chức Chính phủ ngày 19 tháng 6 năm 2015;"""


def test_trap_multiline_subject_clause_joined_with_single_space():
    result = extract_title(DOC_WITH_MULTILINE_SUBJECT_CLAUSE)
    assert result.title == (
        "Nghị định Quy định xử phạt vi phạm hành chính về trật tự, an toàn "
        "giao thông trong lĩnh vực giao thông đường bộ; trừ điểm, phục hồi "
        "điểm giấy phép lái xe"
    )
    assert "\n" not in result.title


# ---------------------------------------------------------------------------
# Trap 6b — the multi-line accumulation must STOP at a new upper-case line
# that is not itself a continuation (the issuing body repeated before the
# "Căn cứ" recitals — real file: 110-2004-nd-cp.docx, "CHÍNH PHỦ" on its own
# line right after the subject clause).
# ---------------------------------------------------------------------------
def test_trap_multiline_accumulation_stops_before_unrelated_uppercase_line():
    text = "CHÍNH PHỦ –––– Số: 110/2004/NĐ-CP | CỘNG HÒA XÃ HỘI CHỦ NGHIÃ VIỆT NAM\n\nNGHỊ ĐỊNH\nVỀ CÔNG TÁC VĂN THƯ\nCHÍNH PHỦ\nCăn cứ Luật Tổ chức Chính phủ ngày 25 tháng 12 năm 2001;"
    result = extract_title(text)
    assert result.title == "Nghị định về công tác văn thư"


# ---------------------------------------------------------------------------
# Trap 7 — the whole trích yếu written ALL CAPS end to end converts to
# sentence-style casing; a trích yếu that already mixes case is passed
# through verbatim (spec item 3).
# ---------------------------------------------------------------------------
def test_trap_all_uppercase_subject_clause_becomes_sentence_case():
    text = "NGHỊ ĐỊNH\nQUY ĐỊNH VỀ TUYỂN DỤNG, SỬ DỤNG VÀ QUẢN LÝ CÔNG CHỨC\nCăn cứ Luật Tổ chức Chính phủ ngày 19 tháng 6 năm 2015;"
    result = extract_title(text)
    assert result.title == "Nghị định quy định về tuyển dụng, sử dụng và quản lý công chức"


def test_mixed_case_subject_clause_is_kept_verbatim():
    text = "NGHỊ ĐỊNH\nVề công tác văn thư\nCăn cứ Luật Tổ chức Chính phủ ngày 19 tháng 6 năm 2015;"
    result = extract_title(text)
    assert result.title == "Nghị định Về công tác văn thư"


# ---------------------------------------------------------------------------
# Trap 8 — no document number anywhere in the front matter -> "", never a
# guess (project-wide "thà trống còn hơn sai" — PO chốt for T2.4b).
# ---------------------------------------------------------------------------
def test_document_with_no_number_returns_empty_string():
    text = "NGHỊ ĐỊNH\nVề công tác văn thư\n\nCăn cứ Luật Tổ chức Chính phủ ngày 19 tháng 6 năm 2015;"
    result = extract_document_number(text)
    assert result.doc_number == ""
    assert result.source_span is None


def test_no_recognized_document_type_line_returns_empty_title():
    """No anchor at all (neither a document-type line nor a `Số:` prefix
    tied to one) -> both suggestions abstain, matching docs/10 §4.2: the
    filename must NEVER be used as a stand-in title."""
    text = "Văn bản này không có dòng tên loại văn bản nào nhận diện được."
    assert extract_title(text).title == ""
    assert extract_document_number(text).doc_number == ""


# ---------------------------------------------------------------------------
# source_span contract — mirrors GoiYNgayKy/GoiYNgayHieuLuc: suggestion-only,
# never persisted, never a guess when empty.
# ---------------------------------------------------------------------------
def test_doc_number_source_span_points_at_the_matched_token():
    result = extract_document_number(DOC_WITH_CITATION_IN_RECITALS)
    start, end = result.source_span
    assert DOC_WITH_CITATION_IN_RECITALS[start:end] == "30/2020/NĐ-CP"


def test_title_source_span_covers_type_line_through_last_subject_line():
    result = extract_title(DOC_WITH_MULTILINE_SUBJECT_CLAUSE)
    start, end = result.source_span
    covered = DOC_WITH_MULTILINE_SUBJECT_CLAUSE[start:end]
    assert covered.startswith("NGHỊ ĐỊNH")
    assert covered.endswith("phục hồi điểm giấy phép lái xe")


def test_suggestion_dataclasses_have_only_the_documented_fields():
    assert {f.name for f in dataclasses.fields(DocNumberSuggestion)} == {
        "doc_number",
        "source_span",
    }
    assert {f.name for f in dataclasses.fields(TitleSuggestion)} == {
        "title",
        "source_span",
    }


def test_module_does_not_persist_or_import_document():
    """Same contract as every other GĐ5 suggestion in this module
    (test_f_scope_boundaries.py, test_i_subject_entities.py)."""
    assert not hasattr(labeling, "Document")
