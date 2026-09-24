"""Nền chung cho test T2.1 — chèn `packages/` vào sys.path để import
`ingestion.*` và `schema.*`, cùng cách `tests/t1_1_schema/conftest.py` làm.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import date, datetime

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from ingestion.intake import IntakeRequest, InMemoryFingerprintIndex  # noqa: E402
from ingestion.space_registry import InMemorySpaceRegistry  # noqa: E402
from schema.document import DateSource  # noqa: E402

#: Mọi Space mà các ca thử T2.1 dùng tới. T2.11 (docs/10 §4.0) đặt một cổng
#: chặn ở `decide_intake`: `space_id` phải đã đăng ký và đang dùng. Các ca ở
#: đây nói về trùng lặp và chuỗi phiên bản, không nói về cổng đó — nên chúng
#: chạy trong một sổ đăng ký đã có sẵn cả hai Space. Chính cổng đó được kiểm
#: ở `tests/t2_11_space_registry/`.
SPACES_USED_BY_THESE_CASES = ("space-a", "space-b")


@pytest.fixture
def fingerprint_index() -> InMemoryFingerprintIndex:
    return InMemoryFingerprintIndex()


@pytest.fixture
def space_registry() -> InMemorySpaceRegistry:
    registry = InMemorySpaceRegistry()
    for space_id in SPACES_USED_BY_THESE_CASES:
        registry.register(space_id)
    return registry


def make_request(
    *,
    document_id: str,
    space_id: str,
    content_fingerprint: str,
    tenant_id: str = "tenant-1",
    declared_previous_version=None,
) -> IntakeRequest:
    """Dựng một `IntakeRequest` hợp lệ tối thiểu — các trường không liên quan
    tới quyết định trùng lặp/bản mới được điền giá trị cố định vô hại."""
    return IntakeRequest(
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        title="Quyết định về việc ban hành quy chế",
        doc_number="15/2024/QĐ-TGĐ",
        issued_date=date(2024, 1, 10),
        issued_date_source=DateSource.EXTRACTED,
        effective_date=date(2024, 2, 1),
        effective_date_source=DateSource.CONFIRMED,
        ingested_at=datetime(2024, 1, 12, 9, 0),
        source_format="pdf",
        content_fingerprint=content_fingerprint,
        extracted_text="Toàn văn ở đây.",
        declared_previous_version=declared_previous_version,
    )
