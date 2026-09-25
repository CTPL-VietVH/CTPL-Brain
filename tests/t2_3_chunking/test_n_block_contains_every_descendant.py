"""T2.3 (n) — bất biến E3 (PO chốt 25/9/2026): `structure_block_*` của một
mẩu CHA bao trọn `span_*` của chính nó **và** bao trọn `span_*` lẫn
`structure_block_*` của MỌI mẩu con cháu — không chỉ của chính nó.

Vì sao vế "mọi con cháu" là vế quan trọng: đơn vị ĐỌC của S2 được dựng bằng
cách theo `parent_chunk_id` lên mẩu cha rồi cắt `extracted_text` theo
`structure_block_*` của mẩu cha. Nếu khoảng đó không bao trọn con cháu thì
mẩu tìm được nằm NGOÀI đoạn văn bản đem cho người đọc — câu trả lời dẫn nguồn
tới một chỗ không chứa cái vừa trích, và **không lỗi nào báo**. Cùng họ với
điều cấm #4 (đếm vị trí sai thì chỉ dẫn nguồn sai chỗ, im lặng).

Cây thử ba cấp Chương › Điều › Khoản, chữ tiếng Việt CÓ DẤU — CLAUDE.md Mục 7
yêu cầu ca thử vị trí phải là chuỗi tiếng Việt có dấu, vì đó là chỗ cách đếm
byte và cách đếm ký tự Unicode tách nhau.
"""

from __future__ import annotations

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU

VAN_BAN_BA_CAP_CO_DAU = """CHƯƠNG II
QUYỀN VÀ NGHĨA VỤ CỦA NGƯỜI LAO ĐỘNG

Điều 7. Quyền của người lao động
Người lao động có các quyền sau đây:
1. Được trả lương đầy đủ, đúng hạn theo hợp đồng lao động đã giao kết.
2. Được bảo đảm an toàn, vệ sinh lao động tại nơi làm việc.

Điều 8. Nghĩa vụ của người lao động
Người lao động có các nghĩa vụ sau đây:
1. Chấp hành kỷ luật lao động và nội quy lao động của đơn vị.
2. Bảo vệ tài sản và bí mật kinh doanh của người sử dụng lao động."""


def test_tron_khoi_cua_cha_bao_tron_moi_mau_con_chau():
    read_result = dung_cau_truc(VAN_BAN_BA_CAP_CO_DAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )

    # Phép thử tự kiểm: phải dựng được đủ ba cấp, nếu không bài test rỗng nghĩa.
    cac_cap = {len(c.structure_path) for c in chunks}
    assert {1, 2, 3} <= cac_cap, (
        f"phép thử tự hỏng: cần cây đủ ba cấp, mới thấy {sorted(cac_cap)}"
    )
    assert "ườ" in read_result.full_text, "phép thử tự hỏng: phải có chữ có dấu"

    theo_id = {c.chunk_id: c for c in chunks}

    # 1. Trọn khối bao span của CHÍNH mẩu đó.
    for chunk in chunks:
        assert chunk.structure_block_start <= chunk.span_start < chunk.span_end, chunk
        assert chunk.span_end <= chunk.structure_block_end, chunk

    # 2. Trọn khối của CHA bao trọn span VÀ trọn khối của mọi mẩu con cháu.
    #    Đi lên theo `parent_chunk_id` để phủ mọi cặp tổ tiên–hậu duệ, không
    #    chỉ cặp cha–con một cấp.
    so_cap_da_kiem = 0
    for chunk in chunks:
        to_tien_id = chunk.parent_chunk_id
        while to_tien_id is not None:
            to_tien = theo_id[to_tien_id]
            assert to_tien.structure_block_start <= chunk.span_start, (
                f"mẩu {chunk.structure_path} bắt đầu ở {chunk.span_start}, "
                f"trước cả trọn khối của tổ tiên {to_tien.structure_path} "
                f"({to_tien.structure_block_start})"
            )
            assert chunk.span_end <= to_tien.structure_block_end, (
                f"mẩu {chunk.structure_path} kết thúc ở {chunk.span_end}, "
                f"sau cả trọn khối của tổ tiên {to_tien.structure_path} "
                f"({to_tien.structure_block_end}) — đơn vị ĐỌC dựng từ tổ tiên "
                "sẽ KHÔNG chứa mẩu vừa tìm được"
            )
            assert to_tien.structure_block_start <= chunk.structure_block_start
            assert chunk.structure_block_end <= to_tien.structure_block_end
            so_cap_da_kiem += 1
            to_tien_id = to_tien.parent_chunk_id

    assert so_cap_da_kiem > 0, "phép thử tự hỏng: không có cặp tổ tiên nào được kiểm"


def test_doc_don_vi_doc_cua_mot_khoan_lay_tron_dieu():
    """Hệ quả đọc được bằng mắt của bất biến trên: đi theo `parent_chunk_id`
    của một Khoản rồi cắt theo `structure_block_*` của mẩu cha phải ra TRỌN
    Điều — đúng câu chữ của S2: *"tìm bằng Khoản, đọc trọn Điều"*.
    """
    read_result = dung_cau_truc(VAN_BAN_BA_CAP_CO_DAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    theo_id = {c.chunk_id: c for c in chunks}

    khoan = next(
        c for c in chunks if c.structure_path[-1:] == ["Khoản 1"] and "Điều 7" in c.structure_path
    )
    cha = theo_id[khoan.parent_chunk_id]
    assert cha.structure_path == ["Chương II", "Điều 7"]

    don_vi_doc = read_result.full_text[cha.structure_block_start : cha.structure_block_end]
    assert "Điều 7. Quyền của người lao động" in don_vi_doc
    assert "Được trả lương đầy đủ" in don_vi_doc
    assert "Được bảo đảm an toàn" in don_vi_doc
    assert "Điều 8." not in don_vi_doc, "đơn vị đọc không được tràn sang Điều kế tiếp"

    # Và cắt theo `span_*` của mẩu cha thì KHÔNG ra trọn Điều — đó chính là lý
    # do 07 Mục 2.2 v1.11 nói rõ phải dùng `structure_block_*` của mẩu cha.
    chi_chu_rieng = read_result.full_text[cha.span_start : cha.span_end]
    assert "Được trả lương đầy đủ" not in chi_chu_rieng
