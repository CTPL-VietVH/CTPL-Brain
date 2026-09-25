"""T2.3 bước 2/2 (o) — CHUNK-bang-bieu, 25/9/2026: mức ranh giới DÒNG ĐƠN,
mức chia thứ BA sau đoạn và câu, dùng khi một CÂU (theo `_tim_diem_cat_cau`)
vẫn vượt trần sau khi đã chia theo đoạn.

Ca thật trong work-order (PO, 25/9/2026): 2/36 tài liệu của kho thử
(`47_2021_nd-cp`, `Luật-61-2020`) có một BẢNG phụ lục — mỗi hàng đứng riêng
một dòng, KHÔNG có dòng trống giữa các hàng (không phải ranh giới đoạn) và
số liệu trong bảng không mang dấu kết câu thật nào (mọi dấu chấm là phân
cách hàng nghìn, giống bẫy đã dùng ở `test_j`) — nên trước 25/9/2026 cả bảng
rơi vào đúng MỘT "câu" và `KhoiVuotTranKhongTheChia` nổ ngay. Mô phỏng ở đây
bằng văn bản NGẮN hơn nhưng cùng hình dạng.
"""

from __future__ import annotations

import pytest

from ingestion.chunking import KhoiVuotTranKhongTheChia, cat_thanh_mau
from ingestion.extraction import extract_file
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, REPO_ROOT, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU

# Một "hàng" của bảng: toàn dấu phân cách hàng nghìn (đứng ngay trước một CHỮ
# SỐ), không dấu kết câu thật nào — cùng bẫy đã dùng ở `test_j`.
_HANG = "1.234.567,89 " * 30
# 60 hàng, MỖI HÀNG MỘT DÒNG (nối bằng "\n" ĐƠN, không dòng trống giữa các
# hàng) — đúng hình dạng "228 dòng, không dòng trống" nêu trong work-order.
_BANG_NHIEU_DONG = "\n".join(_HANG for _ in range(60))

VAN_BAN_KHOAN_CHUA_BANG = f"""Điều 1. Phạm vi điều chỉnh
1. Số liệu chi tiết như sau:
{_BANG_NHIEU_DONG}

Điều 2. Hiệu lực thi hành
Quy chế có hiệu lực kể từ ngày ký."""

# Một DÒNG ĐƠN (không `\n` bên trong) tự nó đã vượt trần — không còn ranh
# giới an toàn nào (đoạn/câu/dòng) để chia tiếp, phải vẫn nổ ngoại lệ hiện
# có, không được cắt giữa dòng.
_DONG_QUA_DAI = "1.234.567,89 " * 500

VAN_BAN_KHOAN_MOT_DONG_KHONG_CHIA_DUOC = f"""Điều 1. Phạm vi điều chỉnh
1. Số liệu: {_DONG_QUA_DAI}

Điều 2. Hiệu lực thi hành
Quy chế có hiệu lực kể từ ngày ký."""


def test_fixture_table_has_no_blank_lines_and_no_real_sentence_punctuation():
    assert len(_BANG_NHIEU_DONG) > TRAN_DO_DAI_MAU_THU
    assert "\n\n" not in _BANG_NHIEU_DONG, (
        "Phép thử tự hỏng: không được có dòng trống bên trong bảng, nếu "
        "không ranh giới ĐOẠN đã đủ để chia, không cần chạm tới mức dòng"
    )
    assert "\n" in _BANG_NHIEU_DONG, (
        "Phép thử tự hỏng: cần có xuống dòng đơn giữa các hàng để có ranh "
        "giới mà chia"
    )
    import re

    for m in re.finditer(r"[.!?…]", _BANG_NHIEU_DONG):
        j = m.end()
        while j < len(_BANG_NHIEU_DONG) and _BANG_NHIEU_DONG[j] in " \t":
            j += 1
        assert j >= len(_BANG_NHIEU_DONG) or _BANG_NHIEU_DONG[j].isdigit(), (
            "Phép thử tự hỏng: không được có dấu kết câu thật nào, để buộc "
            "cả bảng rơi vào đúng MỘT câu ở mức trên"
        )


def test_table_over_cap_is_split_into_multiple_chunks_by_line():
    read_result = dung_cau_truc(VAN_BAN_KHOAN_CHUA_BANG, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    khoan_1 = sorted(
        (c for c in chunks if c.structure_path == ["Điều 1", "Khoản 1"]),
        key=lambda c: c.span_start,
    )
    assert len(khoan_1) >= 2, "Một câu (cả bảng) vượt trần phải bị chia thành nhiều mẩu"
    for c in khoan_1:
        assert c.span_end - c.span_start <= TRAN_DO_DAI_MAU_THU


def test_line_split_fragments_are_perfectly_contiguous_no_characters_lost():
    read_result = dung_cau_truc(VAN_BAN_KHOAN_CHUA_BANG, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    khoan_1 = sorted(
        (c for c in chunks if c.structure_path == ["Điều 1", "Khoản 1"]),
        key=lambda c: c.span_start,
    )
    node_khoan_1 = next(n for n in read_result.root.walk() if n.path == ["Khoản 1"])

    assert khoan_1[0].span_start == node_khoan_1.char_start
    assert khoan_1[-1].span_end == node_khoan_1.char_end
    # Ranh giới DÒNG không loại bỏ gì — liền mạch tuyệt đối, giống ranh giới
    # CÂU, khác ranh giới ĐOẠN.
    for a, b in zip(khoan_1, khoan_1[1:]):
        assert a.span_end == b.span_start

    ghep_lai = "".join(
        read_result.full_text[c.span_start : c.span_end] for c in khoan_1
    )
    doan_goc = read_result.full_text[node_khoan_1.char_start : node_khoan_1.char_end]
    assert ghep_lai == doan_goc


def test_line_split_fragments_share_the_same_structure_block_e1():
    """E1 (07 Mục 2.2 dòng 172): mọi mảnh của cùng một khối LÁ — kể cả khi
    chia tới tận mức DÒNG ĐƠN — vẫn phải mang CÙNG `structure_block_*` =
    trọn khối lá gốc, không phải span riêng của từng mảnh."""
    read_result = dung_cau_truc(VAN_BAN_KHOAN_CHUA_BANG, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    khoan_1 = sorted(
        (c for c in chunks if c.structure_path == ["Điều 1", "Khoản 1"]),
        key=lambda c: c.span_start,
    )
    node_khoan_1 = next(n for n in read_result.root.walk() if n.path == ["Khoản 1"])
    assert len(khoan_1) >= 2, "Phép thử tự hỏng: cần ít nhất hai mảnh để so sánh"

    assert {(c.structure_block_start, c.structure_block_end) for c in khoan_1} == {
        (node_khoan_1.char_start, node_khoan_1.char_end)
    }


def test_line_split_fragments_share_the_same_parent_chunk_id():
    read_result = dung_cau_truc(VAN_BAN_KHOAN_CHUA_BANG, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    theo_path: dict[tuple, list] = {}
    for c in chunks:
        theo_path.setdefault(tuple(c.structure_path), []).append(c)

    khoan_1 = theo_path[("Điều 1", "Khoản 1")]
    dieu_1 = theo_path[("Điều 1",)][0]

    for c in khoan_1:
        assert c.structure_path == ["Điều 1", "Khoản 1"]
        assert c.parent_chunk_id == dieu_1.chunk_id


def test_a_single_line_that_itself_overflows_still_raises_the_unsplittable_error():
    read_result = dung_cau_truc(
        VAN_BAN_KHOAN_MOT_DONG_KHONG_CHIA_DUOC, source_format="txt"
    )
    with pytest.raises(KhoiVuotTranKhongTheChia) as exc_info:
        cat_thanh_mau(
            read_result,
            document_id=DOC_ID,
            space_id=SPACE_ID,
            tenant_id=TENANT_ID,
            tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
        )
    thong_diep = str(exc_info.value)
    assert "DÒNG" in thong_diep, (
        "Thông báo lỗi phải nêu rõ mức ranh giới cuối cùng đã thử là DÒNG, "
        "không còn lẫn với thông báo cũ của mức CÂU"
    )
    assert "Khoản 1" in thong_diep


# ---------------------------------------------------------------------------
# Nghiệm thu trên 2 tài liệu THẬT đã nêu đích danh trong work-order. Dữ liệu
# CỤC BỘ, `data/` bị .gitignore (CLAUDE.md không cấm — đây là dữ liệu khách
# hàng dùng để thử, không phải mã nguồn).
#
# `Luật-61-2020-QH14.docx` đúng hình dạng work-order mô tả (bảng phụ lục
# nhiều dòng, không dòng trống, không dấu kết câu) — mức DÒNG ĐƠN giải quyết
# trọn vẹn, OK.
#
# `47_2021_nd-cp_470561.docx` VẪN escalate — nhưng vì một nguyên nhân KHÁC,
# đọc trực tiếp `word/document.xml` xác nhận: MỘT ô bảng (bị merge ngang 10
# cột) chứa nguyên văn cụm "Các công ty con do công ty mẹ nắm giữ 100% vốn
# điều lệ" lặp lại 10 LẦN trong ĐÚNG MỘT `<w:t>` — không dấu xuống dòng, không
# dấu kết câu, không khoảng trắng phân tách — ngay trong XML gốc của file,
# KHÔNG phải lỗi đọc của `python-docx` hay của reader (T0.3). Đây là lỗi CHẤT
# LƯỢNG DỮ LIỆU nguồn (tài liệu khách hàng), nằm NGOÀI phạm vi file của
# work-order CHUNK-bang-bieu (chunking.py chỉ được cắt tại ranh giới AN TOÀN
# có sẵn trong văn bản — 06 Mục 5.2 cấm bịa cách cắt cứng, và ở đây không còn
# ranh giới nào để mà bịa: không đoạn, không câu, không dòng). Hệ thống
# escalate đúng thiết kế (NT2 "loại trừ phải nhìn thấy được") — đã báo PO ở
# báo cáo work-order, không tự sửa.
# ---------------------------------------------------------------------------
CORPUS_ROOT = REPO_ROOT / "data" / "test-corpus-vn-admin"


def _doc_that(duong_dan_tuong_doi: str):
    file_that = CORPUS_ROOT / duong_dan_tuong_doi
    if not file_that.is_file():
        pytest.fail(
            f"Thiếu file trong tập thử: {file_that}. Dữ liệu CỤC BỘ, không "
            "nằm trong git. Xem data/test-corpus-vn-admin/MANIFEST.md."
        )
    return extract_file(file_that).read_result


def test_luat_61_2020_chunks_successfully_no_longer_fails_stage_3():
    read_result = _doc_that("ban-giam-doc-quan-tri/Luật-61-2020-QH14.docx")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    assert chunks, "phải sinh được ít nhất một mẩu — không còn FAIL-GĐ3"
    mau_vuot_tran = [c for c in chunks if c.span_end - c.span_start > TRAN_DO_DAI_MAU_THU]
    assert mau_vuot_tran == [], (
        f"{len(mau_vuot_tran)} mẩu vẫn vượt trần {TRAN_DO_DAI_MAU_THU} ký tự "
        f"sau khi đã có mức chia DÒNG ĐƠN"
    )


def test_47_2021_ndcp_still_escalates_over_the_cap():
    read_result = _doc_that("ban-giam-doc-quan-tri/47_2021_nd-cp_470561.docx")
    with pytest.raises(KhoiVuotTranKhongTheChia) as exc_info:
        cat_thanh_mau(
            read_result,
            document_id=DOC_ID,
            space_id=SPACE_ID,
            tenant_id=TENANT_ID,
            tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
        )
    thong_diep = str(exc_info.value)
    assert "DÒNG" in thong_diep, (
        "phải rơi đúng vào nhánh escalate mức DÒNG ĐƠN (mức cuối cùng), không "
        "phải mức đoạn hay câu — xác nhận đây thật sự là ca 'hết ranh giới an "
        "toàn', không phải một hồi quy ở mức khác"
    )
