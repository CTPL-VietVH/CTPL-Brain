"""T2.3 bước 2/2 (g) — một Chunk LÁ vượt trần được chia TIẾP tại ranh giới
ĐOẠN (dòng trống), khi mỗi đoạn riêng đã đủ ngắn để không cần chia câu.

06 Mục 5.2 GĐ3 bước 2, Điểm mở #4 (06 Mục 10, PO chốt 5000 ký tự Unicode
21/9/2026). Ba bất biến kiểm ở đây:

  * Các mẩu con cùng gốc giữ NGUYÊN `structure_path` và CÙNG một
    `parent_chunk_id` — chính là `chunk_id` của khối cha một cấp lên (Điều),
    KHÔNG đôn thêm tầng nào.
  * Mỗi mẩu con <= trần.
  * Các mẩu con không chồng lấn, đúng thứ tự, mẩu ĐẦU bắt đầu đúng
    `node.char_start` và mẩu CUỐI kết thúc đúng `node.char_end` — khoảng hở
    giữa hai mẩu liền kề (nếu có) chỉ là dòng trống phân cách đoạn, không
    phải nội dung bị mất.
"""

from __future__ import annotations

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU

# Hai đoạn, mỗi đoạn dưới trần riêng lẻ, NHƯNG cộng lại vượt trần — buộc phải
# tách thành hai mẩu con tại đúng ranh giới dòng trống giữa chúng, không cần
# chia tới cấp câu.
_DOAN_A = (
    "Nội dung phần một của khoản này trình bày chi tiết nghĩa vụ báo cáo định kỳ. " * 40
)
_DOAN_B = (
    "Nội dung phần hai của khoản này trình bày chi tiết trách nhiệm phối hợp liên ngành. " * 40
)

VAN_BAN_KHOAN_HAI_DOAN = f"""Điều 1. Phạm vi điều chỉnh
1. {_DOAN_A}

{_DOAN_B}

Điều 2. Hiệu lực thi hành
Quy chế có hiệu lực kể từ ngày ký."""


def test_tu_thu_khoan_vuot_tran_that():
    assert len(_DOAN_A) < TRAN_DO_DAI_MAU_THU
    assert len(_DOAN_B) < TRAN_DO_DAI_MAU_THU
    assert len(_DOAN_A) + len(_DOAN_B) > TRAN_DO_DAI_MAU_THU, (
        "Phép thử tự hỏng: hai đoạn cộng lại phải vượt trần để có gì mà chia"
    )


def test_khoan_vuot_tran_duoc_chia_thanh_hai_mau_theo_doan():
    read_result = dung_cau_truc(VAN_BAN_KHOAN_HAI_DOAN, source_format="txt")
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
    assert len(khoan_1) == 2, "Hai đoạn không gộp được vào một mẩu thì phải ra đúng hai mẩu"

    for c in khoan_1:
        assert c.span_end - c.span_start <= TRAN_DO_DAI_MAU_THU


def test_mau_con_cung_structure_path_va_cung_parent_chunk_id_dung():
    read_result = dung_cau_truc(VAN_BAN_KHOAN_HAI_DOAN, source_format="txt")
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

    khoan_1 = sorted(theo_path[("Điều 1", "Khoản 1")], key=lambda c: c.span_start)
    dieu_1 = theo_path[("Điều 1",)][0]

    assert len(theo_path[("Điều 1",)]) == 1, "Điều 1 (khối nội bộ) không được chia"
    for c in khoan_1:
        assert c.structure_path == ["Điều 1", "Khoản 1"]
        assert c.parent_chunk_id == dieu_1.chunk_id, (
            "parent_chunk_id của mẩu con phải là chunk_id THẬT của khối cha một "
            "cấp lên (Điều 1), không đôn thêm tầng ảo nào"
        )
    assert khoan_1[0].parent_chunk_id == khoan_1[1].parent_chunk_id


def test_mau_dau_va_cuoi_khop_dung_bien_cua_node_khoan():
    read_result = dung_cau_truc(VAN_BAN_KHOAN_HAI_DOAN, source_format="txt")
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

    # Không chồng lấn, đúng thứ tự; khoảng hở (nếu có) giữa hai mẩu liền kề
    # CHỈ được là khoảng trắng (dòng trống phân cách đoạn) — không mất nội
    # dung thật nào.
    for a, b in zip(khoan_1, khoan_1[1:]):
        assert a.span_end <= b.span_start
        khoang_ho = read_result.full_text[a.span_end : b.span_start]
        assert khoang_ho.strip() == "", (
            f"Khoảng hở giữa hai mẩu con chứa nội dung thật, không chỉ khoảng "
            f"trắng: {khoang_ho!r}"
        )


def test_sibling_fragments_of_one_block_share_the_same_structure_block():
    """E1 (PO chốt 25/9/2026, 07 Mục 2.2 dòng 172): khi một khối LÁ bị chia
    thành nhiều mảnh vì vượt `tran_do_dai_mau`, MỌI mảnh phải mang CÙNG MỘT
    `structure_block_start`/`structure_block_end` — trọn khối LÁ GỐC, không
    phải span riêng của từng mảnh. Nếu không, đơn vị ĐỌC dựng từ một mảnh
    con của Khoản 1 sẽ không trùng đơn vị đọc dựng từ mảnh con còn lại của
    chính Khoản 1 đó — hai câu trả lời cho cùng một Khoản trích ra hai đoạn
    khác nhau, không lỗi nào báo."""
    read_result = dung_cau_truc(VAN_BAN_KHOAN_HAI_DOAN, source_format="txt")
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
    assert len(khoan_1) == 2, "Phép thử tự hỏng: cần ít nhất hai mảnh để so sánh"

    assert {(c.structure_block_start, c.structure_block_end) for c in khoan_1} == {
        (node_khoan_1.char_start, node_khoan_1.char_end)
    }
