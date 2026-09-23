"""`deletion_log` — the permanent-deletion log (06 Mục 5.6).

Lives in PostgreSQL, table `deletion_log` (`store_schema.DELETION_LOG_TABLE`).
No foreign key to `document`: this row must OUTLIVE the document it describes
— a cascading FK would delete the very record the deletion exists to leave
behind.

*"Nhật ký giữ lại: Việc đã xoá: ai, khi nào, tài liệu nào, lý do. **Không giữ
nội dung**"* (06 Mục 5.6) — and that is the entirety of what this type may
carry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class DeletionLogEntry:
    """*"ai, khi nào, tài liệu nào, lý do"* — 06 Mục 5.6, và không gì khác.

    ⚠️ **No field here may carry document content.** No `title`, no
    `doc_number`, no excerpt, no chunk text. The log is the store nothing can
    delete from, so content placed in it survives the very deletion that put
    it there — the back door 06 Mục 9.2 had to close once already, and the
    reason "nguyên văn ... trong nhật ký" is on CLAUDE.md's forbidden-field
    list. `tests/t2_8_deletion/test_k_*` asserts this against a real document.

    `space_id` / `tenant_id` are optional because the profile may already be
    gone when a deletion is retried, or may never have existed. They are a
    trace of where the document used to live, not a permission record (QT1):
    delete them and the system still decides correctly who reads what.

    `purge_completed_at` stays empty until step 3 reports the bytes actually
    reclaimed. S6: *"nghĩa vụ xoá dữ liệu cá nhân chỉ được coi là hoàn thành
    khi bước dọn nền ĐÃ CHẠY XONG, không phải khi người dùng bấm xoá."*
    """

    document_id: str
    deleted_by: str
    reason: str
    requested_at: datetime
    space_id: str | None = None
    tenant_id: str | None = None
    purge_completed_at: datetime | None = None
