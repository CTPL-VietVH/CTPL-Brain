"""Case 2 of the work-order — docs/10 §10: *"Xoá Space | Mọi tài liệu của
Space biến khỏi Qdrant **và** PostgreSQL (kiểm thẳng kho); tài liệu Space khác
không đổi; nộp mới vào Space đó bị từ chối"*.

The parenthesis is the instruction that shapes this file: **kiểm thẳng kho**.
A response body saying `documents_purged: 3` is the service describing itself;
the assertion that matters reads the stores afterwards. A deletion that
counted correctly and deleted nothing would pass the first and fail the second.
"""

from __future__ import annotations

from api.errors import CODE_FIELD, ErrorCode
from conftest import DOOMED_SPACE, KEEPER_SPACE


def test_b_a_space_deletion_removes_every_document_of_that_space(backend, world):
    # -- Backend announces both Spaces (docs/10 §4.0) --------------------- #
    registered = backend.register_space(DOOMED_SPACE)
    assert registered.status_code == 200
    assert registered.json() == {"space_id": DOOMED_SPACE, "state": "in_use"}
    assert backend.register_space(KEEPER_SPACE).status_code == 200

    # -- and the Spaces fill up (straight into the stores: docs/10 §4.1,
    #    the submission endpoint, is not built in this slice) ------------- #
    for index in (1, 2, 3):
        world.seed_document(document_id=f"doc-doomed-{index}", space_id=DOOMED_SPACE)
    world.seed_buffered_document(document_id="doc-buffered", space_id=DOOMED_SPACE)
    # A byte-identical twin in the other Space: 06 Mục 5.7 makes it a
    # different document, and docs/10 §4.0's first anti-mistake rule says it
    # must not be touched. Selecting what to delete by fingerprint instead of
    # by `space_id` would take it too, silently.
    world.seed_document(
        document_id="doc-twin",
        space_id=KEEPER_SPACE,
        content_fingerprint="fingerprint-doc-doomed-1",
    )

    response = backend.delete_space(DOOMED_SPACE)

    assert response.status_code == 202, "docs/10 §4.0 answers a Space deletion with 202"
    body = response.json()
    assert body["completed"] is True
    assert body["documents_purged"] == 3
    assert body["buffer_entries_discarded"] == 1
    assert body["documents_remaining"] == 0
    assert body["unfinished_purges_remaining"] == 0

    # ⭐ Straight into the stores — not through the answer above.
    assert world.document_ids() == {"doc-twin"}, (
        "PostgreSQL still holds documents of the deleted Space (or lost the "
        "twin that lives in another Space)"
    )
    assert world.point_ids() == {"chunk-doc-twin-1", "chunk-doc-twin-2"}, (
        "Qdrant still holds points of the deleted Space"
    )
    assert world.buffered_ids() == set(), "the pre-approval buffer kept an entry"

    # Every removed document left its own log line — 06 Mục 5.6, docs/10 §4.0
    # step 2: *"mỗi tài liệu một dòng nhật ký xoá"*.
    assert world.deletion_log_document_ids() == {
        "doc-doomed-1",
        "doc-doomed-2",
        "doc-doomed-3",
    }


def test_b_the_space_reads_back_as_deleted(backend, world):
    backend.register_space(DOOMED_SPACE)
    world.seed_document(document_id="doc-doomed-1", space_id=DOOMED_SPACE)

    backend.delete_space(DOOMED_SPACE)

    status = backend.read_space(DOOMED_SPACE)
    assert status.status_code == 200
    assert status.json() == {
        "space_id": DOOMED_SPACE,
        "state": "deleted",
        "documents_remaining": 0,
        "unfinished_purges_remaining": 0,
    }


def test_b_a_deleted_space_is_never_registered_again(backend, world):
    """docs/10 §4.0: *"`space_id` đã xoá thì **không được đăng ký lại**"* —
    `409 SPACE_BEING_DELETED`, so an old document in the deletion log can
    never be mistaken for one of a new Space wearing the same code."""
    backend.register_space(DOOMED_SPACE)
    backend.delete_space(DOOMED_SPACE)

    again = backend.register_space(DOOMED_SPACE)

    assert again.status_code == 409
    assert again.json()[CODE_FIELD] == ErrorCode.SPACE_BEING_DELETED


def test_b_deleting_a_space_backend_never_announced_is_refused(backend, world):
    """docs/10 §3.5 `SPACE_NOT_REGISTERED` (404).

    Refused rather than treated as "nothing to delete": a `space_id` AI has
    never heard of is a Backend mistake, and whatever happens to carry that
    code must not be removed on the strength of it.
    """
    world.seed_document(document_id="doc-orphan", space_id="space-never-announced")

    response = backend.delete_space("space-never-announced")

    assert response.status_code == 404
    assert response.json()[CODE_FIELD] == ErrorCode.SPACE_NOT_REGISTERED
    assert world.document_ids() == {"doc-orphan"}, "a refused deletion deleted something"
