"""Case 3 of the work-order — docs/10 §10: *"Xoá tài liệu với `space_id` sai
(tài liệu thật ở Space khác) | `404 OBJECT_NOT_IN_SPACE`, không xoá gì | AI"*.

This is T4 seen from the wire. §1 T4: *"Mỗi bên chỉ khẳng định sự thật thuộc
dữ liệu của mình. BE khẳng định 'người này có vai trò X ở Space S'. AI tự kiểm
'đối tượng này có thật sự nằm ở Space S không'."* — and the reason it exists
even though T2 already trusts Backend: *"nếu BE có lỗi, ví dụ gửi `space_id`
của Space A kèm `document_id` của một tài liệu ở Space B, thì thiếu T4 AI sẽ
để một Manager của A gỡ tài liệu của B."*

Note what the fake Backend does here: it sends a COMPLETE, legal call — key,
actor, idempotency key, both fields. The mistake being tested is not a
malformed request; it is a well-formed request stating something untrue.
"""

from __future__ import annotations

from api.errors import CODE_FIELD, ErrorCode
from conftest import DOOMED_SPACE, KEEPER_SPACE


def test_c_a_document_of_another_space_is_not_deleted(backend, world):
    backend.register_space(DOOMED_SPACE)
    backend.register_space(KEEPER_SPACE)
    world.seed_document(document_id="doc-in-keeper", space_id=KEEPER_SPACE)
    before = world.snapshot()

    response = backend.delete_document("doc-in-keeper", space_id=DOOMED_SPACE)

    assert response.status_code == 404
    assert response.json()[CODE_FIELD] == ErrorCode.OBJECT_NOT_IN_SPACE
    assert world.snapshot() == before, (
        "The refused deletion still changed a store. T4 exists to stop exactly "
        "this: a Manager of one Space removing a document of another."
    )
    assert world.deletion_log_document_ids() == set(), (
        "A refused attempt left a deletion-log line. docs/10 §1 T4 wants the "
        "refusal to happen BEFORE `record_started`, so a wrong `space_id` "
        "leaves no trace of the attempt."
    )
    assert world.cleanup.calls == [], "background cleanup ran for a refused deletion"


def test_c_an_unknown_document_is_refused_the_same_way(backend, world):
    """*"does not exist"* is not a softer case than *"wrong Space"*.

    docs/10 §3.5 gives the reason for answering `404` rather than `403` on
    this code: *"để không tiết lộ đối tượng tồn tại"*. Answering differently
    for an unknown id would leak precisely that.
    """
    backend.register_space(DOOMED_SPACE)
    known = backend.delete_document("doc-nowhere", space_id=DOOMED_SPACE)

    assert known.status_code == 404
    assert known.json()[CODE_FIELD] == ErrorCode.OBJECT_NOT_IN_SPACE


def test_c_the_document_of_the_named_space_is_deleted(backend, world):
    """The other half of the case: a truthful call must still work, otherwise
    the assertion above could pass on a service that refuses everything."""
    backend.register_space(KEEPER_SPACE)
    world.seed_document(document_id="doc-in-keeper", space_id=KEEPER_SPACE)

    response = backend.delete_document("doc-in-keeper", space_id=KEEPER_SPACE)

    assert response.status_code == 200
    assert response.json() == {"outcome": "deleted", "background_cleanup_complete": True}
    assert world.document_ids() == set()
    assert world.point_ids() == set()


def test_c_deleting_the_same_document_twice_reports_already_deleted(backend, world):
    """docs/10 §10: *"Xoá vĩnh viễn gọi hai lần | Lần hai trả `already_deleted`,
    không lỗi"*. Two DIFFERENT idempotency keys — this is a genuine second
    call, not a replay of the first (that is case 5)."""
    backend.register_space(KEEPER_SPACE)
    world.seed_document(document_id="doc-in-keeper", space_id=KEEPER_SPACE)

    first = backend.delete_document("doc-in-keeper", space_id=KEEPER_SPACE)
    second = backend.delete_document("doc-in-keeper", space_id=KEEPER_SPACE)

    assert first.json()["outcome"] == "deleted"
    assert second.status_code == 200
    assert second.json()["outcome"] == "already_deleted"
