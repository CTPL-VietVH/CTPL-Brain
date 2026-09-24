"""T2.7 (b) — GĐ5's output is what the Manager looks at when deciding, so it
has to survive the wait: 06 Mục 5.2 GĐ1 picks this stopping point precisely
because the first four stages *"cho người quyết thấy được nhãn phân loại lúc
duyệt"*.

09 Mục 4.2 on T2.7 names the same requirement from the storage side: *"phải
giữ được trạng thái trung gian (cây cấu trúc, danh sách mẩu, nhãn) qua một
khoảng thời gian không xác định."*
"""

from __future__ import annotations

from datetime import date

from ingestion.intake import InMemoryFingerprintIndex
from ingestion.pre_approval_runner import run_pre_approval_ingestion
from schema.document import DateSource

from .conftest import CHUNK_LENGTH_CAP, make_request, registered_spaces, write_sample


def test_stage5_labels_and_dates_survive_in_the_buffer(tmp_path, buffer_factory) -> None:
    buffer = buffer_factory()
    request = make_request(write_sample(tmp_path))

    run_pre_approval_ingestion(
        request,
        fingerprint_index=InMemoryFingerprintIndex(),
        buffer=buffer,
        space_registry=registered_spaces(),
        chunk_length_cap=CHUNK_LENGTH_CAP,
    )

    held = buffer.get(request.document_id)
    assert held is not None
    document = held.document

    assert "QUYẾT ĐỊNH" in document.category_labels
    assert document.subject_entities  # K3's input signal, kept for GĐ7 later

    # Both dates were really in the text, so both carry EXTRACTED — not the
    # ingestion-date placeholder.
    assert (document.issued_date, document.issued_date_source) == (
        date(2021, 3, 15),
        DateSource.EXTRACTED,
    )
    assert (document.effective_date, document.effective_date_source) == (
        date(2021, 5, 1),
        DateSource.EXTRACTED,
    )
