"""T2.7 (e) — `put` is the transaction boundary: a rejected entry leaves the
buffer exactly as it was.

A half-written entry is the dangerous failure here, and it is invisible after
the fact: a document whose chunk list was truncated at row four looks
identical to a document that genuinely cut into four chunks, and the Manager
would approve a partial reading of the file believing it complete. The real
implementation gets this from one PostgreSQL transaction per call; the
in-memory one gets it by validating everything before mutating anything.
"""

from __future__ import annotations

import pytest
from ingestion.pre_approval_buffer import (
    BufferedIngestion,
    EmbeddedChunkInPreApprovalBufferError,
)
from schema.chunk import Chunk

from .conftest import INGESTED_AT
from .test_d_buffer_refuses_a_chunk_carrying_a_vector import _document


def _chunk(chunk_id: str, *, embedding: list[float] | None = None) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="doc-1",
        space_id="space-private",
        tenant_id="tenant-1",
        structure_path=["Điều 1"],
        span_start=0,
        span_end=26,
        embedding=embedding if embedding is not None else [],
    )


def test_put_is_all_or_nothing(buffer_factory) -> None:
    buffer = buffer_factory()

    # The bad chunk is LAST: a buffer that wrote as it validated would already
    # have committed the two good ones by the time it noticed.
    entry = BufferedIngestion(
        document=_document(),
        buffered_at=INGESTED_AT,
        chunks=[_chunk("chunk-1"), _chunk("chunk-2"), _chunk("chunk-3", embedding=[0.5])],
    )

    with pytest.raises(EmbeddedChunkInPreApprovalBufferError):
        buffer.put(entry)

    assert buffer.get("doc-1") is None
    assert buffer.list_in_space("space-private") == []
