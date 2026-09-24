"""T2.7 (i) — a document with no date anywhere gets the ingestion date and
keeps the source at `DEFAULT_INGESTION_DATE`.

06 Mục 6.4 and 08 T2.4 both insist on the second half: the field must not
*"giả vờ là ngày thật"*. The date column is NOT NULL, so something has to go
in it — the source is what tells the reader the number is a placeholder, and
the timeline (06 Mục 6.4: *"trục thời gian chỉ tin ngày có nguồn tin được"*)
and K3's date gate both read the source, not the date.
"""

from __future__ import annotations

from ingestion.intake import InMemoryFingerprintIndex
from ingestion.pre_approval_runner import run_pre_approval_ingestion
from schema.document import DateSource

from .conftest import (
    CHUNK_LENGTH_CAP,
    INGESTED_AT,
    SAMPLE_DOCUMENT_WITHOUT_DATES,
    make_request,
    registered_spaces,
    write_sample,
)


def test_missing_dates_fall_back_without_pretending(tmp_path, buffer_factory) -> None:
    path = write_sample(
        tmp_path, name="quy-che-khong-ngay.txt", text=SAMPLE_DOCUMENT_WITHOUT_DATES
    )
    buffer = buffer_factory()
    request = make_request(path)

    run_pre_approval_ingestion(
        request,
        fingerprint_index=InMemoryFingerprintIndex(),
        buffer=buffer,
        space_registry=registered_spaces(),
        chunk_length_cap=CHUNK_LENGTH_CAP,
    )

    document = buffer.get(request.document_id).document
    assert document.issued_date == INGESTED_AT.date()
    assert document.issued_date_source is DateSource.DEFAULT_INGESTION_DATE
    assert document.effective_date == INGESTED_AT.date()
    assert document.effective_date_source is DateSource.DEFAULT_INGESTION_DATE
