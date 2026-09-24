"""T2.11 (e) — case 5: call the Space deletion a second time after it has
finished. No error, and nothing is deleted twice.

docs/10 §4.0: *"Gọi `DELETE` lần hai: trả tiến độ hiện tại, không lỗi, không
xoá lặp."* 08 T2.11 *Xong khi*: *"gọi xoá lần hai không lỗi, không xoá lặp"*.

"Not twice" is checked on the things that COULD happen twice and would be
visible: a second deletion_log line, a second background-cleanup call, a
second state transition. Asserting only "the stores are still empty" would
pass even for an implementation that re-ran every step over an empty Space.
"""

from __future__ import annotations

from ingestion.space_deletion import delete_space
from ingestion.space_registry import SpaceState

from .conftest import DOOMED_SPACE


def test_the_second_call_reports_a_finished_space_and_does_no_work(
    world, space_deletion_kwargs
) -> None:
    first = delete_space(DOOMED_SPACE, **space_deletion_kwargs)
    assert first.completed is True

    after_first = world.snapshot()
    cleanup_calls_after_first = list(world.cleanup.calls)
    log_after_first = {entry.document_id: entry for entry in world.log.entries()}

    second = delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    assert second.completed is True
    assert second.state is SpaceState.DELETED
    assert second.documents_purged == 0
    assert second.documents_already_purged == 0
    assert second.documents_remaining == 0
    assert second.buffer_entries_discarded == 0

    assert world.snapshot() == after_first, "no store may change on the second call"
    assert world.cleanup.calls == cleanup_calls_after_first, (
        "background cleanup must not run again for documents already gone"
    )
    assert {entry.document_id: entry for entry in world.log.entries()} == log_after_first, (
        "the log must be byte-for-byte what the first call left"
    )


def test_a_third_call_is_no_different_from_the_second(
    world, space_deletion_kwargs
) -> None:
    delete_space(DOOMED_SPACE, **space_deletion_kwargs)
    second = delete_space(DOOMED_SPACE, **space_deletion_kwargs)
    third = delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    assert second == third, (
        "convergence, not a countdown: every call after the first reports the "
        "same finished state"
    )


def test_the_state_never_walks_backwards(world, space_deletion_kwargs) -> None:
    """There is no undelete. A second call must not reopen the Space as
    BEING_DELETED on its way to re-marking it DELETED — the register would
    then briefly describe a Space whose documents are already gone."""
    delete_space(DOOMED_SPACE, **space_deletion_kwargs)
    assert world.registry.get(DOOMED_SPACE).state is SpaceState.DELETED

    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    assert world.registry.get(DOOMED_SPACE).state is SpaceState.DELETED
