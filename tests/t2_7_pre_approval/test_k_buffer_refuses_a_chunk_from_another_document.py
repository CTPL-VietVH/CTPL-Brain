"""T2.7 (k) — a chunk that belongs to a different document is refused.

`ON DELETE CASCADE` on the real table only cleans up rows that point at the
right parent; the foreign key is what stops the wrong pointer being written
in the first place, and this is that FK at the Python boundary.
"""

from __future__ import annotations

import pytest
from ingestion.pre_approval_buffer import (
    BufferedIngestion,
    ChunkDocumentMismatchError,
)
from schema.chunk import Chunk

from .conftest import INGESTED_AT
from .test_d_buffer_refuses_a_chunk_carrying_a_vector import _document


def test_buffer_refuses_a_chunk_from_another_document(buffer_factory) -> None:
    buffer = buffer_factory()
    entry = BufferedIngestion(
        document=_document(),  # document_id="doc-1"
        buffered_at=INGESTED_AT,
        chunks=[
            Chunk(
                chunk_id="chunk-1",
                document_id="doc-SOMEONE-ELSE",
                space_id="space-private",
                tenant_id="tenant-1",
                structure_path=["Điều 1"],
                span_start=0,
                span_end=26,
                embedding=[],
            )
        ],
    )

    with pytest.raises(ChunkDocumentMismatchError):
        buffer.put(entry)

    assert buffer.get("doc-1") is None
