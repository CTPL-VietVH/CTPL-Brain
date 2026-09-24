"""T2.11 (b) — deleting a whole Space (docs/10 §4.0, 06 Mục 5.6, 08 T2.11).

06 Mục 5.6: *"Khi Backend xoá một Space, AI xoá vĩnh viễn **từng tài liệu có
`space_id` đó** theo đúng quy trình ở mục này, cùng tài liệu còn trong vùng
đệm tiền kiểm và các mục hàng việc của Space."*

This module is a LOOP AROUND `deletion.purge_document_permanently`, not a
second deletion path. Every document still goes through S6 in S6's order and
leaves its own log line (docs/10 §4.0 step 2: *"mỗi tài liệu một dòng nhật ký
xoá"*). A bulk "delete everything in this Space" against either store would
be a second way to delete, free to drift from the audited one.

──────────────────────────────────────────────────────────────────────────
The four steps, and what each one is NOT
──────────────────────────────────────────────────────────────────────────

docs/10 §4.0, verbatim order:

    1. mark the Space `BEING_DELETED`   ← closes the door first, see below
    2. purge every document whose PROFILE carries this `space_id`
    3. drop the pre-approval buffer entries of the Space
       (and the T2.9 worklist items — see the TODO, that queue does not exist)
    4. mark the Space `DELETED`

**Step 1 comes first, and that ordering is the mechanism.** From that moment
every submission into the Space is refused by
`space_registry.assert_space_accepts_documents` (docs/10 §4.0: *"Từ lúc này
mọi lời gọi nộp tài liệu hay thao tác ghi vào Space trả `409
SPACE_BEING_DELETED`"*). Marking it last instead would let a document land
in the Space after the loop had already walked past it — and nothing would
ever mention it again.

**Step 2 selects by `space_id` ON THE DOCUMENT PROFILE, and by nothing
else.** docs/10 §4.0, ràng buộc chống xoá nhầm 1: *"Chọn tài liệu cần xoá
**chỉ theo `space_id` trên hồ sơ tài liệu** — không theo vân tay nội dung,
tên hay số hiệu. Bản trùng khít ở Space khác là tài liệu khác (`document_id`
khác, 06 §5.7) và **không bị đụng tới**."* A byte-identical twin in another
Space is a different document with a different `document_id`; selecting by
`content_fingerprint` would delete it too, silently, and no test the deleted
Space can run would ever notice.

**No Space child is walked.** docs/10 §4.0, ràng buộc 2: *"AI **không tự suy
ra phải xoá Space con**. Xoá Space nào thì BE gọi riêng cho Space đó — cây là
dữ liệu của BE."* This module could not walk the tree even if it wanted to:
the register holds no tree (see `space_registry.py`), by design.

──────────────────────────────────────────────────────────────────────────
"Chạy nền" — what makes calling this again safe, and what it is not
──────────────────────────────────────────────────────────────────────────

docs/10 §4.0: `DELETE /v1/spaces/{space_id}` returns `202` *"và chạy nền"*;
calling it twice *"trả tiến độ hiện tại, không lỗi, không xoá lặp"*.

`delete_space` is the unit of work that background runner calls — possibly
many times, and it reaches the same end state whether it is called once or
ten times. The mechanism is the one T2.8 already uses, not a new one:

* **the worklist is re-derived from the stores on every call**, never carried
  in memory between calls. A document finished by an earlier call is in
  neither source below, so it is not in the next worklist — there is no
  cursor to lose and no "have I done this one?" flag to get wrong;
* **each document's purge is itself re-runnable** (S6, `deletion.py`), so a
  process cut in the middle of one document is resumed by the next call;
* **`already_completed` is not an error.** It means a finished deletion was
  found in the log — information, not failure — so the loop moves on.

──────────────────────────────────────────────────────────────────────────
The worklist has TWO sources, and the second one is not optional
──────────────────────────────────────────────────────────────────────────

    1. documents whose PROFILE carries this `space_id`
    2. document ids on OPEN deletion-log lines of this `space_id`
       (`purge_completed_at IS NULL`), deduplicated against the first

Source 2 closes a hole the first source cannot see. One document's purge runs
`vector store → (relations + profile, one transaction) → dọn nền`; cut the
process between the transaction and `dọn nền` and the profile is already
gone, so **source 1 has nothing left to report** — while S6 says the
obligation is not discharged: *"nghĩa vụ xoá dữ liệu cá nhân chỉ được coi là
hoàn thành khi bước dọn nền ĐÃ CHẠY XONG."* The open log line is the only
remaining trace of that unfinished work, which is precisely why step 0 writes
`space_id` into it before step 2 destroys the profile it reads it from.

Those ids go through the SAME `purge_document_permanently` as everything
else. Its `_check_object_in_space` already handles a missing profile by
falling back to the log line's `space_id` (T2.8/T4,
`tests/t2_8_deletion/test_p`), and its steps are individually re-runnable, so
re-running one only finishes the `dọn nền` that was left: the vector delete
matches nothing, the transaction removes no rows.

**`completed` therefore needs both sources empty.** A Space with no profiles
left but an open log line is not finished — reporting it `DELETED` would tell
Backend the bytes are gone while the engines have not said so, and Backend's
next step is to delete the Space on its side (docs/10 §4.0, *"Thứ tự phía
BE"*), after which nobody would ever ask about that Space again.

⚠️ What this is NOT: a thread, a task queue, or a scheduler. There is no
owner yet for the process that calls it (T2.10 — the write surface — and the
HTTP layer of docs/10 are not built). Inventing one here would be choosing
an execution model the plan has not chosen.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from ingestion.deletion import (
    BackgroundCleanup,
    DeletableProfileStore,
    DeletionLog,
    VectorStoreDeleter,
    purge_document_permanently,
)
from ingestion.pre_approval_buffer import PreApprovalBuffer
from ingestion.relations_scan import SpaceDocumentSource
from ingestion.space_registry import (
    SpaceNotRegistered,
    SpaceRegistration,
    SpaceRegistry,
    SpaceState,
)

__all__ = [
    "SPACE_DELETION_REASON_PREFIX",
    "SpaceDeletionProgress",
    "begin_space_deletion",
    "delete_space",
]


#: Prefix every per-document log line carries, so a document removed because
#: its whole Space went away is distinguishable in the deletion log from one
#: a Manager deleted on its own.
#:
#: The value is Vietnamese, character-for-character as docs/10 §4.0 step 2
#: specifies it: *"mỗi tài liệu một dòng nhật ký xoá với lý do dạng **"xoá
#: Space: <reason>"**"*. Two reasons that is not a violation of CLAUDE.md điều
#: tuyệt đối #4, and both matter:
#:
#: (a) this is a **data value written into `deletion_log.reason`** (06 Mục
#:     5.6), not an exception message and not an identifier. The English-only
#:     rule covers source code and states its own exception for data —
#:     `reason` is composed with the Vietnamese text a Manager typed, and the
#:     person reading the log reads one language, not two.
#: (b) the spec writes this exact string, so copying it keeps the stored value
#:     comparable character-for-character with docs/10.
#:
#: PO chốt 24/9/2026 (was `"space deletion: "` until then). Everything else in
#: this module — this constant's NAME included — stays English.
SPACE_DELETION_REASON_PREFIX = "xoá Space: "


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True, kw_only=True)
class SpaceDeletionProgress:
    """What one call did, and how much is left.

    docs/10 §4.0 gives `GET /v1/spaces/{space_id}` the job of reporting
    *"trạng thái và tiến độ (số tài liệu đã xoá / còn lại)"*; these are the
    numbers that answer it.

    The counts describe THIS call, so a second call over a finished Space
    reports zeros — the same honesty `DeletionOutcome` uses in T2.8. What
    says the job is done is `completed`, not a count.

    `documents_remaining` counts profiles still carrying this `space_id`;
    `unfinished_purges_remaining` counts open deletion-log lines of this
    Space — documents whose rows are already gone but whose `dọn nền` has not
    reported done. They are two different kinds of "left to do" and collapsing
    them into one number would hide the second, which is the one with no other
    trace. `completed` is true only when both are zero.
    """

    space_id: str
    state: SpaceState
    documents_purged: int
    documents_already_purged: int
    documents_remaining: int
    unfinished_purges_remaining: int
    buffer_entries_discarded: int
    completed: bool


def begin_space_deletion(
    space_id: str, *, space_registry: SpaceRegistry
) -> SpaceRegistration:
    """Step 1 of docs/10 §4.0 on its own: **close the door**.

    Split out because the door has to close INSIDE the `DELETE` request while
    the emptying runs in the background (§4.0 returns `202` *"và chạy nền"*).
    Closing it in the background job instead would leave a window in which
    the caller has been told `202` and a submission into that Space would
    still be accepted — and the loop may already have walked past the place
    that document lands. §4.0 is explicit about the ordering: *"Từ lúc này
    mọi lời gọi nộp tài liệu hay thao tác ghi vào Space trả `409
    SPACE_BEING_DELETED`"*.

    Idempotent, in both directions of "already": a Space already
    `BEING_DELETED` stays there, and a Space already `DELETED` is returned
    untouched rather than moved backwards.

    Returns the registration AFTER the move, so the caller does not read it
    twice.

    Raises:
        SpaceNotRegistered: AI has never heard of this `space_id`. Refused
            rather than treated as "nothing to delete" — see `delete_space`.
    """
    registration = space_registry.get(space_id)
    if registration is None:
        raise SpaceNotRegistered(
            f"space_id={space_id!r} was never registered, so there is no Space to "
            f"delete (docs/10 §4.0). Refusing rather than deleting whatever happens "
            f"to carry that space_id."
        )
    if registration.state is SpaceState.DELETED:
        return registration
    return space_registry.advance_state(space_id, to=SpaceState.BEING_DELETED)


def delete_space(
    space_id: str,
    *,
    reason: str,
    deleted_by: str,
    space_registry: SpaceRegistry,
    document_source: SpaceDocumentSource,
    profile_store: DeletableProfileStore,
    vector_store: VectorStoreDeleter,
    background_cleanup: BackgroundCleanup,
    deletion_log: DeletionLog,
    pre_approval_buffer: PreApprovalBuffer,
    clock: Callable[[], datetime] = _utc_now,
) -> SpaceDeletionProgress:
    """Delete one Space: every document in it, its buffer entries, then itself.

    Call it again to continue after an interruption, and again after that to
    get the current progress — the terminal state is the same either way. See
    the module docstring for why re-deriving the worklist from TWO sources is
    what makes that true, and why a document whose profile is already gone is
    still in it.

    `documents_purged` counts documents this call FINISHED, which includes one
    whose only remaining step was the `dọn nền` an earlier call did not get to.

    `deleted_by` and `reason` are recorded, not checked. Who may delete a
    Space is Backend's decision (docs/10 §1 T1–T2: BE authenticates, AI
    executes); what AI checks for itself is WHERE — and it does, per document,
    inside `purge_document_permanently` (docs/10 §1 T4).

    Raises:
        SpaceNotRegistered: the Space was never registered. Refused rather
            than treated as "nothing to delete": a `space_id` AI has never
            heard of is a Backend mistake, and its documents — if any exist
            under that code — must not be removed on the strength of it.
    """
    # ---- 1. Close the door BEFORE emptying the room ----------------------
    # Idempotent, so it does not matter whether the HTTP layer already called
    # it inside the request (it does — see `begin_space_deletion`) or whether
    # this is a background re-run.
    registration = begin_space_deletion(space_id, space_registry=space_registry)

    if registration.state is SpaceState.DELETED:
        # Already finished, by this call's predecessor. docs/10 §4.0: a second
        # DELETE *"trả tiến độ hiện tại, không lỗi, không xoá lặp"* — so report,
        # touch nothing. Re-running the loop here would be harmless but would
        # re-read both stores for a Space that has been empty since.
        return SpaceDeletionProgress(
            space_id=space_id,
            state=SpaceState.DELETED,
            documents_purged=0,
            documents_already_purged=0,
            documents_remaining=0,
            unfinished_purges_remaining=0,
            buffer_entries_discarded=0,
            completed=True,
        )

    # ---- 2. Everything of this Space that is not finished yet -------------
    doomed = _worklist(
        space_id=space_id, document_source=document_source, deletion_log=deletion_log
    )

    documents_purged = 0
    documents_already_purged = 0
    for document_id in doomed:
        outcome = purge_document_permanently(
            document_id,
            space_id=space_id,
            deleted_by=deleted_by,
            reason=f"{SPACE_DELETION_REASON_PREFIX}{reason}",
            profile_store=profile_store,
            vector_store=vector_store,
            background_cleanup=background_cleanup,
            deletion_log=deletion_log,
            clock=clock,
        )
        if outcome.already_completed:
            # An earlier call finished this one. Not an error, not a reason to
            # stop: the log said so, and the steps ran again anyway (T2.8 never
            # reads the log to decide what to do).
            documents_already_purged += 1
        else:
            documents_purged += 1

    # ---- 3a. The pre-approval buffer of this Space -----------------------
    # 06 Mục 5.6: *"cùng tài liệu còn trong vùng đệm tiền kiểm"*. These rows
    # are in no shared store and have no vectors (T2.7), so there is nothing
    # to purge in S6's sense — dropping the entry IS the deletion. No log line
    # either: 06 Mục 5.6's log is about documents that were in the stores.
    buffer_entries_discarded = 0
    for entry in pre_approval_buffer.list_in_space(space_id):
        if pre_approval_buffer.discard(entry.document.document_id):
            buffer_entries_discarded += 1

    # ---- 3b. The knowledge-care worklist of this Space -------------------
    # TODO(T2.9): docs/10 §4.0 step 3 also requires dropping *"các mục hàng
    # việc thuộc Space"* — the knowledge-care worklist (08 T2.9: pending
    # relation proposals, pending new-version claims, "this may be out of
    # date" items). That queue is NOT BUILT anywhere in this repo yet, so
    # there is nothing here to delete and this module deliberately deletes
    # nothing on its behalf. When T2.9 lands, its worklist MUST be emptied
    # here, between the buffer sweep and the final state change — a Space
    # reported `DELETED` while worklist items still name its documents would
    # leave items pointing at documents that no longer exist.

    # ---- 4. Done only when BOTH sources of work are empty -----------------
    # Re-read both rather than trusting the loop above: if a concurrent writer
    # slipped a document in before step 1 closed the door, this call reports it
    # as remaining instead of declaring an empty Space that is not empty; and
    # if an engine has not reported its `dọn nền` done, the open log line keeps
    # the Space out of `DELETED` (S6 — the obligation is not discharged yet).
    remaining = _profiles_in(space_id=space_id, document_source=document_source)
    unfinished = deletion_log.open_entries_for_space(space_id)
    completed = not remaining and not unfinished
    state = (
        space_registry.advance_state(space_id, to=SpaceState.DELETED).state
        if completed
        else SpaceState.BEING_DELETED
    )

    return SpaceDeletionProgress(
        space_id=space_id,
        state=state,
        documents_purged=documents_purged,
        documents_already_purged=documents_already_purged,
        documents_remaining=len(remaining),
        unfinished_purges_remaining=len(unfinished),
        buffer_entries_discarded=buffer_entries_discarded,
        completed=completed,
    )


def _profiles_in(
    *, space_id: str, document_source: SpaceDocumentSource
) -> list[str]:
    """Document ids whose PROFILE carries this `space_id` — source 1.

    The `document.space_id == space_id` test is not redundant:
    `documents_in` takes a SET of Spaces, and this is the one place where a
    store that over-returned would mean deleting someone else's documents.
    Selecting on the profile's own `space_id` is docs/10 §4.0's first
    anti-mistake rule stated as code.
    """
    return [
        document.document_id
        for document in document_source.documents_in(frozenset({space_id}))
        if document.space_id == space_id
    ]


def _worklist(
    *,
    space_id: str,
    document_source: SpaceDocumentSource,
    deletion_log: DeletionLog,
) -> list[str]:
    """Source 1 ∪ source 2, deduplicated by `document_id`, order stable.

    See the module docstring for why source 2 exists. Profiles come first so
    that the common case runs in store order, and an id already seen there is
    never visited twice — one `purge_document_permanently` call per document
    per run, which is what keeps the counts in `SpaceDeletionProgress` honest.
    """
    worklist = _profiles_in(space_id=space_id, document_source=document_source)
    seen = set(worklist)
    for entry in deletion_log.open_entries_for_space(space_id):
        if entry.document_id not in seen:
            seen.add(entry.document_id)
            worklist.append(entry.document_id)
    return worklist
