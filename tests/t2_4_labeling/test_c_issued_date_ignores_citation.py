"""T2.4 (c) — Ca thử LÊN TIẾNG chống false-positive: một câu DẪN CHIẾU văn
bản khác (vd "Căn cứ Quyết định số 115/QĐ-TCT ngày 12 tháng 3 năm 2025")
KHÔNG được nhận nhầm thành ngày ký của CHÍNH văn bản đang đọc.

Phân biệt bằng cấu trúc dòng: dateline thật đứng RIÊNG một dòng (đầu dòng
hoặc ngay sau dấu phẩy); câu dẫn chiếu thì cụm "ngày ..." nằm GIỮA câu, ngay
sau số hiệu văn bản, không có dấu phẩy phía trước.
"""

from __future__ import annotations

from schema.document import DateSource

from ingestion.labeling import trich_ngay_ky

from .conftest import VAN_BAN_CHI_CO_DAN_CHIEU


def test_tu_thu_dan_chieu_khong_co_phay_truoc_ngay():
    """Phép thử tự hỏng nếu fixture không đúng hình dạng bẫy đã lường trước."""
    dong_dan_chieu = "Căn cứ Quyết định số 115/QĐ-TCT ngày 12 tháng 3 năm 2025."
    assert dong_dan_chieu in VAN_BAN_CHI_CO_DAN_CHIEU
    vi_tri_ngay = dong_dan_chieu.index("ngày")
    ky_tu_truoc = dong_dan_chieu[vi_tri_ngay - 1]
    assert ky_tu_truoc != ",", "Phép thử tự hỏng: câu dẫn chiếu phải KHÔNG có dấu phẩy trước 'ngày'"
    assert not dong_dan_chieu.startswith("ngày") and not dong_dan_chieu.startswith("Ngày")


def test_cau_dan_chieu_khong_bi_nhan_nham_thanh_ngay_ky():
    ket_qua = trich_ngay_ky(VAN_BAN_CHI_CO_DAN_CHIEU)
    assert ket_qua.issued_date is None, (
        "Bị nhận nhầm ngày dẫn chiếu (12/3/2025) thành ngày ký của chính văn bản"
    )
    assert ket_qua.issued_date_source == DateSource.DEFAULT_INGESTION_DATE
