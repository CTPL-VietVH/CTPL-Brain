"""T2.1 (c) — Người upload khai tường minh "đây là bản mới của X" (06 Mục 5.7).

Chỉ nhánh khai báo TƯỜNG MINH thuộc T2.1 — nhánh máy tự phân tích đề xuất
thuộc T2.4 (Cập nhật 19/9 PO, docs/08 T2.1), xem test_e.
"""

from __future__ import annotations

from ingestion.intake import receive_and_validate
from schema.document import VersionDeclaredBy

from .conftest import make_request


def test_declared_previous_version_extends_the_same_version_chain(fingerprint_index):
    previous = receive_and_validate(
        make_request(document_id="doc-old", space_id="space-a", content_fingerprint="fp-v1"),
        fingerprint_index=fingerprint_index,
    ).document
    assert previous.version_ordinal == 1

    newer = receive_and_validate(
        make_request(
            document_id="doc-new",
            space_id="space-a",
            content_fingerprint="fp-v2",
            declared_previous_version=previous,
        ),
        fingerprint_index=fingerprint_index,
    ).document

    assert newer.version_chain_id == previous.version_chain_id
    assert newer.version_ordinal == previous.version_ordinal + 1
    assert newer.version_declared_by is VersionDeclaredBy.UPLOADER_DECLARED_AT_INGESTION


def test_declared_previous_version_chains_across_three_uploads(fingerprint_index):
    v1 = receive_and_validate(
        make_request(document_id="doc-v1", space_id="space-a", content_fingerprint="fp-v1"),
        fingerprint_index=fingerprint_index,
    ).document
    v2 = receive_and_validate(
        make_request(
            document_id="doc-v2",
            space_id="space-a",
            content_fingerprint="fp-v2",
            declared_previous_version=v1,
        ),
        fingerprint_index=fingerprint_index,
    ).document
    v3 = receive_and_validate(
        make_request(
            document_id="doc-v3",
            space_id="space-a",
            content_fingerprint="fp-v3",
            declared_previous_version=v2,
        ),
        fingerprint_index=fingerprint_index,
    ).document

    assert v1.version_chain_id == v2.version_chain_id == v3.version_chain_id
    assert (v1.version_ordinal, v2.version_ordinal, v3.version_ordinal) == (1, 2, 3)
