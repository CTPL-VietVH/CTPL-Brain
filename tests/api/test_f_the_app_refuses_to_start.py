"""Case 6 of the work-order, and the API layer's share of 08 T1.2:

    *"có một test **chạy service với file cấu hình thiếu LẦN LƯỢT TỪNG KHOÁ**,
    và mỗi lần đều khẳng định service không khởi động được, báo rõ thiếu khoá
    nào."*

plus the same standard applied to the service key (docs/10 §1 T1): a
deployment with no credential must not reach the port.

⚠️ The parametrisation reads the REAL config files, exactly as
`tests/t1_2_config/test_a_missing_key_refuses_to_start.py` does, and for the
reason stated there: taking the list from `CONTRACT_KEYS` & co. would let one
person remove a key from that tuple, add a default in code, and delete the
test case for it in the same edit — with the suite still green. Reading the
files means adding a parameter to `config/` automatically adds a case here.

**No app object may exist after any of these.** A service that comes up and
then answers `503` is a different design (docs/10 §3.5 `SERVICE_MISCONFIGURED`
is for a running service whose STORE drifted); a service with no configuration
and no credential has nothing to serve from.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from api.app import build_app
from api.idempotency import InMemoryIdempotencyStore
from api.ingestion_routes import (
    INGESTION_EXCEPTION_HANDLERS,
    IngestionServices,
    create_ingestion_router,
)
from api.security import SERVICE_KEY_ENV_VAR, ServiceKeyNotConfigured
from api.settings import ReadinessReport
from conftest import CONFIG_FILENAMES, REPO_ROOT, TEST_SERVICE_KEY
from schema.config import MissingConfigKeyError


def _real_mapping(filename: str) -> dict:
    with (REPO_ROOT / "config" / filename).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


#: (file, key) for every key of every real config file — "lần lượt TỪNG khoá".
EVERY_KEY = [
    pytest.param(filename, key, id=f"{filename}:{key}")
    for filename in CONFIG_FILENAMES
    for key in _real_mapping(filename)
]


def _build(
    *,
    config_dir: pathlib.Path,
    environ: dict[str, str],
    services: IngestionServices,
    idempotency_store: InMemoryIdempotencyStore,
):
    def probe() -> ReadinessReport:
        return ReadinessReport(ready=True, not_ready_reason=None)

    return build_app(
        config_dir=config_dir,
        environ=environ,
        service_key_env_var=SERVICE_KEY_ENV_VAR,
        routers=[create_ingestion_router(services=services)],
        exception_handlers=INGESTION_EXCEPTION_HANDLERS,
        readiness=probe,
        idempotency_store=idempotency_store,
    )


@pytest.mark.parametrize("filename, missing_key", EVERY_KEY)
def test_f_a_missing_config_key_stops_the_app_from_being_built(
    config_dir, environ, services, idempotency_store, filename, missing_key
):
    """Remove one key from one file → no app, and the message names the key.

    The day someone writes `data.get("document_cap", 6)` "for convenience",
    the `retrieval.yaml:document_cap` case here stops raising and turns red.
    """
    path = config_dir / filename
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert missing_key in data, "the copied config file no longer has this key"
    del data[missing_key]
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)

    with pytest.raises(MissingConfigKeyError) as excinfo:
        _build(
            config_dir=config_dir,
            environ=environ,
            services=services,
            idempotency_store=idempotency_store,
        )

    message = str(excinfo.value)
    assert f"`{missing_key}`" in message, (
        f"The refusal must name the missing key. Got: {message}"
    )
    assert str(path) in message, "The refusal must name the file."


@pytest.mark.parametrize("filename", CONFIG_FILENAMES)
def test_f_a_config_file_that_is_not_there_stops_the_app(
    config_dir, environ, services, idempotency_store, filename
):
    """All three groups are loaded at startup, including the one today's
    endpoints do not read — see `build_app`'s docstring. A deployment missing
    `retrieval.yaml` must not come up serving Space deletions and then fail on
    the first question."""
    (config_dir / filename).unlink()

    with pytest.raises(Exception) as excinfo:
        _build(
            config_dir=config_dir,
            environ=environ,
            services=services,
            idempotency_store=idempotency_store,
        )

    assert filename in str(excinfo.value)


@pytest.mark.parametrize(
    "broken_environ, why",
    [
        ({}, "variable absent"),
        ({SERVICE_KEY_ENV_VAR: ""}, "variable present but empty"),
        ({SERVICE_KEY_ENV_VAR: "   "}, "variable present but blank"),
    ],
)
def test_f_a_missing_service_key_stops_the_app_from_being_built(
    config_dir, services, idempotency_store, broken_environ, why
):
    """docs/10 §1 T1 — no credential, no service.

    Blank counts as absent: an empty value in a `.env` file is the shape a
    half-finished install has, and it must not be the shape that boots. Were
    it allowed through, the comparison in `presented_key_matches` would be
    against an empty secret.
    """
    with pytest.raises(ServiceKeyNotConfigured) as excinfo:
        _build(
            config_dir=config_dir,
            environ=broken_environ,
            services=services,
            idempotency_store=idempotency_store,
        )

    assert SERVICE_KEY_ENV_VAR in str(excinfo.value), (
        f"The refusal ({why}) must name the environment variable — that name "
        "is the only thing the person on duty can act on."
    )


def test_f_the_secret_itself_never_appears_in_the_refusal(
    config_dir, services, idempotency_store
):
    """A misconfiguration message is read by whoever is on call and often
    pasted into a ticket. It names the VARIABLE, never a value."""
    wrong_variable = "CBRAIN_API_SERVICE_KEY_TYPO"

    def probe() -> ReadinessReport:
        return ReadinessReport(ready=True, not_ready_reason=None)

    with pytest.raises(ServiceKeyNotConfigured) as excinfo:
        build_app(
            config_dir=config_dir,
            environ={SERVICE_KEY_ENV_VAR: TEST_SERVICE_KEY},
            service_key_env_var=wrong_variable,
            routers=[create_ingestion_router(services=services)],
            exception_handlers=INGESTION_EXCEPTION_HANDLERS,
            readiness=probe,
            idempotency_store=idempotency_store,
        )

    assert wrong_variable in str(excinfo.value)
    assert TEST_SERVICE_KEY not in str(excinfo.value)


def test_f_a_complete_configuration_does_build(
    config_dir, environ, services, idempotency_store
):
    """The control case. Without it, every assertion above would also pass on
    a `build_app` that refuses everything."""
    app = _build(
        config_dir=config_dir,
        environ=environ,
        services=services,
        idempotency_store=idempotency_store,
    )
    assert app is not None
