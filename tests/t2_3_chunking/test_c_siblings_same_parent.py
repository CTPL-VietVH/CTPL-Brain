"""T2.3 (c) — S2 quy tắc con #1: hai mẩu con của CÙNG một khối cha (hai
Khoản cùng một Điều) phải được gán CÙNG một `parent_chunk_id`, và giá trị
đó phải chính là `chunk_id` thật của mẩu Điều (không phải một chuỗi bất kỳ
trùng ngẫu nhiên).

⚠️ Test này KHÔNG kiểm tra dedup ở lượt đọc (đó là T3.5, docs/09 dòng 213,
ngoài phạm vi T2.3) — chỉ kiểm T2.3 đã gán đúng con trỏ để T3.5 khử trùng
được.
"""

from __future__ import annotations

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU, VAN_BAN_LONG_NHAU


def test_hai_khoan_cung_dieu_co_cung_parent_chunk_id():
    read_result = dung_cau_truc(VAN_BAN_LONG_NHAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    theo_path = {tuple(c.structure_path): c for c in chunks}

    dieu_1 = theo_path[("Chương I", "Điều 1")]
    khoan_1 = theo_path[("Chương I", "Điều 1", "Khoản 1")]
    khoan_2 = theo_path[("Chương I", "Điều 1", "Khoản 2")]

    assert khoan_1.parent_chunk_id == khoan_2.parent_chunk_id
    assert khoan_1.parent_chunk_id == dieu_1.chunk_id, (
        "parent_chunk_id phải trỏ đúng tới chunk_id THẬT của mẩu Điều 1, "
        "không chỉ tình cờ bằng nhau giữa hai Khoản"
    )


def test_hai_dieu_cung_chuong_co_cung_parent_chunk_id():
    """Kiểm lại quy tắc ở một cấp khác: Điều 1 và Điều 2 cùng con Chương I."""
    read_result = dung_cau_truc(VAN_BAN_LONG_NHAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    theo_path = {tuple(c.structure_path): c for c in chunks}

    chuong = theo_path[("Chương I",)]
    dieu_1 = theo_path[("Chương I", "Điều 1")]
    dieu_2 = theo_path[("Chương I", "Điều 2")]

    assert dieu_1.parent_chunk_id == dieu_2.parent_chunk_id == chuong.chunk_id
