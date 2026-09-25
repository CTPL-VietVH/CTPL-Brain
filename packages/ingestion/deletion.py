"""T2.8 — permanent deletion of one document (06 Mục 5.6, 07 Mục 6 S6).

*"Xoá vĩnh viễn — xoá tài liệu cùng mọi dữ liệu đã nạp từ nó"*: the profile,
the chunks, the vectors, and the relation links of that document. What stays
behind is a log line saying it happened: *"Nhật ký giữ lại: Việc đã xoá: ai,
khi nào, tài liệu nào, lý do. **Không giữ nội dung**"* (06 Mục 5.6).

──────────────────────────────────────────────────────────────────────────
Why this module lives in `packages/ingestion/`
──────────────────────────────────────────────────────────────────────────

`docs/08` puts T2.8 in **Nhóm 2 — Ingestion v2** (it sits between T2.7 and
T2.9, before the `### Nhóm 3 — Retrieval v2` heading). It also belongs here
structurally: deletion is the exact mirror of `promotion.py`, reuses the same
two store ports, and Retrieval never writes to either store. A copy of this
logic in `packages/retrieval/` would be a write path inside the read service.

──────────────────────────────────────────────────────────────────────────
The order, and why each step is where it is
──────────────────────────────────────────────────────────────────────────

S6 (07 Mục 6), as shortened by 08 dòng 212 for the two physical stores:
**kho vector → (quan hệ + hồ sơ, MỘT giao dịch) → dọn nền.**

   -1. _check_object_in_space(...)        ← T4, docs/10 §1; no store write
    0. deletion_log.record_started(...)   ← trace, not one of the three steps
    1. vector store  — the document stops being findable HERE
    2. PostgreSQL, ONE transaction — relations + profile
    3. background cleanup — the bytes actually go
    4. deletion_log.mark_purged(...)

S6's reason, verbatim: *"đường đọc là tính phạm vi quyền → tìm trong kho
vector → kéo họ hàng ở kho đồ thị → đọc hồ sơ để dựng đơn vị đọc và dẫn
nguồn. Cổng chặn nằm ở KHO VECTOR."* Delete the vectors first and the next
question already cannot reach the document; delete the profile first and the
chunks stay findable while the step that builds the reading unit has nothing
to read — the dangling pointer S6 exists to prevent (điều cấm #17).

**Step 0 is not a fourth store write dressed up as one.** It runs first for
two reasons that both disappear if it runs later:

* `space_id` and `tenant_id` only exist until step 2 commits. A log line
  written afterwards could not say which Space lost a document.
* A deletion interrupted between steps leaves a half-deleted document that
  nothing else in the system will ever mention. NT2's third clause — *"chỗ
  nào bỏ sót gây hại thì phải NHÌN THẤY ĐƯỢC"* — is what forbids that, and a
  log row with `purge_completed_at` still empty is what makes it visible.

**The log is never read to decide what to do.** Every step below runs on
every call regardless of what the log says, so QT1's test passes: delete the
log and the system still deletes correctly. That is also what makes a repeat
call converge without any "have I already done this?" branch to get wrong.

──────────────────────────────────────────────────────────────────────────
No shared transaction across the Qdrant↔PostgreSQL boundary
──────────────────────────────────────────────────────────────────────────

07 Mục 2 dòng 65 calls it *"ranh giới duy nhất còn thiếu giao dịch chung"*.
There is no 2PC here and none is wanted. Correctness rests on three things
instead, and `tests/t2_8_deletion/` exists to prove each of them:

1. a fixed order, so every interrupted state is a harmless one;
2. every step re-runnable — S6: *"mỗi bước phải làm lại được mà không hỏng
   thêm, để hỏng giữa chừng thì chạy tiếp chứ không phải dọn tay"*;
3. fault-injection tests that actually cut the process at each step.

──────────────────────────────────────────────────────────────────────────
What this module deliberately does NOT do
──────────────────────────────────────────────────────────────────────────

**It does not check permissions.** 06 Mục 5.6 says who may do this (*"Admin,
và Manager của Space chứa tài liệu"*), but 08 T2.10 records that the write
surface carrying Manager actions — permanent deletion named among them — has
no owner yet and that *"phải quyết tường minh chứ không mặc định"*. Inventing
a permission gate here would be that default decision. `deleted_by` arrives
as a caller-supplied identity for the log; authorising it is the caller's job.

**This is not the same thing as the `space_id` check the module DOES do.**
docs/10 §1 T4 draws that line explicitly: BE (the caller) is trusted about
*who* — role, vai trò, quyền; AI checks *where* — whether `document_id`
actually lives in the `space_id` the caller named, because that fact belongs
to AI's own data, not BE's. Checking role would be re-deciding BE's job;
checking Space membership is this module refusing to act on a BE mistake
that hands it mismatched `document_id`/`space_id`.

**It does not clean conversation history.** 06 Mục 5.6 limit 2, and Điểm mở
#15 (06 Mục 10) — a known, accepted v1 limitation, not a bug.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from schema.deletion_log import DeletionLogEntry
from schema.store_schema import CHUNK_DOCUMENT_ID_FIELD

__all__ = [
    "BackgroundCleanup",
    "DeletableProfileStore",
    "DeletionLog",
    "DeletionOutcome",
    "DeletionRequestIncomplete",
    "InMemoryBackgroundCleanup",
    "InMemoryDeletableProfileStore",
    "InMemoryDeletionLog",
    "InMemoryVectorStoreDeleter",
    "ObjectNotInSpace",
    "ProfileDeletionCounts",
    "QdrantVectorStoreDeleter",
    "VectorStoreDeleter",
    "purge_document_permanently",
]


class DeletionRequestIncomplete(Exception):
    """A field 06 Mục 5.6 requires the log to carry is missing or blank.

    Refused before anything is touched. The log line is not paperwork around
    the deletion — it is the only thing left once the deletion has run, so a
    deletion that cannot be logged is a deletion that must not start.
    """


class ObjectNotInSpace(Exception):
    """docs/10 §1 T4: the document does not actually live in `space_id`.

    Mirrors the API's `OBJECT_NOT_IN_SPACE` (docs/10 §3.5) — the reason T4
    exists at all: *"nếu BE có lỗi, ví dụ gửi space_id của Space A kèm
    document_id của một tài liệu ở Space B, thì thiếu T4 AI sẽ để một Manager
    của A gỡ tài liệu của B"*. Also raised when there is no evidence — no
    profile, no deletion_log line — that the document ever belonged to any
    Space; "unknown document_id" is not a softer case than "wrong Space".

    Always raised before `deletion_log.record_started`, so a wrong `space_id`
    leaves no trace of the attempt (docs/10 §1 T4: *"tránh xoá nhầm bản trùng
    ở Space khác"*).
    """


# --------------------------------------------------------------------------- #
# The log entry — `DeletionLogEntry` itself lives in `schema/deletion_log.py`
# now that it corresponds to a real table (CLAUDE.md Mục 6: one definition,
# in `packages/schema/`, imported above).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True, kw_only=True)
class ProfileDeletionCounts:
    """What the one PostgreSQL transaction removed. Both counts are zero on a
    second run — that is convergence, not a failure."""

    relations_deleted: int
    profile_rows_deleted: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DeletionOutcome:
    """What one call did.

    `already_completed` reports that a finished deletion was found in the log
    on entry. It is INFORMATION ONLY: the steps run either way, so a lost or
    lying log cannot leave data behind.

    The counts describe work done by THIS call, so a second call reports
    zeros. The terminal state is identical — which is what idempotent means —
    and reporting zeros is the honest way to say the first call had already
    done it.
    """

    document_id: str
    log_entry: DeletionLogEntry
    profile_was_present: bool
    vector_points_deleted: int
    relations_deleted: int
    profile_rows_deleted: int
    purge_settled: bool
    already_completed: bool


# --------------------------------------------------------------------------- #
# Ports — one per durable effect, which is also what makes "cut the process at
# one step" a definable thing (see `tests/fault_injection.py`).
# --------------------------------------------------------------------------- #


class VectorStoreDeleter(Protocol):
    """Step 1. Removes every point of one document from the vector store.

    Must be idempotent: deleting a document with no points left is a no-op
    returning 0, never an error.
    """

    def delete_document_points(self, document_id: str) -> int: ...


class DeletableProfileStore(Protocol):
    """Step 2, and the whole of it.

    ⭐ **`delete_document_and_relations` is the transaction boundary.** One
    call removes every relation touching the document AND the profile row, or
    removes neither. 07 Mục 2 dòng 65 is what makes this one atomic unit:
    *"hai bước xoá quan hệ và hồ sơ nằm chung một cơ sở dữ liệu nên thành một
    giao dịch nguyên khối"*.

    Relations are removed in BOTH directions. A link is deleted when either
    endpoint is — 06 Mục 5.6 says *"các liên kết quan hệ của nó"*, and a
    surviving `B --amends--> A` would point at a document that no longer
    exists (the two foreign keys in `store_schema.py` refuse exactly that).
    """

    def get_document(self, document_id: str) -> Any | None: ...

    def delete_document_and_relations(self, document_id: str) -> ProfileDeletionCounts: ...


class BackgroundCleanup(Protocol):
    """Step 3 — *"dọn nền"*.

    S6: *"xoá ở kho vector thường chỉ là xoá logic, dữ liệu chỉ thật sự mất
    sau bước dọn nền"*. Returns whether the engines report the space actually
    reclaimed; `False` is not an error, it means run me again later.
    """

    def purge(self, document_id: str) -> bool: ...


class DeletionLog(Protocol):
    """The log 06 Mục 5.6 requires.

    `record_started` is INSERT-IF-ABSENT, and that is the whole of "không
    nhân đôi log": a retry must not create a second line, and must not
    overwrite the first — the first one names who actually ordered the
    deletion, and a retry by an operator is not that person.

    ⭐ `open_entries_for_space` is the ONE read this module's callers make to
    find work, and it is deliberately not the same thing as "what to do next"
    for a single document: `purge_document_permanently` still never consults
    the log to decide its own steps (see the module docstring). It exists
    because a HALF-purged document leaves no other trace — see that method.
    """

    def get(self, document_id: str) -> DeletionLogEntry | None: ...

    def record_started(self, entry: DeletionLogEntry) -> DeletionLogEntry: ...

    def mark_purged(self, document_id: str, *, at: datetime) -> DeletionLogEntry: ...

    def open_entries_for_space(self, space_id: str) -> list[DeletionLogEntry]: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _check_object_in_space(
    *,
    document_id: str,
    space_id: str,
    profile: Any | None,
    previous: DeletionLogEntry | None,
) -> None:
    """docs/10 §1 T4: *"AI tự kiểm 'đối tượng này có thật sự nằm ở Space S
    không'"*.

    Checked against whichever piece of evidence survives the run:

    1. the profile, when one is still present — the common case;
    2. failing that, the deletion_log line a previous, interrupted call
       already wrote — step 0 records `space_id` before step 2 removes the
       profile, so the line outlives it (the whole point of the BẪY this
       function exists to close: a resumed call cannot re-derive `space_id`
       from a profile that is already gone);
    3. failing both, the document has no evidence of ever belonging to any
       Space, and is refused the same way a Space mismatch is — "does not
       exist" is not a softer outcome than "wrong Space".
    """
    if profile is not None:
        actual_space_id = getattr(profile, "space_id", None)
    elif previous is not None:
        actual_space_id = previous.space_id
    else:
        raise ObjectNotInSpace(
            f"document_id={document_id!r} has no profile and no deletion_log "
            f"line — nothing shows it ever belonged to space_id={space_id!r}."
        )
    if actual_space_id != space_id:
        raise ObjectNotInSpace(
            f"document_id={document_id!r} belongs to space_id={actual_space_id!r}, "
            f"not the space_id={space_id!r} given for this deletion."
        )


# --------------------------------------------------------------------------- #
# The deletion
# --------------------------------------------------------------------------- #


def purge_document_permanently(
    document_id: str,
    *,
    space_id: str,
    deleted_by: str,
    reason: str,
    profile_store: DeletableProfileStore,
    vector_store: VectorStoreDeleter,
    background_cleanup: BackgroundCleanup,
    deletion_log: DeletionLog,
    clock: Callable[[], datetime] = _utc_now,
) -> DeletionOutcome:
    """Delete one document from both stores, in S6 order, re-runnably.

    Every step runs on every call. Nothing here asks "was this already done?"
    before acting — each step is a no-op when its work is already done, which
    is a stronger guarantee than a branch that has to be right.

    `deleted_by` is recorded, not checked — that identity is asserted by the
    Backend (docs/10 §1 T1–T2: BE authenticates the person, AI executes).
    `space_id` IS checked: this module verifies the document actually belongs
    to the Space named, independent of who the caller claims to be (docs/10
    §1 T4). See `_check_object_in_space` for the two-source, then-refuse
    order that check follows.

    Raises:
        DeletionRequestIncomplete: `document_id`, `space_id`, `deleted_by` or
            `reason` is blank. Raised before the first step, so nothing is
            touched.
        ObjectNotInSpace: the document belongs to a different Space than
            `space_id` claims, or there is no evidence it belongs to any
            Space at all. Raised before `deletion_log.record_started`, so a
            wrong `space_id` leaves no trace of the attempt.
    """
    document_id = _require(document_id, "document_id")
    space_id = _require(space_id, "space_id")
    deleted_by = _require(deleted_by, "deleted_by")
    reason = _require(reason, "reason")

    previous = deletion_log.get(document_id)
    already_completed = previous is not None and previous.purge_completed_at is not None

    # ---- T4: the object must actually live where the caller says it does --
    profile = profile_store.get_document(document_id)
    _check_object_in_space(
        document_id=document_id, space_id=space_id, profile=profile, previous=previous
    )

    # ---- 0. The trace, before step 2 destroys what it needs to name ------
    log_entry = deletion_log.record_started(
        DeletionLogEntry(
            document_id=document_id,
            deleted_by=deleted_by,
            reason=reason,
            requested_at=clock(),
            space_id=getattr(profile, "space_id", None),
            tenant_id=getattr(profile, "tenant_id", None),
        )
    )

    # ---- 1. Vector store — the gate closes here --------------------------
    # No store-stamp check, unlike `write_to_qdrant`. That check protects the
    # collection from vectors of a different model; deleting by document id
    # cannot corrupt anything, and refusing to delete because the embedding
    # config drifted would block an obligation (06 Mục 5.6) over a mismatch
    # that deletion is not the cause of and cannot make worse.
    vector_points_deleted = vector_store.delete_document_points(document_id)

    # ---- 2. PostgreSQL — relations + profile, ONE transaction ------------
    counts = profile_store.delete_document_and_relations(document_id)

    # ---- 3. Dọn nền — where the bytes actually go ------------------------
    purge_settled = background_cleanup.purge(document_id)

    # ---- 4. Close the trace, only once step 3 says it is really done ----
    if purge_settled:
        log_entry = deletion_log.mark_purged(document_id, at=clock())

    return DeletionOutcome(
        document_id=document_id,
        log_entry=log_entry,
        profile_was_present=profile is not None,
        vector_points_deleted=vector_points_deleted,
        relations_deleted=counts.relations_deleted,
        profile_rows_deleted=counts.profile_rows_deleted,
        purge_settled=purge_settled,
        already_completed=already_completed,
    )


def _require(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeletionRequestIncomplete(
            f"{field_name} is blank. 06 Mục 5.6 requires the log to keep "
            f'"ai, khi nào, tài liệu nào, lý do" — a deletion that cannot be '
            f"logged does not start."
        )
    return value


# --------------------------------------------------------------------------- #
# Real adapter — Qdrant
# --------------------------------------------------------------------------- #


class QdrantVectorStoreDeleter:
    """`VectorStoreDeleter` over a live Qdrant collection.

    The mirror of `promotion.QdrantVectorStoreWriter`, and just as thin.
    Deletes by FILTER on the `document_id` payload field rather than by point
    id: the ids of a document's chunks are only knowable by asking the store,
    and a delete-by-filter is idempotent by construction — run it twice and
    the second run matches nothing.

    The count is read before the delete purely for the report; Qdrant's
    delete does not return one. A count that raced with a concurrent write
    would be off, which is why `DeletionOutcome` calls it work done, not a
    guarantee about the store.
    """

    def __init__(self, *, qdrant_client: Any, collection_name: str) -> None:
        self._client = qdrant_client
        self._collection_name = collection_name

    def delete_document_points(self, document_id: str) -> int:
        """`wait=True` is not a removable performance knob: it is what makes
        this call return only AFTER the delete has applied across the
        collection. Without it, a `count()` or `search()` immediately after
        could still observe the pre-delete state — documented Qdrant
        behaviour, not a guess.
        """
        from qdrant_client import models

        selector = models.Filter(
            must=[
                models.FieldCondition(
                    key=CHUNK_DOCUMENT_ID_FIELD, match=models.MatchValue(value=document_id)
                )
            ]
        )
        before = self._client.count(
            collection_name=self._collection_name, count_filter=selector, exact=True
        ).count
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=models.FilterSelector(filter=selector),
            wait=True,
        )
        return before


# --------------------------------------------------------------------------- #
# In-memory implementations — tests and single-process runs, NOT the real
# stores (same disclaimer as `promotion.InMemorySharedProfileStore`).
# --------------------------------------------------------------------------- #


class InMemoryVectorStoreDeleter:
    """`VectorStoreDeleter` over `promotion.InMemoryVectorStoreWriter`.

    Takes the writer itself, not a copy of its dict, so a test that promotes
    and then deletes is acting on ONE store — the same property the real
    deployment has, and the one a second dict would quietly lose.
    """

    def __init__(self, vector_writer: Any) -> None:
        self._writer = vector_writer

    def delete_document_points(self, document_id: str) -> int:
        doomed = [
            chunk_id
            for chunk_id, chunk in self._writer.points.items()
            if chunk.document_id == document_id
        ]
        for chunk_id in doomed:
            del self._writer.points[chunk_id]
        return len(doomed)


class InMemoryDeletableProfileStore:
    """Adds the S6 delete to `promotion.InMemorySharedProfileStore`.

    A subclass rather than an edit to that class: T2.7 is closed, and the
    promote path has no business growing a delete method it never calls.

    `delete_document_and_relations` stages everything and applies it in one
    block — the in-memory stand-in for one PostgreSQL transaction, exactly as
    `write_document_and_relations` does for the write side.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        # Everything else — `get_document`, `documents_in`, the fingerprint
        # index — stays the wrapped store's behaviour, unduplicated.
        return getattr(self._inner, name)

    def delete_document_and_relations(self, document_id: str) -> ProfileDeletionCounts:
        documents = self._inner._documents
        relations = self._inner._relations

        # Both endpoints: a link is deleted when EITHER side is. The two
        # foreign keys in `schema/store_schema.py` (both ON DELETE CASCADE)
        # are what would enforce this in PostgreSQL.
        doomed_relations = [
            relation_id
            for relation_id, relation in relations.items()
            if document_id in (relation.from_document_id, relation.to_document_id)
        ]
        profile_present = document_id in documents

        # Apply — nothing above this line changed anything.
        for relation_id in doomed_relations:
            del relations[relation_id]
        if profile_present:
            del documents[document_id]

        return ProfileDeletionCounts(
            relations_deleted=len(doomed_relations),
            profile_rows_deleted=1 if profile_present else 0,
        )


class InMemoryDeletionLog:
    """`DeletionLog` in a dict, keyed by `document_id`.

    The key IS the no-duplicate rule: one document can only be permanently
    deleted once, so a second `record_started` for the same id finds the
    first line and leaves it alone. The proposed table makes `document_id`
    the primary key for the same reason — 08 dòng 210 wants this kind of
    guarantee at the storage layer, *"không chỉ kiểm tra ở tầng ứng dụng"*.
    """

    def __init__(self) -> None:
        self._entries: dict[str, DeletionLogEntry] = {}

    def get(self, document_id: str) -> DeletionLogEntry | None:
        return self._entries.get(document_id)

    def record_started(self, entry: DeletionLogEntry) -> DeletionLogEntry:
        existing = self._entries.get(entry.document_id)
        if existing is not None:
            # INSERT-IF-ABSENT. Keeping the first line is not a detail: it
            # names who ordered the deletion, and an operator re-running a
            # crashed command is not that person.
            return existing
        self._entries[entry.document_id] = entry
        return entry

    def open_entries_for_space(self, space_id: str) -> list[DeletionLogEntry]:
        """Every line of this Space whose `purge_completed_at` is still empty.

        These are the deletions that STARTED and did not finish — and for a
        document already past step 2 they are the only evidence left that work
        remains: the profile is gone, so nothing that reads the `document`
        table can see it any more. `space_deletion.delete_space` unions this
        with the profile-derived worklist for exactly that reason.

        `space_id` is compared against the value step 0 recorded, which is why
        step 0 has to run before step 2 destroys the profile it reads it from.
        Rows whose `space_id` is `None` (no profile at the time, 07's optional
        column) belong to no Space and are never returned — a Space-wide sweep
        must not adopt a deletion it cannot prove was in its own Space.

        The real implementation reads the partial index
        `deletion_log_unfinished_idx` (`schema/store_schema.py`), which holds
        exactly the open rows and no others.
        """
        return [
            entry
            for entry in self._entries.values()
            if entry.space_id == space_id and entry.purge_completed_at is None
        ]

    def mark_purged(self, document_id: str, *, at: datetime) -> DeletionLogEntry:
        entry = self._entries[document_id]
        if entry.purge_completed_at is not None:
            return entry  # already closed; the first completion time stands
        closed = DeletionLogEntry(
            document_id=entry.document_id,
            deleted_by=entry.deleted_by,
            reason=entry.reason,
            requested_at=entry.requested_at,
            space_id=entry.space_id,
            tenant_id=entry.tenant_id,
            purge_completed_at=at,
        )
        self._entries[document_id] = closed
        return closed

    def entries(self) -> list[DeletionLogEntry]:
        return list(self._entries.values())


class InMemoryBackgroundCleanup:
    """`BackgroundCleanup` that records its calls.

    `settles=False` models the honest real-world case — S6 says the vector
    store's delete is usually logical and the bytes go later — so a test can
    check that the log stays open until the engines actually report done.
    """

    def __init__(self, *, settles: bool = True) -> None:
        self._settles = settles
        self.calls: list[str] = []

    def purge(self, document_id: str) -> bool:
        self.calls.append(document_id)
        return self._settles
