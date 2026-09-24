"""The control case for the whole folder: a fully correct deployment (real
PostgreSQL, real Qdrant, a FAKE BGE-M3) builds and serves — without it, every
refusal test elsewhere in this folder could also be passing against a
function that refuses everything.

Also covers item 2 of the work order: *"Khởi động: `recover()` rồi
`worker.start()`. Tắt: dừng worker gọn gàng."* — through `TestClient`'s own
context manager, which is what actually triggers FastAPI's `lifespan`.
"""

from __future__ import annotations

from starlette.testclient import TestClient

from api.main import build_deployment_app


def test_d_a_complete_deployment_builds(
    pg, qdrant, config_dir, complete_environ, deployment_env, fake_model
) -> None:
    app = build_deployment_app(
        config_dir=config_dir,
        environ=complete_environ,
        deployment=deployment_env,
        pg_connection=pg,
        qdrant_client=qdrant,
        embedding_model=fake_model,
    )
    assert app is not None


def test_d_meta_reports_ready_true_end_to_end(
    pg, qdrant, config_dir, complete_environ, deployment_env, fake_model
) -> None:
    app = build_deployment_app(
        config_dir=config_dir,
        environ=complete_environ,
        deployment=deployment_env,
        pg_connection=pg,
        qdrant_client=qdrant,
        embedding_model=fake_model,
    )
    with TestClient(app) as client:
        response = client.get(
            "/v1/meta", headers={"X-Service-Key": complete_environ["CBRAIN_API_SERVICE_KEY"]}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["not_ready_reason"] is None
    assert body["contract_version"]
    assert body["limits"] == {
        "accepted_formats": ["pdf", "docx", "md", "txt"],
        "max_upload_bytes": 104857600,
    }


def test_d_a_real_space_registration_reaches_the_real_postgresql(
    pg, qdrant, config_dir, complete_environ, deployment_env, fake_model
) -> None:
    """One write, through the real HTTP surface, landing in the real
    `space_registry` table — proof the live `PgSpaceRegistry` wiring (not
    just the readiness probe) is correct."""
    app = build_deployment_app(
        config_dir=config_dir,
        environ=complete_environ,
        deployment=deployment_env,
        pg_connection=pg,
        qdrant_client=qdrant,
        embedding_model=fake_model,
    )
    headers = {
        "X-Service-Key": complete_environ["CBRAIN_API_SERVICE_KEY"],
        "Idempotency-Key": "test-d-register-space",
    }
    with TestClient(app) as client:
        response = client.post(
            "/v1/spaces",
            headers=headers,
            json={"space_id": "space-composition-root-test", "actor": {"user_id": "u1", "acting_as": "manager"}},
        )
    assert response.status_code == 200

    row = pg.execute(
        "SELECT state FROM space_registry WHERE space_id = %s",
        ("space-composition-root-test",),
    ).fetchone()
    assert row is not None
    assert row[0] == "in_use"


def test_d_lifespan_starts_and_stops_the_worker(
    pg, qdrant, config_dir, complete_environ, deployment_env, fake_model
) -> None:
    """Item 2: `recover()` then `worker.start()` at startup; `worker.stop()`
    on shutdown. `TestClient` as a context manager drives FastAPI's real
    ASGI lifespan protocol — this is not calling the lifespan function
    directly, it is the same startup/shutdown `uvicorn` triggers.
    """
    app = build_deployment_app(
        config_dir=config_dir,
        environ=complete_environ,
        deployment=deployment_env,
        pg_connection=pg,
        qdrant_client=qdrant,
        embedding_model=fake_model,
    )

    with TestClient(app):
        pass  # the whole point: startup and shutdown must both complete cleanly

    # If `worker.stop()` had not run, the daemon thread would still be
    # joinable-but-alive; nothing here asserts a private attribute, since
    # this test's job is that the ASGI lifespan protocol completes without
    # hanging or raising — a `worker.start()` called twice would raise
    # RuntimeError (api.background.BackgroundWorker.start's own docstring),
    # which a second `with TestClient(app):` below proves did not happen.
    with TestClient(app):
        pass
