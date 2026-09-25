"""T2.3 (m) — hợp của `span_*` trên mọi mẩu phủ đúng văn bản: **không chồng
nhau, và không bỏ sót chữ nào**.

Đây là bài test bắt được cả hai cách hỏng đối xứng của GĐ3, mà không cách nào
tự báo lỗi lúc chạy:

* **chồng nhau** → cùng một câu được tạo vector nhiều lần, top-k bị chính nó
  chiếm chỗ (lỗi cũ: mỗi ký tự nằm trong span của mọi tổ tiên, 3,48 lần);
* **bỏ sót** → có chữ trong tài liệu không mẩu nào chứa, tức không câu hỏi
  nào tìm tới được. Đo thật trước khi sửa: **11,8% ký tự của kho** chỉ nằm
  trong phần chữ riêng của khối nội bộ, cộng thêm **0,7%** ở khối đầu văn
  bản — tất cả đều ngoài mọi mẩu lá, biến mất im lặng.

Chỗ DUY NHẤT được phép hở là khoảng trắng: `_split_block_to_cap` bỏ chính
dòng trống dùng làm ranh giới khi đóng gói hai nhóm liền kề. Bài test vì vậy
phát biểu chính xác: *mọi ký tự không được phủ đều phải là khoảng trắng*.
"""

from __future__ import annotations

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU, VAN_BAN_LONG_NHAU

# Có KHỐI ĐẦU VĂN BẢN thật: tên cơ quan, số hiệu và phần "Căn cứ…" đứng trước
# Chương I — đúng hình dạng của 35/36 tài liệu trong kho thử.
VAN_BAN_CO_KHOI_DAU = """BỘ NỘI VỤ
Số: 01/2011/TT-BNV

THÔNG TƯ
Hướng dẫn thể thức và kỹ thuật trình bày văn bản hành chính

Căn cứ Nghị định số 48/2008/NĐ-CP ngày 17 tháng 4 năm 2008 của Chính phủ;

CHƯƠNG I
QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
1. Thông tư này hướng dẫn thể thức trình bày văn bản hành chính.
2. Cơ quan, tổ chức phải tuân thủ hướng dẫn tại Thông tư này.

Điều 2. Đối tượng áp dụng
Thông tư này áp dụng đối với các cơ quan nhà nước và doanh nghiệp nhà nước."""


def _cat(van_ban: str):
    read_result = dung_cau_truc(van_ban, source_format="txt")
    return read_result, cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )


def _kiem_phu(van_ban: str) -> None:
    read_result, chunks = _cat(van_ban)
    full_text = read_result.full_text
    do_phu = [0] * len(full_text)
    for chunk in chunks:
        assert chunk.span_start < chunk.span_end, (
            f"mẩu rỗng ở {chunk.structure_path}: [{chunk.span_start}, {chunk.span_end})"
        )
        for i in range(chunk.span_start, chunk.span_end):
            do_phu[i] += 1

    chong_nhau = [i for i, n in enumerate(do_phu) if n > 1]
    assert chong_nhau == [], (
        f"{len(chong_nhau)} ký tự nằm trong nhiều hơn MỘT mẩu — cùng một câu "
        f"chữ bị tạo vector nhiều lần. Ví dụ quanh vị trí {chong_nhau[0]}: "
        f"{full_text[max(0, chong_nhau[0] - 30):chong_nhau[0] + 30]!r}"
    )

    bo_sot = [i for i, n in enumerate(do_phu) if n == 0 and not full_text[i].isspace()]
    assert bo_sot == [], (
        f"{len(bo_sot)} ký tự KHÔNG phải khoảng trắng nằm ngoài mọi mẩu — chữ "
        f"đó không câu hỏi nào tìm tới được. Ví dụ quanh vị trí {bo_sot[0]}: "
        f"{full_text[max(0, bo_sot[0] - 30):bo_sot[0] + 30]!r}"
    )


def test_cay_long_nhau_duoc_phu_kin_khong_chong_khong_ho():
    _kiem_phu(VAN_BAN_LONG_NHAU)


def test_khoi_dau_van_ban_cung_duoc_phu():
    """Khối đầu văn bản (tên cơ quan, số hiệu, phần "Căn cứ…") trước 25/9/2026
    nằm ngoài mọi mẩu — nay phải được phủ như mọi phần khác."""
    _kiem_phu(VAN_BAN_CO_KHOI_DAU)

    read_result, chunks = _cat(VAN_BAN_CO_KHOI_DAU)
    khoi_dau = [c for c in chunks if c.structure_path == []]
    assert len(khoi_dau) == 1, (
        "khối đầu văn bản phải sinh ra mẩu, và `structure_path` của nó là "
        "danh sách RỖNG — nó không nằm ở cấp nào của cây (07 Mục 2.2 v1.11)"
    )
    mau = khoi_dau[0]
    assert mau.span_start == 0
    assert mau.parent_chunk_id is None, (
        "khối đầu đã là đơn vị cấu trúc cao nhất — S2 quy tắc con 2: không có cha"
    )
    # Đơn vị ĐỌC của nó là trọn khối của chính nó.
    assert mau.structure_block_start == 0
    assert mau.structure_block_end == mau.span_end
    assert "Số: 01/2011/TT-BNV" in read_result.full_text[mau.span_start : mau.span_end]
