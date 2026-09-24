"""T2.1 (b) — Trùng khít, KHÁC Space: hợp lệ, không cảnh báo (06 Mục 5.7).

Nửa sau ca thử "Xong khi" của T2.1 (docs/08): nạp cùng một file vào hai
Space ra HAI tài liệu, không cảnh báo cho người upload — báo tên Space kia
sẽ tiết lộ sự tồn tại của tài liệu ngoài quyền đọc của họ (ngược Mục 9.5).
"""

from __future__ import annotations

from ingestion.intake import receive_and_validate

from .conftest import make_request


def test_same_fingerprint_in_two_spaces_creates_two_documents_without_warning(
    fingerprint_index,
    space_registry,
):
    in_space_a = receive_and_validate(
        make_request(document_id="doc-1", space_id="space-a", content_fingerprint="fp-x"),
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    )
    in_space_b = receive_and_validate(
        make_request(document_id="doc-2", space_id="space-b", content_fingerprint="fp-x"),
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    )

    assert in_space_a.created is True
    assert in_space_b.created is True
    assert in_space_a.duplicate_of is None
    assert in_space_b.duplicate_of is None
    assert in_space_a.document.document_id != in_space_b.document.document_id

    all_matches = fingerprint_index.find_by_fingerprint("fp-x")
    assert len(all_matches) == 2
    assert {d.space_id for d in all_matches} == {"space-a", "space-b"}
