"""T2.4 bước 2/2 (g) — `trich_ngay_hieu_luc`: các nhánh resolve + ba bẫy đã
lường trước, kiểm bằng đoạn văn bản tự dựng ngắn (đối chiếu 21 văn bản thật
nằm ở `test_h_effective_date_corpus_accuracy.py`).
"""

from __future__ import annotations

import dataclasses
from datetime import date

from schema.document import DateSource

from ingestion.labeling import GoiYNgayHieuLuc, trich_ngay_hieu_luc

DATELINE = "Hà Nội, ngày 10 tháng 3 năm 2020\n\n"


def test_ke_tu_ngay_ky_resolve_qua_issued_date():
    van_ban = DATELINE + "Nghị định này có hiệu lực thi hành kể từ ngày ký ban hành."
    ket_qua = trich_ngay_hieu_luc(van_ban)
    assert ket_qua.effective_date == date(2020, 3, 10)
    assert ket_qua.effective_date_source == DateSource.EXTRACTED


def test_ngay_cu_the_truc_tiep():
    van_ban = "Luật này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2021, trừ quy định tại khoản 2 Điều này."
    ket_qua = trich_ngay_hieu_luc(van_ban)
    assert ket_qua.effective_date == date(2021, 1, 1)
    assert ket_qua.effective_date_source == DateSource.EXTRACTED


def test_bo_qua_moc_ngoai_le_o_khoan_2():
    """Đúng hình dạng thật của Luật-61-2020-QH14 (Điều 76): Khoản 1 = mốc
    CHÍNH, Khoản 2 = ngoại lệ áp dụng cho MỘT quy định — phải lấy Khoản 1."""
    van_ban = (
        "Điều 76. Điều khoản thi hành\n"
        "1. Luật này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2021, trừ quy định "
        "tại khoản 2 Điều này.\n"
        "2. Quy định tại khoản 3 Điều 75 của Luật này có hiệu lực thi hành từ ngày "
        "01 tháng 9 năm 2020."
    )
    ket_qua = trich_ngay_hieu_luc(van_ban)
    assert ket_qua.effective_date == date(2021, 1, 1)


def test_sau_n_ngay_ke_tu_ngay_ky_co_issued_date():
    van_ban = DATELINE + "Thông tư này có hiệu lực sau 45 ngày, kể từ ngày ký."
    ket_qua = trich_ngay_hieu_luc(van_ban)
    assert ket_qua.effective_date == date(2020, 4, 24)  # 2020-03-10 + 45 ngày
    assert ket_qua.effective_date_source == DateSource.EXTRACTED


def test_sau_n_ngay_ke_tu_ngay_ky_khong_co_issued_date_thi_khong_resolve():
    """Không có dateline nào để trích issued_date → KHÔNG được đoán bằng
    cách khác — 06 Mục 6.4 cấm suy diễn một ngày "trông hợp lý"."""
    van_ban = "Thông tư này có hiệu lực sau 45 ngày, kể từ ngày ký."
    ket_qua = trich_ngay_hieu_luc(van_ban)
    assert ket_qua.effective_date is None
    assert ket_qua.effective_date_source == DateSource.DEFAULT_INGESTION_DATE


def test_ke_tu_ngay_dang_cong_bao_khong_resolve_du_co_dateline():
    """"Kể từ ngày đăng Công báo" KHÔNG BAO GIỜ resolve được — kể cả khi văn
    bản CÓ dateline (ngày ký), vì đó là một sự kiện KHÁC, không phải ngày
    ký. Không được lặng lẽ dùng ngày ký để lấp chỗ trống."""
    van_ban = DATELINE + "Nghị định này có hiệu lực thi hành sau 15 ngày, kể từ ngày đăng Công báo."
    ket_qua = trich_ngay_hieu_luc(van_ban)
    assert ket_qua.effective_date is None
    assert ket_qua.effective_date_source == DateSource.DEFAULT_INGESTION_DATE


def test_khong_co_cum_kich_hoat_nao():
    ket_qua = trich_ngay_hieu_luc("Văn bản này không nói gì về hiệu lực cả.")
    assert ket_qua.effective_date is None
    assert ket_qua.effective_date_source == DateSource.DEFAULT_INGESTION_DATE


def test_bay_cau_muon_moc_khong_bi_nham_la_tuyen_bo_hieu_luc():
    """Bẫy 1 — thứ tự từ NGƯỢC: "kể từ ngày <văn bản> có hiệu lực" chỉ mượn
    mốc cho một nghĩa vụ khác, KHÔNG phải câu tuyên bố hiệu lực (đúng hình
    dạng thật ở 47_2021_nd-cp_470561.docx)."""
    van_ban = (
        "Trong thời hạn 01 năm kể từ ngày Nghị định này có hiệu lực thi hành và "
        "06 tháng trước kỳ phải công nhận lại doanh nghiệp, Bộ Quốc phòng rà soát."
    )
    ket_qua = trich_ngay_hieu_luc(van_ban)
    assert ket_qua.effective_date is None
    assert ket_qua.effective_date_source == DateSource.DEFAULT_INGESTION_DATE


def test_bay_chu_the_khong_phai_chinh_van_ban():
    """Bẫy 2 — chủ thể của "có hiệu lực" là một đối tượng KHÁC (hợp đồng),
    không phải chính văn bản đang đọc (đúng hình dạng thật ở Điều 23,
    Bộ-luật-45-2019-QH14: "Hợp đồng lao động có hiệu lực kể từ ngày...")."""
    van_ban = "Hợp đồng lao động có hiệu lực kể từ ngày hai bên giao kết, trừ trường hợp khác."
    ket_qua = trich_ngay_hieu_luc(van_ban)
    assert ket_qua.effective_date is None
    assert ket_qua.effective_date_source == DateSource.DEFAULT_INGESTION_DATE


def test_bay_ngay_van_ban_bi_thay_the_khong_bi_nham():
    """Bẫy 3 — ngày của văn bản BỊ THAY THẾ nằm ngay sau trong cùng câu,
    không được nhận nhầm thành ngày hiệu lực (đúng hình dạng thật ở Điều 54,
    2021_291+292_06-2021-NĐ-CP.pdf)."""
    van_ban = (
        DATELINE + "Nghị định này có hiệu lực từ ngày ký ban hành và thay thế "
        "Nghị định số 46/2015/NĐ-CP ngày 12 tháng 5 năm 2015 của Chính phủ."
    )
    ket_qua = trich_ngay_hieu_luc(van_ban)
    assert ket_qua.effective_date == date(2020, 3, 10), (
        "Bị nhận nhầm ngày của văn bản bị thay thế (12/5/2015) thay vì ngày ký thật"
    )


def test_scope_khong_co_truong_effective_date_source_sai_ten():
    ten_truong = {f.name for f in dataclasses.fields(GoiYNgayHieuLuc)}
    assert ten_truong == {"effective_date", "effective_date_source"}
