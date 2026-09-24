"""T2.1 (j) — audit #4, PO chốt Phương án A (21/9): khai `declared_previous_version`
trỏ vào một tài liệu đã `removed_as_wrong` thì coi như KHÔNG khai báo — rơi về
nhánh "không khai báo" (chuỗi phiên bản mới), KHÔNG raise lỗi.

Lý do chốt: `removed_as_wrong` đã là nguyên tắc "coi như không tồn tại" xuyên
suốt module này từ E3/E4 (xem test_g) — không có lý do để nhánh khai-bản-mới
xử lý khác nhánh chống-trùng.
"""

from __future__ import annotations

from datetime import date, datetime

from ingestion.intake import receive_and_validate
from schema.document import DateSource, Document, VersionDeclaredBy

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
        ingested_at=datetime(2024, 1, 1),
        source_format="pdf",
        content_fingerprint=content_fingerprint,
        extracted_text="Nội dung sai.",
        version_chain_id="chain-removed",
        version_ordinal=3,
        removed_as_wrong=True,
        removed_reason="Nạp nhầm bản nháp chưa ký",
    )


def test_declared_previous_version_removed_as_wrong_does_not_raise_and_starts_fresh_chain(
    fingerprint_index,
    space_registry,
):
    removed = _removed_as_wrong_document(
        document_id="doc-removed", space_id="space-a", content_fingerprint="fp-old"
    )
    fingerprint_index.register(removed)

    result = receive_and_validate(
        make_request(
            document_id="doc-new",
            space_id="space-a",
            content_fingerprint="fp-new",
            declared_previous_version=removed,
        ),
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    )

    assert result.created is True
    assert result.document.version_chain_id != removed.version_chain_id
    assert result.document.version_ordinal == 1
    assert result.document.version_declared_by is None
