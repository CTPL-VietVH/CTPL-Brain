"""T2.7 (f) — a second upload of the same file into the same private Space
while the first is still waiting is reported as a duplicate, not buffered
twice.

08's 21/9 update (PO, audit #2) asks for `UNIQUE (space_id,
content_fingerprint)` at the STORAGE level *"không chỉ kiểm tra ở tầng ứng
dụng"* — application-only checking loses the race when two uploads of one
file land together. The buffer table carries that constraint, and the
in-memory implementation refuses what PostgreSQL would refuse.

Note the gap this closes: `decide_intake` can only see the official store, so
without the buffer's own lookup two identical pending uploads would both sail
through and land in front of the Manager as two separate approvals.
"""

from __future__ import annotations

from ingestion.intake import InMemoryFingerprintIndex
from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.pre_approval_runner import DuplicateLocation, run_pre_approval_ingestion

from .conftest import CHUNK_LENGTH_CAP, make_request, write_sample


def test_second_pending_upload_of_one_file_is_refused(tmp_path) -> None:
    fingerprint_index = InMemoryFingerprintIndex()
    buffer = InMemoryPreApprovalBuffer()
    path = write_sample(tmp_path)

    first = run_pre_approval_ingestion(
        make_request(path, document_id="doc-first"),
        fingerprint_index=fingerprint_index,
        buffer=buffer,
        chunk_length_cap=CHUNK_LENGTH_CAP,
    )
    assert first.buffered is not None

    second = run_pre_approval_ingestion(
        make_request(path, document_id="doc-second"),
        fingerprint_index=fingerprint_index,
        buffer=buffer,
        chunk_length_cap=CHUNK_LENGTH_CAP,
    )

    assert second.buffered is None
    assert second.duplicate is not None
    assert second.duplicate.document_id == "doc-first"
    assert second.duplicate.found_in is DuplicateLocation.PRE_APPROVAL_BUFFER
    assert len(buffer.list_in_space("space-private")) == 1
    assert buffer.get("doc-second") is None
