"""T2.8 (a) — 06 Mục 5.6: *"Xoá những gì: Tài liệu, các đơn vị cắt, vector,
và các liên kết quan hệ của nó"*.

The whole list, in one pass, with the neighbouring documents untouched.
"""

from __future__ import annotations

from ingestion.deletion import purge_document_permanently


def test_profile_chunks_vectors_and_relations_all_go(world, deletion_kwargs):
    outcome = purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert world.point_ids() == {"chunk-neighbour-1"}
    assert world.document_ids() == {"doc-neighbour", "doc-bystander"}
    assert world.relation_ids() == {"rel-elsewhere"}

    assert outcome.profile_was_present is True
    assert outcome.vector_points_deleted == 2
    assert outcome.relations_deleted == 2
    assert outcome.profile_rows_deleted == 1
    assert outcome.purge_settled is True
    assert outcome.already_completed is False


def test_the_log_keeps_the_event_and_the_cleanup_closed_it(world, deletion_kwargs):
    outcome = purge_document_permanently("doc-doomed", **deletion_kwargs)

    entries = world.log.entries()
    assert len(entries) == 1
    entry = entries[0]

    # "ai, khi nào, tài liệu nào, lý do" — 06 Mục 5.6, all four present.
    assert entry.document_id == "doc-doomed"
    assert entry.deleted_by == "manager-lan"
    assert entry.reason.startswith("Người upload đưa nhầm")
    assert entry.requested_at is not None

    # S6: the obligation is discharged by dọn nền, not by the click.
    assert entry.purge_completed_at is not None
    assert world.cleanup.calls == ["doc-doomed"]
    assert outcome.log_entry == entry
