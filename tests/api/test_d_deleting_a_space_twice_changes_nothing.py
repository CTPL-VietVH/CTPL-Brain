"""Case 4 of the work-order — docs/10 §4.0: *"Gọi `DELETE` lần hai: trả tiến
độ hiện tại, không lỗi, không xoá lặp."*

⚠️ Both calls carry DIFFERENT `Idempotency-Key`s, and that is the point. With
one key the second call never reaches the route at all (that is case 5,
`test_e`), so it would prove the middleware works and say nothing about the
deletion. Here the route really runs twice, and the property under test is the
one `space_deletion.delete_space` was built for: the terminal state is the
same whether it is called once or ten times.
"""

from __future__ import annotations

from conftest import DOOMED_SPACE


def test_d_the_second_delete_reports_progress_and_deletes_nothing_again(backend, world):
    backend.register_space(DOOMED_SPACE)
    for index in (1, 2):
        world.seed_document(document_id=f"doc-doomed-{index}", space_id=DOOMED_SPACE)

    first = backend.delete_space(DOOMED_SPACE)
    after_first = world.snapshot()
    cleanup_calls_after_first = list(world.cleanup.calls)

    second = backend.delete_space(DOOMED_SPACE)

    assert first.status_code == second.status_code == 202, "the repeat is not an error"
    assert first.json()["documents_purged"] == 2
    assert first.json()["completed"] is True

    body = second.json()
    assert body["completed"] is True
    assert body["state"] == "deleted"
    # Zeros, not two: the counts describe THIS call. Reporting 2 again would
    # be the response claiming work that nothing did.
    assert body["documents_purged"] == 0
    assert body["documents_already_purged"] == 0
    assert body["documents_remaining"] == 0
    assert body["unfinished_purges_remaining"] == 0
    assert body["buffer_entries_discarded"] == 0

    assert world.snapshot() == after_first, "the second call changed a store"
    assert world.cleanup.calls == cleanup_calls_after_first, (
        "background cleanup ran again for documents that were already gone — "
        "'không xoá lặp' is about the work, not just about the counts"
    )


def test_d_a_third_read_still_agrees_with_the_second_delete(backend, world):
    """`GET` must tell the same story as the repeated `DELETE`, and must not
    be the thing that advances it — see the route's docstring on why a `GET`
    may never call `delete_space`."""
    backend.register_space(DOOMED_SPACE)
    world.seed_document(document_id="doc-doomed-1", space_id=DOOMED_SPACE)
    backend.delete_space(DOOMED_SPACE)
    backend.delete_space(DOOMED_SPACE)

    before = world.snapshot()
    status = backend.read_space(DOOMED_SPACE)

    assert status.json()["state"] == "deleted"
    assert world.snapshot() == before, "a GET wrote to a store"
