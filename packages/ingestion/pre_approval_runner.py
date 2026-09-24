"""T2.7, part 2/2 — the pre-approval stage chain: GĐ1 → GĐ2 → GĐ3 → GĐ5, then
STOP (06 Mục 5.2 GĐ1, 08 T2.7).

06 Mục 5.2 GĐ1, CHỐT 14/9/2026: *"Chạy GĐ2, GĐ3 và GĐ5 (đọc file, cắt, gán
nhãn — GĐ4 hoãn ở v1), rồi DỪNG TRƯỚC GĐ6 và GĐ7. Kết quả nằm trong vùng làm
việc riêng của Ingestion, chưa ghi vào ba kho dùng chung."*

The stopping point is not arbitrary: *"bốn bước đầu chỉ cần bản thân tài liệu
và cho người quyết thấy được nhãn phân loại lúc duyệt; hai bước sau mới là thứ
chạm vào kho dùng chung và làm tài liệu tìm được."*

--------------------------------------------------------------------------
The one thing this module must not do
--------------------------------------------------------------------------

It does NOT call `intake.receive_and_validate`. That function ends with
`fingerprint_index.register(document)` — a write into the official profile
store — which is precisely the invariant violation 08 T2.7 warns about:
*"Ghi hồ sơ tài liệu vào đó rồi chỉ hoãn nạp vector là đã vi phạm bất biến."*

The pre-approval path therefore uses `intake.decide_intake` instead: the same
GĐ1 decision (duplicate check, version chain assignment), READ-ONLY against
the shared store. The document is registered there only when a Manager
approves — a step that does not exist yet (see the T2.7 report).

It does not import `vectorization` (GĐ6) or `relations`/`relations_scan`
(GĐ7) at all, and `tests/t2_7_pre_approval/` asserts that by reading this
module's import list: an accidental call cannot be added here without a
test going red.

--------------------------------------------------------------------------
Who decides that a document needs pre-approval
--------------------------------------------------------------------------

Not this module, and nothing stored. Whether a Space is `riêng` (pre-check)
or `kế thừa`/thông thường (post-check) is a live property of the Space tree —
NT3 forbids it from living in ingested data, and 07 Mục 0 puts the Space
contract outside both sources of truth. The caller decides freshly and calls
this function for the pre-check path; there is no `space_type` parameter to
get stale.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from ingestion.chunking import cat_thanh_mau
from ingestion.extraction import ExtractionResult, extract_file
from ingestion.intake import FingerprintIndex, decide_intake
from ingestion.labeling import (
    extract_subject_entities,
    goi_y_nhan,
    trich_ngay_hieu_luc,
    trich_ngay_ky,
)
from ingestion.pre_approval_buffer import BufferedIngestion, PreApprovalBuffer
from ingestion.space_registry import SpaceRegistry, assert_space_accepts_documents
from schema.document import DateSource, Document

__all__ = [
    "DuplicateHit",
    "DuplicateLocation",
    "PreApprovalRequest",
    "PreApprovalResult",
    "prepare_ingestion",
    "run_pre_approval_ingestion",
]


class DuplicateLocation(str, Enum):
    """Where the twin of this upload was found.

    Two places have to be told apart because the answer to the uploader
    differs: a twin in the shared store is already usable, a twin in the
    buffer is still waiting for the same Manager.
    """

    SHARED_STORE = "shared_store"
    PRE_APPROVAL_BUFFER = "pre_approval_buffer"


@dataclass(frozen=True, slots=True, kw_only=True)
class DuplicateHit:
    document_id: str
    found_in: DuplicateLocation


@dataclass(frozen=True, slots=True, kw_only=True)
class PreApprovalRequest:
    """One upload, before any stage has run.

    `title` and `doc_number` come from the uploader: no GĐ5 function extracts
    them (`labeling.py` covers labels, both dates and subject entities), so
    they cannot be derived here — see the T2.7 report. Over `POST
    /v1/ingestions` nobody supplies them either (PO chốt 24/9/2026: Backend
    does not send them and the filename must NOT be used as a title), so that
    caller passes the empty string and `suggestions` reports `null`.

    `ingested_at` is passed in rather than read from the clock so the caller
    owns the timestamp, and so a test is not racing `datetime.now()`.

    `path` is optional for exactly one caller: `prepare_ingestion` takes the
    GĐ2 result as an argument, and the `POST /v1/ingestions` path deletes the
    staged file the instant GĐ2 returns (docs/10 §4.1), so by then there is
    no path to name. `run_pre_approval_ingestion`, which reads the file
    itself, requires it and says so.
    """

    path: str | pathlib.Path | None = None
    document_id: str
    space_id: str
    tenant_id: str
    title: str
    doc_number: str
    ingested_at: datetime
    declared_previous_version: Document | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PreApprovalResult:
    """Exactly one of `buffered` / `duplicate` is set.

    Kept as two mutually exclusive fields rather than a flag beside a value:
    a boolean that has to agree with a nullable field is the shape DX1 (07
    Mục 2.3) rejects — two cells that must match will one day not match.

    ⚠️ **`buffered` names the TYPE, not the destination.** This is also the
    result of `prepare_ingestion`, which both submission paths share
    (docs/10 §4.1): on the Space-riêng path the value is handed to
    `PreApprovalBuffer.put`, and on the ordinary path it is handed straight
    to `promotion.promote_approved_ingestion` and never enters a buffer.
    That both paths carry the SAME `BufferedIngestion` value into the SAME
    write function is the point — see `prepare_ingestion`.
    """

    buffered: BufferedIngestion | None = None
    duplicate: DuplicateHit | None = None


def _resolve_date(
    suggested: date | None,
    suggested_source: DateSource,
    *,
    ingested_at: datetime,
) -> tuple[date, DateSource]:
    """Turn a GĐ5 suggestion into the `(date, source)` pair `Document`
    requires.

    `labeling.GoiYNgayKy` documents this as the caller's job: a `None` date
    means *"chưa ai biết ngày thật"*, and the caller fills the ingestion date
    while KEEPING the source at `DEFAULT_INGESTION_DATE` — 06 Mục 6.4 wants
    the reader told the date is not real, never handed a plausible-looking
    number (07 S-note on 6.4; 08 T2.4: *"không giả vờ là ngày thật"*).
    """
    if suggested is None:
        return ingested_at.date(), DateSource.DEFAULT_INGESTION_DATE
    return suggested, suggested_source


def prepare_ingestion(
    request: PreApprovalRequest,
    *,
    extraction: ExtractionResult,
    fingerprint_index: FingerprintIndex,
    buffer: PreApprovalBuffer,
    space_registry: SpaceRegistry,
    chunk_length_cap: int,
) -> PreApprovalResult:
    """GĐ1 → GĐ5 → GĐ3 over an ALREADY-READ file, stopping before GĐ6/GĐ7.

    ⭐ **This is the head both submission paths share, and sharing it is a
    decision, not a convenience** (PO chốt 24/9/2026). docs/10 §4.1 gives one
    submission endpoint and two destinations — *"`space_is_private = true`
    thì chạy GĐ2, GĐ3, GĐ5 rồi dừng ở vùng đệm (T2.7). Ngược lại thì chạy
    trọn và ghi vào kho."* Two destinations must not mean two pipelines:

        prepare_ingestion(...)  ─┬─►  buffer.put(entry)              (riêng)
                                 │        … later, on approve:
                                 └─►  promote_approved_ingestion(entry)
                                          ▲
                                          └── the ordinary path goes here
                                              DIRECTLY, same entry, same
                                              function, same write order.

    A second write path would be a second chance to get S6-in-reverse wrong
    (`promotion.py`: profile+relations in one transaction, THEN the vector
    gate). `tests/api/` asserts that both paths reach the same function,
    because a comment cannot keep them together.

    `extraction` is passed in rather than read here: the caller owns the
    staged file and deletes it the moment GĐ2 is done (docs/10 §4.1 — *"Bản
    tạm bị xoá ngay sau khi đọc xong chữ, kể cả khi từ chối giữa chừng"*), so
    the read has to happen outside this function's lifetime.

    `chunk_length_cap` has no default — CLAUDE.md Mục 4 quy tắc 2; the caller
    reads `config/ingestion.yaml` and passes the live value down, exactly as
    `cat_thanh_mau` requires it.

    Stage order note: GĐ2 has already run when this is called, and that is
    the required order, not an accident — the duplicate key is
    `content_fingerprint`, computed from the text GĐ2 reads out (06 Mục 5.7:
    *"vân tay nội dung, tính ở GĐ2 sau khi đã đọc được chữ ra"*).

    Raises:
        SpaceNotRegistered / SpaceNotAcceptingDocuments: the Space is unknown
            or no longer accepting documents (docs/10 §4.0). Re-checked here
            even though the submission already checked it: an upload queued
            before a Space deletion started must not land after it.
        BanMoiKhacSpace: the declared previous version is in another Space.
        KhongDungDuocCauTruc / KhoiVuotTranKhongTheChia: GĐ3 could not cut.
        Nothing is written anywhere when any of these is raised.
    """
    # ---- T2.11 — the Space gate, before any work is done -----------------
    assert_space_accepts_documents(request.space_id, space_registry=space_registry)

    # ---- GĐ1 — decide, READ-ONLY against the shared store ----------------
    pending_twin = buffer.find_in_space_by_fingerprint(
        space_id=request.space_id,
        content_fingerprint=extraction.content_fingerprint,
    )
    if pending_twin is not None and pending_twin.document.document_id != request.document_id:
        return PreApprovalResult(
            duplicate=DuplicateHit(
                document_id=pending_twin.document.document_id,
                found_in=DuplicateLocation.PRE_APPROVAL_BUFFER,
            )
        )

    decision = decide_intake(
        space_id=request.space_id,
        content_fingerprint=extraction.content_fingerprint,
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
        declared_previous_version=request.declared_previous_version,
    )
    if not decision.proceed:
        if decision.duplicate_of is None:
            raise AssertionError(
                "decide_intake returned proceed=False without duplicate_of — internal "
                "invariant violated"
            )
        return PreApprovalResult(
            duplicate=DuplicateHit(
                document_id=decision.duplicate_of,
                found_in=DuplicateLocation.SHARED_STORE,
            )
        )
    if decision.version_chain_id is None or decision.version_ordinal is None:
        raise AssertionError(
            "decide_intake returned proceed=True without a version chain — internal "
            "invariant violated"
        )

    # ---- GĐ5 — labels, both dates, subject entities ----------------------
    # (GĐ4, the sensitive-content scan, is HOÃN in v1 — CLAUDE.md Mục 2.)
    category_labels = goi_y_nhan(extraction.extracted_text)
    issued = trich_ngay_ky(extraction.extracted_text)
    effective = trich_ngay_hieu_luc(extraction.extracted_text)
    subject_entities = extract_subject_entities(extraction.extracted_text)

    issued_date, issued_date_source = _resolve_date(
        issued.issued_date, issued.issued_date_source, ingested_at=request.ingested_at
    )
    effective_date, effective_date_source = _resolve_date(
        effective.effective_date,
        effective.effective_date_source,
        ingested_at=request.ingested_at,
    )

    document = Document(
        document_id=request.document_id,
        space_id=request.space_id,
        tenant_id=request.tenant_id,
        title=request.title,
        doc_number=request.doc_number,
        issued_date=issued_date,
        issued_date_source=issued_date_source,
        effective_date=effective_date,
        effective_date_source=effective_date_source,
        ingested_at=request.ingested_at,
        source_format=extraction.source_format,
        content_fingerprint=extraction.content_fingerprint,
        extracted_text=extraction.extracted_text,
        version_chain_id=decision.version_chain_id,
        version_ordinal=decision.version_ordinal,
        version_declared_by=decision.version_declared_by,
        category_labels=category_labels,
        subject_entities=subject_entities.subject_entities,
    )

    # ---- GĐ3 — cut into chunks ------------------------------------------
    chunks = cat_thanh_mau(
        extraction.read_result,
        document_id=request.document_id,
        space_id=request.space_id,
        tenant_id=request.tenant_id,
        tran_do_dai_mau=chunk_length_cap,
    )

    # ---- STOP. GĐ6 and GĐ7 do not run, and nothing has been written to any
    # store: this function is READ-ONLY end to end. Where the value goes next
    # is the caller's decision — see the diagram in the docstring.
    return PreApprovalResult(
        buffered=BufferedIngestion(
            document=document,
            chunks=chunks,
            buffered_at=request.ingested_at,
        )
    )


def run_pre_approval_ingestion(
    request: PreApprovalRequest,
    *,
    fingerprint_index: FingerprintIndex,
    buffer: PreApprovalBuffer,
    space_registry: SpaceRegistry,
    chunk_length_cap: int,
) -> PreApprovalResult:
    """The Space-riêng path: read the file, prepare it, park it in the buffer.

    GĐ2 here and the rest in `prepare_ingestion`. The Space gate is checked
    BEFORE GĐ2 as well as inside `prepare_ingestion`, so a file aimed at a
    Space that is going away is not read and cut first.

    Raises:
        Everything `prepare_ingestion` raises, plus
        DinhDangKhongNhan / KhongDocDuocLopChu: GĐ2 refused the file.
        Nothing is buffered when any of these is raised — the single `put`
        happens after every stage has succeeded.
    """
    assert_space_accepts_documents(request.space_id, space_registry=space_registry)

    if request.path is None:
        raise ValueError(
            "run_pre_approval_ingestion reads the file itself, so "
            "PreApprovalRequest.path is required here. A caller that has "
            "already run GĐ2 calls prepare_ingestion(extraction=...) instead."
        )

    # ---- GĐ2 — read the file out ----------------------------------------
    extraction = extract_file(request.path)

    result = prepare_ingestion(
        request,
        extraction=extraction,
        fingerprint_index=fingerprint_index,
        buffer=buffer,
        space_registry=space_registry,
        chunk_length_cap=chunk_length_cap,
    )
    if result.buffered is not None:
        # One `put` = one transaction (see `PreApprovalBuffer.put`).
        buffer.put(result.buffered)
    return result
