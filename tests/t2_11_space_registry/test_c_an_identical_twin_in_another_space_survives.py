"""T2.11 (c) — case 3: a byte-identical copy of one of the deleted documents,
sitting in ANOTHER Space, is untouched.

docs/10 §4.0, ràng buộc chống xoá nhầm 1: *"Chọn tài liệu cần xoá **chỉ theo
`space_id` trên hồ sơ tài liệu** — không theo vân tay nội dung, tên hay số
hiệu. Bản trùng khít ở Space khác là tài liệu khác (`document_id` khác, 06
§5.7) và **không bị đụng tới**."*

This is the failure that would never be noticed from inside the deleted
Space: selecting by `content_fingerprint` deletes exactly the right documents
there, and one extra somewhere else. Nobody in the doomed Space can see the
damage, and the Space that lost a document has no event to look at.

`doc-doomed-1` and `doc-twin` share `SHARED_FINGERPRINT` (see the conftest
map), so a fingerprint-based selection would match both.
"""

from __future__ import annotations

from ingestion.space_deletion import delete_space

from .conftest import DOOMED_SPACE, SHARED_FINGERPRINT


def test_the_twin_survives_with_its_profile_chunks_and_fingerprint(
    world, space_deletion_kwargs
) -> None:
    twin_before = world.inner_store.get_document("doc-twin")
    assert twin_before.content_fingerprint == SHARED_FINGERPRINT
    assert world.inner_store.get_document("doc-doomed-1").content_fingerprint == (
        SHARED_FINGERPRINT
    ), "the two really are byte-identical uploads of one file"

    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    twin_after = world.inner_store.get_document("doc-twin")
    assert twin_after == twin_before, "the twin's profile must be untouched, field by field"
    assert world.point_ids() == {"chunk-doc-twin-1", "chunk-doc-twin-2"}


def test_the_twin_is_still_findable_by_the_shared_fingerprint(
    world, space_deletion_kwargs
) -> None:
    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    matches = world.inner_store.find_by_fingerprint(SHARED_FINGERPRINT)
    assert [document.document_id for document in matches] == ["doc-twin"]


def test_the_twin_gets_no_deletion_log_line(world, space_deletion_kwargs) -> None:
    """A document that was not deleted must have no record saying it was —
    the log is the only evidence left after a deletion, so a spurious line
    would be indistinguishable from a real loss."""
    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    assert world.log.get("doc-twin") is None


def test_only_the_crossing_link_goes_not_the_document_at_its_far_end(
    world, space_deletion_kwargs
) -> None:
    """06 Mục 5.6 deletes *"các liên kết quan hệ của nó"*. `rel-crossing`
    pointed from `doc-doomed-3` into the other Space: the link goes because
    one endpoint went, and the far endpoint stays because nothing happened to
    it."""
    assert "rel-crossing" in world.relation_ids()

    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    assert "rel-crossing" not in world.relation_ids()
    assert "doc-twin" in world.document_ids()
