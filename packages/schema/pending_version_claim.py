"""`pending_version_claim` — đề nghị chờ xác nhận bản mới (07 Mục 2.4).

Sinh ra từ 06 Mục 5.7, đường thứ hai: người upload không khai "đây là bản
mới của X" thì máy phân tích rồi đề nghị, và cả người upload lẫn Manager đều
được nhắc — ai xác nhận trước cũng được.

KHÔNG phải một `Relation` loại thứ năm. Chuỗi phiên bản và quan hệ là hai
trục khác nhau: "văn bản sửa đổi" là hai tài liệu riêng cùng là bản ghi
thật, còn "bản mới" là cùng một danh tính. Quan trọng hơn, hai loại đề nghị
hành xử ngược nhau — một `Relation` **chưa duyệt vẫn được kéo** vào ngữ
cảnh, còn một `PendingVersionClaim` **chưa xác nhận thì hai tài liệu vẫn
hoàn toàn rời** (07 Mục 2.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClaimState(str, Enum):
    """07 Mục 2.4."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@dataclass(slots=True, kw_only=True)
class PendingVersionClaim:
    """Đề nghị chờ xác nhận bản mới — 07 Mục 2.4."""

    claim_id: str
    new_document_id: str
    candidate_previous_document_id: str
    similarity: float

    notified_uploader: bool = False
    notified_manager: bool = False
    state: ClaimState = ClaimState.PENDING
