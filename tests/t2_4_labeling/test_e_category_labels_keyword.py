"""T2.4 (e) — `goi_y_nhan` nhận diện THỂ LOẠI hành chính qua từ khoá ở đầu
văn bản (giả định tạm, xem docstring `labeling.py` và Escalations báo cáo
T2.4). Không nhận diện được từ khoá nào → danh sách RỖNG, không suy diễn.
"""

from __future__ import annotations

from ingestion.labeling import goi_y_nhan

from .conftest import VAN_BAN_CHI_CO_DAN_CHIEU, VAN_BAN_CO_DATELINE, VAN_BAN_KHONG_CO_NGAY_NAO


def test_nhan_dien_duoc_the_loai_quyet_dinh():
    nhan = goi_y_nhan(VAN_BAN_CO_DATELINE)
    assert "QUYẾT ĐỊNH" in nhan


def test_nhan_dien_duoc_the_loai_quy_trinh():
    nhan = goi_y_nhan(VAN_BAN_CHI_CO_DAN_CHIEU)
    assert "QUY TRÌNH" in nhan


def test_khong_nhan_dien_duoc_thi_ve_danh_sach_rong():
    assert goi_y_nhan(VAN_BAN_KHONG_CO_NGAY_NAO) == []


def test_khong_phan_biet_hoa_thuong_van_nhan_dien_duoc():
    van_ban = "Hà nội, ngày 1 tháng 1 năm 2024\n\nQuyết định\nVề việc..."
    assert "QUYẾT ĐỊNH" in goi_y_nhan(van_ban)
