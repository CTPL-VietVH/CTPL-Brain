"""T2.3 (e) — Mọi `Chunk` mà `cat_thanh_mau` sinh ra chỉ được mang đúng
whitelist 10 trường của 07 Mục 2.2 (QT2); và cơ chế bảo vệ `slots=True` của
`Chunk` (packages/schema/chunk.py) vẫn đứng vững — `TypeError` khi cố truyền
một trường lạ, kể cả từ bên trong module GĐ3 này.

Khuôn mẫu: `tests/t1_4_negative_space/test_a_whitelist_exact.py`.
"""

from __future__ import annotations

import dataclasses

import pytest
from schema.chunk import Chunk

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, VAN_BAN_LONG_NHAU

# Chép tay, KHÔNG import từ nơi khác — cùng lý do
# `tests/t1_4_negative_space/conftest.py` nêu: tự chứng minh vòng tròn thì
# mất tác dụng bắt lỗi.
CHUNK_WHITELIST = {
    "chunk_id",
    "document_id",
    "space_id",
    "tenant_id",
    "structure_path",
    "span_start",
    "span_end",
    "embedding",
    "parent_chunk_id",
    "category_labels",
}

CAM_LOT_VAO_CHUNK = {
    "full_text",
    "heading",
    "marker",
    "level",
    "children",
    "bat_thuong",
    "outcome",
    "notes",
    "source_format",
    "content_fingerprint",
}


def test_chunk_that_su_sinh_ra_chi_mang_dung_whitelist():
    read_result = dung_cau_truc(VAN_BAN_LONG_NHAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result, document_id=DOC_ID, space_id=SPACE_ID, tenant_id=TENANT_ID
    )
    assert chunks, "văn bản thử phải sinh ra ít nhất một mẩu để test có ý nghĩa"

    ten_truong = {f.name for f in dataclasses.fields(Chunk)}
    assert ten_truong == CHUNK_WHITELIST

    for chunk in chunks:
        for cam in CAM_LOT_VAO_CHUNK:
            assert not hasattr(chunk, cam), (
                f"Trường bị cấm {cam!r} lọt vào Chunk sinh bởi cat_thanh_mau"
            )


@pytest.mark.parametrize("truong_la", sorted(CAM_LOT_VAO_CHUNK))
def test_truyen_truong_la_vao_chunk_raise_typeerror(truong_la):
    """Lưới an toàn `slots=True`: một trường lạ ở BẤT KỲ đâu — kể cả nếu ai
    đó lỡ sửa `cat_thanh_mau` để truyền thêm — phải nổ `TypeError` ngay lúc
    khởi tạo, không lọt âm thầm vào payload."""
    kwargs = dict(
        chunk_id="chunk-1",
        document_id="doc-1",
        space_id="space-1",
        tenant_id="tenant-1",
        structure_path=["Điều 1"],
        span_start=0,
        span_end=10,
        embedding=[],
    )
    kwargs[truong_la] = "gia-tri-bat-hop-phap"
    with pytest.raises(TypeError):
        Chunk(**kwargs)
