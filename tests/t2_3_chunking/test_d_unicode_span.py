"""T2.3 (d) — `span_start`/`span_end` khớp CHÍNH XÁC `char_start`/`char_end`
gốc của Node, thử trên văn bản có dấu tiếng Việt (CLAUDE.md Mục 3 #4, 07
Mục 2.2: đếm theo KÝ TỰ UNICODE, không phải byte).

`full_text[span_start:span_end]` phải cắt ra đúng đoạn kỳ vọng — so với một
chuỗi VIẾT TAY sẵn, không suy ngược lại từ chính Node để tránh test tự
chứng minh vòng tròn.
"""

from __future__ import annotations

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, VAN_BAN_LONG_NHAU

# Đoạn kỳ vọng của khối "Điều 2" — chọn khối CUỐI văn bản để span_end trùng
# đúng len(full_text), tránh mọi mập mờ về dòng trống ở ranh giới kế tiếp.
DOAN_KY_VONG_DIEU_2 = (
    "Điều 2. Giải thích từ ngữ\n"
    "Các từ ngữ trong quy chế này được hiểu theo quy định của pháp luật hiện hành."
)


def test_tu_thu_van_ban_co_dau_that():
    n_ky_tu = len(VAN_BAN_LONG_NHAU)
    n_byte = len(VAN_BAN_LONG_NHAU.encode("utf-8"))
    assert n_byte != n_ky_tu, "Phép thử tự hỏng: văn bản thử phải có dấu tiếng Việt"


def test_span_khop_dung_char_start_char_end_cua_node():
    read_result = dung_cau_truc(VAN_BAN_LONG_NHAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result, document_id=DOC_ID, space_id=SPACE_ID, tenant_id=TENANT_ID
    )
    theo_path = {tuple(c.structure_path): c for c in chunks}
    dieu_2_node = next(
        n for n in read_result.root.walk() if n.path == ["Điều 2"]
    )
    dieu_2_chunk = theo_path[("Chương I", "Điều 2")]

    assert dieu_2_chunk.span_start == dieu_2_node.char_start
    assert dieu_2_chunk.span_end == dieu_2_node.char_end


def test_cat_full_text_theo_span_ra_dung_doan_ky_vong():
    read_result = dung_cau_truc(VAN_BAN_LONG_NHAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result, document_id=DOC_ID, space_id=SPACE_ID, tenant_id=TENANT_ID
    )
    theo_path = {tuple(c.structure_path): c for c in chunks}
    dieu_2_chunk = theo_path[("Chương I", "Điều 2")]

    doan_cat_ra = read_result.full_text[dieu_2_chunk.span_start : dieu_2_chunk.span_end]
    assert doan_cat_ra == DOAN_KY_VONG_DIEU_2
    assert dieu_2_chunk.span_end == len(read_result.full_text)


def test_nham_dung_chi_so_byte_thi_cat_sai():
    """Ca thử LÊN TIẾNG: áp cùng cặp span lên chuỗi BYTE thay vì chuỗi ký tự
    phải cho ra kết quả SAI — chứng minh hai cách đếm không hoán đổi được
    (cùng tinh thần `tests/t1_4_negative_space/test_c_unicode_span_boundaries.py`).
    """
    read_result = dung_cau_truc(VAN_BAN_LONG_NHAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result, document_id=DOC_ID, space_id=SPACE_ID, tenant_id=TENANT_ID
    )
    theo_path = {tuple(c.structure_path): c for c in chunks}
    dieu_2_chunk = theo_path[("Chương I", "Điều 2")]

    van_ban_byte = read_result.full_text.encode("utf-8")
    doan_cat_theo_byte = van_ban_byte[dieu_2_chunk.span_start : dieu_2_chunk.span_end]
    doan_giai_ma_lai = doan_cat_theo_byte.decode("utf-8", errors="replace")

    assert doan_giai_ma_lai != DOAN_KY_VONG_DIEU_2, (
        "Văn bản thử không đủ lệch byte/ký tự trước đoạn mục tiêu để phép "
        "thử này có ý nghĩa — cần thêm dấu tiếng Việt trước Điều 2"
    )
