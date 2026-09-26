"""Case 7 of the work-order — `GET /v1/meta` (docs/10 §3.6).

Two properties, and the second is the one worth the file:

1. the endpoint answers `ready`, `not_ready_reason`, `contract_version` and
   `limits`;
2. ⭐ **every NUMBER in that answer comes from a config file.** The test walks
   the whole JSON and collects every `int`/`float` it finds, then asserts the
   set is exactly the set derivable from the config the app was built with.
   Today that set is empty, and the assertion still does its job: the moment
   someone publishes `"max_recent_turns": 10` with a literal behind it, this
   turns red. CLAUDE.md Mục 4 quy tắc 5 — *"Không con số cứng trong mã"* —
   applied where it is easiest to break, because a number on a status endpoint
   looks like documentation rather than configuration.

There is a third property this file guards from the other direction: `limits`
must not grow to include tuning parameters. docs/10 §2: *"Cấu hình mô hình và
tham số | AI | **Không qua API.** Chỉ đổi bằng file cấu hình. Cố ý không đưa
lên giao diện quản trị."* So `document_cap`, `inheritance_decay` and the rest
of 07 Mục 3.2 are checked to be ABSENT, by name.
"""

from __future__ import annotations

import yaml

from api.ingestion_routes import (
    INGESTION_EXCEPTION_HANDLERS,
    create_ingestion_router,
)
from api.security import SERVICE_KEY_ENV_VAR
from api.settings import ReadinessReport
from conftest import TEST_SERVICE_KEY
from fake_backend import FakeBackend
from schema.version import LOCAL_SCHEMA_VERSION

#: Twelve of the thirteen parameters of 07 Mục 3.2 — none of them may appear here.
#:
#: ⭐ The thirteenth, `max_upload_bytes`, is deliberately ABSENT from this set:
#: docs/10 §3.6 REQUIRES `/v1/meta` to publish *"cỡ file tối đa"*, so Backend
#: can stop an upload it already knows will come back `413`. That is not a
#: hole in docs/10 §2 (*"Cấu hình mô hình và tham số ... Không qua API"*) —
#: the value is still changed only by editing `config/ingestion.yaml`; this
#: endpoint merely reads it out. Its siblings `source_download_timeout_seconds`,
#: `qdrant_upsert_batch_points` and `embedding_batch_size` ARE in the set: none
#: of them is something Backend can act on.
TUNING_PARAMETER_NAMES = frozenset(
    {
        "inheritance_decay",
        "document_cap",
        "cap_warning_multiple",
        "relation_pull_threshold",
        "saturation_epsilon",
        "saturation_rounds",
        "scan_pair_budget",
        "scan_time_budget",
        "chunk_length_cap",
        "source_download_timeout_seconds",
        "qdrant_upsert_batch_points",
        "embedding_batch_size",
    }
)


def _numbers(value) -> list[float]:
    """Every int/float anywhere in a JSON value.

    `bool` is excluded: `True` is an `int` in Python, and `ready` is not a
    number anybody configured.
    """
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, dict):
        return [number for item in value.values() for number in _numbers(item)]
    if isinstance(value, list):
        return [number for item in value for number in _numbers(item)]
    return []


def test_g_meta_answers_the_four_fields_of_section_3_6(backend):
    response = backend.read_meta()

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"ready", "not_ready_reason", "contract_version", "limits"}
    assert body["ready"] is True
    assert body["not_ready_reason"] is None


def test_g_contract_version_is_the_shared_schema_version(backend):
    """The only version number in this repo that describes a deployed
    artifact: the two numbers of `packages/schema/version.py` (07 Mục 3.1,
    DX3). Written as `str(LOCAL_SCHEMA_VERSION)` rather than typed out, so it
    cannot drift from the module it describes."""
    body = backend.read_meta().json()

    assert body["contract_version"] == str(LOCAL_SCHEMA_VERSION)


def test_g_limits_are_read_from_the_config_the_app_was_built_with(backend, config_dir):
    """Both limits on the wire == both limits in the file.

    The expected values are read from the config file this app was built
    from, never typed into the test: a literal here would be a third home for
    the parameter (07 Mục 3.3 quy tắc 2).

    `max_upload_bytes` joined the answer on 24/9/2026, when `POST
    /v1/ingestions` started enforcing it — docs/10 §3.6 asks for *"cỡ file
    tối đa"*, and the rule this file guards is that a number only appears
    here once some code actually enforces it.
    """
    ingestion_config = yaml.safe_load(
        (config_dir / "ingestion.yaml").read_text(encoding="utf-8")
    )

    body = backend.read_meta().json()

    assert body["limits"] == {
        "accepted_formats": ingestion_config["accepted_formats"],
        "max_upload_bytes": ingestion_config["max_upload_bytes"],
    }


def test_g_every_number_in_the_answer_comes_from_config(backend, config_dir):
    """⭐ No literal number may reach Backend through this endpoint."""
    ingestion_config = yaml.safe_load(
        (config_dir / "ingestion.yaml").read_text(encoding="utf-8")
    )
    retrieval_config = yaml.safe_load(
        (config_dir / "retrieval.yaml").read_text(encoding="utf-8")
    )
    contract_config = yaml.safe_load(
        (config_dir / "contract.yaml").read_text(encoding="utf-8")
    )
    from_config = set(
        _numbers(ingestion_config) + _numbers(retrieval_config) + _numbers(contract_config)
    )

    published = set(_numbers(backend.read_meta().json()))

    assert published <= from_config, (
        "GET /v1/meta published a number that is in no config file: "
        f"{sorted(published - from_config)}. Every limit Backend reads here "
        "must have a config key behind it (CLAUDE.md Mục 4 quy tắc 5)."
    )


def test_g_no_tuning_parameter_is_published(backend):
    """docs/10 §2 keeps 07 Mục 3.2 off the API surface entirely."""
    body = backend.read_meta().json()
    leaked = TUNING_PARAMETER_NAMES & set(body["limits"])

    assert not leaked, (
        f"GET /v1/meta publishes tuning parameters: {sorted(leaked)}. docs/10 "
        '§2: "Cấu hình mô hình và tham số ... Không qua API."'
    )


def test_g_a_service_that_is_not_ready_says_why(
    config_dir, environ, services, idempotency_store
):
    """§3.6 exists so Backend *"biết AI đang từ chối phục vụ trước khi người
    dùng gặp lỗi 503"*. A deployment that is not serving must say what is
    wrong, in the same call."""
    from api.app import build_app

    reason = "Cấu hình hợp đồng lệch con dấu của kho vector (07 Mục 3.1)."

    def probe() -> ReadinessReport:
        return ReadinessReport(ready=False, not_ready_reason=reason)

    app = build_app(
        config_dir=config_dir,
        environ=environ,
        service_key_env_var=SERVICE_KEY_ENV_VAR,
        routers=[create_ingestion_router(services=services)],
        exception_handlers=INGESTION_EXCEPTION_HANDLERS,
        readiness=probe,
        idempotency_store=idempotency_store,
    )

    with FakeBackend(app, service_key=TEST_SERVICE_KEY) as fake:
        body = fake.read_meta().json()

    assert body["ready"] is False
    assert body["not_ready_reason"] == reason


def test_g_meta_is_still_behind_the_service_key(backend):
    """§3.6 says *"Không cần `actor`"* — the human identity. It does not
    exempt the service credential, and §1 T1 says *"Mọi lời gọi"*."""
    assert backend.read_meta(send_service_key=False).status_code == 401


def test_g_unused_services_fixture_is_the_same_world(services, world):
    """Guard for the fixtures themselves: the app under test must be wired to
    the same stores a case inspects, or every assertion about a store is
    vacuous."""
    assert services.space_registry is world.registry
    assert services.profile_store is world.profile_store
    assert services.document_source is world.profile_store
