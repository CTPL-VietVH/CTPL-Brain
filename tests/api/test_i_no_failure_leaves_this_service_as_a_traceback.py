"""Whatever goes wrong, Backend gets `{code, message}` — docs/10 §3.5.

Two kinds of failure are covered, and neither is a business refusal:

* a malformed body. FastAPI's own answer is `{"detail": [...]}`, which carries
  no `code` at all — Backend would have to branch on English prose. The
  handler splits it: a failure on a SCOPE field is `400 SCOPE_MISSING` (§3.3),
  anything else is `422 INVALID_REQUEST`.
* an unforeseen exception. The catch-all turns it into `500 INTERNAL_ERROR`
  with a body that describes nothing, while the traceback goes to the log with
  the request id attached.

The `SCOPE_MISSING` cases are the ones docs/10 §10 lists as a shared
acceptance case — *"Lời gọi thiếu `readable_space_ids` | `400 SCOPE_MISSING`,
không trả dữ liệu"* — read here for the field this slice actually has.
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter

from api.app import build_app
from api.errors import CODE_FIELD, MESSAGE_FIELD, ErrorCode
from api.ingestion_routes import (
    INGESTION_EXCEPTION_HANDLERS,
    create_ingestion_router,
)
from api.security import REQUEST_ID_HEADER, SERVICE_KEY_ENV_VAR
from api.settings import ReadinessReport
from conftest import DOOMED_SPACE, TEST_SERVICE_KEY
from fake_backend import DEFAULT_ACTOR, FakeBackend


@pytest.mark.parametrize(
    "body, what_is_wrong",
    [
        ({"actor": DEFAULT_ACTOR}, "space_id absent"),
        ({"space_id": "", "actor": DEFAULT_ACTOR}, "space_id blank — the workspace='' bug"),
        ({"space_id": DOOMED_SPACE}, "actor absent"),
        ({"space_id": DOOMED_SPACE, "actor": {"acting_as": "manager"}}, "actor.user_id absent"),
        (
            {"space_id": DOOMED_SPACE, "actor": {"user_id": "", "acting_as": "manager"}},
            "actor.user_id blank",
        ),
    ],
)
def test_i_a_missing_or_blank_scope_field_is_scope_missing(backend, body, what_is_wrong):
    response = backend.call("POST", "/v1/spaces", json=body)

    assert response.status_code == 400, what_is_wrong
    assert response.json()[CODE_FIELD] == ErrorCode.SCOPE_MISSING
    assert set(response.json()) == {CODE_FIELD, MESSAGE_FIELD}


@pytest.mark.parametrize(
    "body, what_is_wrong",
    [
        (
            {"space_id": DOOMED_SPACE, "actor": DEFAULT_ACTOR, "space_is_private": True},
            "a field this endpoint does not have",
        ),
        (
            {"space_id": DOOMED_SPACE, "actor": {"user_id": "u1", "acting_as": "owner"}},
            "a role outside the four of docs/10 §3.2",
        ),
    ],
)
def test_i_other_malformed_bodies_are_invalid_request_not_scope_missing(
    backend, body, what_is_wrong
):
    """`SCOPE_MISSING` is the one code Backend acts on automatically (send the
    scope). Stretching it to cover a typo elsewhere would make that reaction
    wrong half the time."""
    response = backend.call("POST", "/v1/spaces", json=body)

    assert response.status_code == 422, what_is_wrong
    assert response.json()[CODE_FIELD] == ErrorCode.INVALID_REQUEST


def test_i_an_unforeseen_failure_becomes_internal_error_not_a_traceback(
    config_dir, environ, services, idempotency_store
):
    """The catch-all. Built with one extra route that raises, because the
    property under test is what happens when NOTHING claimed the exception."""
    broken = APIRouter()

    @broken.get("/v1/deliberately-broken")
    def raise_something() -> None:
        raise RuntimeError("password=hunter2 leaked through a stack trace")

    def probe() -> ReadinessReport:
        return ReadinessReport(ready=True, not_ready_reason=None)

    app = build_app(
        config_dir=config_dir,
        environ=environ,
        service_key_env_var=SERVICE_KEY_ENV_VAR,
        routers=[create_ingestion_router(services=services), broken],
        exception_handlers=INGESTION_EXCEPTION_HANDLERS,
        readiness=probe,
        idempotency_store=idempotency_store,
    )

    with FakeBackend(app, service_key=TEST_SERVICE_KEY) as fake:
        response = fake.call("GET", "/v1/deliberately-broken")

    assert response.status_code == 500
    assert response.json()[CODE_FIELD] == ErrorCode.INTERNAL_ERROR
    assert set(response.json()) == {CODE_FIELD, MESSAGE_FIELD}
    assert "hunter2" not in response.text, "the exception's own words reached the caller"
    assert "Traceback" not in response.text
    assert response.headers.get(REQUEST_ID_HEADER), (
        "even a 500 must carry the id an operator will search the log for"
    )
