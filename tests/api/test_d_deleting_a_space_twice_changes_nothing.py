"""Case 4 of the work-order — docs/10 §4.0: *"Gọi `DELETE` lần hai: trả tiến
độ hiện tại, không lỗi, không xoá lặp."*

⚠️ Both calls carry DIFFERENT `Idempotency-Key`s, and that is the point. With
one key the second call never reaches the route at all (that is case 5,
`test_e`), so it would prove the middleware works and say nothing about the
deletion. Here the route really runs twice, and the property under test is the
one `space_deletion.delete_space` was built for: the terminal state is the
same whether it is called once or ten times.

Since 24/9/2026 the emptying runs on the background worker (docs/10 §4.0 —
`202` *"và chạy nền"*), so each case says explicitly when it lets the worker
run. The repeat property now has a second half worth checking: TWO queued
jobs for one Space also converge, because each re-derives its worklist.
"""

from __future__ import annotations

from conftest import DOOMED_SPACE


def test_d_the_second_delete_reports_progress_and_deletes_nothing_again(backend, world):
    backend.register_space(DOOMED_SPACE)
    for index in (1, 2):
        world.seed_document(document_id=f"doc-doomed-{index}", space_id=DOOMED_SPACE)

    first = backend.delete_space(DOOMED_SPACE)
    world.run_background()
    after_first = world.snapshot()
    cleanup_calls_after_first = list(world.cleanup.calls)

    second = backend.delete_space(DOOMED_SPACE)
    world.run_background()

    assert first.status_code == second.status_code == 202, "the repeat is not an error"

    body = second.json()
    assert body["state"] == "deleted"
    assert body["documents_remaining"] == 0
    assert body["unfinished_purges_remaining"] == 0

    assert world.snapshot() == after_first, "the second call changed a store"
    assert world.cleanup.calls == cleanup_calls_after_first, (
        "background cleanup ran again for documents that were already gone — "
        "'không xoá lặp' is about the work, not just about the counts"
    )


def test_d_two_jobs_queued_for_one_space_converge(backend, world):
    """Both `DELETE`s land on the worker BEFORE either runs.

    This is the shape a real Backend produces when it retries an unanswered
    call, and it is the one the in-request version could never reach. The
    second job finds the Space already `DELETED` and returns without touching
    a store (`delete_space`'s first branch).
    """
    backend.register_space(DOOMED_SPACE)
    world.seed_document(document_id="doc-doomed-1", space_id=DOOMED_SPACE)

    backend.delete_space(DOOMED_SPACE)
    backend.delete_space(DOOMED_SPACE)
    assert world.worker.pending() == 2, "both calls should have queued a job"

    world.run_background()

    assert world.document_ids() == set()
    assert world.deletion_log_document_ids() == {"doc-doomed-1"}, (
        "the document was purged twice — each purge writes one log line, so a "
        "second entry would mean the repeat did the work again"
    )
    assert backend.read_space(DOOMED_SPACE).json()["state"] == "deleted"


def test_d_a_third_read_still_agrees_with_the_second_delete(backend, world):
    """`GET` must tell the same story as the repeated `DELETE`, and must not
    be the thing that advances it — see the route's docstring on why a `GET`
    may never call `delete_space`."""
    backend.register_space(DOOMED_SPACE)
    world.seed_document(document_id="doc-doomed-1", space_id=DOOMED_SPACE)
    backend.delete_space(DOOMED_SPACE)
    world.run_background()
    backend.delete_space(DOOMED_SPACE)
    world.run_background()

    before = world.snapshot()
    status = backend.read_space(DOOMED_SPACE)

    assert status.json()["state"] == "deleted"
    assert world.snapshot() == before, "a GET wrote to a store"
