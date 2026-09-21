"""T2.4 (b) — không trích được ngày ký → `issued_date=None`,
`issued_date_source=DEFAULT_INGESTION_DATE`. TUYỆT ĐỐI không đoán một ngày
"trông hợp lý" thay thế (06 Mục 6.4 cấm rõ).
"""

from __future__ import annotations

from schema.document import DateSource

from ingestion.labeling import trich_ngay_ky

from .conftest import VAN_BAN_KHONG_CO_NGAY_NAO


def test_khong_co_ngay_nao_thi_ve_default_va_none():
    ket_qua = trich_ngay_ky(VAN_BAN_KHONG_CO_NGAY_NAO)
    assert ket_qua.issued_date is None
    assert ket_qua.issued_date_source == DateSource.DEFAULT_INGESTION_DATE


def test_chuoi_rong_thi_ve_default_va_none():
    ket_qua = trich_ngay_ky("")
    assert ket_qua.issued_date is None
    assert ket_qua.issued_date_source == DateSource.DEFAULT_INGESTION_DATE
