"""T2.7 (j) — dropping a rejected entry works, and dropping it twice is not
an error.

The repeat-safety is the shape T2.8 will need for permanent deletion (08
T2.8: *"chạy lệnh xoá hai lần liên tiếp trên cùng một tài liệu không gây lỗi
và không đổi kết quả"*), and it costs nothing to get right here.
"""

from __future__ import annotations

from ingestion.intake import InMemoryFingerprintIndex
from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.pre_approval_runner import run_pre_approval_ingestion

from .conftest import CHUNK_LENGTH_CAP, make_request, registered_spaces, write_sample


def test_discard_releases_an_entry_and_is_repeatable(tmp_path) -> None:
    buffer = InMemoryPreApprovalBuffer()
    request = make_request(write_sample(tmp_path))
    run_pre_approval_ingestion(
        request,
        fingerprint_index=InMemoryFingerprintIndex(),
        buffer=buffer,
        space_registry=registered_spaces(),
        chunk_length_cap=CHUNK_LENGTH_CAP,
    )
    assert buffer.get(request.document_id) is not None

    assert buffer.discard(request.document_id) is True
    assert buffer.get(request.document_id) is None
    assert buffer.list_in_space("space-private") == []

    # Second time: no exception, same end state.
    assert buffer.discard(request.document_id) is False
    assert buffer.get(request.document_id) is None
