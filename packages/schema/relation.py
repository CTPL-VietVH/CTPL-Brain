"""`relation` — liên kết quan hệ giữa hai tài liệu (07 Mục 2.3).

Nơi cư trú: lớp quan hệ trong PostgreSQL ("kho đồ thị" là tên LOGIC — vật lý
chỉ có hai kho, xem CLAUDE.md Mục 5). Retrieval đọc kho này TẠI THỜI ĐIỂM
TRUY VẤN, nên `approval_state` có hiệu lực tức thì mà không phải nạp lại
mẩu — và vì vậy TUYỆT ĐỐI không được chép `approval_state` xuống payload
của `Chunk` (07 Mục 2.3, Mục 5).

Quy ước chiều — đọc thành một câu: `from_document_id` TÁC ĐỘNG LÊN
`to_document_id`. Ví dụ: Quyết định 15 sửa Quyết định 10 → from=QĐ15,
to=QĐ10.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RelationType(str, Enum):
    """Bốn loại quan hệ (07 Mục 2.3) — 06 Mục 6.2 xử lý mỗi loại khác hẳn nhau."""

    AMENDS_OR_REPLACES = "amends_or_replaces"
    ATTACHMENT = "attachment"
    REFERENCES = "references"
    SAME_TOPIC = "same_topic"


class ApprovalState(str, Enum):
    """Hai vai của một liên kết (07 Mục 2.3)."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RelationOrigin(str, Enum):
    """Nguồn gốc của liên kết — cũng gánh luôn dấu "chắc chắn" (DX1, CHỐT 14/9).

    Chắc chắn ⇔ origin ∈ {MACHINE_READ_EXPLICIT_REFERENCE, MANAGER_ASSIGNED}.
    KHÔNG có trường `is_certain` riêng — suy ra từ giá trị này, vì hai ô
    phải khớp nhau thì sẽ có ngày lệch nhau (07 Mục 2.3).

    ⚠️ Thêm một giá trị `origin` mới thì BẮT BUỘC xét lại tập "chắc chắn" ở
    trên — cái giá đã chấp nhận có ý thức khi gộp hai khái niệm vào một ô.
    """

    MACHINE_INFERRED = "machine_inferred"
    MACHINE_READ_EXPLICIT_REFERENCE = "machine_read_explicit_reference"
    MANAGER_ASSIGNED = "manager_assigned"


@dataclass(slots=True, kw_only=True)
class Relation:
    """Liên kết quan hệ — 07 Mục 2.3.

    Liên kết do người gắn tay (`origin=MANAGER_ASSIGNED`): `confidence` phải
    để TRỐNG (None), không phải 0 — trống nghĩa là "không máy nào chấm", 0
    nghĩa là "máy đã chấm và chấm rất thấp". `approval_state` khởi tạo thẳng
    ở APPROVED và `approved_by` chính là người gắn. Ngưỡng kéo liên kết
    (`relation_pull_threshold` ở config/retrieval.yaml) chỉ áp cho liên kết
    có `origin=MACHINE_INFERRED` — không áp cho liên kết người gắn hay liên
    kết đọc dẫn chiếu tường minh (07 Mục 2.3, CLAUDE.md Mục 3 #21).
    """

    relation_id: str
    from_document_id: str
    to_document_id: str
    relation_type: RelationType
    origin: RelationOrigin
    approval_state: ApprovalState

    confidence: float | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
