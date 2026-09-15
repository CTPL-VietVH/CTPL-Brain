"""T0.3 — Bộ đọc file và bộ chuẩn hoá phân cấp.

⚠️ **Đây KHÔNG phải nghiệm thu T0.3.** `docs/08` T0.3 đòi một tập thử **có tên
gọi** gồm ≥20 văn bản hành chính VN thật (≥5 soạn tay không Heading style, ≥5
PDF), đạt ≥90% dựng đúng hoàn toàn phân cấp. Tập đó **chưa được gom**. Xem
`README.md` cạnh file này.

Những ca ở đây chứng minh ba điều, và chỉ ba điều đó:
  1. Bốn bộ đọc trả ra **cùng một hình dạng cây** — điểm cắm GĐ2 đứng được.
  2. Vị trí đầu/cuối đếm theo **ký tự Unicode**, đúng trên tiếng Việt có dấu.
  3. Không dựng được phân cấp thì **NÓI RA**, tuyệt đối không cắt theo độ dài.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from ingestion.reader.readers import (DinhDangKhongNhan, doc_file)  # noqa: E402
from ingestion.reader.structure import Level, Outcome  # noqa: E402
from ingestion.reader.vn_normalizer import chuan_hoa_van_ban, dung_cau_truc  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------- hình dạng cây

@pytest.mark.parametrize("ten_file", [
    "quy_che.txt", "quy_che.md",
    "quy_che_khong_style.docx", "quy_che_co_style.docx", "quy_che.pdf",
])
def test_bon_dinh_dang_ra_cung_mot_hinh_dang_cay(ten_file):
    """⭐ Điểm cắm GĐ2: mọi bộ đọc trả ra cùng một hình dạng.

    Nếu ca này đỏ ở đúng một định dạng thì nghĩa là bước sau sẽ phải rẽ nhánh
    theo định dạng gốc — thứ mà 07 Mục 6 (S4) cấm.
    """
    kq = doc_file(FIXTURES / ten_file)

    assert kq.outcome is Outcome.DIEU_KHOAN, \
        f"{ten_file}: {kq.outcome.value} — {kq.notes}"
    assert len(kq.blocks(Level.CHUONG)) == 2, \
        f"{ten_file}: phải 2 Chương, thấy {len(kq.blocks(Level.CHUONG))}"
    assert len(kq.blocks(Level.DIEU)) == 4, \
        f"{ten_file}: phải 4 Điều, thấy {len(kq.blocks(Level.DIEU))}"
    assert len(kq.blocks(Level.DIEM)) == 3, \
        f"{ten_file}: phải 3 Điểm (a,b,c), thấy {len(kq.blocks(Level.DIEM))}"
    kq.kiem_vi_tri()


def test_docx_khong_co_heading_style_van_dung_duoc_phan_cap():
    """⭐ Ca khó mà docs/08 B2 điểm 1 cảnh báo là PHỔ BIẾN ngoài đời.

    Mọi đoạn trong file này đều là style `Normal`, chỉ in đậm và đánh số bằng
    tay. Nếu bộ đọc dựa vào Heading style thì nó ra một khối chữ phẳng.
    """
    khong_style = doc_file(FIXTURES / "quy_che_khong_style.docx")
    co_style = doc_file(FIXTURES / "quy_che_co_style.docx")

    assert khong_style.outcome is Outcome.DIEU_KHOAN
    assert len(khong_style.blocks(Level.DIEU)) == len(co_style.blocks(Level.DIEU)) == 4
    assert len(khong_style.blocks(Level.CHUONG)) == len(co_style.blocks(Level.CHUONG)) == 2
    print("\n[T0.3] .docx KHÔNG Heading style dựng phân cấp y hệt bản CÓ style "
          "→ regex là đường chính, đúng như docs/08 B2 dự đoán")


def test_cay_long_dung_thu_bac():
    """Chương › Điều › Khoản › Điểm phải lồng đúng, không phẳng ra."""
    kq = doc_file(FIXTURES / "quy_che.txt")
    chuong = kq.blocks(Level.CHUONG)

    assert [c.marker for c in chuong] == ["I", "II"]
    dieu_trong_chuong_1 = [n for n in chuong[0].walk() if n.level is Level.DIEU]
    assert [d.marker for d in dieu_trong_chuong_1] == ["1", "2"]

    dieu_1 = dieu_trong_chuong_1[0]
    khoan = [n for n in dieu_1.walk() if n.level is Level.KHOAN]
    assert [k.marker for k in khoan] == ["1", "2"]

    diem = [n for n in khoan[1].walk() if n.level is Level.DIEM]
    assert [d.marker for d in diem] == ["a", "b", "c"]
    assert dieu_1.path == ["Điều 1"]
    print("[T0.3] lồng đúng: Chương I › Điều 1 › Khoản 2 › Điểm a/b/c")


# ------------------------------------------------- vị trí ký tự Unicode

def test_vi_tri_dem_theo_ky_tu_unicode_tren_tieng_viet_co_dau():
    """⭐ Điều cấm số 4: đếm byte thì đoạn cắt sai mà không lỗi nào báo."""
    kq = doc_file(FIXTURES / "quy_che.txt")

    for node in kq.root.walk():
        if node.level is Level.DOCUMENT:
            continue
        doan = node.text(kq.full_text)
        assert doan, f"{node.level.nhan} {node.marker}: cắt ra rỗng"
        if node.marker:
            assert node.marker in doan[:60], \
                f"{node.level.nhan} {node.marker}: vị trí trỏ sai chỗ — {doan[:60]!r}"

    n_ky_tu = len(kq.full_text)
    n_byte = len(kq.full_text.encode("utf-8"))
    assert n_byte > n_ky_tu, "Phép thử tự hỏng: văn bản phải có dấu"
    print(f"\n[T0.3] {n_ky_tu:,} ký tự / {n_byte:,} byte — lệch {n_byte - n_ky_tu:,}; "
          f"mọi vị trí cắt ra đúng khối")


def test_chuan_hoa_nfc_truoc_khi_dem_vi_tri():
    """Cùng một chữ, hai cách mã hoá dấu, phải ra cùng một số ký tự.

    Không chuẩn hoá thì `char_start` tính lúc nạp và `SUBSTRING` chạy lúc trả
    lời đếm ra hai con số khác nhau — im lặng, y hệt cái bẫy byte.
    """
    dung_san = "Điều"                      # NFC
    to_hop = "Điều".replace("ề", "ề")  # dựng lại từ tổ hợp
    to_hop_that = "Điều"        # e + ^ + huyền

    assert len(dung_san) == 4
    assert len(to_hop_that) == 6, "Phép thử tự hỏng: chuỗi tổ hợp phải dài hơn"
    assert len(chuan_hoa_van_ban(to_hop_that)) == 4, "NFC phải gộp về 4 ký tự"
    assert chuan_hoa_van_ban(to_hop_that) == dung_san
    print(f"[T0.3] tổ hợp {len(to_hop_that)} ký tự → NFC {len(chuan_hoa_van_ban(to_hop_that))} ký tự, "
          f"khớp bản dựng sẵn")


# --------------------------------------- KHÔNG dựng được thì phải NÓI RA

def test_khong_dung_duoc_thi_noi_ra_chu_khong_cat_theo_do_dai():
    """⛔ Đường bị cấm là im lặng hạ chuẩn (docs/06 Mục 5.2, docs/08 T0.3)."""
    kq = doc_file(FIXTURES / "khong_cau_truc.txt")

    assert kq.outcome is Outcome.KHONG_DUNG_DUOC
    assert not kq.dung_duoc
    # Không được tự sinh ra khối con nào — tức là không có cắt theo độ dài
    assert kq.root.children == [], \
        "Không dựng được phân cấp mà vẫn sinh ra khối con → đã cắt theo độ dài"
    assert any("KHÔNG rơi về cắt theo độ dài" in n for n in kq.notes)
    print(f"\n[T0.3] văn bản không cấu trúc → '{kq.outcome.value}'")
    print(f"[T0.3] không sinh khối con nào ⇒ không có cắt theo độ dài ngầm")


def test_khong_co_gia_tri_nao_nghia_la_cat_theo_do_dai():
    """Chặn bằng cấu trúc: enum kết cục không có chỗ cho 'cắt theo độ dài'."""
    gia_tri = {o.name for o in Outcome}
    assert gia_tri == {"DIEU_KHOAN", "TIEU_DE", "TIEU_DE_PHONG_DOAN", "KHONG_DUNG_DUOC"}
    for o in Outcome:
        assert "độ dài" not in o.value or "KHÔNG" in o.value
    # Đúng MỘT giá trị được đánh dấu là phỏng đoán — chỗ phán đoán phải nhìn
    # thấy được ở tầng kiểu, không chìm trong ghi chú (NT2 ý 3)
    assert [o.name for o in Outcome if o.la_phong_doan] == ["TIEU_DE_PHONG_DOAN"]
    print("[T0.3] enum Outcome không có giá trị nào nghĩa là 'cắt theo độ dài'; "
          "chỗ phỏng đoán được tách riêng thành một giá trị")


def test_tai_lieu_khong_dieu_khoan_dung_theo_chuoi_tieu_de():
    """07 Mục 2.2: tài liệu không có điều khoản thì là chuỗi tiêu đề lồng nhau."""
    kq = doc_file(FIXTURES / "quy_trinh.txt")

    assert kq.outcome is Outcome.TIEU_DE
    tieu_de = kq.blocks(Level.HEADING)
    assert len(tieu_de) >= 6
    markers = [t.marker for t in tieu_de]
    assert "1" in markers and "1.1" in markers and "2.3" in markers
    kq.kiem_vi_tri()
    print(f"\n[T0.3] quy trình không điều khoản → {kq.outcome.value}; {kq.notes}")


# ------------------------------------------------------- từ chối định dạng

def test_tu_choi_dinh_dang_ngoai_danh_sach_v1(tmp_path):
    """docs/08 T2.2: bốn định dạng, từ chối phần còn lại KÈM THÔNG BÁO RÕ."""
    f = tmp_path / "bang_tinh.xlsx"
    f.write_bytes(b"PK\x03\x04 khong phai tai lieu van ban")

    with pytest.raises(DinhDangKhongNhan) as e:
        doc_file(f)
    assert ".xlsx" in str(e.value) and "từ chối" in str(e.value)
    print(f"\n[T0.3] từ chối .xlsx: {e.value}")


def test_source_format_duoc_ghi_lai_nhung_khong_de_re_nhanh():
    """S4: GHI định dạng gốc, nhưng cấm mọi bước sau rẽ nhánh theo nó."""
    ket_qua = {ten: doc_file(FIXTURES / ten) for ten in
               ("quy_che.txt", "quy_che.md", "quy_che_khong_style.docx", "quy_che.pdf")}

    assert {k.source_format for k in ket_qua.values()} == {"txt", "md", "docx", "pdf"}
    # Cùng một hình dạng bất kể source_format — đó là điều làm việc rẽ nhánh
    # thành không cần thiết ngay từ đầu
    hinh_dang = {ten: (len(k.blocks(Level.CHUONG)), len(k.blocks(Level.DIEU)))
                 for ten, k in ket_qua.items()}
    assert len(set(hinh_dang.values())) == 1, f"Hình dạng lệch nhau: {hinh_dang}"
    print(f"[T0.3] 4 định dạng → cùng hình dạng {next(iter(hinh_dang.values()))} "
          f"(Chương, Điều); source_format chỉ để ghi lại")


def test_ghep_o_chu_pdf_theo_khe_ho_khong_chen_dau_cach_bua():
    """⭐ Ca hồi quy: PDF pháp luật VN tách ký tự CÓ DẤU thành ô riêng.

    Đo thật trên Thông tư 01/2011/TT-BNV: ô `'CÔNG BÁO/S'` kết thúc ở x=266.72,
    ô `'ố'` bắt đầu ở x=266.73 — liền nhau. Bản đầu nối mù bằng dấu cách, cho
    ra `"CÔNG BÁO/S ố"`, `"B Ộ  N Ộ I V Ụ"`, `"Ngh ị đị nh"`. Khi ấy chuỗi
    "Điều" **không bao giờ khớp**, và 4/5 PDF trong tập thử tụt xuống
    `TIEU_DE` với 0 Điều — hỏng hoàn toàn mà vẫn "dựng ra được một cây".

    Đây đúng kiểu hỏng im lặng mà cả thiết kế dựng lên để chặn, nên nó xứng
    đáng có một ca thử riêng thay vì chỉ là một lần sửa.
    """
    import importlib
    mod = importlib.import_module("ingestion.reader.readers")

    # Dựng lại đúng hình dạng ô đã đo được
    o_lien_nhau = [(188.35, 266.72, "CÔNG BÁO/S"), (266.73, 273.23, "ố")]
    o_cach_xa = [(64.06, 70.56, "8"), (188.35, 266.72, "CÔNG BÁO")]

    # Hàm ghép nằm trong _doc_pdf; kiểm qua ngưỡng đã công bố
    assert mod._NGUONG_CACH_CHU_PT > 0.01, "Ngưỡng phải lớn hơn khe hở giữa ô liền nhau"
    assert mod._NGUONG_CACH_CHU_PT < 118.0, "Ngưỡng phải nhỏ hơn khe hở giữa hai cột thật"

    khe_lien = o_lien_nhau[1][0] - o_lien_nhau[0][1]
    khe_xa = o_cach_xa[1][0] - o_cach_xa[0][1]
    assert khe_lien <= mod._NGUONG_CACH_CHU_PT, \
        f"Ô liền nhau (khe {khe_lien:.2f}pt) phải được nối THẲNG, không chèn dấu cách"
    assert khe_xa > mod._NGUONG_CACH_CHU_PT, \
        f"Ô cách xa (khe {khe_xa:.2f}pt) phải được chèn dấu cách"
    print(f"\n[T0.3] khe hở {khe_lien:.2f}pt → nối thẳng; {khe_xa:.2f}pt → chèn dấu cách "
          f"(ngưỡng {mod._NGUONG_CACH_CHU_PT}pt)")


def test_pdf_khong_co_lop_chu_bi_tu_choi_on_ao(tmp_path):
    """v1 từ chối ảnh quét. Từ chối ỒN ÀO, không đọc ra chữ rỗng rồi đi tiếp."""
    from ingestion.reader.readers import KhongDocDuocLopChu
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    f = tmp_path / "rong.pdf"
    c = canvas.Canvas(str(f), pagesize=A4)
    c.showPage()          # một trang trắng, không có lớp chữ
    c.save()

    with pytest.raises(KhongDocDuocLopChu) as e:
        doc_file(f)
    assert "ảnh quét" in str(e.value)
    print(f"\n[T0.3] PDF không lớp chữ → từ chối ồn ào, không đi tiếp với văn bản rỗng")
