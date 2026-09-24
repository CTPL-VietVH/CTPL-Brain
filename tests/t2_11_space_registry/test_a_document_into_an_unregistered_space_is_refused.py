"""T2.11 (a) — case 1: a document aimed at a Space nobody registered is
refused, on BOTH ingestion paths.

08 T2.11: *"T2.1 từ chối nộp tài liệu vào Space chưa đăng ký hoặc không ở
trạng thái đang dùng."* docs/10 §4.1 says the same from the API side and
names the code: `404 SPACE_NOT_REGISTERED`.

Why both paths are checked here: a private Space goes through
`pre_approval_runner`, a normal one through `receive_and_validate`, and the
gate would be worth nothing if it only stood in front of one of them. It is
implemented ONCE, in `decide_intake` — the single point both paths cross —
and this file is what pins that down.

The second assertion in each case is the one that matters most: the refusal
must leave NOTHING behind. A rejected upload that has already registered its
fingerprint would make the next, legitimate upload of the same file look
like a duplicate of a document that does not exist.
"""

from __future__ import annotations

import pytest

from ingestion.intake import InMemoryFingerprintIndex, IntakeRequest, receive_and_validate
from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.pre_approval_runner import PreApprovalRequest, run_pre_approval_ingestion
from ingestion.space_registry import InMemorySpaceRegistry, SpaceNotRegistered

from .conftest import DOOMED_SPACE, INGESTED_AT, make_document

CHUNK_LENGTH_CAP = 5000
UNKNOWN_SPACE = "space-nobody-announced"


def _request(space_id: str) -> IntakeRequest:
    document = make_document(document_id="doc-new", space_id=space_id)
    return IntakeRequest(
        document_id=document.document_id,
        space_id=document.space_id,
        tenant_id=document.tenant_id,
        title=document.title,
        doc_number=document.doc_number,
        issued_date=document.issued_date,
        issued_date_source=document.issued_date_source,
        effective_date=document.effective_date,
        effective_date_source=document.effective_date_source,
        ingested_at=document.ingested_at,
        source_format=document.source_format,
        content_fingerprint=document.content_fingerprint,
        extracted_text=document.extracted_text,
    )


def test_the_official_path_refuses_an_unregistered_space() -> None:
    fingerprint_index = InMemoryFingerprintIndex()
    registry = InMemorySpaceRegistry()
    registry.register(DOOMED_SPACE)  # a DIFFERENT Space is registered

    with pytest.raises(SpaceNotRegistered):
        receive_and_validate(
            _request(UNKNOWN_SPACE),
            fingerprint_index=fingerprint_index,
            space_registry=registry,
        )

    assert fingerprint_index.find_by_fingerprint("fingerprint-doc-new") == [], (
        "a refused upload must not leave its fingerprint behind"
    )


def test_the_pre_approval_path_refuses_an_unregistered_space(tmp_path) -> None:
    path = tmp_path / "quyet-dinh.txt"
    path.write_text("Điều 1. Phạm vi điều chỉnh.\nQuyết định này quy định.\n", encoding="utf-8")
    buffer = InMemoryPreApprovalBuffer()
    registry = InMemorySpaceRegistry()
    registry.register(DOOMED_SPACE)

    with pytest.raises(SpaceNotRegistered):
        run_pre_approval_ingestion(
            PreApprovalRequest(
                path=path,
                document_id="doc-new",
                space_id=UNKNOWN_SPACE,
                tenant_id="tenant-1",
                title="Quyết định",
                doc_number="15/2021/QĐ-BNV",
                ingested_at=INGESTED_AT,
            ),
            fingerprint_index=InMemoryFingerprintIndex(),
            buffer=buffer,
            space_registry=registry,
            chunk_length_cap=CHUNK_LENGTH_CAP,
        )

    assert buffer.list_in_space(UNKNOWN_SPACE) == [], (
        "a refused upload must not be parked in the buffer either"
    )


def test_an_unknown_space_is_never_registered_on_first_use() -> None:
    """The tempting repair for the two cases above is to create the Space on
    first sight. docs/10 §4.0 gives registration to Backend alone — a Space
    AI invented would hold documents nobody can reach, because no `DELETE`
    and no permission grant will ever name that code."""
    registry = InMemorySpaceRegistry()

    with pytest.raises(SpaceNotRegistered):
        receive_and_validate(
            _request(UNKNOWN_SPACE),
            fingerprint_index=InMemoryFingerprintIndex(),
            space_registry=registry,
        )

    assert registry.get(UNKNOWN_SPACE) is None
    assert registry.registrations() == []
