"""T2.1 (e) — Ranh giới với T2.4: module này KHÔNG được sinh ra
`PendingVersionClaim`.

Cập nhật 19/9 (PO, theo N9, docs/08 T2.1): nhánh "người upload không khai thì
máy tự phân tích đề xuất" thuộc T2.4 (GĐ5), không phải T2.1. Nếu về sau có ai
thêm logic tạo `PendingVersionClaim` vào `ingestion/intake.py`, ranh giới hai
task đã bị xoá — test này phải đỏ ngay khi đó xảy ra.
"""

from __future__ import annotations

import inspect

import ingestion.intake as intake_module


def test_intake_module_does_not_import_or_construct_pending_version_claim():
    source = inspect.getsource(intake_module)
    assert "pending_version_claim" not in source
    assert "PendingVersionClaim(" not in source


def test_undeclared_upload_is_never_flagged_as_needing_confirmation(fingerprint_index, space_registry):
    from ingestion.intake import receive_and_validate

    from .conftest import make_request

    result = receive_and_validate(
        make_request(document_id="doc-1", space_id="space-a", content_fingerprint="fp-a"),
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
    )

    # `IntakeResult` không có, và không được có, một trường kiểu
    # "cần Manager xác nhận" — đó là việc của T2.4/T2.9, không phải T2.1.
    assert not hasattr(result, "pending_claim")
