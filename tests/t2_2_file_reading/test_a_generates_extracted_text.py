"""T2.2 — GĐ2 sinh `extracted_text`, nguồn chân lý duy nhất của chữ nghĩa.

`docs/08` T2.2: *"Bốn định dạng... Sinh `extracted_text` — nguồn chân lý duy
nhất của chữ nghĩa."* Bốn định dạng đã được T0.3 chứng minh cùng ra một hình
dạng cây (`tests/t0_3_reader/test_reader.py`); ở đây chỉ kiểm phần T2.2 thêm
vào: đóng gói thành `ExtractionResult` với `extracted_text` + `source_format`
đúng, và `extracted_text` chính là `read_result.full_text` — không phải một
bản sao độc lập có thể lệch đi.
"""

from __future__ import annotations

import pytest

from .conftest import FIXTURES

from ingestion.extraction import ExtractionResult, extract_file  # noqa: E402
from ingestion.reader.structure import Level  # noqa: E402


@pytest.mark.parametrize("ten_file,dinh_dang", [
    ("quy_che.txt", "txt"),
    ("quy_che.md", "md"),
    ("quy_che_khong_style.docx", "docx"),
    ("quy_che_co_style.docx", "docx"),
    ("quy_che.pdf", "pdf"),
])
def test_sinh_extracted_text_va_source_format_dung(ten_file, dinh_dang):
    ket_qua = extract_file(FIXTURES / ten_file)

    assert isinstance(ket_qua, ExtractionResult)
    assert ket_qua.source_format == dinh_dang
    assert ket_qua.extracted_text.strip() != ""
    # Điều 1 phải xuất hiện trong chữ đọc ra — bốn tài liệu quy chế đều có
    assert "Điều 1" in ket_qua.extracted_text


def test_extracted_text_la_full_text_cua_read_result_khong_phai_ban_sao_roi():
    """`extracted_text` phải LÀ `read_result.full_text`, không phải một bản
    sao tính riêng — hai bản chữ độc lập thì chúng sẽ lệch nhau (CLAUDE.md
    Mục 3 #3, áp cho quan hệ mẩu/cạnh mẩu, cùng lý do áp ở đây)."""
    ket_qua = extract_file(FIXTURES / "quy_che.txt")
    assert ket_qua.extracted_text == ket_qua.read_result.full_text


def test_read_result_giu_nguyen_cay_cau_truc_cho_T2_3():
    """GĐ2 không được vứt bỏ cây cấu trúc — T2.3 (GĐ3 cắt mẩu) cần nó và
    không được mở lại file gốc lần hai."""
    ket_qua = extract_file(FIXTURES / "quy_che.txt")
    so_dieu = len(ket_qua.read_result.blocks(Level.DIEU))
    assert so_dieu >= 4
