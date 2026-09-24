"""Case 1 of the work-order — docs/10 §1 T1: *"Mọi lời gọi không qua xác thực
dịch vụ đều bị từ chối."*

Three things are asserted, and the second is the one that is easy to lose:

1. no key and wrong key both get `401`;
2. they get the SAME body — a difference in wording would confirm to a prober
   that the header name is right, which is the same reasoning §3.5 uses for
   answering `404` instead of `403` on `OBJECT_NOT_IN_SPACE`;
3. nothing was written. A refusal that still ran the write would be the worst
   kind of pass: green test, open door.
"""

from __future__ import annotations

import pytest

from api.errors import CODE_FIELD, MESSAGE_FIELD, ErrorCode
from api.security import REQUEST_ID_HEADER
from conftest import DOOMED_SPACE


def test_a_call_with_no_service_key_is_refused(backend, world):
    response = backend.call(
        "POST",
        "/v1/spaces",
        json={"space_id": DOOMED_SPACE, "actor": {"user_id": "u1", "acting_as": "manager"}},
        send_service_key=False,  # the rule this case breaks, named at the call site
    )

    assert response.status_code == 401
    assert response.json()[CODE_FIELD] == ErrorCode.UNAUTHENTICATED
    assert world.registry.get(DOOMED_SPACE) is None, (
        "A call that failed service authentication still reached the Space "
        "register — the write ran behind a 401."
    )


def test_a_wrong_service_key_is_refused_with_the_identical_body(backend, world):
    """Both refusals must be indistinguishable to the caller."""
    without = backend.call(
        "POST",
        "/v1/spaces",
        json={"space_id": DOOMED_SPACE, "actor": {"user_id": "u1", "acting_as": "manager"}},
        send_service_key=False,
    )
    wrong = backend.call(
        "POST",
        "/v1/spaces",
        json={"space_id": DOOMED_SPACE, "actor": {"user_id": "u1", "acting_as": "manager"}},
        service_key="not-the-service-key",
    )

    assert wrong.status_code == without.status_code == 401
    assert wrong.json() == without.json(), (
        "Missing key and wrong key answer differently — that difference tells "
        "a prober which half they got right."
    )
    assert set(wrong.json()) == {CODE_FIELD, MESSAGE_FIELD}, (
        "docs/10 §3.5: the error envelope carries exactly `code` and `message`."
    )
    assert world.registry.get(DOOMED_SPACE) is None


@pytest.mark.parametrize(
    "method, path, json_body",
    [
        ("POST", "/v1/spaces", {"space_id": DOOMED_SPACE, "actor": {"user_id": "u1", "acting_as": "manager"}}),
        ("DELETE", f"/v1/spaces/{DOOMED_SPACE}", {"reason": "r", "actor": {"user_id": "u1", "acting_as": "manager"}}),
        ("GET", f"/v1/spaces/{DOOMED_SPACE}", None),
        ("DELETE", "/v1/documents/doc-1", {"space_id": DOOMED_SPACE, "reason": "r", "actor": {"user_id": "u1", "acting_as": "manager"}}),
        ("GET", "/v1/meta", None),
    ],
)
def test_a_every_endpoint_is_behind_service_authentication(backend, method, path, json_body):
    """T1 says *"Mọi lời gọi"*, so the check is not a per-route decision.

    `GET /v1/meta` is in the list on purpose: §3.6 exempts it from `actor`
    (the human), not from the service credential. An unauthenticated readiness
    endpoint is also a free monitor of when this deployment is down.
    """
    response = backend.call(method, path, json=json_body, send_service_key=False)

    assert response.status_code == 401, f"{method} {path} answered without a service key"
    assert response.json()[CODE_FIELD] == ErrorCode.UNAUTHENTICATED


def test_a_a_refused_call_still_carries_a_request_id(backend):
    """docs/10 §3.4 — every response, including the ones that never reached a
    route, is traceable."""
    response = backend.call("GET", "/v1/meta", send_service_key=False)

    assert response.headers.get(REQUEST_ID_HEADER), (
        "A 401 came back with no X-Request-Id — the one call an operator is "
        "most likely to be asked about is the one they cannot find."
    )
