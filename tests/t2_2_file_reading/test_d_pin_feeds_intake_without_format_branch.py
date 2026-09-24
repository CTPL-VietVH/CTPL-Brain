"""T2.2 là ĐIỂM CẮM (`docs/08` T2.2, `docs/06` Mục 5.2 GĐ2): *"mọi bước sau
chỉ nhận văn bản, cấu trúc, vị trí; không bước nào được rẽ nhánh theo định
dạng gốc."*

Ca thử ở đây chứng minh điểm cắm đứng được tại đúng chỗ nối với T2.1 (GĐ1,
`ingestion.intake`, đã xong ở commit 3dc23e0): `ExtractionResult` của bốn
định dạng khác nhau đều nạp thẳng vào `IntakeRequest` qua ĐÚNG MỘT đường —
không có `if source_format == ...` nào ở lời gọi.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest

from .conftest import FIXTURES

from ingestion.extraction import extract_file  # noqa: E402
from ingestion.intake import InMemoryFingerprintIndex, IntakeRequest, receive_and_validate  # noqa: E402
from ingestion.space_registry import InMemorySpaceRegistry  # noqa: E402
from schema.document import DateSource  # noqa: E402


def _so_dang_ky_co_space(space_id: str) -> InMemorySpaceRegistry:
    """Sổ đăng ký Space đã có sẵn Space của ca thử (T2.11, docs/10 §4.0).

    Ca thử này nói về điểm cắm định dạng, không nói về cổng chặn Space —
    cổng đó được kiểm ở `tests/t2_11_space_registry/`."""
    registry = InMemorySpaceRegistry()
    registry.register(space_id)
    return registry


def _nap_mot_file(ten_file: str, *, space_id: str, fingerprint_index, space_registry):
    """Đường nạp DUY NHẤT dùng cho mọi định dạng — không rẽ nhánh theo
    `source_format` ở bất kỳ đâu trong hàm này."""
    ket_qua_gd2 = extract_file(FIXTURES / ten_file)
    request = IntakeRequest(
        document_id=str(uuid.uuid4()),
        space_id=space_id,
        tenant_id="tenant-1",
        title="Quy chế quản lý tài sản công",
        doc_number="15/2024/QĐ-TGĐ",
        issued_date=date(2024, 1, 10),
        issued_date_source=DateSource.EXTRACTED,
        effective_date=date(2024, 2, 1),
        effective_date_source=DateSource.CONFIRMED,
        ingested_at=datetime(2024, 1, 12, 9, 0),
        source_format=ket_qua_gd2.source_format,
        content_fingerprint=ket_qua_gd2.content_fingerprint,
        extracted_text=ket_qua_gd2.extracted_text,
    )
    return receive_and_validate(
        request, fingerprint_index=fingerprint_index, space_registry=space_registry
    )


@pytest.mark.parametrize("ten_file", [
    "quy_che.txt", "quy_che.md", "quy_che_khong_style.docx", "quy_che.pdf",
])
def test_bon_dinh_dang_cung_nap_duoc_qua_mot_duong_khong_re_nhanh(ten_file):
    fingerprint_index = InMemoryFingerprintIndex()
    space_registry = _so_dang_ky_co_space("space-1")
    ket_qua = _nap_mot_file(
        ten_file,
        space_id="space-1",
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    )

    assert ket_qua.created is True
    assert ket_qua.document.extracted_text != ""
    assert ket_qua.document.content_fingerprint != ""


def test_hai_dinh_dang_khac_nhau_cua_cung_mot_noi_dung_khong_bi_coi_la_hai_tai_lieu_trung(tmp_path):
    """Không phải tiêu chí "Xong khi" của T2.2, nhưng là hệ quả trực tiếp
    đáng kiểm của điểm cắm: hai lượt nạp CÙNG một file (txt) vào CÙNG một
    Space phải bị GĐ1 báo trùng — đúng ca "Xong khi" của T2.1, giờ đi qua
    trọn đường GĐ2 → GĐ1 thay vì `content_fingerprint` giả lập tay."""
    fingerprint_index = InMemoryFingerprintIndex()
    space_registry = _so_dang_ky_co_space("space-1")

    lan_1 = _nap_mot_file(
        "quy_che.txt",
        space_id="space-1",
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    )
    lan_2 = _nap_mot_file(
        "quy_che.txt",
        space_id="space-1",
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    )

    assert lan_1.created is True
    assert lan_2.created is False
    assert lan_2.duplicate_of == lan_1.document.document_id
