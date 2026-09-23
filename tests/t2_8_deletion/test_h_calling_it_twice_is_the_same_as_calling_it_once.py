"""T2.8 (h) — acceptance (b): call the command TWICE in a row on the same
document and get the same result as the first time. No error, and no other
document harmed.
"""

from __future__ import annotations

from ingestion.deletion import purge_document_permanently


def test_the_second_call_leaves_exactly_the_same_state(world, deletion_kwargs):
    purge_document_permanently("doc-doomed", **deletion_kwargs)
    after_first = world.snapshot()

    second = purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert world.snapshot() == after_first
    assert second.already_completed is True
    assert len(world.log.entries()) == 1


def test_the_second_call_reports_zero_work_rather_than_pretending(world, deletion_kwargs):
    """The counts describe work done by THIS call, so the second call reports
    zeros. Echoing the first call's numbers would read as "deleted again",
    which is not a thing that can happen."""
    first = purge_document_permanently("doc-doomed", **deletion_kwargs)
    second = purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert (first.vector_points_deleted, first.relations_deleted, first.profile_rows_deleted) == (2, 2, 1)
    assert (second.vector_points_deleted, second.relations_deleted, second.profile_rows_deleted) == (0, 0, 0)
    assert second.profile_was_present is False
    assert second.purge_settled is True


def test_a_third_call_changes_nothing_either(world, deletion_kwargs):
    for _ in range(3):
        purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert world.snapshot() == ({"chunk-neighbour-1"}, {"doc-neighbour", "doc-bystander"}, {"rel-elsewhere"})
    assert len(world.log.entries()) == 1
