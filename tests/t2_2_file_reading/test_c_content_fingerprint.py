"""T2.2 / 06 Mục 5.7: vân tay nội dung tính Ở GĐ2, **sau khi đã đọc được chữ
ra** — không băm file thô. T2.1 (đã xong, commit 3dc23e0) chỉ NHẬN vân tay đã
tính sẵn rồi quyết trùng/không-trùng; các ca thử "trùng khít" ở
`tests/t2_1_intake/` giả định vân tay ổn định theo chữ. Ở đây kiểm đúng chỗ
vân tay được SINH ra.
"""

from __future__ import annotations

from .conftest import FIXTURES

from ingestion.extraction import compute_content_fingerprint, extract_file  # noqa: E402


def test_van_tay_on_dinh_doc_lai_cung_file_ra_cung_gia_tri():
    a = extract_file(FIXTURES / "quy_che.txt")
    b = extract_file(FIXTURES / "quy_che.txt")
    assert a.content_fingerprint == b.content_fingerprint


def test_van_tay_khac_nhau_khi_chu_khac_nhau():
    a = extract_file(FIXTURES / "quy_che.txt")
    b = extract_file(FIXTURES / "quy_trinh.txt")
    assert a.content_fingerprint != b.content_fingerprint


def test_van_tay_la_chuoi_hex_khong_rong():
    a = extract_file(FIXTURES / "quy_che.txt")
    assert len(a.content_fingerprint) == 64  # sha256 hex
    int(a.content_fingerprint, 16)  # không raise nghĩa là đúng hệ hex


def test_van_tay_tinh_tren_chu_da_doc_ra_khong_tinh_tren_byte_file_tho(tmp_path):
    """Hai file khác byte thô (khác kiểu xuống dòng CRLF/LF) nhưng cùng một
    nội dung chữ, sau chuẩn hoá (`vn_normalizer.chuan_hoa_van_ban`) phải ra
    CÙNG một vân tay — vì vân tay là vân tay của `extracted_text`, không phải
    của file gốc (06 Mục 5.7). Băm file thô sẽ làm hai bản này bị coi là hai
    tài liệu khác nhau dù người đọc thấy y hệt nhau."""
    goc = (FIXTURES / "quy_che.txt").read_text(encoding="utf-8")

    file_lf = tmp_path / "lf.txt"
    file_lf.write_bytes(goc.replace("\r\n", "\n").encode("utf-8"))

    file_crlf = tmp_path / "crlf.txt"
    file_crlf.write_bytes(goc.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))

    assert file_lf.read_bytes() != file_crlf.read_bytes()

    a = extract_file(file_lf)
    b = extract_file(file_crlf)
    assert a.content_fingerprint == b.content_fingerprint


def test_compute_content_fingerprint_la_ham_thuan_tuy_tren_van_ban():
    assert compute_content_fingerprint("abc") == compute_content_fingerprint("abc")
    assert compute_content_fingerprint("abc") != compute_content_fingerprint("abd")
