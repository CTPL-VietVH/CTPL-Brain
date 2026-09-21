"""T2.1 (g) — Tài liệu đã `removed_as_wrong` không được tính là "trùng khít"
khi chống trùng-cùng-Space.

Sửa bug E3 (báo cáo T2.1): bộ lọc trùng trước đây trỏ upload mới về một tài
liệu đã bị Manager gỡ vì sai — tài liệu đó đã bị Retrieval lọc cứng khỏi mọi
câu trả lời (NT4), nên trỏ về nó là trỏ vào hư không. Phải coi tài liệu
`removed_as_wrong` là "không tồn tại" đối với mục đích chống trùng, và cho
tạo tài liệu mới.
"""

from __future__ import annotations

from datetime import date, datetime

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
        ingested_at=datetime(2024, 1, 1),
        source_format="pdf",
        content_fingerprint=content_fingerprint,
        extracted_text="Nội dung sai.",
        version_chain_id="chain-removed",
        version_ordinal=1,
        removed_as_wrong=True,
        removed_reason="Nạp nhầm bản nháp chưa ký",
    )


def test_reupload_of_fingerprint_matching_only_a_removed_as_wrong_document_creates_new_document(
    fingerprint_index,
):
    removed = _removed_as_wrong_document(
        document_id="doc-removed", space_id="space-a", content_fingerprint="fp-x"
    )
    fingerprint_index.register(removed)

    result = receive_and_validate(
        make_request(document_id="doc-new", space_id="space-a", content_fingerprint="fp-x"),
        fingerprint_index=fingerprint_index,
    )

    assert result.created is True
    assert result.duplicate_of is None
    assert result.document.document_id != removed.document_id


def test_reupload_still_reports_duplicate_against_a_non_removed_match_in_same_space(
    fingerprint_index,
):
    removed = _removed_as_wrong_document(
        document_id="doc-removed", space_id="space-a", content_fingerprint="fp-x"
    )
    fingerprint_index.register(removed)
    valid = receive_and_validate(
        make_request(document_id="doc-valid", space_id="space-a", content_fingerprint="fp-x"),
        fingerprint_index=fingerprint_index,
    ).document

    third = receive_and_validate(
        make_request(document_id="doc-third", space_id="space-a", content_fingerprint="fp-x"),
        fingerprint_index=fingerprint_index,
    )

    assert third.created is False
    assert third.duplicate_of == valid.document_id
