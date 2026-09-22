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
from ingestion.extraction import extract_file
from ingestion.intake import FingerprintIndex, decide_intake
from ingestion.labeling import (
    extract_subject_entities,
    goi_y_nhan,
    trich_ngay_hieu_luc,
    trich_ngay_ky,
)
from ingestion.pre_approval_buffer import BufferedIngestion, PreApprovalBuffer
from schema.document import DateSource, Document

__all__ = [
    "DuplicateHit",
    "DuplicateLocation",
    "PreApprovalRequest",
    "PreApprovalResult",
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
    """One upload into a private Space.

    `title` and `doc_number` come from the uploader: no GĐ5 function extracts
    them (`labeling.py` covers labels, both dates and subject entities), so
    they cannot be derived here — see the T2.7 report.

    `ingested_at` is passed in rather than read from the clock so the caller
    owns the timestamp, and so a test is not racing `datetime.now()`.
    """

    path: str | pathlib.Path
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


def run_pre_approval_ingestion(
    request: PreApprovalRequest,
    *,
    fingerprint_index: FingerprintIndex,
    buffer: PreApprovalBuffer,
    chunk_length_cap: int,
) -> PreApprovalResult:
    """Run GĐ2, GĐ3 and GĐ5 for one upload into a private Space and park the
    whole result in the pre-approval buffer.

    `chunk_length_cap` has no default — CLAUDE.md Mục 4 quy tắc 2; the caller
    reads `config/ingestion.yaml` and passes the live value down, exactly as
    `cat_thanh_mau` requires it.

    Stage order note: GĐ2 runs FIRST even though GĐ1 is "nhận và xác thực",
    because the duplicate key is `content_fingerprint`, computed from the text
    GĐ2 reads out (06 Mục 5.7: *"vân tay nội dung, tính ở GĐ2 sau khi đã đọc
    được chữ ra"*). `intake.py` says the same from the other side: calling GĐ1
    before GĐ2 has finished is calling it in the wrong order.

    Raises:
        DinhDangKhongNhan / KhongDocDuocLopChu: GĐ2 refused the file.
        KhongDungDuocCauTruc / KhoiVuotTranKhongTheChia: GĐ3 could not cut.
        Nothing is buffered when any of these is raised — the single `put`
        happens after every stage has succeeded.
    """
    # ---- GĐ2 — read the file out ----------------------------------------
    extraction = extract_file(request.path)

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

    # ---- STOP. GĐ6 and GĐ7 do not run; nothing is written to a shared
    # store. One `put` = one transaction (see `PreApprovalBuffer.put`).
    entry = BufferedIngestion(
        document=document,
        chunks=chunks,
        buffered_at=request.ingested_at,
    )
    buffer.put(entry)
    return PreApprovalResult(buffered=entry)
