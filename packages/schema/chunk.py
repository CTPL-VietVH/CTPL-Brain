"""`chunk` — đơn vị cắt và vector (07 Mục 2.2).

Nơi cư trú: kho vector (Qdrant). Đây là đơn vị để TÌM, không phải đơn vị để
ĐỌC (Mục 6.1 của 06).

⚠️ QT2 — payload cạnh mẩu CHỈ được chứa các trường dưới đây, không hơn. Đây
là whitelist tuyệt đối: bất kỳ trường nào khác — kể cả trường hợp lệ ở
`Document` như `title`, `effective_date`, hay `approval_state` của
`Relation` — đặt vào đây đều là vi phạm (07 Mục 5).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, kw_only=True)
class Chunk:
    """Mẩu cắt — 07 Mục 2.2.

    `span_start`/`span_end` đếm theo KÝ TỰ UNICODE, không phải byte — lệch
    cách đếm thì đoạn cắt sai, không lỗi nào báo, chỉ là dẫn nguồn sai chỗ
    (07 Mục 2.2, CLAUDE.md Mục 3 #4).

    Mẩu KHÔNG giữ bản sao chữ của mình; chữ nằm ở `Document.extracted_text`
    duy nhất, mẩu chỉ giữ vị trí (`span_start`, `span_end`). Đơn vị ĐỌC lấy
    được bằng cách theo `parent_chunk_id` rồi cắt theo vị trí của mẩu cha —
    để trống nếu mẩu đã là đơn vị cấu trúc cao nhất của tài liệu (S2).

    `category_labels` là NGOẠI LỆ DUY NHẤT của QT2: một bản sao để xếp hạng
    nhanh, chấp nhận phải gán lại toàn bộ mẩu khi đổi cách phân loại.
    """

    chunk_id: str
    document_id: str
    space_id: str
    tenant_id: str
    structure_path: list[str]
    span_start: int
    span_end: int
    embedding: list[float]

    parent_chunk_id: str | None = None
    category_labels: list[str] = field(default_factory=list)
