"""T2.8 (m) — the command runs the same three steps whether or not a profile
is found, and says so honestly.

Not a hypothetical: a promote cut halfway leaves a profile with no vectors,
and a deletion cut halfway leaves vectors with no profile (test d). If
deletion skipped its remaining steps whenever the profile was missing, the
second of those states would be unreachable by any command — permanent
orphans, and nothing in the system would mention them.
"""

from __future__ import annotations

from ingestion.deletion import purge_document_permanently


def test_an_unknown_document_id_is_not_an_error(world, deletion_kwargs):
    before = world.snapshot()

    outcome = purge_document_permanently("doc-never-existed", **deletion_kwargs)

    assert outcome.profile_was_present is False
    assert (outcome.vector_points_deleted, outcome.relations_deleted, outcome.profile_rows_deleted) == (0, 0, 0)
    assert world.snapshot() == before, "no other document may be touched"


def test_all_three_steps_still_run(world, deletion_kwargs):
    outcome = purge_document_permanently("doc-never-existed", **deletion_kwargs)

    assert world.cleanup.calls == ["doc-never-existed"]
    assert outcome.purge_settled is True


def test_the_attempt_is_still_logged_but_without_a_space_it_cannot_know(world, deletion_kwargs):
    purge_document_permanently("doc-never-existed", **deletion_kwargs)

    entry = world.log.entries()[0]
    assert entry.document_id == "doc-never-existed"
    assert entry.deleted_by == "manager-lan"
    assert entry.space_id is None, "there was no profile left to read it from"
    assert entry.tenant_id is None


def test_orphaned_vectors_are_still_reachable_by_the_command(world, deletion_kwargs):
    """The exact state test (d) leaves behind: profile gone, points still in
    the vector store. Running the command again must clear them."""
    world.inner_store._documents.pop("doc-doomed")

    outcome = purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert outcome.vector_points_deleted == 2
    assert world.point_ids() == {"chunk-neighbour-1"}
