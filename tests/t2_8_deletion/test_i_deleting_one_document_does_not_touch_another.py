"""T2.8 (i) — acceptance (b), second half: *"không xoá nhầm tài liệu khác"*.

Deleting one document must leave every other document's profile, chunks and
unrelated links exactly where they were — including a document in the same
Space, which is the one a filter bug would take down with it.
"""

from __future__ import annotations

from ingestion.deletion import purge_document_permanently


def test_the_neighbour_in_the_same_space_survives_intact(world, deletion_kwargs):
    neighbour_before = world.inner_store.get_document("doc-neighbour")

    purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert world.inner_store.get_document("doc-neighbour") == neighbour_before
    assert "chunk-neighbour-1" in world.point_ids()


def test_a_document_in_another_space_is_untouched(world, deletion_kwargs):
    bystander_before = world.inner_store.get_document("doc-bystander")

    purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert world.inner_store.get_document("doc-bystander") == bystander_before


def test_deleting_the_neighbour_instead_takes_the_other_half(world, deletion_kwargs):
    """The mirror run: aim at `doc-neighbour` and the losses swap over.
    A delete that ignored its argument would pass one direction and fail
    this one."""
    purge_document_permanently("doc-neighbour", **deletion_kwargs)

    assert world.point_ids() == {"chunk-doomed-1", "chunk-doomed-2"}
    assert world.document_ids() == {"doc-doomed", "doc-bystander"}
    assert world.relation_ids() == set(), "all three links had doc-neighbour on one end"
