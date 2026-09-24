"""T2.11 (d) — case 4: cut the process right after the second document is
fully deleted, then call again. The second call finishes the job.

08 T2.11 *Xong khi*: *"cắt tiến trình giữa chừng rồi chạy lại vẫn hoàn tất"*.

The cut is placed AFTER `background_cleanup.purge` of document #2 — the last
step of one document's purge (S6 step 3) — so the interrupted state is
exactly "two documents done, one untouched, buffer not yet swept, Space still
marked BEING_DELETED".

What makes the resume work is the absence of a cursor: the worklist is
re-derived from the store on the next call, and the two finished documents
are no longer in the Space, so they are not in it. There is no progress
counter to lose, and nothing that would redo them if there were.
"""

from __future__ import annotations

import pytest

from fault_injection import InjectedCrash, crash_after
from ingestion.space_deletion import delete_space
from ingestion.space_registry import SpaceState

from .conftest import DOOMED_SPACE


def _cut_after_the_second_document(world, space_deletion_kwargs) -> None:
    crashing = crash_after(world.cleanup, "purge", on_call=2)
    with pytest.raises(InjectedCrash):
        delete_space(
            DOOMED_SPACE, **{**space_deletion_kwargs, "background_cleanup": crashing}
        )
    crashing.assert_fired()


def test_the_interrupted_state_is_two_done_one_untouched(
    world, space_deletion_kwargs
) -> None:
    _cut_after_the_second_document(world, space_deletion_kwargs)

    assert world.document_ids() == {"doc-doomed-3", "doc-twin"}
    assert world.point_ids() == {
        "chunk-doc-doomed-3-1",
        "chunk-doc-doomed-3-2",
        "chunk-doc-twin-1",
        "chunk-doc-twin-2",
    }
    assert world.registry.get(DOOMED_SPACE).state is SpaceState.BEING_DELETED, (
        "the door stays shut while the deletion is unfinished"
    )
    assert "doc-buffered" in world.buffered_ids(), "step 3 was never reached"
    assert {entry.document_id for entry in world.log.entries()} == {
        "doc-doomed-1",
        "doc-doomed-2",
    }


def test_calling_again_finishes_the_rest(world, space_deletion_kwargs) -> None:
    _cut_after_the_second_document(world, space_deletion_kwargs)

    progress = delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    assert progress.completed is True
    # TWO, not one: `doc-doomed-3` was never started, and `doc-doomed-2`'s
    # `dọn nền` had run but the process died before step 4 could close its log
    # line — so that line was still open and it is picked up through the
    # open-log source of the worklist (see test_i). `doc-doomed-1`, whose line
    # did close, is not revisited.
    assert progress.documents_purged == 2
    assert progress.documents_remaining == 0
    assert progress.unfinished_purges_remaining == 0
    assert progress.buffer_entries_discarded == 1
    assert world.document_ids() == {"doc-twin"}
    assert world.point_ids() == {"chunk-doc-twin-1", "chunk-doc-twin-2"}
    assert world.buffered_ids() == {"doc-buffered-keeper"}
    assert world.registry.get(DOOMED_SPACE).state is SpaceState.DELETED


def test_the_resumed_run_does_not_double_any_log_line(
    world, space_deletion_kwargs
) -> None:
    """A second line for a document already deleted would misreport who
    ordered it: `record_started` is INSERT-IF-ABSENT (T2.8), and the resumed
    Space deletion must not be the thing that breaks that."""
    _cut_after_the_second_document(world, space_deletion_kwargs)

    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    document_ids = [entry.document_id for entry in world.log.entries()]
    assert sorted(document_ids) == ["doc-doomed-1", "doc-doomed-2", "doc-doomed-3"]
    assert len(document_ids) == len(set(document_ids))


def test_a_cut_before_any_document_still_leaves_the_door_shut(
    world, space_deletion_kwargs
) -> None:
    """The ordering claim of docs/10 §4.0 step 1: the Space is marked
    BEING_DELETED BEFORE the first document is touched, so a process that
    dies immediately still refuses new uploads. Marking it at the end
    instead would leave the Space open for the whole run."""
    crashing = crash_after(world.vector_store, "delete_document_points", on_call=1)
    with pytest.raises(InjectedCrash):
        delete_space(DOOMED_SPACE, **{**space_deletion_kwargs, "vector_store": crashing})
    crashing.assert_fired()

    assert world.registry.get(DOOMED_SPACE).state is SpaceState.BEING_DELETED

    progress = delete_space(DOOMED_SPACE, **space_deletion_kwargs)
    assert progress.completed is True
    assert world.document_ids() == {"doc-twin"}
