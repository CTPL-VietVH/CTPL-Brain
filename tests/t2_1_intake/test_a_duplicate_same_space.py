"""T2.1 (a) — Trùng khít, CÙNG Space: báo trùng, không nạp lại (06 Mục 5.7).

Đây chính là nửa đầu ca thử "Xong khi" của T2.1 (docs/08): nạp cùng một file
hai lần vào một Space chỉ ra MỘT tài liệu.
"""

from __future__ import annotations

from ingestion.intake import receive_and_validate

from .conftest import make_request


def test_second_ingest_of_same_content_in_same_space_does_not_create_a_new_document(
    fingerprint_index,
):
    first = receive_and_validate(
        make_request(document_id="doc-1", space_id="space-a", content_fingerprint="fp-x"),
        fingerprint_index=fingerprint_index,
    )
    assert first.created is True
    assert first.duplicate_of is None

    second = receive_and_validate(
        make_request(document_id="doc-2", space_id="space-a", content_fingerprint="fp-x"),
        fingerprint_index=fingerprint_index,
    )
    assert second.created is False
    assert second.duplicate_of == first.document.document_id
    assert second.document.document_id == first.document.document_id


def test_repeated_ingest_in_one_space_leaves_exactly_one_document_indexed(fingerprint_index):
    for i in range(3):
        receive_and_validate(
            make_request(document_id=f"doc-{i}", space_id="space-a", content_fingerprint="fp-x"),
            fingerprint_index=fingerprint_index,
        )

    documents_in_space = fingerprint_index.find_by_fingerprint("fp-x")
    assert len(documents_in_space) == 1
