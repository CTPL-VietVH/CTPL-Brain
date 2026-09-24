"""T2.7 (g) — GĐ1's duplicate check still runs on the pre-approval path, and
still reads the SHARED store: an upload whose twin is already approved and
live is refused before anything is buffered.

The read is the point. `run_pre_approval_ingestion` calls
`intake.decide_intake` — read-only — and never `intake.receive_and_validate`,
whose last line is `fingerprint_index.register(document)`. Registering there
is exactly the invariant violation 08 T2.7 warns about: *"Ghi hồ sơ tài liệu
vào đó rồi chỉ hoãn nạp vector là đã vi phạm bất biến."*
"""

from __future__ import annotations

from ingestion.intake import InMemoryFingerprintIndex
from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.pre_approval_runner import DuplicateLocation, run_pre_approval_ingestion
from schema.document import DateSource, Document

from .conftest import CHUNK_LENGTH_CAP, INGESTED_AT, make_request, registered_spaces, write_sample


def test_duplicate_already_in_the_shared_store_is_reported(tmp_path) -> None:
    path = write_sample(tmp_path)
    buffer = InMemoryPreApprovalBuffer()
    fingerprint_index = InMemoryFingerprintIndex()

    # Find out what fingerprint this file produces, then pre-register an
    # approved twin under it.
    probe = run_pre_approval_ingestion(
        make_request(path, document_id="doc-probe"),
        fingerprint_index=fingerprint_index,
        buffer=InMemoryPreApprovalBuffer(),
        space_registry=registered_spaces(),
        chunk_length_cap=CHUNK_LENGTH_CAP,
    )
    fingerprint = probe.buffered.document.content_fingerprint

    fingerprint_index.register(
        Document(
            document_id="doc-already-live",
            space_id="space-private",
            tenant_id="tenant-1",
            title="Bản đã duyệt",
            doc_number="15/2021/QĐ-BNV",
            issued_date=INGESTED_AT.date(),
            issued_date_source=DateSource.EXTRACTED,
            effective_date=INGESTED_AT.date(),
            effective_date_source=DateSource.EXTRACTED,
            ingested_at=INGESTED_AT,
            source_format="txt",
            content_fingerprint=fingerprint,
            extracted_text="đã duyệt",
            version_chain_id="chain-live",
            version_ordinal=1,
        )
    )

    result = run_pre_approval_ingestion(
        make_request(path, document_id="doc-new"),
        fingerprint_index=fingerprint_index,
        buffer=buffer,
        space_registry=registered_spaces(),
        chunk_length_cap=CHUNK_LENGTH_CAP,
    )

    assert result.buffered is None
    assert result.duplicate is not None
    assert result.duplicate.document_id == "doc-already-live"
    assert result.duplicate.found_in is DuplicateLocation.SHARED_STORE
    assert buffer.list_in_space("space-private") == []
