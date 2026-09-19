"""Nền chung cho test T1.4 — chèn `packages/` vào sys.path để import `schema.*`.

Cùng cách `tests/t1_1_schema/conftest.py`: `packages/` không có `__init__.py`
ở gốc, mỗi package con (`schema`, `ingestion`, `retrieval`) là điểm vào
riêng.
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

# 07 Mục 2.2 — whitelist tuyệt đối (QT2) của `Chunk`, chép tay MỘT LẦN DUY
# NHẤT ở đây, dùng chung cho `test_a_whitelist_exact.py` và
# `test_b_forbidden_field_names.py`. Cố ý KHÔNG import từ `schema.chunk` —
# nếu import từ đó thì test tự chứng minh vòng tròn (Chunk khớp với chính
# nó), mất tác dụng bắt lỗi khi ai đó lỡ sửa `chunk.py`.
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
