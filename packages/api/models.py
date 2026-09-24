"""The wire shapes of docs/10 — request bodies and response bodies.

Every field name here comes from docs/10 §3.2, §4.0, §5.6 or §3.6, and every
one of them is also the name of a field that already exists somewhere in
`packages/schema/` or in a business result dataclass. That overlap is checked
by a test rather than by eye (`tests/api/test_h_wire_names_follow_schema.py`):
CLAUDE.md Mục 6 — *"Tên trường định nghĩa đúng một lần trong `packages/schema/`;
không service nào tự khai báo lại"* — and a pydantic model IS a second
declaration unless something keeps the two spellings tied together. The bug
that rule exists for (`doc_profile_code` / `profile_code`) costs nothing to
create here and returns an empty result with no error.

⚠️ `extra="forbid"` on every request model. An unknown field is refused, not
ignored: `{"space_ids": "A"}` sent to an endpoint expecting `space_id` would
otherwise be read as "no scope at all", and docs/10 §3.3 is explicit that
missing scope must never be softened. Refusing the unknown field turns a typo
into a message that names it — the same reason `schema.config._check_keys`
refuses an unknown config key instead of skipping it.

⛔ What these models must NEVER grow: a field that carries a permission
verdict into AI's stored data. `actor` is read, recorded as a trace
(`deleted_by`), and dropped at the end of the call (QT1, docs/10 §1 T5).
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Actor",
    "ActorRole",
    "DocumentDeletionOutcome",
    "DocumentDeletionRequest",
    "DocumentDeletionResponse",
    "IngestionSource",
    "IngestionStatusResponse",
    "IngestionSubmissionRequest",
    "IngestionSubmissionResponse",
    "IngestionSuggestions",
    "MetaResponse",
    "SpaceDeletionRequest",
    "SpaceRegistrationRequest",
    "SpaceRegistrationResponse",
    "SpaceStatusResponse",
]


class ActorRole(str, Enum):
    """docs/10 §3.2 — *"vai trò BE khẳng định người này đang dùng cho đúng thao
    tác này, ở đúng Space nêu trong lời gọi"*.

    ⛔ AI does not check this value against the operation. docs/10 §1 T2: *"BE
    quyết quyền, AI thực thi quyền ... AI **không kiểm lại** người dùng, vai
    trò hay cây Space."* It is validated only as a spelling — an unknown role
    means Backend and AI disagree about the vocabulary, which is worth a loud
    refusal — and then recorded as a trace.

    It has no home in `packages/schema/`, and must not get one: a role is a
    permission fact, and QT1 keeps permission facts out of AI's data.
    """

    VIEWER = "viewer"
    CONTRIBUTOR = "contributor"
    MANAGER = "manager"
    ADMIN = "admin"


class Actor(BaseModel):
    """docs/10 §3.2 — who Backend says is making this call.

    `user_id` is *"một định danh không trong suốt: không tra, không diễn giải"*
    (§1 T5). It is written into `deleted_by` and into the deletion log, and
    nothing in AI ever looks it up.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1)
    acting_as: ActorRole


class SpaceRegistrationRequest(BaseModel):
    """`POST /v1/spaces` — docs/10 §4.0."""

    model_config = ConfigDict(extra="forbid")

    space_id: str = Field(min_length=1)
    actor: Actor


class SpaceRegistrationResponse(BaseModel):
    """What the register now says about this Space.

    Deliberately the same body on the first call and on every repeat: docs/10
    §4.0 — *"Gọi lại cùng `space_id` đang dùng → trả kết quả như lần đầu
    (idempotent)"*. A `201` first and a `200` after would make the two calls
    distinguishable, which is exactly what idempotent says they are not.
    """

    model_config = ConfigDict(extra="forbid")

    space_id: str
    state: str


class SpaceDeletionRequest(BaseModel):
    """`DELETE /v1/spaces/{space_id}` — docs/10 §4.0.

    `reason` is mandatory *"vì nhật ký giữ lý do"* (§5.6, 06 Mục 5.6): every
    document removed by this call gets a log line whose reason is built from
    it, and a deletion that cannot be explained does not start.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)
    actor: Actor


class SpaceStatusResponse(BaseModel):
    """`GET /v1/spaces/{space_id}` — read-only progress.

    ⭐ **Also the body of `DELETE /v1/spaces/{space_id}` (202)** — PO chốt
    24/9/2026, written into docs/10 §4.0: *"**Thân phản hồi của `DELETE`
    (202) giống hệt thân của `GET`**, để BE chỉ phải hiểu một dạng."* Before
    that decision `DELETE` answered with the whole `SpaceDeletionProgress`
    object; it could, because the deletion ran inside the request. Now that
    it runs in the background there is nothing honest to say about "how many
    did THIS call delete" — the answer at `202` time is always zero — so the
    only meaningful answer is the same progress snapshot `GET` returns.

    No `documents_purged`: the number of finished deletions is not readable
    through the `DeletionLog` Protocol (it exposes the OPEN lines only), and
    inventing it here would mean either a second query path into the log or a
    number that is quietly wrong. Still owed to §4.0 (*"số tài liệu đã xoá /
    còn lại"*) and still an escalation — it belongs to the task that opens
    that Protocol.
    """

    model_config = ConfigDict(extra="forbid")

    space_id: str
    state: str
    documents_remaining: int
    unfinished_purges_remaining: int


class DocumentDeletionOutcome(str, Enum):
    """docs/10 §5.6 — `{ outcome: "deleted" | "already_deleted" }`."""

    DELETED = "deleted"
    ALREADY_DELETED = "already_deleted"


class DocumentDeletionRequest(BaseModel):
    """`DELETE /v1/documents/{document_id}` — docs/10 §5.6.

    `space_id` is not decoration and not a permission claim: it is the fact AI
    checks for itself (§1 T4). Backend says *who*; AI says *whether that
    document is actually in that Space*, and refuses with
    `OBJECT_NOT_IN_SPACE` when it is not.
    """

    model_config = ConfigDict(extra="forbid")

    space_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    actor: Actor


class DocumentDeletionResponse(BaseModel):
    """docs/10 §5.6 — *"`false` là bình thường, vì Qdrant tự nén theo lịch
    riêng"*.

    `background_cleanup_complete=False` is a fact about the engines, not a
    failure: 07 Mục 6 S6 only considers the obligation discharged once that
    step has run, so the honest answer is to say it has not yet.
    """

    model_config = ConfigDict(extra="forbid")

    outcome: DocumentDeletionOutcome
    background_cleanup_complete: bool


class IngestionSource(BaseModel):
    """`POST /v1/ingestions` → `source` — docs/10 §4.1, chốt 24/9/2026.

    *"`url` là **đường dẫn có chữ ký, hạn ngắn** (presigned GET) do BE sinh
    cho đúng một file."*

    ⛔ None of these five fields has a home in `packages/schema/`, and none
    may get one. They describe a TRANSFER, not a document: `url` is a
    temporary permission, `sha256`/`size_bytes` are checked once and thrown
    away, `filename` is a string a person typed (and is explicitly NOT the
    document's title — §4.2), and `content_type` is the sender's claim about
    bytes this service identifies for itself by extension. `ingestion_record`
    stores not one of them.

    `content_type` is accepted and deliberately UNUSED: refusing a
    submission because Backend sent `application/octet-stream` would reject
    files the readers handle perfectly, and trusting it to choose a reader
    would put a second format decision beside `reader.readers.doc_file`'s.
    It is part of the contract, so it is part of the model; the field being
    inert is the point, not an oversight.
    """

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    sha256: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    filename: str = Field(min_length=1)
    content_type: str = Field(min_length=1)


class IngestionSubmissionRequest(BaseModel):
    """`POST /v1/ingestions` — docs/10 §4.1.

    ⛔ **No `title` and no `doc_number`** (PO chốt 24/9/2026, escalation E3).
    §4.2 is explicit that both are AI's to suggest: *"`title` và `doc_number`
    do AI gợi ý (07 §2.1 ...) — BE **không** gửi chúng khi nộp"*. Adding them
    to this model would move the decision to Backend and quietly make 07 §2.1
    wrong about who writes those fields.

    `space_is_private` is Backend's statement about the Space *at this
    moment* — §4.1: *"loại Space **tại thời điểm nộp**"*. AI consumes it here
    and does not store it; what survives is the branch this submission takes
    (`ingestion_record.requires_pre_approval`, which explains the
    difference). Backend sends it rather than AI looking it up because T2
    keeps the Space tree on Backend's side.
    """

    model_config = ConfigDict(extra="forbid")

    source: IngestionSource
    space_id: str = Field(min_length=1)
    space_is_private: bool
    actor: Actor
    declared_previous_document_id: str | None = None


class IngestionSubmissionResponse(BaseModel):
    """`202` — docs/10 §4.1: `{ ingestion_id, status: "processing" }`.

    `status` is a plain `str` carrying `wire_status(...)`, not an enum of its
    own: the values belong to `schema.ingestion_record`, and a second
    enumeration here would be a second list to keep in step.
    """

    model_config = ConfigDict(extra="forbid")

    ingestion_id: str
    status: str


class IngestionSuggestions(BaseModel):
    """`suggestions` — docs/10 §4.2, the input to *"máy gợi ý, người xác
    nhận"* (06 §5.2 GĐ5).

    ⚠️ `title` and `doc_number` are `null` and will stay `null` until the
    extractor for them exists (T2.4b). PO chốt 24/9/2026: *"Khi bộ trích hai
    trường này chưa có, AI trả `null`, **không** lấy tên file giả làm tên văn
    bản."* A filename dressed as a title is worse than an empty box, because
    a Manager confirming the screen would never notice they had approved one.

    The two `*_source` fields travel with their dates and are not decoration:
    06 §6.4 wants the reader told when a date is the ingestion date standing
    in for one nobody could find.
    """

    model_config = ConfigDict(extra="forbid")

    category_labels: list[str]
    issued_date: date | None
    issued_date_source: str | None
    effective_date: date | None
    effective_date_source: str | None
    title: str | None
    doc_number: str | None


class IngestionStatusResponse(BaseModel):
    """`GET /v1/ingestions/{ingestion_id}?space_id=` — docs/10 §4.2.

    Every field is always present, `null` where it does not apply, rather
    than the body changing shape per status. §4.2 lists what comes "kèm
    theo" each status; a stable shape says the same thing and gives Backend
    one parser instead of six. What must NOT happen is a field carrying a
    value it has no business carrying — a `document_id` on a `rejected`
    submission would name a document that was never created.

    `relations_scan_state` is read from the document profile, never stored on
    the ingestion row: GĐ7 keeps running after the row is terminal (06 §5.1),
    so a copy here would be the stale one (NT3).
    """

    model_config = ConfigDict(extra="forbid")

    ingestion_id: str
    status: str
    code: str | None = None
    document_id: str | None = None
    existing_document_id: str | None = None
    suggestions: IngestionSuggestions | None = None
    relations_scan_state: str | None = None


class MetaResponse(BaseModel):
    """`GET /v1/meta` — docs/10 §3.6.

    `limits` is a free-form object because its contents grow with the surface:
    today it carries what Ingestion publishes, and `max_recent_turns`, the
    `conversation_state` ceilings and the maximum file size join it when the
    endpoints that own them exist. Declaring those keys now with invented
    numbers would be worse than leaving them out — Backend is told to read
    this endpoint precisely so it *"không phải đoán K"*.
    """

    model_config = ConfigDict(extra="forbid")

    ready: bool
    not_ready_reason: str | None
    contract_version: str
    limits: dict[str, object]
