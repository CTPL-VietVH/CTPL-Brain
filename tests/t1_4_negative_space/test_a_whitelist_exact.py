"""T1.4 (a) — Whitelist tuyệt đối của `Chunk` (07 Mục 2.2, QT2).

07 Mục 2.2 liệt kê CHÍNH XÁC mười trường được phép đặt cạnh mẩu vector —
không hơn, không kém. `category_labels` là ngoại lệ duy nhất của QT2 (một
bản sao nhãn để xếp hạng nhanh, đã được quyết ở 6.4) chứ không phải một lỗ
hổng của whitelist.

Đây là ca thử "hệ thống LÊN TIẾNG": bất kỳ ai thêm một trường mới vào
`Chunk` — dù đặt tên gì, dù có nằm trong 8 danh mục cấm liệt kê tường minh ở
07 Mục 5 hay không — cũng phải làm đỏ đúng MỘT bài test dưới đây trước khi
kịp lọt vào payload thật của Qdrant.
"""

from __future__ import annotations

import dataclasses

from .conftest import CHUNK_WHITELIST
from schema.chunk import Chunk


def _chunk_field_names() -> set[str]:
    return {f.name for f in dataclasses.fields(Chunk)}


def test_chunk_has_exactly_ten_fields():
    assert len(dataclasses.fields(Chunk)) == len(CHUNK_WHITELIST) == 10, (
        "07 Mục 2.2 định nghĩa đúng 10 trường cho `chunk` (8 bắt buộc + "
        "`parent_chunk_id`/`category_labels` có mặc định) — số trường lệch "
        "đi là dấu hiệu chắc chắn có trường lạ hoặc thiếu trường hợp lệ."
    )


def test_chunk_fields_match_whitelist_exactly():
    """Lưới an toàn tổng — bắt được BẤT KỲ trường lạ nào, kể cả loại chưa ai
    nghĩ ra tên cụ thể để liệt kê ở 07 Mục 5.
    """
    assert _chunk_field_names() == CHUNK_WHITELIST


def test_chunk_constructs_with_only_whitelisted_fields():
    """Ca thử "chạy trôi" — cần nhưng không đủ một mình; test_chunk_fields_
    match_whitelist_exactly ở trên mới là ca thử LÊN TIẾNG khi sai.
    """
    chunk = Chunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        space_id="space-1",
        tenant_id="tenant-1",
        structure_path=["Chương II", "Điều 7", "Khoản 3"],
        span_start=0,
        span_end=120,
        embedding=[0.1, 0.2, 0.3],
    )
    assert chunk.parent_chunk_id is None
    assert chunk.category_labels == []
