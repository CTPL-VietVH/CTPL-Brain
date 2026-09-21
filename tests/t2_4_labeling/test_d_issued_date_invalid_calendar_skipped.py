"""T2.4 (d) — một chuỗi khớp khuôn số nhưng KHÔNG phải ngày thật trên lịch
(vd "31 tháng 4" — tháng 4 chỉ có 30 ngày) phải bị BỎ QUA, không tự vòng
xuống ngày cuối tháng hay ném lỗi mập mờ; và phải tiếp tục dò trận khớp kế
tiếp nếu có.
"""

from __future__ import annotations

from datetime import date

from schema.document import DateSource

from ingestion.labeling import trich_ngay_ky


def test_ngay_khong_hop_le_bi_bo_qua_roi_ve_default():
    van_ban = "Hà Nội, ngày 31 tháng 4 năm 2026\n\nQUYẾT ĐỊNH\n..."
    ket_qua = trich_ngay_ky(van_ban)
    assert ket_qua.issued_date is None
    assert ket_qua.issued_date_source == DateSource.DEFAULT_INGESTION_DATE


def test_ngay_khong_hop_le_roi_ngay_hop_le_thi_lay_ngay_hop_le():
    """Trận khớp đầu tiên (31/4) không phải ngày thật nên bị bỏ qua; hàm
    phải dò TIẾP tới trận khớp kế tiếp thoả điều kiện (đứng đầu dòng hoặc
    sau dấu phẩy) thay vì dừng lại và kết luận "không trích được"."""
    van_ban = (
        "Hà Nội, ngày 31 tháng 4 năm 2026\n\n"
        "QUYẾT ĐỊNH\n\n"
        "Điều 1. Hiệu lực\n"
        "Quyết định này có hiệu lực kể từ ngày ký.\n\n"
        "Hà Nội, ngày 5 tháng 9 năm 2026\n"
        "TM. GIÁM ĐỐC"
    )
    ket_qua = trich_ngay_ky(van_ban)
    assert ket_qua.issued_date == date(2026, 9, 5)
    assert ket_qua.issued_date_source == DateSource.EXTRACTED
