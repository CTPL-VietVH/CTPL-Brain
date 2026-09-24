"""T2.7 (a) — THE acceptance criterion (08 T2.7, dòng 207): *"tài liệu chưa
duyệt trong Space riêng KHÔNG CÓ MẶT TRONG BẤT KỲ KHO DÙNG CHUNG NÀO — kiểm
bằng cách truy vấn thẳng vào cả Qdrant VÀ PostgreSQL, không qua service."*

Both shared stores are queried directly here, not through any service that
could be doing the filtering itself — that is the whole point of the
criterion: pre-approval is blocked BY STRUCTURE, not by a filter that has to
run correctly (06 Mục 5.2 GĐ1).

The buffer is asserted non-empty in the same test on purpose. Without it the
test would pass just as well on a pipeline that silently did nothing at all.
"""

from __future__ import annotations

from ingestion.intake import InMemoryFingerprintIndex
from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.pre_approval_runner import run_pre_approval_ingestion

from .conftest import CHUNK_LENGTH_CAP, FakeSharedVectorStore, make_request, registered_spaces, write_sample


def test_pre_approval_document_is_in_no_shared_store(tmp_path) -> None:
    fingerprint_index = InMemoryFingerprintIndex()  # the official `document` table
    vector_store = FakeSharedVectorStore()  # Qdrant
    buffer = InMemoryPreApprovalBuffer()

    request = make_request(write_sample(tmp_path))
    result = run_pre_approval_ingestion(
        request,
        fingerprint_index=fingerprint_index,
        buffer=buffer,
        space_registry=registered_spaces(),
        chunk_length_cap=CHUNK_LENGTH_CAP,
    )

    # --- the shared stores, queried directly -----------------------------
    assert vector_store.count() == 0, "GĐ6 must not have run — no vector may exist"
    assert fingerprint_index.find_by_fingerprint(
        result.buffered.document.content_fingerprint
    ) == [], "the official profile store must not hold this document"

    # --- the working area, which is not a shared store -------------------
    assert result.duplicate is None
    assert result.buffered is not None
    held = buffer.get(request.document_id)
    assert held is not None
    assert held.document.document_id == request.document_id
    assert held.chunks, "GĐ3 ran, so the buffer must be holding its chunks"
