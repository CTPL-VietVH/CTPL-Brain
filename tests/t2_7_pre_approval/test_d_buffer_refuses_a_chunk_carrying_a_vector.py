"""T2.7 (d) — the buffer refuses a chunk that already has an embedding.

The real table has no `embedding` column at all, which is the structural
guarantee; this is the same refusal at the Python boundary so the mistake
surfaces as a red test instead of as an INSERT error against a live
PostgreSQL nobody is running during development.

06 Mục 5.2 GĐ1 is explicit that pre-approval must be blocked *"bằng cấu trúc
chứ không bằng một bộ lọc phải chạy đúng"* — a column that does not exist
cannot be filled by a caller who forgets.
"""

from __future__ import annotations

import pytest
from ingestion.pre_approval_buffer import (
    BufferedIngestion,
    EmbeddedChunkInPreApprovalBufferError,
    InMemoryPreApprovalBuffer,
)
from schema.chunk import Chunk
from schema.document import DateSource, Document

from .conftest import INGESTED_AT


def _document() -> Document:
    return Document(
        document_id="doc-1",
        space_id="space-private",
        tenant_id="tenant-1",
        title="Quyết định thử",
        doc_number="15/2021/QĐ-BNV",
        issued_date=INGESTED_AT.date(),
        issued_date_source=DateSource.EXTRACTED,
        effective_date=INGESTED_AT.date(),
        effective_date_source=DateSource.EXTRACTED,
        ingested_at=INGESTED_AT,
        source_format="txt",
        content_fingerprint="fp-1",
        extracted_text="Điều 1. Phạm vi điều chỉnh",
        version_chain_id="chain-1",
        version_ordinal=1,
    )


def test_buffer_refuses_a_chunk_carrying_a_vector() -> None:
    buffer = InMemoryPreApprovalBuffer()
    entry = BufferedIngestion(
        document=_document(),
        buffered_at=INGESTED_AT,
        chunks=[
            Chunk(
                chunk_id="chunk-1",
                document_id="doc-1",
                space_id="space-private",
                tenant_id="tenant-1",
                structure_path=["Điều 1"],
                span_start=0,
                span_end=26,
                embedding=[0.1, 0.2, 0.3],
            )
        ],
    )

    with pytest.raises(EmbeddedChunkInPreApprovalBufferError):
        buffer.put(entry)

    assert buffer.get("doc-1") is None
