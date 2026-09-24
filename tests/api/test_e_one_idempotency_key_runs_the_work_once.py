"""Case 5 of the work-order — docs/10 §3.4: *"Mọi lời gọi ghi mang header
`Idempotency-Key`. Gửi lại cùng khoá thì nhận lại đúng kết quả lần đầu, không
ghi thêm."*

The load-bearing assertion is the one that counts work at the BOTTOM of the
stack (`world.cleanup.calls`), not the one comparing two response bodies. A
middleware that re-ran the route and happened to produce the same JSON would
pass a body comparison and fail this — and re-running is exactly what *"không
ghi thêm"* forbids.
"""

from __future__ import annotations

from api.errors import CODE_FIELD, ErrorCode
from conftest import DOOMED_SPACE, KEEPER_SPACE


def test_e_the_same_key_and_the_same_body_replays_the_first_answer(backend, world):
    backend.register_space(KEEPER_SPACE)
    world.seed_document(document_id="doc-in-keeper", space_id=KEEPER_SPACE)

    first = backend.delete_document(
        "doc-in-keeper", space_id=KEEPER_SPACE, idempotency_key="key-delete-1"
    )
    calls_after_first = list(world.cleanup.calls)

    replay = backend.delete_document(
        "doc-in-keeper", space_id=KEEPER_SPACE, idempotency_key="key-delete-1"
    )

    assert first.status_code == 200
    assert first.json() == {"outcome": "deleted", "background_cleanup_complete": True}
    assert replay.status_code == first.status_code
    assert replay.json() == first.json(), "a replay must return the first answer"

    # ⭐ The business function did not run a second time. Without the
    # middleware the answer would have been `already_deleted` — a different,
    # and therefore visibly wrong, body.
    assert world.cleanup.calls == calls_after_first, (
        "the deletion ran again behind a replayed Idempotency-Key"
    )


def test_e_a_replay_carries_its_own_request_id(backend, world):
    """The stored response is the BODY, not the headers: two distinct calls
    must not share one `X-Request-Id`, or one incident cannot be told from the
    other in either side's log (docs/10 §3.4)."""
    backend.register_space(KEEPER_SPACE)
    world.seed_document(document_id="doc-in-keeper", space_id=KEEPER_SPACE)

    first = backend.call(
        "DELETE",
        "/v1/documents/doc-in-keeper",
        json={
            "space_id": KEEPER_SPACE,
            "reason": "Tài liệu đưa nhầm vào kho",
            "actor": {"user_id": "manager-lan", "acting_as": "manager"},
        },
        idempotency_key="key-delete-2",
        request_id="request-first",
    )
    replay = backend.call(
        "DELETE",
        "/v1/documents/doc-in-keeper",
        json={
            "space_id": KEEPER_SPACE,
            "reason": "Tài liệu đưa nhầm vào kho",
            "actor": {"user_id": "manager-lan", "acting_as": "manager"},
        },
        idempotency_key="key-delete-2",
        request_id="request-second",
    )

    assert first.headers["X-Request-Id"] == "request-first"
    assert replay.headers["X-Request-Id"] == "request-second"
    assert replay.json() == first.json()


def test_e_the_same_key_with_a_different_body_is_refused(backend, world):
    """Never the stored answer: replying about Space A when asked about Space
    B is the silent failure the key is supposed to prevent."""
    backend.register_space(DOOMED_SPACE)
    backend.register_space(KEEPER_SPACE)
    world.seed_document(document_id="doc-doomed-1", space_id=DOOMED_SPACE)
    world.seed_document(document_id="doc-in-keeper", space_id=KEEPER_SPACE)

    first = backend.delete_space(DOOMED_SPACE, idempotency_key="key-space-1")
    reused = backend.delete_space(KEEPER_SPACE, idempotency_key="key-space-1")
    # The refused call must not have QUEUED anything either — since 24/9 the
    # emptying is a background job, so a `422` that had already submitted one
    # would delete the second Space a moment later, with the refusal already
    # on the wire.
    world.run_background()

    assert first.status_code == 202
    assert reused.status_code == 422
    assert reused.json()[CODE_FIELD] == ErrorCode.IDEMPOTENCY_KEY_REUSED
    assert world.document_ids() == {"doc-in-keeper"}, (
        "the refused call either deleted the second Space or returned the "
        "first Space's answer about it"
    )
    assert backend.read_space(KEEPER_SPACE).json()["state"] == "in_use"


def test_e_a_write_without_an_idempotency_key_is_refused(backend, world):
    """docs/10 §3.4 makes the header mandatory on writes. Waving it through
    would be the fake Backend being *"dễ dãi"* about the contract — §10
    forbids that of the fake, and this endpoint has no reason to be softer
    than the fake is."""
    response = backend.call(
        "POST",
        "/v1/spaces",
        json={"space_id": DOOMED_SPACE, "actor": {"user_id": "u1", "acting_as": "manager"}},
        send_idempotency_key=False,  # the rule this case breaks
    )

    assert response.status_code == 400
    assert response.json()[CODE_FIELD] == ErrorCode.IDEMPOTENCY_KEY_MISSING
    assert world.registry.get(DOOMED_SPACE) is None, "the write ran behind a 400"


def test_e_reads_need_no_idempotency_key(backend, world):
    """A `GET` carries no write, so §3.4 does not ask for the header — and a
    service that demanded it would make Backend mint keys for reads."""
    backend.register_space(DOOMED_SPACE)

    response = backend.call("GET", f"/v1/spaces/{DOOMED_SPACE}")

    assert response.status_code == 200
