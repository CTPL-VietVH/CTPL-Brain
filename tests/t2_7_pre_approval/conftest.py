"""Shared fixtures for T2.7 (pre-approval buffer) tests — inserts `packages/`
into `sys.path` to import `ingestion.*` and `schema.*`, same as
`tests/t2_6_relations/conftest.py`.

No live PostgreSQL and no live Qdrant: the acceptance criterion of 08 T2.7 is
about what is ABSENT from the shared stores, and `InMemoryFingerprintIndex` +
`FakeSharedVectorStore` below stand in for the two of them. The buffer's own
in-memory implementation enforces every constraint its DDL enforces, so a
violation is a red test here rather than an integrity error on someone's
first real INSERT.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import datetime

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from ingestion.pre_approval_runner import PreApprovalRequest  # noqa: E402
from ingestion.space_registry import InMemorySpaceRegistry  # noqa: E402

#: Every Space these cases submit into. T2.11 (docs/10 §4.0) made a live
#: Space register a precondition of any upload, official path or
#: pre-approval path alike; these cases are about the buffer, not about that
#: gate, so they run against a register where both Spaces already exist. The
#: gate itself is tested in `tests/t2_11_space_registry/`.
SPACES_USED_BY_THESE_CASES = ("space-private", "space-other")


def registered_spaces() -> InMemorySpaceRegistry:
    """A fresh register holding exactly the Spaces above, all `IN_USE`."""
    registry = InMemorySpaceRegistry()
    for space_id in SPACES_USED_BY_THESE_CASES:
        registry.register(space_id)
    return registry


# Trần độ dài mẩu — PO chốt 5000 ký tự Unicode (21/9/2026). `cat_thanh_mau`
# và `run_pre_approval_ingestion` đều KHÔNG cho giá trị này một mặc định
# trong mã (CLAUDE.md Mục 4 quy tắc 2), nên mọi lời gọi phải truyền tay.
CHUNK_LENGTH_CAP = 5000

INGESTED_AT = datetime(2026, 9, 22, 14, 0)

# A document in the standard Vietnamese administrative shape: quốc hiệu, số
# hiệu, ngày ký, thể loại, then Chương › Điều › Khoản. Every GĐ5 signal is
# present on purpose, so a test can prove the buffer KEPT them rather than
# merely prove nothing crashed.
SAMPLE_DOCUMENT = """BỘ NỘI VỤ
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: 15/2021/QĐ-BNV
Hà Nội, ngày 15 tháng 3 năm 2021

QUYẾT ĐỊNH
Về việc ban hành Quy chế quản lý tài liệu nội bộ

CHƯƠNG I
QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
1. Quyết định này quy định về công tác quản lý tài liệu nội bộ của cơ quan.
2. Mọi cán bộ, công chức phải chịu trách nhiệm bảo quản tài liệu được giao.

Điều 2. Đối tượng áp dụng
Quyết định này áp dụng đối với toàn thể cán bộ, công chức của Bộ Nội vụ.

CHƯƠNG II
ĐIỀU KHOẢN THI HÀNH

Điều 3. Hiệu lực thi hành
Quyết định này có hiệu lực thi hành kể từ ngày 01 tháng 5 năm 2021.
"""

# Same structure, no date anywhere — for the "không giả vờ là ngày thật"
# fallback (08 T2.4, 06 Mục 6.4).
SAMPLE_DOCUMENT_WITHOUT_DATES = """CHƯƠNG I
QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
Quy chế này áp dụng cho toàn thể cán bộ, nhân viên của công ty.

Điều 2. Giải thích từ ngữ
Các từ ngữ trong quy chế này được hiểu theo quy định của pháp luật hiện hành.
"""


def write_sample(
    tmp_path: pathlib.Path,
    *,
    name: str = "quyet-dinh-15.txt",
    text: str = SAMPLE_DOCUMENT,
) -> pathlib.Path:
    """Write a sample document to a real file — GĐ2 reads files, so the chain
    cannot be exercised from a string."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def make_request(
    path: pathlib.Path,
    *,
    document_id: str = "doc-t2-7-1",
    space_id: str = "space-private",
    tenant_id: str = "tenant-1",
    title: str = "Quyết định ban hành Quy chế quản lý tài liệu nội bộ",
    doc_number: str = "15/2021/QĐ-BNV",
) -> PreApprovalRequest:
    return PreApprovalRequest(
        path=path,
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        title=title,
        doc_number=doc_number,
        ingested_at=INGESTED_AT,
    )


class FakeSharedVectorStore:
    """Stand-in for Qdrant — the OTHER shared store 08 T2.7 requires querying
    directly.

    It is deliberately never wired into the pre-approval path: the assertion
    that matters is that it stays empty, and a store the chain cannot reach
    even by accident is the honest way to model *"chưa ghi vào ba kho dùng
    chung"*.
    """

    def __init__(self) -> None:
        self._points: dict[str, object] = {}

    def upsert(self, point_id: str, payload: object) -> None:
        self._points[point_id] = payload

    def count(self) -> int:
        return len(self._points)

    def get(self, point_id: str) -> object | None:
        return self._points.get(point_id)
