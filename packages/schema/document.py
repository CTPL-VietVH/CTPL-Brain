"""`document` — hồ sơ tài liệu (07 Mục 2.1).

Nơi cư trú: kho hồ sơ (PostgreSQL). Retrieval đọc **sau khi** đã có kết quả
tìm, để dựng đơn vị ĐỌC và dẫn nguồn — không dùng để lọc ứng viên lúc tìm
(đó là việc của `chunk`, xem `chunk.py`, QT2).

Không có trường `publication_state`: mọi thứ trong kho dùng chung đều đã
dùng được (CHỐT 14/9, S1) — tài liệu chờ Manager duyệt không nằm ở đây.
Không có trường `is_latest_version`: suy ra từ `version_chain_id` +
`version_ordinal` lúc cần (NT3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class DateSource(str, Enum):
    """Nguồn của `issued_date` / `effective_date` (07 Mục 2.1).

    Chỉ EXTRACTED và CONFIRMED đáng tin. DEFAULT_INGESTION_DATE nghĩa là
    "chưa ai biết ngày thật" — bên đọc phải nói rõ không biết ngày hiệu lực
    thay vì đọc ra một con số trông hợp lý.
    """

    EXTRACTED = "extracted"
    CONFIRMED = "confirmed"
    DEFAULT_INGESTION_DATE = "default_ingestion_date"


class VersionDeclaredBy(str, Enum):
    """Hai đường tuyên bố bản mới của một tài liệu (07 Mục 2.1, nguồn 06 Mục 5.7)."""

    UPLOADER_DECLARED_AT_INGESTION = "uploader_declared_at_ingestion"
    UPLOADER_CONFIRMED_SUGGESTION = "uploader_confirmed_suggestion"
    MANAGER_CONFIRMED_SUGGESTION = "manager_confirmed_suggestion"


class RelationsScanState(str, Enum):
    """Cửa sổ đối chiếu quan hệ của tài liệu còn mở hay đã dừng (07 Mục 2.1)."""

    EXPANDING = "expanding"
    STOPPED = "stopped"


@dataclass(slots=True, kw_only=True)
class Document:
    """Hồ sơ tài liệu — 07 Mục 2.1.

    ⚠️ `removed_as_wrong` và `superseded` PHẢI ở lại hai trường riêng biệt —
    KHÔNG được gộp thành một trường `status`/`document_state`. Gộp lại thì
    Manager đánh dấu một quyết định cũ hết hiệu lực sẽ vô tình làm câu hỏi
    "tháng 1/2024 ai là giám đốc" không trả lời được nữa (06 Mục 6.3,
    CLAUDE.md Mục 3 #1).

    Trong mỗi cặp trạng thái, ô đúng/sai (`removed_as_wrong`, `superseded`)
    là ô có thẩm quyền; các ô `_by`/`_at` đi kèm chỉ là DẤU VẾT (QT1) —
    không được suy trạng thái từ việc `_at` có giá trị hay không.
    """

    document_id: str
    space_id: str
    tenant_id: str
    title: str
    doc_number: str
    issued_date: date
    issued_date_source: DateSource
    effective_date: date
    effective_date_source: DateSource
    ingested_at: datetime
    source_format: str
    content_fingerprint: str
    extracted_text: str
    version_chain_id: str
    version_ordinal: int

    removed_as_wrong: bool = False
    removed_reason: str | None = None
    removed_by: str | None = None
    removed_at: datetime | None = None

    superseded: bool = False
    superseded_by: str | None = None
    superseded_at: datetime | None = None

    category_labels: list[str] = field(default_factory=list)
    labels_confirmed_by: str | None = None
    labels_confirmed_at: datetime | None = None

    version_declared_by: VersionDeclaredBy | None = None
    relations_scan_state: RelationsScanState = RelationsScanState.EXPANDING
