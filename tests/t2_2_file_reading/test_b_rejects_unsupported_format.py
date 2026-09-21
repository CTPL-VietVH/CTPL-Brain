"""T2.2: *"từ chối phần còn lại kèm thông báo rõ"* — không đoán bừa, không
đọc đại. `extract_file` không lặp lại logic từ chối (đã có ở T0.3
`ingestion.reader.readers.doc_file`), chỉ phải KHÔNG NUỐT MẤT nó.
"""

from __future__ import annotations

import pytest

from .conftest import FIXTURES

from ingestion.extraction import DinhDangKhongNhan, KhongDocDuocLopChu, extract_file  # noqa: E402


def test_tu_choi_dinh_dang_ngoai_danh_sach_v1_kem_thong_bao_ro(tmp_path):
    file_khong_ho_tro = tmp_path / "bang_tinh.xlsx"
    file_khong_ho_tro.write_bytes(b"khong quan trong noi dung")

    with pytest.raises(DinhDangKhongNhan) as loi:
        extract_file(file_khong_ho_tro)

    thong_bao = str(loi.value)
    assert "xlsx" in thong_bao
    assert "bang_tinh.xlsx" in thong_bao


def test_tu_choi_pdf_khong_co_lop_chu(tmp_path):
    """PDF không rút được chữ (rỗng/ảnh quét) phải bị từ chối ồn ào, không đi
    tiếp với `extracted_text` rỗng — cùng ca T0.3 đã dùng
    (`tests/t0_3_reader/test_reader.py`), kiểm qua tầng bọc của T2.2."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf_rong = tmp_path / "anh_quet.pdf"
    c = canvas.Canvas(str(pdf_rong), pagesize=A4)
    c.showPage()  # một trang trắng, không có lớp chữ
    c.save()

    with pytest.raises(KhongDocDuocLopChu):
        extract_file(pdf_rong)
