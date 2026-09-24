"""T2.11 (i) — the hole between step 2 and step 3 of ONE document, and the
second worklist source that closes it (PO chốt phương án A, 24/9/2026).

One document's purge runs `vector store → (relations + profile, one
transaction) → dọn nền` (S6). Cut the process between the transaction and
`dọn nền` and the profile is already gone — so a worklist derived from
profiles alone has nothing left to report, while S6 says the job is not done:
*"nghĩa vụ xoá dữ liệu cá nhân chỉ được coi là hoàn thành khi bước dọn nền ĐÃ
CHẠY XONG, không phải khi người dùng bấm xoá."*

The open deletion-log line is the only trace left of that unfinished work, and
`delete_space` now unions it into the worklist.

Two cases, and they are the two halves of the same claim:

* **A** — the engines DO settle on the retry: the leftover document is picked
  up, its `dọn nền` runs, its log line closes, the Space reaches `DELETED`.
* **B** — the engines do NOT settle: the Space must stay `BEING_DELETED`.
  Without this half, an implementation that simply ignored open log lines
  would pass case A whenever the retry happened to settle, which it usually
  does.

Case B is also the more dangerous direction in production: docs/10 §4.0's
*"Thứ tự phía BE"* has Backend delete the Space on its side once AI reports
*đã xoá*, and after that nobody asks about that Space again.
"""

from __future__ import annotations

import pytest

from fault_injection import InjectedCrash, crash_before
from ingestion.deletion import InMemoryBackgroundCleanup
from ingestion.space_deletion import delete_space
from ingestion.space_registry import SpaceState

from .conftest import DOOMED_SPACE


def _cut_between_the_transaction_and_the_cleanup(world, space_deletion_kwargs) -> None:
    """The exact hole: document #1 fully done, document #2 past its
    PostgreSQL transaction, dead before its `dọn nền`.

    `crash_before(cleanup, "purge", on_call=2)` is what puts the process
    there — call #1 is document #1's cleanup, so cutting BEFORE call #2 means
    document #2's rows are gone and its bytes are not.
    """
    crashing = crash_before(world.cleanup, "purge", on_call=2)
    with pytest.raises(InjectedCrash):
        delete_space(
            DOOMED_SPACE, **{**space_deletion_kwargs, "background_cleanup": crashing}
        )
    crashing.assert_fired()

    assert "doc-doomed-2" not in world.document_ids(), "step 2 committed"
    assert world.point_ids() == {
        "chunk-doc-doomed-3-1",
        "chunk-doc-doomed-3-2",
        "chunk-doc-twin-1",
        "chunk-doc-twin-2",
    }, "and step 1 had already removed its points"
    open_line = world.log.get("doc-doomed-2")
    assert open_line is not None
    assert open_line.purge_completed_at is None, "the obligation is still open"
    assert open_line.space_id == DOOMED_SPACE, (
        "step 0 recorded the Space before step 2 destroyed the profile — the only "
        "reason this document can be found again at all"
    )


# --------------------------------------------------------------------------- #
# Case A — the leftover document is finished by the next call
# --------------------------------------------------------------------------- #


def test_the_document_with_no_profile_left_is_still_in_the_worklist(
    world, space_deletion_kwargs
) -> None:
    _cut_between_the_transaction_and_the_cleanup(world, space_deletion_kwargs)
    assert world.log.open_entries_for_space(DOOMED_SPACE) != [], "precondition"

    progress = delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    assert "doc-doomed-2" in world.cleanup.calls, (
        "the dọn nền skipped by the interrupted call must have run now — a "
        "worklist built from profiles alone could not have found this document"
    )
    assert world.log.get("doc-doomed-2").purge_completed_at is not None, (
        "and the log line must be closed, because the engines reported done"
    )
    assert progress.unfinished_purges_remaining == 0
    assert progress.completed is True
    assert world.registry.get(DOOMED_SPACE).state is SpaceState.DELETED


def test_finishing_the_leftover_does_not_touch_its_rows_a_second_time(
    world, space_deletion_kwargs
) -> None:
    """The retry runs every S6 step again, and every one of them is a no-op:
    the vector delete matches nothing, the transaction removes no rows. That
    is what makes re-running safe rather than a second deletion."""
    _cut_between_the_transaction_and_the_cleanup(world, space_deletion_kwargs)
    relations_before = world.relation_ids()

    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    assert world.document_ids() == {"doc-twin"}
    assert world.point_ids() == {"chunk-doc-twin-1", "chunk-doc-twin-2"}
    assert world.relation_ids() <= relations_before
    log_ids = [entry.document_id for entry in world.log.entries()]
    assert sorted(log_ids) == ["doc-doomed-1", "doc-doomed-2", "doc-doomed-3"]
    assert len(log_ids) == len(set(log_ids)), "no document may get a second line"


def test_the_leftover_is_visited_exactly_once_per_run(
    world, space_deletion_kwargs
) -> None:
    """It is in the open-log source and NOT in the profile source, so the
    union must not double-count it — and if it were ever in both, the
    deduplication is what keeps one purge per document per run."""
    _cut_between_the_transaction_and_the_cleanup(world, space_deletion_kwargs)

    progress = delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    # doc-doomed-3 (profile source) + doc-doomed-2 (open-log source).
    assert progress.documents_purged == 2
    assert progress.documents_already_purged == 0
    assert world.cleanup.calls.count("doc-doomed-2") == 1


# --------------------------------------------------------------------------- #
# Case B — the engines have not settled, so the Space is not finished
# --------------------------------------------------------------------------- #


def test_an_unsettled_cleanup_keeps_the_space_being_deleted(
    world, space_deletion_kwargs
) -> None:
    unsettled = InMemoryBackgroundCleanup(settles=False)

    progress = delete_space(
        DOOMED_SPACE, **{**space_deletion_kwargs, "background_cleanup": unsettled}
    )

    assert progress.completed is False, (
        "the rows are gone but the bytes are not — S6 does not call that done"
    )
    assert progress.state is SpaceState.BEING_DELETED
    assert progress.documents_remaining == 0, "no profile is left..."
    assert progress.unfinished_purges_remaining == 3, "...and yet three purges are open"
    assert world.registry.get(DOOMED_SPACE).state is SpaceState.BEING_DELETED, (
        "reporting DELETED here would let Backend drop the Space on its side "
        "while the engines have not reclaimed anything (docs/10 §4.0, Thứ tự phía BE)"
    )


def test_the_unsettled_space_is_finished_once_the_engines_report_done(
    world, space_deletion_kwargs
) -> None:
    unsettled = InMemoryBackgroundCleanup(settles=False)
    delete_space(DOOMED_SPACE, **{**space_deletion_kwargs, "background_cleanup": unsettled})

    progress = delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    assert progress.documents_purged == 3, (
        "all three were found again through their open log lines, with no "
        "profile left anywhere"
    )
    assert progress.completed is True
    assert world.registry.get(DOOMED_SPACE).state is SpaceState.DELETED
    assert all(
        entry.purge_completed_at is not None for entry in world.log.entries()
    )


def test_an_unsettled_space_still_refuses_new_documents(
    world, space_deletion_kwargs
) -> None:
    """`BEING_DELETED` is not a cosmetic label: the door stays shut for as
    long as the deletion is unfinished, which is the whole reason step 1 runs
    before the loop."""
    unsettled = InMemoryBackgroundCleanup(settles=False)
    delete_space(DOOMED_SPACE, **{**space_deletion_kwargs, "background_cleanup": unsettled})

    with pytest.raises(Exception) as refusal:
        world.registry.register(DOOMED_SPACE)

    assert "being_deleted" in str(refusal.value)
