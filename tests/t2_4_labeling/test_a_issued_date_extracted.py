"""T2.4 (a) — dateline chuẩn hành chính VN ở đầu văn bản → `issued_date`
trích đúng, nguồn `EXTRACTED` (06 Mục 5.2 GĐ5, 06 Mục 6.4, 07 Mục 2.1).
"""

from __future__ import annotations

from datetime import date

from schema.document import DateSource

from ingestion.labeling import trich_ngay_ky

from .conftest import VAN_BAN_CO_DATELINE


def test_tu_thu_van_ban_co_dateline_that():
    assert "ngày 15 tháng 9 năm 2026" in VAN_BAN_CO_DATELINE, (
        "Phép thử tự hỏng: fixture phải chứa đúng dateline mong đợi"
    )


def test_trich_dung_ngay_ky_nguon_extracted():
    ket_qua = trich_ngay_ky(VAN_BAN_CO_DATELINE)
    assert ket_qua.issued_date == date(2026, 9, 15)
    assert ket_qua.issued_date_source == DateSource.EXTRACTED


def test_ngay_don_vi_khong_co_dem_0_van_trich_dung():
    """"ngày 5 tháng 9" (không đệm số 0) cũng phải trích đúng như "ngày 05"."""
    van_ban = "Hà Nội, ngày 5 tháng 9 năm 2024\n\nQUYẾT ĐỊNH\n..."
    ket_qua = trich_ngay_ky(van_ban)
    assert ket_qua.issued_date == date(2024, 9, 5)
    assert ket_qua.issued_date_source == DateSource.EXTRACTED


def test_ngay_dung_dau_dong_khong_co_dia_danh_van_trich_dung():
    """Một số văn bản (thường ở khối ký tên) chỉ ghi "Ngày ..." đứng đầu
    dòng, không kèm địa danh phía trước — vẫn phải trích được."""
    van_ban = "Ngày 20 tháng 6 năm 2023\n\nTM. GIÁM ĐỐC"
    ket_qua = trich_ngay_ky(van_ban)
    assert ket_qua.issued_date == date(2023, 6, 20)
    assert ket_qua.issued_date_source == DateSource.EXTRACTED
