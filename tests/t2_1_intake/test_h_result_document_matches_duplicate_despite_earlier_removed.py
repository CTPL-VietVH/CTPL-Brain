"""T2.1 (h) — CRITICAL audit #1: `IntakeResult.document` phải khớp
`duplicate_of`, kể cả khi một bản `removed_as_wrong` đăng ký TRƯỚC bản
đang hoạt động trong cùng một Space.

Root cause đã tìm: bộ lọc loại `removed_as_wrong` chỉ áp trong `decide_intake`
lúc tính `duplicate_of`; lần tra lại thứ hai trong `receive_and_validate` (để
lấy `Document` trả về) dùng `next(... if d.space_id == space_id)` — không lọc
`removed_as_wrong` — nên khi bản gỡ-vì-sai đứng TRƯỚC bản hoạt động trong danh
sách trùng vân tay, `next()` trả nhầm bản đã gỡ.

`test_g` cũ chỉ so `third.duplicate_of == valid.document_id`, không so
`third.document.document_id` — nên không bắt được lỗi này. Test này so
thẳng `result.document.document_id`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from ingestion.intake import receive_and_validate
from schema.document import DateSource, Document

from .conftest import make_request


def _removed_as_wrong_document(*, document_id: str, space_id: str, content_fingerprint: str) -> Document:
    return Document(
        document_id=document_id,
        space_id=space_id,
        tenant_id="tenant-1",
        title="Bản đã bị gỡ vì sai",
        doc_number="99/2024/QĐ-TGĐ",
        issued_date=date(2024, 1, 1),
        issued_date_source=DateSource.EXTRACTED,
        effective_date=date(2024, 1, 1),
        effective_date_source=DateSource.EXTRACTED,
        ingested_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        source_format="pdf",
        content_fingerprint=content_fingerprint,
        extracted_text="Nội dung sai.",
        version_chain_id="chain-removed",
        version_ordinal=1,
        removed_as_wrong=True,
        removed_reason="Nạp nhầm bản nháp chưa ký",
    )


def test_document_field_points_to_the_active_match_not_the_earlier_removed_one(fingerprint_index, space_registry):
    removed = _removed_as_wrong_document(
        document_id="doc-removed", space_id="space-a", content_fingerprint="fp-x"
    )
    fingerprint_index.register(removed)
    valid = receive_and_validate(
        make_request(document_id="doc-valid", space_id="space-a", content_fingerprint="fp-x"),
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    ).document

    third = receive_and_validate(
        make_request(document_id="doc-third", space_id="space-a", content_fingerprint="fp-x"),
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    )

    assert third.created is False
    assert third.duplicate_of == valid.document_id
    assert third.document.document_id == valid.document_id
    assert third.document.document_id != removed.document_id
