"""T2.3 (i) — một Node NỘI BỘ (có con) sinh ra ĐÚNG MỘT mẩu mang **phần chữ
RIÊNG** của nó, không mang chữ của con cháu (07 Mục 2.2 v1.11, PO chốt
25/9/2026).

⚠️ **Bài test này từng khẳng định điều NGƯỢC LẠI** — rằng mẩu của Node nội bộ
giữ nguyên span bao trùm cả cây con, với lập luận: span dài của Node nội bộ là
cộng dồn từ con cháu nên không phải bằng chứng nội dung riêng của nó quá dài.
Lập luận đó đúng về cấu trúc và sai về hậu quả. Đo thật 24/9/2026 trên 36 tài
liệu: **18/36 không nạp được**, 47 mẩu vượt trần ngữ cảnh 8192 token của
BGE-M3 (nặng nhất 233.712 token), và **47/48 mẩu vượt trần là mẩu của Node
nội bộ**. Giữ span bao trùm nghĩa là `tran_do_dai_mau` không có tác dụng gì
lên chúng — đúng cái lỗ hổng work-order CHUNK-mau-noi-bo đóng lại.

Cái KHÔNG đổi: trọn khối vẫn còn nguyên, ở `structure_block_start` /
`structure_block_end`, nên đơn vị ĐỌC của S2 không mất gì.
"""

from __future__ import annotations

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU

# Một Chương chứa nhiều Điều, mỗi Điều DƯỚI trần ký tự, nhưng CỘNG DỒN của cả
# Chương (Node nội bộ) vượt trần — và vượt luôn trần NGỮ CẢNH 8192 token của
# BGE-M3, vì đó mới là kích thước tái hiện được lỗi thật (xem
# `test_k_no_chunk_over_the_context_ceiling.py`: 80 Điều mỗi Điều một câu chỉ
# ra 2.058 token, chưa chạm trần, nên không chứng minh được gì).
_MOT_CAU = (
    "Nội dung của điều này quy định một nghĩa vụ cụ thể của cơ quan, tổ chức "
    "và cá nhân có liên quan trong phạm vi được giao. "
)
_SO_CAU_MOI_DIEU = 8


def _sinh_van_ban_chuong_nhieu_dieu(so_dieu: int) -> str:
    than_dieu = _MOT_CAU * _SO_CAU_MOI_DIEU
    dieu_list = [
        f"Điều {i}. Quy định số {i}\n1. {than_dieu}" for i in range(1, so_dieu + 1)
    ]
    return "CHƯƠNG I\nQUY ĐỊNH CHUNG\n\n" + "\n\n".join(dieu_list)


VAN_BAN_CHUONG_VUOT_TRAN = _sinh_van_ban_chuong_nhieu_dieu(so_dieu=80)


def _cat(van_ban: str):
    return cat_thanh_mau(
        dung_cau_truc(van_ban, source_format="txt"),
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )


def test_tu_thu_chuong_vuot_tran_nhung_tung_dieu_khong_vuot():
    read_result = dung_cau_truc(VAN_BAN_CHUONG_VUOT_TRAN, source_format="txt")
    chuong = next(n for n in read_result.root.walk() if n.path == ["Chương I"])
    assert chuong.char_end - chuong.char_start > TRAN_DO_DAI_MAU_THU, (
        "Phép thử tự hỏng: cả Chương phải vượt trần để có gì mà kiểm"
    )

    cac_dieu = [n for n in read_result.root.walk() if n.level.nhan == "Điều"]
    assert cac_dieu, "Phép thử tự hỏng: phải dựng được ít nhất một Điều"
    for dieu in cac_dieu:
        assert dieu.char_end - dieu.char_start <= TRAN_DO_DAI_MAU_THU, (
            "Phép thử tự hỏng: từng Điều phải dưới trần, để phép thử chỉ kiểm "
            "hành vi của khối NỘI BỘ (Chương)"
        )


def test_chuong_noi_bo_chi_mang_chu_rieng_cua_no():
    read_result = dung_cau_truc(VAN_BAN_CHUONG_VUOT_TRAN, source_format="txt")
    chunks = _cat(VAN_BAN_CHUONG_VUOT_TRAN)
    chuong_chunks = [c for c in chunks if c.structure_path == ["Chương I"]]

    assert len(chuong_chunks) == 1, (
        "Chữ RIÊNG của Chương (dòng tiêu đề) thừa sức dưới trần, nên nó vẫn "
        "phải là ĐÚNG MỘT mẩu"
    )
    chuong_chunk = chuong_chunks[0]
    node_chuong = next(n for n in read_result.root.walk() if n.path == ["Chương I"])
    dieu_dau_tien = node_chuong.children[0]

    # span = phần chữ RIÊNG: từ đầu khối tới ngay trước con đầu tiên.
    assert chuong_chunk.span_start == node_chuong.char_start
    assert chuong_chunk.span_end == dieu_dau_tien.char_start
    assert chuong_chunk.span_end - chuong_chunk.span_start <= TRAN_DO_DAI_MAU_THU

    # ...và trọn khối KHÔNG mất đi, nó chuyển sang cặp vị trí thứ hai.
    assert chuong_chunk.structure_block_start == node_chuong.char_start
    assert chuong_chunk.structure_block_end == node_chuong.char_end
    assert (
        chuong_chunk.structure_block_end - chuong_chunk.structure_block_start
        > TRAN_DO_DAI_MAU_THU
    ), "Phép thử tự hỏng: trọn khối phải vẫn vượt trần thì mới có gì để kiểm"


def test_mau_cua_chuong_khong_chua_chu_cua_bat_ky_dieu_nao():
    """Ca thử LÊN TIẾNG cho đúng cái lỗi cũ: nếu ai đó trả span về bao trùm
    cây con, chữ của Điều 1 sẽ nằm trong mẩu của Chương và test này đỏ."""
    read_result = dung_cau_truc(VAN_BAN_CHUONG_VUOT_TRAN, source_format="txt")
    chunks = _cat(VAN_BAN_CHUONG_VUOT_TRAN)
    chuong_chunk = next(c for c in chunks if c.structure_path == ["Chương I"])
    van_ban_chuong = read_result.full_text[
        chuong_chunk.span_start : chuong_chunk.span_end
    ]

    assert "Điều 1." not in van_ban_chuong
    assert _MOT_CAU.strip() not in van_ban_chuong
    assert "CHƯƠNG I" in van_ban_chuong, (
        "mẩu của Chương vẫn phải mang chính dòng tiêu đề của nó — đó là phần "
        "chữ riêng, và là 11,8% văn bản của kho sẽ mất nếu bỏ mẩu này đi"
    )
