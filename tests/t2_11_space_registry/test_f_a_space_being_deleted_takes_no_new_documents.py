"""T2.11 (f) — case 6: a Space in state *đang xoá* refuses new documents.

docs/10 §4.0 step 1: *"Chuyển Space sang *đang xoá*. Từ lúc này mọi lời gọi
nộp tài liệu hay thao tác ghi vào Space trả `409 SPACE_BEING_DELETED`."* 08
T2.11 *Xong khi*: *"nộp mới vào Space đang xoá bị từ chối"*.

The first case reaches that state the way production will — by interrupting a
real deletion — rather than by setting the flag by hand. A document accepted
in that window is the exact harm the ordering of step 1 exists to prevent: it
lands in a Space the loop has already walked past, and nothing will ever
mention it again.
"""

from __future__ import annotations

import pytest

from fault_injection import InjectedCrash, crash_after
from ingestion.intake import InMemoryFingerprintIndex, IntakeRequest, receive_and_validate
from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.pre_approval_runner import PreApprovalRequest, run_pre_approval_ingestion
from ingestion.space_deletion import delete_space
from ingestion.space_registry import (
    SpaceNotAcceptingDocuments,
    SpaceState,
)

from .conftest import DOOMED_SPACE, INGESTED_AT, make_document

CHUNK_LENGTH_CAP = 5000


def _request_into(space_id: str) -> IntakeRequest:
    document = make_document(document_id="doc-late", space_id=space_id)
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


def _interrupt_mid_deletion(world, space_deletion_kwargs) -> None:
    crashing = crash_after(world.cleanup, "purge", on_call=1)
    with pytest.raises(InjectedCrash):
        delete_space(
            DOOMED_SPACE, **{**space_deletion_kwargs, "background_cleanup": crashing}
        )
    crashing.assert_fired()
    assert world.registry.get(DOOMED_SPACE).state is SpaceState.BEING_DELETED


def test_the_official_path_refuses_a_space_being_deleted(
    world, space_deletion_kwargs
) -> None:
    _interrupt_mid_deletion(world, space_deletion_kwargs)

    with pytest.raises(SpaceNotAcceptingDocuments):
        receive_and_validate(
            _request_into(DOOMED_SPACE),
            fingerprint_index=world.inner_store,
            space_registry=world.registry,
        )

    assert "doc-late" not in world.document_ids()


def test_the_pre_approval_path_refuses_a_space_being_deleted(
    world, space_deletion_kwargs, tmp_path
) -> None:
    _interrupt_mid_deletion(world, space_deletion_kwargs)
    path = tmp_path / "quyet-dinh.txt"
    path.write_text("Điều 1. Phạm vi điều chỉnh.\nQuyết định này quy định.\n", encoding="utf-8")
    buffer = InMemoryPreApprovalBuffer()

    with pytest.raises(SpaceNotAcceptingDocuments):
        run_pre_approval_ingestion(
            PreApprovalRequest(
                path=path,
                document_id="doc-late",
                space_id=DOOMED_SPACE,
                tenant_id="tenant-1",
                title="Quyết định",
                doc_number="15/2021/QĐ-BNV",
                ingested_at=INGESTED_AT,
            ),
            fingerprint_index=InMemoryFingerprintIndex(),
            buffer=buffer,
            space_registry=world.registry,
            chunk_length_cap=CHUNK_LENGTH_CAP,
        )

    assert buffer.list_in_space(DOOMED_SPACE) == []


def test_a_finished_space_refuses_new_documents_too(
    world, space_deletion_kwargs
) -> None:
    """`DELETED` is not a softer state than `BEING_DELETED` for this purpose:
    only `IN_USE` accepts documents, and a Space that is gone accepts
    nothing."""
    delete_space(DOOMED_SPACE, **space_deletion_kwargs)
    assert world.registry.get(DOOMED_SPACE).state is SpaceState.DELETED

    with pytest.raises(SpaceNotAcceptingDocuments):
        receive_and_validate(
            _request_into(DOOMED_SPACE),
            fingerprint_index=world.inner_store,
            space_registry=world.registry,
        )


def test_the_other_space_keeps_accepting_documents(
    world, space_deletion_kwargs
) -> None:
    """Refusal is scoped to the Space being deleted. The register holds no
    tree, so there is no way for one Space's deletion to close another —
    and this pins that it does not."""
    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    result = receive_and_validate(
        _request_into("space-keeper"),
        fingerprint_index=world.inner_store,
        space_registry=world.registry,
    )

    assert result.created is True
    assert result.document.space_id == "space-keeper"
