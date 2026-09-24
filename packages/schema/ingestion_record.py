"""`ingestion_record` — one row per submission to `POST /v1/ingestions`
(docs/10 §4.1, §4.2), and at the same time the work queue the background
runner reads.

Lives in PostgreSQL, table `ingestion_record`
(`store_schema.INGESTION_RECORD_TABLE`). Same split as `space_registry.py`
and `deletion_log.py`: the SHAPE that goes in the table lives here, the
Protocol, the refusals and the pipeline that writes it stay in
`packages/ingestion/`. CLAUDE.md Mục 6 — *"Tên trường định nghĩa đúng một
lần trong `packages/schema/`; không service nào tự khai báo lại"*.

──────────────────────────────────────────────────────────────────────────
`ingestion_id` is NOT `document_id` (chốt 24/9/2026, docs/10 §4.2)
──────────────────────────────────────────────────────────────────────────

*"`ingestion_id` và `document_id` là **hai định danh khác nhau** ... đối
tượng nạp có thể kết thúc mà không sinh tài liệu (`rejected`, `duplicate`,
`failed`)"*. Reusing one identifier for both would mean minting a
`document_id` for a file that was refused before GĐ2 finished reading it —
an id pointing at nothing, visible to Backend.

──────────────────────────────────────────────────────────────────────────
⛔ What this table must NEVER grow a column for
──────────────────────────────────────────────────────────────────────────

Four prohibitions, PO chốt 24/9/2026 (escalation E1), each with its own
reason — none of them is tidiness:

* **`url`** — the presigned link Backend sends in `source` (§4.1). It is a
  TEMPORARY PERMISSION, not a fact about the document: *"AI **không lưu
  `url`** ở bất cứ đâu (nhật ký, bảng, thông báo lỗi) — đường dẫn có chữ ký
  là một thứ quyền tạm thời"*. A column holding it would keep a usable key
  to Backend's object store long after the call ended.
* **Any permission signal of the caller.** `submitted_by` is the whole of
  what is kept, and it is an OPAQUE trace (§1 T5: *"không tra, không diễn
  giải"*). In particular `actor.acting_as` has no column: a role is a
  permission fact, and QT1 plus the CLAUDE.md forbidden-field table keep
  those out of AI's stored data.
* **`space_is_private`** — the live type of the Space. NT3: it changes when
  a human clicks something, so a copy here would be the stale one. See
  `requires_pre_approval` below, which is deliberately NOT that column.
* **Document content.** No `extracted_text`, no excerpt, no title. The text
  has exactly one home (07 Mục 2.1), and a second copy is the reasoning of
  điều cấm #3.

Nothing here is a permission verdict, so the table passes QT1's test: delete
it and the system still decides correctly who may read what — Backend sends
`readable_space_ids` fresh on every question (docs/10 §3.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final


class IngestionStatus(str, Enum):
    """Where one submission has got to.

    Seven values, and only six of the wire's (docs/10 §4.2). `QUEUED` and
    `RUNNING` are both reported to Backend as `processing` — see
    `wire_status` for why the finer pair is kept in the column.

    A `str` Enum like every other enum in this package (`SpaceState`,
    `DateSource`, `RelationsScanState`), so the value stored in the `status`
    column and the value compared in Python are ONE string, not two that
    must agree.
    """

    #: Accepted, file already staged, waiting for the runner. This is the
    #: queue: a row in this state IS a pending job.
    QUEUED = "queued"

    #: The single worker is on it right now. ⚠️ See `ORPHANED_STATUS` — this
    #: value is only trustworthy while exactly one worker process is alive.
    RUNNING = "running"

    #: docs/10 §4.2 — terminal, and each says something different:
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    AWAITING_APPROVAL = "awaiting_approval"
    ACTIVE = "active"
    FAILED = "failed"


class IngestionFailureCode(str, Enum):
    """The values the `code` column may hold — docs/10 §4.2 *"kèm `code`"*.

    Only the codes that can be STORED land here; the transport-level codes
    of §3.5 (`UNAUTHENTICATED`, `FILE_TOO_LARGE`, `SOURCE_UNREACHABLE` …)
    are answered inside the call that fails and never reach a row, so their
    home stays `api.errors.ErrorCode`. Where a spelling exists on both sides
    — `OBJECT_NOT_IN_SPACE` — a test asserts the two agree rather than
    trusting two people to type the same string twice (CLAUDE.md Mục 6).

    Every value below is copied character for character from the §3.5 table.
    """

    #: GĐ2 refused the file: outside the four v1 formats, or a PDF with no
    #: text layer. docs/10 §3.5 puts both behind one code.
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"

    #: *"Đọc được file nhưng không cắt hoặc tạo vector được"* — the one code
    #: PO chốt 24/9 for all three refusals GĐ3/GĐ6 can raise (escalation E5).
    #: They are one code because they are one fact for Backend: the file was
    #: readable and the pipeline still could not turn it into chunks, and
    #: none of the three is fixed by Backend doing something different.
    DOCUMENT_NOT_STRUCTURABLE = "DOCUMENT_NOT_STRUCTURABLE"

    #: The uploader declared *"bản mới của X"* and X lives in another Space.
    NEW_VERSION_OTHER_SPACE = "NEW_VERSION_OTHER_SPACE"

    #: The declared previous document could not be found in this Space when
    #: the runner reached it. ⛔ Never silently treated as a brand-new
    #: document (PO chốt 24/9, K11).
    OBJECT_NOT_IN_SPACE = "OBJECT_NOT_IN_SPACE"

    #: Unforeseen failure. Paired with `IngestionStatus.FAILED`, never with
    #: `REJECTED`: *rejected* means the submission was wrong, *failed* means
    #: this service was.
    INTERNAL_ERROR = "INTERNAL_ERROR"


#: docs/10 §4.2 — what Backend is told while a submission is still moving.
#: A wire value, deliberately NOT a member of `IngestionStatus`: no row ever
#: holds it, and a seventh enum member nobody may store would be a value with
#: two meanings.
WIRE_STATUS_PROCESSING: Final = "processing"

#: The states a submission can still leave. Exported so the runner, the read
#: endpoint and the tests share one definition of "still moving".
UNFINISHED_STATUSES: Final[frozenset[IngestionStatus]] = frozenset(
    {IngestionStatus.QUEUED, IngestionStatus.RUNNING}
)

#: ⚠️ **The one state a restart must not believe.** PO chốt 24/9/2026: with
#: exactly ONE worker thread, a `RUNNING` row found at startup cannot be
#: running — the process that claimed it is the one that just died — so it
#: goes straight back to `QUEUED`. No timeout, no heartbeat, no guess: the
#: conclusion follows from "one replica", and a threshold would be a second
#: number to tune and a second thing to get wrong.
#:
#: ⛔ **This is exactly why running two replicas of AI Services is FORBIDDEN
#: until there is a durable claim mechanism** (a separate task). A second
#: replica restarting would hand a live job of the first back to the queue
#: and the same file would be ingested twice.
ORPHANED_STATUS: Final = IngestionStatus.RUNNING


def wire_status(status: IngestionStatus) -> str:
    """The value `GET /v1/ingestions/{id}` publishes for a stored status.

    docs/10 §4.2 gives Backend six statuses and no queue: *"`processing` |
    đang chạy"* covers both waiting and working, because the difference is
    AI's own scheduling and Backend can act on neither.

    The finer pair is kept in the column anyway, and not as a second boolean
    beside `status`: two cells that must agree will one day not agree (the
    reasoning of 07 Mục 2.3's `is_certain`). One column, one truth, and this
    function is the only place the projection happens.
    """
    if status in UNFINISHED_STATUSES:
        return WIRE_STATUS_PROCESSING
    return status.value


@dataclass(frozen=True, slots=True, kw_only=True)
class IngestionRecord:
    """One submission: what it was, where it got to, and what it produced.

    `frozen=True` with `dataclasses.replace` for every transition, the same
    shape `promotion.py` uses: a row that is mutated in place can be advanced
    by a caller holding a stale copy, and the store would never know.
    """

    #: Minted by AI when the call is accepted. NOT a `document_id` — see the
    #: module docstring.
    ingestion_id: str

    #: Where the document is being submitted. PO chốt 24/9 (E1): this column
    #: stays. It is what `GET /v1/ingestions/{id}?space_id=` checks itself
    #: against (T4 — *"AI tự kiểm đối tượng này có thật sự nằm ở Space S"*),
    #: and what the worklist of §4.5 filters on.
    space_id: str

    #: R6 — one install per customer. Read from the environment at startup
    #: (docs/10 §2), never sent per call.
    tenant_id: str

    status: IngestionStatus

    #: `actor.user_id`, stored as an OPAQUE identifier (docs/10 §1 T5). It is
    #: a trace of who submitted, never consulted to decide anything.
    submitted_by: str

    #: When the call was accepted, i.e. after the file was fetched and
    #: verified. Also the queue's order: oldest unfinished job first.
    submitted_at: datetime

    #: Last state change. A restart's orphan sweep rewrites it, which is the
    #: honest answer — the row really did change then.
    updated_at: datetime

    #: ⭐ **NOT a copy of `space_is_private`** — read this before adding any
    #: reader of it.
    #:
    #: What it records is a DECISION about this one submission, taken once,
    #: at the moment Backend asserted the Space type: docs/10 §4.1 says the
    #: flag Backend sends is *"loại Space **tại thời điểm nộp**"*, and that
    #: *"Luật 'Space riêng thì tiền kiểm' nằm ở AI"*. So the fact is
    #: consumed when it arrives, and what survives in the row is the branch
    #: this job must take — stop in the pre-approval buffer, or go through to
    #: the shared stores.
    #:
    #: Why it is not the forbidden column: it describes an ingestion, not a
    #: Space. ⛔ Nothing may read it as *"this Space is private"*, and nothing
    #: may read it at all once the row is terminal. Whether a change of Space
    #: type should release entries already waiting is docs/10 §8 Q4, still
    #: OPEN — so this column must never be used to answer it.
    #:
    #: Why it cannot simply be left out: the pipeline runs after the call
    #: returns (§4.1 *"Chạy bất đồng bộ"*), and AI may not look the Space
    #: type up for itself (T2 — AI does not hold or consult the Space tree).
    requires_pre_approval: bool

    #: The staged copy of the file, by NAME, inside the staging directory the
    #: deployment supplies. A name and not a path: where staging lives is a
    #: per-install deployment fact (R6, the reason `schema.config`'s loaders
    #: take no default path), and a stored absolute path would be a second
    #: home for it. Cleared — set to `None` — the moment the bytes are gone,
    #: so an orphan sweep can tell a staged file apart from a leaked one.
    staged_filename: str | None = None

    #: The uploader's *"đây là bản mới của X"* (§4.1), verified against this
    #: Space before the call returned. Kept so the runner resolves the same
    #: X, and so a document that vanished in between is a LOUD refusal
    #: (`OBJECT_NOT_IN_SPACE`) rather than a silent new version chain.
    declared_previous_document_id: str | None = None

    #: Set exactly when `status is ACTIVE`: the document this submission
    #: produced.
    document_id: str | None = None

    #: Set exactly when `status is DUPLICATE`: the twin that was already
    #: there. docs/10 §4.2 — one `duplicate` status on the wire whether the
    #: twin sits in the shared store or in the pre-approval buffer; which of
    #: the two it was stays in AI's own log.
    existing_document_id: str | None = None

    #: Set exactly when `status is REJECTED` or `FAILED` — docs/10 §4.2.
    #: Typed as the enum rather than a bare string so an invented code
    #: cannot reach Backend.
    code: IngestionFailureCode | None = None
