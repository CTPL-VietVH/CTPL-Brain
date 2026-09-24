"""T2.1 (d) — Không khai báo, không trùng: tài liệu mới đứng đầu chuỗi riêng.

`version_declared_by` phải là `None` — module này KHÔNG tự đoán ai là bản cũ
(đó là việc của T2.4, xem test_e).
"""

from __future__ import annotations

from ingestion.intake import receive_and_validate

from .conftest import make_request


def test_undeclared_upload_starts_its_own_version_chain_at_ordinal_one(fingerprint_index, space_registry):
    result = receive_and_validate(
        make_request(document_id="doc-1", space_id="space-a", content_fingerprint="fp-a"),
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    )

    assert result.document.version_ordinal == 1
    assert result.document.version_declared_by is None
    assert result.document.version_chain_id


def test_two_unrelated_undeclared_uploads_get_different_version_chains(fingerprint_index, space_registry):
    first = receive_and_validate(
        make_request(document_id="doc-1", space_id="space-a", content_fingerprint="fp-a"),
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    ).document
    second = receive_and_validate(
        make_request(document_id="doc-2", space_id="space-a", content_fingerprint="fp-b"),
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    ).document

    assert first.version_chain_id != second.version_chain_id
