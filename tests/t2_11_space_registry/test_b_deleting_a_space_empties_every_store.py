"""T2.11 (b) — case 2: delete a Space holding three official documents and
one document still in the pre-approval buffer; every one of them disappears
from every store.

08 T2.11 *Xong khi*: *"xoá Space thì mọi tài liệu của nó biến khỏi **cả**
Qdrant **và** PostgreSQL (kiểm thẳng kho, không qua service)"*. The stores
here are the in-memory stand-ins, and they are queried directly — never
through the module that just wrote to them.

Also pinned here: docs/10 §4.0 step 2's *"mỗi tài liệu một dòng nhật ký
xoá"*. One line per document, not one per Space — 06 Mục 5.6 keeps the log
per document (*"ai, khi nào, tài liệu nào, lý do"*), and a single Space-level
line would be unable to say which documents went.
"""

from __future__ import annotations

from ingestion.space_deletion import SPACE_DELETION_REASON_PREFIX, delete_space
from ingestion.space_registry import SpaceState

from .conftest import (
    DELETED_BY,
    DELETION_REASON,
    DOOMED_SPACE,
    KEEPER_SPACE,
)


def test_every_document_of_the_space_is_gone_from_every_store(
    world, space_deletion_kwargs
) -> None:
    progress = delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    assert progress.completed is True
    assert progress.documents_purged == 3
    assert progress.buffer_entries_discarded == 1
    assert progress.documents_remaining == 0

    # --- the stores, queried directly ------------------------------------
    assert world.document_ids() == {"doc-twin"}, "the profile store keeps only the twin"
    assert world.point_ids() == {"chunk-doc-twin-1", "chunk-doc-twin-2"}, (
        "the vector store keeps only the twin's chunks"
    )
    assert world.relation_ids() == set(), (
        "both links touched a deleted document, so both are gone"
    )
    assert world.buffered_ids() == {"doc-buffered-keeper"}, (
        "the staging area keeps only the OTHER Space's entry"
    )


def test_the_space_itself_ends_up_marked_deleted(world, space_deletion_kwargs) -> None:
    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    assert world.registry.get(DOOMED_SPACE).state is SpaceState.DELETED
    assert world.registry.get(KEEPER_SPACE).state is SpaceState.IN_USE, (
        "no other Space may be touched — the register holds no tree to walk"
    )


def test_each_document_leaves_its_own_log_line_naming_the_space_deletion(
    world, space_deletion_kwargs
) -> None:
    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    entries = {entry.document_id: entry for entry in world.log.entries()}
    assert set(entries) == {"doc-doomed-1", "doc-doomed-2", "doc-doomed-3"}, (
        "one line per document (06 Mục 5.6), and none for the buffered entry — "
        "it was never in a shared store"
    )
    for entry in entries.values():
        assert entry.reason == f"{SPACE_DELETION_REASON_PREFIX}{DELETION_REASON}"
        assert entry.deleted_by == DELETED_BY
        assert entry.space_id == DOOMED_SPACE
        assert entry.purge_completed_at is not None


def test_the_log_keeps_no_content_of_the_documents_it_removed(
    world, space_deletion_kwargs
) -> None:
    """06 Mục 5.6: *"Không giữ nội dung"*. The Space-wide path must not become
    the one place where document text survives a deletion."""
    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    for entry in world.log.entries():
        rendered = repr(entry)
        assert "Phạm vi điều chỉnh" not in rendered
        assert "công tác văn thư" not in rendered
