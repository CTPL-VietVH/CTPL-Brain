"""Ca thử cho lớp gắn cờ BẤT THƯỜNG ĐÁNH SỐ Điều.

Dùng **đoạn trích tối thiểu** tái hiện đúng hiện tượng, không dùng file gốc:
tập thử thật nằm ở `data/` (ngoài git), nên ca thử phải tự chứa.

⚠️ Cờ này là **gợi ý cần người phân loại**, không phải phán quyết. Ca thử ở đây
vì vậy khẳng định hai điều — cờ **rơi đúng chỗ số hiệu đứt mạch**, và cây
**không bị đụng vào** — chứ không khẳng định "mốc bị gắn cờ là mốc sai".
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from ingestion.reader.structure import BatThuongDanhSo, Level  # noqa: E402
from ingestion.reader.vn_normalizer import dung_cau_truc  # noqa: E402

# Rút gọn từ 2023/nghi-dinh-35 — nghị định SỬA ĐỔI, BỔ SUNG. Thân bài trích
# nguyên văn điều khoản của nghị định bị sửa, nên đầy dẫn chiếu; khi ngắt dòng
# đẩy cụm "Điều <số>" xuống đầu dòng thì mẫu neo đầu dòng bắt nhầm.
NGHI_DINH_SUA_DOI = """NGHỊ ĐỊNH
Sửa đổi, bổ sung một số điều của các Nghị định thuộc lĩnh vực xây dựng

Điều 1. Sửa đổi, bổ sung một số khoản của Điều 14 Nghị định số 06/2021/NĐ-CP
1. Sửa đổi khoản 3 như sau:
Điều 2. Sửa đổi, bổ sung một số khoản của Điều 10 Nghị định số 15/2021/NĐ-CP
1. Bổ sung điểm d vào sau điểm c khoản 2 như sau:
Điều 3. Sửa đổi, bổ sung một số điều của Nghị định số 85/2020/NĐ-CP
1. Thay thế cụm từ tại khoản 2 Điều 31; Điều 32; Điều 36; khoản 2, khoản 3
Điều 19 Nghị định này bằng cụm từ mới.
2. Bãi bỏ khoản 5, khoản 6 Điều 41; khoản 3 Điều 50 và
Điều 40 Nghị định số 85/2020/NĐ-CP.
Điều 4. Sửa đổi, bổ sung một số điều của Nghị định số 11/2013/NĐ-CP
1. Quy định tại Luật Xây dựng số 50/2014/QH13 đã được sửa đổi tại điểm đ khoản 1
Điều 3 Luật số 62/2020/QH14 được áp dụng.
Điều 5. Điều khoản thi hành
1. Nghị định này có hiệu lực kể từ ngày ký.
"""

# Văn bản "sạch" — đánh số Điều liên tục, không có dẫn chiếu rơi đầu dòng.
VAN_BAN_SACH = """CHƯƠNG I
QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
1. Quy chế này quy định về quản lý tài sản công.
Điều 2. Đối tượng áp dụng
1. Áp dụng cho toàn bộ đơn vị trực thuộc.
Điều 3. Giải thích từ ngữ
1. Trong Quy chế này, các từ ngữ được hiểu như sau:

CHƯƠNG II
TỔ CHỨC THỰC HIỆN

Điều 4. Trách nhiệm của Thủ trưởng đơn vị
1. Thủ trưởng đơn vị chịu trách nhiệm triển khai.
Điều 5. Hiệu lực thi hành
1. Quy chế này có hiệu lực kể từ ngày ký.
"""


def _dieu(text: str):
    kq = dung_cau_truc(text, "txt")
    return kq, sorted(kq.blocks(Level.DIEU), key=lambda n: n.char_start)


def test_van_ban_danh_so_lien_tuc_khong_bi_gan_co_nao():
    """⭐ Không được bắt oan. Đây là vế quan trọng hơn vế bắt đúng.

    Trên tập thử thật, 15/21 văn bản không lỗi đều đạt 0 cờ. Cờ oan làm người
    soát mất niềm tin vào chính cái cờ, nên nó tệ hơn bỏ sót.
    """
    kq, dieu = _dieu(VAN_BAN_SACH)

    assert [d.marker for d in dieu] == ["1", "2", "3", "4", "5"]
    assert kq.bi_gan_co() == [], \
        f"Bắt oan: {[(d.marker, d.heading[:30]) for d in kq.bi_gan_co()]}"
    print("\n[cờ] văn bản đánh số liên tục 1..5 → 0 cờ")


def test_dan_chieu_roi_dau_dong_bi_gan_co():
    """Ba dẫn chiếu (`Điều 19`, `Điều 40`, `Điều 3` lặp) phải mang cờ."""
    kq, dieu = _dieu(NGHI_DINH_SUA_DOI)

    co = {d.marker for d in kq.bi_gan_co()}
    assert {"19", "40"} <= co, f"Thiếu cờ ở dẫn chiếu: đang có {co}"

    noi_tiep = [d.marker for d in dieu if d.bat_thuong is None]
    assert noi_tiep == ["1", "2", "3", "4", "5"], \
        f"Dãy nối tiếp phải là 1..5, đang là {noi_tiep}"
    print(f"[cờ] {len(co)} mốc mang cờ: {sorted(co)}; dãy nối tiếp còn {noi_tiep}")


def test_chi_gan_co_KHONG_dong_vao_cay():
    """⛔ Ràng buộc cứng: cây phải y hệt như khi không có lớp gắn cờ.

    Với loại (b) — nguồn khuyết dải số — và loại (c) — mẫu văn bản lồng — thì
    mốc bị gắn cờ là **mốc THẬT**. Tự xoá là mất hẳn một Điều có thật, im lặng,
    và tệ hơn cái lỗi đang chữa.
    """
    kq, dieu = _dieu(NGHI_DINH_SUA_DOI)

    # 8 mốc: 5 Điều thật (1,2,3,4,5) + 3 dẫn chiếu rơi đầu dòng (19, 40, và
    # "Điều 3 Luật số 62/2020/QH14"). Cả 8 phải còn nguyên trong cây.
    assert len(dieu) == 8, f"Phải giữ đủ 8 mốc Điều trong cây, đang là {len(dieu)}"
    assert len(kq.bi_gan_co()) > 0, "Phép thử tự hỏng: phải có cờ mới kiểm được"
    for n in dieu:
        assert n.char_start < n.char_end
        assert n.text(kq.full_text).strip(), "Khối bị gắn cờ vẫn phải đọc được nguyên văn"
    kq.kiem_vi_tri()
    print(f"[cờ] {len(dieu)} mốc còn nguyên trong cây, "
          f"{len(kq.bi_gan_co())} mang cờ — không mốc nào bị xoá")


def test_co_mang_dung_MOT_gia_tri_va_ten_khong_ngu_y_nguyen_nhan():
    """Tên cờ không được ngụ ý một nguyên nhân duy nhất.

    Bản trước tên là "nghi ngờ nhận thừa" — sai, vì xác minh tay tìm ra **ba**
    nguyên nhân khác hẳn nhau và **hai trong ba không phải lỗi bộ đọc**.
    """
    assert [b.name for b in BatThuongDanhSo] == ["KHONG_NOI_TIEP"]
    mo_ta = BatThuongDanhSo.KHONG_NOI_TIEP.value
    assert "cần người phân loại" in mo_ta
    for tu_cam in ("nhận thừa", "sai", "lỗi"):
        assert tu_cam not in mo_ta, \
            f"Tên/mô tả cờ không được ngụ ý phán quyết: chứa {tu_cam!r}"
    print(f"[cờ] mô tả: {mo_ta!r}")


def test_bien_the_hau_to_khong_bi_gan_co():
    """`Điều 3a` chèn sau `Điều 3` là hợp lệ, không phải bất thường."""
    text = VAN_BAN_SACH.replace(
        "Điều 4. Trách nhiệm của Thủ trưởng đơn vị",
        "Điều 3a. Điều khoản chuyển tiếp\n1. Nội dung chuyển tiếp.\n"
        "Điều 4. Trách nhiệm của Thủ trưởng đơn vị")
    kq, dieu = _dieu(text)

    assert "3a" in [d.marker for d in dieu]
    assert kq.bi_gan_co() == [], \
        f"Biến thể hậu tố bị bắt oan: {[d.marker for d in kq.bi_gan_co()]}"
    print("[cờ] Điều 3 → 3a → 4 : 0 cờ")
