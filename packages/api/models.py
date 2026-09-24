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

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Actor",
    "ActorRole",
    "DocumentDeletionOutcome",
    "DocumentDeletionRequest",
    "DocumentDeletionResponse",
    "MetaResponse",
    "SpaceDeletionRequest",
    "SpaceDeletionResponse",
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


class SpaceDeletionResponse(BaseModel):
    """Every field of `space_deletion.SpaceDeletionProgress`, unabridged.

    docs/10 §4.0 asks `GET /v1/spaces/{space_id}` for *"trạng thái và tiến độ
    (số tài liệu đã xoá / còn lại)"*. The two "remaining" counts are kept
    apart on purpose — see `SpaceDeletionProgress`: profiles still carrying
    the `space_id`, and purges whose background cleanup has not reported done.
    Collapsing them would hide the second, which is the one with no other
    trace anywhere in the system.
    """

    model_config = ConfigDict(extra="forbid")

    space_id: str
    state: str
    documents_purged: int
    documents_already_purged: int
    documents_remaining: int
    unfinished_purges_remaining: int
    buffer_entries_discarded: int
    completed: bool


class SpaceStatusResponse(BaseModel):
    """`GET /v1/spaces/{space_id}` — read-only progress.

    No `documents_purged`: the number of finished deletions is not readable
    through the `DeletionLog` Protocol (it exposes the OPEN lines only), and
    inventing it here would mean either a second query path into the log or a
    number that is quietly wrong. Reported as an escalation instead.
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
