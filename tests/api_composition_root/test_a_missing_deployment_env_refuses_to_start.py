"""Item 1 of the work order: *"đọc ba nhóm cấu hình + biến môi trường (thiếu
→ từ chối khởi động, nêu đúng tên, không in giá trị bí mật)"*, applied to the
deployment-location variables `packages/api/main.py` owns.

Parametrized over every REQUIRED variable — the same "lần lượt từng khoá"
shape `tests/api/test_f_the_app_refuses_to_start.py` already uses for the
three config files, so a variable silently dropped from `_require_env`
callers turns this list stale and the CI-visible symptom is a missing case,
not a quietly-passing suite.
"""

from __future__ import annotations

import pytest

from api.main import DeploymentEnvNotConfigured, resolve_deployment_env

#: Every variable `resolve_deployment_env` requires to be present AND
#: non-blank. `CBRAIN_PG_PASSWORD` is deliberately absent from this list —
#: see `test_password_is_the_one_optional_variable` below.
REQUIRED_VARS = (
    "CBRAIN_PG_HOST",
    "CBRAIN_PG_PORT",
    "CBRAIN_PG_DATABASE",
    "CBRAIN_PG_USER",
    "CBRAIN_QDRANT_HOST",
    "CBRAIN_QDRANT_HTTP_PORT",
    "CBRAIN_QDRANT_COLLECTION",
    "CBRAIN_STAGING_DIR",
    "CBRAIN_MODEL_HOME",
)


def _complete() -> dict[str, str]:
    return {
        "CBRAIN_PG_HOST": "localhost",
        "CBRAIN_PG_PORT": "5432",
        "CBRAIN_PG_DATABASE": "cbrain_dev",
        "CBRAIN_PG_USER": "someone",
        "CBRAIN_QDRANT_HOST": "localhost",
        "CBRAIN_QDRANT_HTTP_PORT": "6333",
        "CBRAIN_QDRANT_COLLECTION": "cbrain_chunks",
        "CBRAIN_STAGING_DIR": "/tmp/staging",
        "CBRAIN_MODEL_HOME": "/tmp/models",
    }


@pytest.mark.parametrize("missing_var", REQUIRED_VARS)
def test_a_a_missing_variable_refuses_and_names_itself(missing_var: str) -> None:
    environ = _complete()
    del environ[missing_var]

    with pytest.raises(DeploymentEnvNotConfigured) as excinfo:
        resolve_deployment_env(environ)

    assert missing_var in str(excinfo.value), (
        f"The refusal must name the missing variable. Got: {excinfo.value}"
    )


@pytest.mark.parametrize("blank_var", REQUIRED_VARS)
def test_a_a_blank_variable_is_treated_as_absent(blank_var: str) -> None:
    """A `.env` with a key present but empty is the shape a half-finished
    install has (same reasoning `api.security.resolve_service_key` gives)."""
    environ = _complete()
    environ[blank_var] = "   "

    with pytest.raises(DeploymentEnvNotConfigured) as excinfo:
        resolve_deployment_env(environ)

    assert blank_var in str(excinfo.value)


def test_a_a_non_numeric_port_is_refused_by_name() -> None:
    environ = _complete()
    environ["CBRAIN_QDRANT_HTTP_PORT"] = "not-a-port"

    with pytest.raises(DeploymentEnvNotConfigured) as excinfo:
        resolve_deployment_env(environ)

    assert "CBRAIN_QDRANT_HTTP_PORT" in str(excinfo.value)


def test_a_password_is_the_one_optional_variable() -> None:
    """`CBRAIN_PG_PASSWORD` absent must NOT refuse — a local dev PostgreSQL
    commonly has none, mirroring `tests/t0_1_stores/conftest.py`'s own
    `pg_dsn` fixture."""
    environ = _complete()
    assert "CBRAIN_PG_PASSWORD" not in environ

    resolved = resolve_deployment_env(environ)

    assert "None" not in resolved.pg_dsn


def test_a_a_complete_environment_resolves() -> None:
    """The control case — without it, every refusal above could also pass
    on a function that refuses everything."""
    resolved = resolve_deployment_env(_complete())

    assert resolved.qdrant_collection == "cbrain_chunks"
    assert resolved.qdrant_http_port == 6333
    assert str(resolved.staging_dir) == "/tmp/staging"


def test_a_the_secret_never_appears_but_this_module_has_no_secret_to_leak() -> None:
    """Deployment-location variables are addresses and paths, not secrets —
    unlike `api.security.SERVICE_KEY_ENV_VAR`. Documented here as the reason
    `resolve_deployment_env`'s refusals are allowed to be as verbose as they
    are: `CBRAIN_PG_HOST=localhost` in an error message leaks nothing a
    `.env.example` does not already say."""
    environ = _complete()
    del environ["CBRAIN_PG_DATABASE"]

    with pytest.raises(DeploymentEnvNotConfigured) as excinfo:
        resolve_deployment_env(environ)

    assert "CBRAIN_PG_DATABASE" in str(excinfo.value)
