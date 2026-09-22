"""T2.3 bước 2/2 (i) — một Node NỘI BỘ (có con) mà span của nó vượt trần
KHÔNG được chia, dù dài hơn `tran_do_dai_mau` gấp nhiều lần.

Lý do: `char_start`/`char_end` của một Node cha luôn BAO TRÙM toàn bộ nội
dung con cháu (bất biến containment, `structure.py` `ReadResult.kiem_vi_tri`
dòng ~216) — span dài của Node nội bộ là CỘNG DỒN từ con cháu, không phải
bằng chứng nội dung RIÊNG của chính nó quá dài. Chia nó sẽ vi phạm điều cấm
#1 của GĐ3 bước 1 (không được GỘP/tách một khối cấu trúc không đúng ranh
giới của nó) và làm hỏng bất biến "mỗi khối cấu trúc = một mẩu" cho khối cha.
"""

from __future__ import annotations

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU

# Một Chương chứa nhiều Điều NGẮN (mỗi Điều dưới trần), nhưng CỘNG DỒN của cả
# Chương (Node nội bộ) vượt trần rõ ràng.
_MOT_DIEU_NGAN = (
    "Nội dung ngắn gọn của điều này quy định một nghĩa vụ cụ thể, không dài. "
)


def _sinh_van_ban_chuong_nhieu_dieu(so_dieu: int) -> str:
    dieu_list = [
        f"Điều {i}. Quy định số {i}\n1. {_MOT_DIEU_NGAN}" for i in range(1, so_dieu + 1)
    ]
    return "CHƯƠNG I\nQUY ĐỊNH CHUNG\n\n" + "\n\n".join(dieu_list)


VAN_BAN_CHUONG_VUOT_TRAN = _sinh_van_ban_chuong_nhieu_dieu(so_dieu=80)


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
            "Phép thử tự hỏng: từng Điều (khối LÁ) phải dưới trần, để phép "
            "thử chỉ kiểm hành vi của khối NỘI BỘ (Chương), không lẫn hành vi "
            "chia khối lá"
        )


def test_chuong_noi_bo_vuot_tran_van_la_dung_mot_mau():
    read_result = dung_cau_truc(VAN_BAN_CHUONG_VUOT_TRAN, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    chuong_chunks = [c for c in chunks if c.structure_path == ["Chương I"]]

    assert len(chuong_chunks) == 1, (
        "Node nội bộ (Chương) vượt trần vẫn phải là ĐÚNG MỘT mẩu — bước 2 "
        "chỉ áp dụng cho Chunk LÁ"
    )
    chuong_chunk = chuong_chunks[0]
    node_chuong = next(n for n in read_result.root.walk() if n.path == ["Chương I"])
    assert chuong_chunk.span_start == node_chuong.char_start
    assert chuong_chunk.span_end == node_chuong.char_end
    assert chuong_chunk.span_end - chuong_chunk.span_start > TRAN_DO_DAI_MAU_THU
