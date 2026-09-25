"""T2.3 (l) — mẩu của MỌI khối có con chỉ mang chữ RIÊNG của khối đó, không
mang một ký tự nào của con cháu (07 Mục 2.2 v1.11).

Khác `test_i`: ở đây kiểm trên cây BA CẤP và kiểm TẤT CẢ khối nội bộ, không
chỉ Chương — vì lỗi cũ có mặt ở mọi cấp (đo thật: mẩu vượt trần rơi vào cả
Phần, Chương, Mục và Điều).

Đây cũng là lưới chặn cho hướng "sửa cho gọn" nguy hiểm nhất: trả `span_*`
của khối nội bộ về bao trùm cây con thì mỗi ký tự lại được đem tạo vector một
lần ở mỗi tầng — đo thật 24/9/2026: **3,48 lần trên toàn kho**, và cùng một
câu chữ trúng ở bốn tầng chiếm mất chỗ của nhau trong top-k.
"""

from __future__ import annotations

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU, VAN_BAN_LONG_NHAU


def test_khong_mau_noi_bo_nao_chua_chu_cua_con_chau():
    read_result = dung_cau_truc(VAN_BAN_LONG_NHAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )

    noi_bo = [n for n in read_result.root.walk() if n.children and n.path]
    assert noi_bo, "phép thử tự hỏng: văn bản thử phải có khối nội bộ"

    for node in noi_bo:
        duong_dan_cuoi = node.path[0]
        mau = [c for c in chunks if c.structure_path and c.structure_path[-1] == duong_dan_cuoi]
        assert mau, f"khối nội bộ {duong_dan_cuoi!r} phải có mẩu của riêng nó"

        for chunk in mau:
            for con in node.children:
                assert chunk.span_end <= con.char_start, (
                    f"mẩu của {duong_dan_cuoi!r} lấn sang chữ của con "
                    f"{con.path[0]!r}: span kết thúc ở {chunk.span_end} trong khi "
                    f"con bắt đầu ở {con.char_start}"
                )
            # ...nhưng trọn khối thì vẫn phải bao con — đó là cặp vị trí thứ hai.
            assert chunk.structure_block_end >= node.children[-1].char_end


def test_khoi_khong_co_con_van_mang_tron_khoi():
    """Đối chứng: với khối KHÔNG có con thì hai cặp vị trí bằng nhau — nếu ai
    đó cắt nhầm phần riêng cho cả khối lá, bài test này đỏ."""
    read_result = dung_cau_truc(VAN_BAN_LONG_NHAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    la = [n for n in read_result.root.walk() if not n.children and n.path]
    assert la, "phép thử tự hỏng: phải có khối lá"

    for node in la:
        mau = [
            c
            for c in chunks
            if c.structure_path
            and c.structure_path[-1] == node.path[0]
            and c.structure_block_start == node.char_start
        ]
        assert len(mau) == 1, (
            f"khối lá {node.path[0]!r} đủ ngắn thì phải là ĐÚNG MỘT mẩu "
            "(06 Mục 5.2 GĐ3, điều cấm 3 của bước 1)"
        )
        assert mau[0].span_start == node.char_start
        assert mau[0].span_end == node.char_end
        assert mau[0].structure_block_start == mau[0].span_start
        assert mau[0].structure_block_end == mau[0].span_end
