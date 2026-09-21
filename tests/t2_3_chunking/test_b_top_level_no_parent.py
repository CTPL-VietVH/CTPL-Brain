"""T2.3 (b) — S2 quy tắc con #2: một khối cấu trúc đã là đơn vị cấu trúc CAO
NHẤT của tài liệu (con trực tiếp của gốc, không có Chương/Phần/Mục bao
ngoài) thì `parent_chunk_id` phải để `None` — không có cha để lên.

07 Mục 2.2, S2: *"Mẩu đã là đơn vị cấu trúc cao nhất của tài liệu thì đơn vị
đọc là chính nó ... Ví dụ một Điều ngắn không bị cắt nhỏ thì không có cha để
lên."*
"""

from __future__ import annotations

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, VAN_BAN_DIEU_TOP_LEVEL


def test_dieu_top_level_khong_co_cha():
    read_result = dung_cau_truc(VAN_BAN_DIEU_TOP_LEVEL, source_format="txt")
    chunks = cat_thanh_mau(
        read_result, document_id=DOC_ID, space_id=SPACE_ID, tenant_id=TENANT_ID
    )

    assert len(chunks) == 2
    theo_path = {tuple(c.structure_path): c for c in chunks}

    dieu_1 = theo_path[("Điều 1",)]
    dieu_2 = theo_path[("Điều 2",)]

    assert dieu_1.parent_chunk_id is None
    assert dieu_2.parent_chunk_id is None
