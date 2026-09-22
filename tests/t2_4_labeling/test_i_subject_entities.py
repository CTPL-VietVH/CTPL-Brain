"""T2.4-add-subject-entities — `extract_subject_entities` suggests
`Document.subject_entities` via the three anchors LOCKED 2026-09-22 (07
Section 2.1 line 93 + callout lines 127-135): (1) "V/v" subject line, (2)
UPPERCASE title, (3) Điều 1 "Phạm vi điều chỉnh" fallback, tried in that
priority order.

Written in English per CLAUDE.md Section 0 #4 (this is new code, not a
rename of the existing Vietnamese-named test files in this directory).
"""

from __future__ import annotations

from ingestion.labeling import SubjectEntitySuggestion, extract_subject_entities

# ---------------------------------------------------------------------------
# Anchor (1) — synthetic "V/v" subject line. No document in
# data/test-corpus-vn-admin/ carries "V/v" near the head (the corpus is all
# Luật/Nghị định, not individual Quyết định/Công văn acts), so this anchor
# is exercised with a hand-built fixture in the administrative style used
# for real Quyết định/Công văn documents (matches the table-cell "|" join
# convention already used for the dateline fixtures in conftest.py).
# ---------------------------------------------------------------------------
DOC_WITH_SUBJECT_LINE = """ỦY BAN NHÂN DÂN TỈNH X | CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Số: 15/QĐ-UBND | Độc lập - Tự do - Hạnh phúc

QUYẾT ĐỊNH
V/v: Bổ nhiệm ông Nguyễn Văn A giữ chức vụ Giám đốc Sở Nội vụ

ỦY BAN NHÂN DÂN TỈNH X

Căn cứ Luật Tổ chức chính quyền địa phương ngày 19 tháng 6 năm 2015;
QUYẾT ĐỊNH:

Điều 1. Bổ nhiệm ông Nguyễn Văn A giữ chức vụ Giám đốc Sở Nội vụ kể từ ngày
ký ban hành."""

# ---------------------------------------------------------------------------
# Anchor (3) fallback — no "V/v" line, no recognized UPPERCASE title keyword
# at the head, but a "Điều 1. Phạm vi điều chỉnh" clause is present.
# ---------------------------------------------------------------------------
DOC_WITH_SCOPE_ARTICLE_ONLY = """VĂN BẢN NỘI BỘ SỐ 07/2026

Điều 1. Phạm vi điều chỉnh
Văn bản này quy định về việc quản lý tài sản cố định trong doanh nghiệp.

Điều 2. Đối tượng áp dụng
Văn bản này áp dụng cho toàn thể cán bộ, nhân viên công ty."""

DOC_WITH_NO_SIGNAL = (
    "Văn bản này hoàn toàn không có dòng trích yếu, tiêu đề in hoa nhận diện "
    "được, hay điều khoản phạm vi điều chỉnh nào."
)


def test_anchor_1_subject_line_wins_over_lower_priority_anchors():
    result = extract_subject_entities(DOC_WITH_SUBJECT_LINE)
    assert isinstance(result, SubjectEntitySuggestion)
    assert result.subject_entities == [
        "Bổ nhiệm ông Nguyễn Văn A giữ chức vụ Giám đốc Sở Nội vụ"
    ]


def test_anchor_2_uppercase_title_nghi_dinh_138():
    """Real file verified by Cowork against the corpus (work-order T2.4-add-
    subject-entities): title block is "NGHỊ ĐỊNH" on its own line, followed
    by the (non-uppercase) subject line on the very next line."""
    from ingestion.extraction import extract_file

    from .conftest import CORPUS_ROOT

    extracted_text = extract_file(
        CORPUS_ROOT / "nhan-su/Nghị-định-138-2020-NĐ-CP.docx"
    ).extracted_text
    result = extract_subject_entities(extracted_text)
    assert result.subject_entities == ["Quy định về tuyển dụng, sử dụng và quản lý công chức"]


def test_anchor_2_uppercase_title_luat_xay_dung():
    """LUẬT-50-2014-QH13.docx — title and subject share a single ALL-CAPS
    line ("LUẬT XÂY DỰNG")."""
    from ingestion.extraction import extract_file

    from .conftest import CORPUS_ROOT

    extracted_text = extract_file(
        CORPUS_ROOT / "ky-thuat-van-hanh/Luật-50-2014-QH13.docx"
    ).extracted_text
    result = extract_subject_entities(extracted_text)
    assert result.subject_entities == ["XÂY DỰNG"]


def test_anchor_2_uppercase_title_luat_dau_thau():
    """Luat Dau thau 2023.docx — title keyword "LUẬT" alone on its line,
    subject "ĐẤU THẦU" on the next line."""
    from ingestion.extraction import extract_file

    from .conftest import CORPUS_ROOT

    extracted_text = extract_file(
        CORPUS_ROOT / "tai-chinh-ke-toan/Luat Dau thau 2023.docx"
    ).extracted_text
    result = extract_subject_entities(extracted_text)
    assert result.subject_entities == ["ĐẤU THẦU"]


def test_anchor_3_scope_article_fallback_when_no_higher_anchor_signal():
    result = extract_subject_entities(DOC_WITH_SCOPE_ARTICLE_ONLY)
    assert result.subject_entities == ["quản lý tài sản cố định trong doanh nghiệp"]


def test_no_signal_anywhere_returns_empty_list_not_a_guess():
    result = extract_subject_entities(DOC_WITH_NO_SIGNAL)
    assert result.subject_entities == []


def test_module_does_not_persist_or_import_document():
    """Same contract as `GoiYNgayKy`/`GoiYNgayHieuLuc` (test_f_scope_boundaries.py):
    suggestion only, no side effect, no import of the storage-facing `Document`
    class into the labeling module's namespace."""
    from ingestion import labeling

    assert not hasattr(labeling, "Document")


def test_suggestion_dataclass_has_only_the_documented_field():
    """07 line 135 (LOCKED 2026-09-22): no `_confirmed_by`/`_at` pair,
    unlike `category_labels` — mirrored here at the suggestion-type level so
    a future edit adding that pair back fails loudly."""
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(SubjectEntitySuggestion)}
    assert field_names == {"subject_entities"}
