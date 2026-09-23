"""T2.8 (c) — cut the process BEFORE step 1. Nothing has been deleted; the
re-run must do the whole deletion normally.

This is the cheap end of the fault matrix, and the one that would catch a
module that decided "the log says I started, so I will skip ahead".
"""

from __future__ import annotations

import pytest

from fault_injection import InjectedCrash, crash_before
from ingestion.deletion import purge_document_permanently


def test_nothing_is_lost_and_the_re_run_finishes_the_job(world, deletion_kwargs):
    before = world.snapshot()

    crashing = crash_before(world.vector_store, "delete_document_points")
    with pytest.raises(InjectedCrash):
        purge_document_permanently("doc-doomed", **{**deletion_kwargs, "vector_store": crashing})
    crashing.assert_fired()

    assert world.snapshot() == before, "a cut before step 1 must not have deleted anything"
    assert world.log.entries()[0].purge_completed_at is None, (
        "the log line is open — this is exactly the half-finished state it exists to show"
    )

    outcome = purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert world.snapshot() == ({"chunk-neighbour-1"}, {"doc-neighbour", "doc-bystander"}, {"rel-elsewhere"})
    assert outcome.vector_points_deleted == 2
    assert outcome.relations_deleted == 2
    assert outcome.profile_rows_deleted == 1
    assert len(world.log.entries()) == 1
    assert world.log.entries()[0].purge_completed_at is not None
