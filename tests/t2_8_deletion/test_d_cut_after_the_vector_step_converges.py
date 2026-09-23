"""T2.8 (d) — cut the process AFTER step 1, before the PostgreSQL
transaction. This is the state S6 chose to make possible.

The vectors are gone, the profile and relations are still there. That
combination is harmless: the document is already unfindable (the gate is the
vector store), and nothing points at anything missing. The reverse order
would have produced the dangling pointer instead.
"""

from __future__ import annotations

import pytest

from fault_injection import InjectedCrash, crash_after
from ingestion.deletion import purge_document_permanently


def test_the_intermediate_state_is_the_harmless_one(world, deletion_kwargs):
    crashing = crash_after(world.vector_store, "delete_document_points")
    with pytest.raises(InjectedCrash):
        purge_document_permanently("doc-doomed", **{**deletion_kwargs, "vector_store": crashing})
    crashing.assert_fired()

    assert world.point_ids() == {"chunk-neighbour-1"}, "step 1 did run"
    assert "doc-doomed" in world.document_ids(), "step 2 did not"
    assert {"rel-in", "rel-out"} <= world.relation_ids()

    # No chunk in the store points at a profile that is gone — the invariant
    # S6 was written to protect.
    for chunk in world.vector_writer.points.values():
        assert chunk.document_id in world.document_ids()


def test_the_re_run_converges_and_does_not_double_the_log(world, deletion_kwargs):
    crashing = crash_after(world.vector_store, "delete_document_points")
    with pytest.raises(InjectedCrash):
        purge_document_permanently("doc-doomed", **{**deletion_kwargs, "vector_store": crashing})
    crashing.assert_fired()

    outcome = purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert world.snapshot() == ({"chunk-neighbour-1"}, {"doc-neighbour", "doc-bystander"}, {"rel-elsewhere"})
    assert outcome.vector_points_deleted == 0, "step 1 was already done — a no-op, not an error"
    assert outcome.relations_deleted == 2
    assert outcome.profile_rows_deleted == 1
    assert len(world.log.entries()) == 1
