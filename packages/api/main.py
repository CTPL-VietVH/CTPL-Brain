"""The composition root — the ONE module in this repo allowed to open a real
PostgreSQL connection, a real Qdrant client, and load the real BGE-M3 model,
and wire them into `api.app.build_app` plus the single background worker
(docs/10 §4.1 *"một bản sao duy nhất"*).

`packages/api/__init__.py` names exactly this gap: *"No composition root
that builds live stores... Wiring them to PostgreSQL and Qdrant belongs with
the write surface (08 T2.10), which has no owner yet."* This module is that
owner.

──────────────────────────────────────────────────────────────────────────
Layering — three things, kept separate on purpose
──────────────────────────────────────────────────────────────────────────

1. `resolve_deployment_env` — pure, no I/O. Reads the store-location
   environment variables (`.env`, same category as `CBRAIN_PG_HOST`: a
   per-install deployment fact, R6, not one of the three config groups of
   CLAUDE.md Mục 4). Missing or blank → refuse, naming the variable, same
   shape as `api.security.resolve_service_key`.
2. `connect_postgres` / `connect_qdrant` / `load_embedding_model` — open the
   real connections and load the real model. `load_embedding_model` takes an
   injectable `loader` so a test can hand it a fake `SentenceTransformer`
   without touching the 2.5GB model.
3. `build_deployment_app` — takes ALREADY-CONNECTED clients and an
   ALREADY-LOADED model and wires the live `Pg*`/`Qdrant*` store adapters into
   `IngestionPipeline` + `IngestionServices`, then calls `api.app.build_app`.
   This is what makes it testable against a real (disposable) PostgreSQL +
   Qdrant with a FAKE model, the same split `tests/t0_1_stores/conftest.py`
   already uses for the two live stores.

`create_app_from_env` is the only function that ties all three together by
reading `os.environ` and connecting for real — it is what `app_factory`
(the uvicorn entry point) calls.

──────────────────────────────────────────────────────────────────────────
What refuses to start, and what only degrades `GET /v1/meta`
──────────────────────────────────────────────────────────────────────────

Two different failure shapes, both required by the work order and both
already named in docs/10 §3.5 / §3.6:

* **Refuses to start** (raises before `uvicorn` binds a port): a deployment
  env var missing, a required PostgreSQL table missing (`_assert_tables_exist`
  — this module CHECKS, never `CREATE TABLE`s; that is
  `tools/provision/provision_stores.py`'s job, run once, by hand, before the
  service is ever started), the Qdrant collection missing or its stamp
  mismatching `config/contract.yaml` (`schema.embedding_registry`
  `assert_collection_ready_for_contract`, called once here before the app is
  handed to `uvicorn`).
* **Degrades `GET /v1/meta`** (docs/10 §3.6): the SAME stamp check, called
  again on every `/v1/meta` request by the `readiness` closure built in
  `_build_readiness`, because a store that goes unreachable AFTER a healthy
  start (network partition, PostgreSQL restart) must be visible as
  `ready=false` rather than crash the process or serve wrong answers.

⚠️ **Known limitation, reported as an escalation**: `_build_readiness` reuses
the SAME long-lived `psycopg.Connection` opened at startup. If PostgreSQL
drops the TCP connection outright (not just becomes briefly slow), `psycopg`
does not silently reconnect — `readiness()` will keep reporting `ready=false`
even after PostgreSQL is back up, until this process is restarted. A
connection pool with retry belongs with the "kho idempotency bền" follow-up
this task explicitly excludes; noted here so it is not mistaken for having
been solved.

──────────────────────────────────────────────────────────────────────────
What is explicitly NOT here (see the work order)
──────────────────────────────────────────────────────────────────────────

* No real Space-tree client (T2.6b) — `relation_scope` is
  `UnavailableSpaceScanScope`, the same honest stand-in
  `tests/api/conftest.py`'s `World` uses, so every freshly ingested document
  keeps saying *"chưa đối chiếu xong"* (docs/10 §7.1, PO chốt 24/9, K5).
* No durable idempotency store — `InMemoryIdempotencyStore`, same as every
  existing test. A restart forgets in-flight replay keys; a retried write
  simply re-runs (every business function here is independently re-runnable —
  see `api.idempotency`'s own docstring for why that is still safe).
* No pre-approval review endpoints (§4.3/§4.4) — this task builds only what
  §4.0–§4.2 and `GET /v1/meta` need to run end to end.
* No advisory-lock guard against a second copy of this process. See the
  report for the proposal and its risk — not installed here, by instruction.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

import psycopg
from fastapi import FastAPI
from qdrant_client import QdrantClient

from api.app import build_app
from api.background import BackgroundWorker
from api.idempotency import InMemoryIdempotencyStore
from api.ingestion_routes import (
    INGESTION_EXCEPTION_HANDLERS,
    IngestionServices,
    create_ingestion_router,
)
from api.security import SERVICE_KEY_ENV_VAR, TENANT_ID_ENV_VAR, resolve_tenant_id
from api.settings import ReadinessReport
from ingestion.deletion import QdrantVectorStoreDeleter
from ingestion.ingestion_pipeline import IngestionPipeline
from ingestion.pg_document_stores import PgBackgroundCleanup, PgDeletionLog, PgDocumentStore
from ingestion.pg_queue_stores import (
    PgIngestionRecordStore,
    PgPreApprovalBuffer,
    PgSpaceRegistry,
)
from ingestion.pre_approval_buffer import PRE_APPROVAL_CHUNK_TABLE, PRE_APPROVAL_DOCUMENT_TABLE
from ingestion.promotion import QdrantVectorStoreWriter
from ingestion.relations_scan import UnavailableSpaceScanScope
from ingestion.staging import StagingArea
from ingestion.vectorization import BgeM3Like
from schema.config import ContractConfig, load_contract_config, load_ingestion_config
from schema.embedding_registry import (
    EMBEDDING_MODEL_COLLECTIONS_TABLE,
    EMBEDDING_MODELS_TABLE,
    assert_collection_ready_for_contract,
)
from schema.store_schema import (
    DELETION_LOG_TABLE,
    DOCUMENT_TABLE,
    INGESTION_RECORD_TABLE,
    RELATION_TABLE,
    SPACE_REGISTRY_TABLE,
)

__all__ = [
    "REPO_ROOT",
    "CONFIG_DIR",
    "DeploymentEnv",
    "DeploymentEnvNotConfigured",
    "MissingTablesError",
    "app_factory",
    "build_deployment_app",
    "connect_postgres",
    "connect_qdrant",
    "create_app_from_env",
    "load_embedding_model",
    "resolve_deployment_env",
]

logger = logging.getLogger(__name__)

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
#: `config/` lives next to this checkout — R6 means each install IS a full
#: checkout of this repo (CLAUDE.md Mục 4: "chỗ đặt thư mục config/ là tham số
#: TRIỂN KHAI"; the composition root is exactly the caller that must "nêu rõ
#: đường dẫn" — it does, explicitly, right here, rather than leaving it to a
#: hidden default three layers down).
CONFIG_DIR: Final = REPO_ROOT / "config"


# --------------------------------------------------------------------------- #
# 1. Deployment-location environment variables — pure, no I/O
# --------------------------------------------------------------------------- #

_PG_HOST_VAR: Final = "CBRAIN_PG_HOST"
_PG_PORT_VAR: Final = "CBRAIN_PG_PORT"
_PG_DATABASE_VAR: Final = "CBRAIN_PG_DATABASE"
_PG_USER_VAR: Final = "CBRAIN_PG_USER"
_PG_PASSWORD_VAR: Final = "CBRAIN_PG_PASSWORD"
_QDRANT_HOST_VAR: Final = "CBRAIN_QDRANT_HOST"
_QDRANT_HTTP_PORT_VAR: Final = "CBRAIN_QDRANT_HTTP_PORT"
_QDRANT_COLLECTION_VAR: Final = "CBRAIN_QDRANT_COLLECTION"
_STAGING_DIR_VAR: Final = "CBRAIN_STAGING_DIR"
_MODEL_HOME_VAR: Final = "CBRAIN_MODEL_HOME"


class DeploymentEnvNotConfigured(RuntimeError):
    """A deployment-location environment variable is absent, blank, or not the
    shape it must be (e.g. a port that is not a number).

    Same shape as `api.security.ServiceKeyNotConfigured` /
    `TenantIdNotConfigured` on purpose: name the variable, never the value,
    and raise while the process is being ASSEMBLED, not on the first request.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class DeploymentEnv:
    """Where the two physical stores live, and the two local directories this
    process needs — resolved once, at startup. `frozen=True` for the same
    reason `ContractConfig` is: read once, trusted for the life of the
    process.
    """

    pg_dsn: str
    qdrant_host: str
    qdrant_http_port: int
    qdrant_collection: str
    staging_dir: Path
    model_home: Path


def _require_env(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name)
    if value is None or not value.strip():
        raise DeploymentEnvNotConfigured(
            f"Environment variable {name!r} is missing or blank. AI Services "
            f"REFUSES TO START rather than guess a store address or a local "
            f"path (CLAUDE.md Mục 4 quy tắc 2, applied to deployment "
            f"parameters). Set it — see .env.example."
        )
    return value


def resolve_deployment_env(environ: Mapping[str, str]) -> DeploymentEnv:
    """Read every deployment-location variable, or refuse — before anything
    is connected.

    `CBRAIN_PG_PASSWORD` is the one variable here allowed to be absent or
    blank: a local dev PostgreSQL commonly has no password at all, and
    `tests/t0_1_stores/conftest.py`'s `pg_dsn` fixture already treats it the
    same way.

    Raises:
        DeploymentEnvNotConfigured: any other variable is missing or blank,
            or a port is present but not an integer.
    """
    pg_host = _require_env(environ, _PG_HOST_VAR)
    pg_port = _require_env(environ, _PG_PORT_VAR)
    pg_database = _require_env(environ, _PG_DATABASE_VAR)
    pg_user = _require_env(environ, _PG_USER_VAR)
    pg_password = environ.get(_PG_PASSWORD_VAR) or ""
    auth = f"{pg_user}:{pg_password}" if pg_password else pg_user
    pg_dsn = f"postgresql://{auth}@{pg_host}:{pg_port}/{pg_database}"

    qdrant_host = _require_env(environ, _QDRANT_HOST_VAR)
    qdrant_http_port_raw = _require_env(environ, _QDRANT_HTTP_PORT_VAR)
    try:
        qdrant_http_port = int(qdrant_http_port_raw)
    except ValueError as exc:
        raise DeploymentEnvNotConfigured(
            f"{_QDRANT_HTTP_PORT_VAR!r} = {qdrant_http_port_raw!r} is not an "
            f"integer port number."
        ) from exc

    qdrant_collection = _require_env(environ, _QDRANT_COLLECTION_VAR)
    staging_dir = Path(_require_env(environ, _STAGING_DIR_VAR))
    model_home = Path(_require_env(environ, _MODEL_HOME_VAR))

    return DeploymentEnv(
        pg_dsn=pg_dsn,
        qdrant_host=qdrant_host,
        qdrant_http_port=qdrant_http_port,
        qdrant_collection=qdrant_collection,
        staging_dir=staging_dir,
        model_home=model_home,
    )


# --------------------------------------------------------------------------- #
# 2. Real connections and the real model — the only I/O in this module
# --------------------------------------------------------------------------- #


def connect_postgres(deployment: DeploymentEnv) -> psycopg.Connection:
    """One autocommit connection, held for the life of the process.

    Autocommit, not a pool: v1 runs exactly ONE worker thread
    (`api.background.BackgroundWorker`) plus the request-handling coroutines,
    and every `Pg*` store adapter already wraps its own multi-statement work
    in `with connection.transaction()` (see `ingestion/pg_document_stores.py`
    and `ingestion/pg_queue_stores.py`'s module docstrings) — those open a
    real `BEGIN…COMMIT` even under autocommit. A pool is the natural next
    step once this runs more than one process (07 Mục 3.1's own escape hatch
    for a future non-disruptive model swap), not before.
    """
    return psycopg.connect(deployment.pg_dsn, autocommit=True)


def connect_qdrant(deployment: DeploymentEnv) -> QdrantClient:
    client = QdrantClient(host=deployment.qdrant_host, port=deployment.qdrant_http_port)
    client.get_collections()  # fail fast if Qdrant is not reachable at all
    return client


def _default_sentence_transformer_loader(model_name: str) -> BgeM3Like:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class ModelHomeNotFound(RuntimeError):
    """`CBRAIN_MODEL_HOME` does not exist — the offline Hugging Face cache
    holding BGE-M3 was never populated on this machine. Mirrors
    `tests/t0_2_embedding/conftest.py`'s own refusal for the same reason."""


def load_embedding_model(
    deployment: DeploymentEnv,
    contract_config: ContractConfig,
    *,
    loader: Callable[[str], BgeM3Like] = _default_sentence_transformer_loader,
) -> BgeM3Like:
    """Load the model named by `config/contract.yaml`, offline (R2: no
    outbound call at runtime).

    `loader` is injected so a test can hand back a `FakeBgeM3` (the same
    shape `tests/api/conftest.py` already uses) instead of loading ~2.5GB —
    see this module's own docstring, layering section 2.

    Raises:
        ModelHomeNotFound: `deployment.model_home` does not exist.
    """
    if not deployment.model_home.is_dir():
        raise ModelHomeNotFound(
            f"{deployment.model_home} does not exist. Download BGE-M3 there "
            f"first — see tests/t0_2_embedding/README.md — before starting "
            f"AI Services ({_MODEL_HOME_VAR})."
        )
    # R2 — "mặc định chạy nội bộ": no call leaves this machine to resolve the
    # model. `HF_HUB_OFFLINE=1` makes a network attempt raise instead of
    # silently succeeding the one time it is reachable.
    os.environ["HF_HOME"] = str(deployment.model_home)
    os.environ["HF_HUB_OFFLINE"] = "1"
    return loader(contract_config.embedding_model)


# --------------------------------------------------------------------------- #
# 3. Table-existence check — CHECKS only, never creates
# --------------------------------------------------------------------------- #

#: Every table this deployment reads or writes, across the three logical
#: stores that live in PostgreSQL (07 Mục 2, docs/10 §2, §4.0/§4.1, T1.3).
#: Read off `schema.store_schema` / `ingestion.pre_approval_buffer` /
#: `schema.embedding_registry` rather than typed a second time — CLAUDE.md
#: Mục 6.
_REQUIRED_TABLES: Final[tuple[str, ...]] = (
    DOCUMENT_TABLE,
    RELATION_TABLE,
    DELETION_LOG_TABLE,
    SPACE_REGISTRY_TABLE,
    INGESTION_RECORD_TABLE,
    PRE_APPROVAL_DOCUMENT_TABLE,
    PRE_APPROVAL_CHUNK_TABLE,
    EMBEDDING_MODELS_TABLE,
    EMBEDDING_MODEL_COLLECTIONS_TABLE,
)


class MissingTablesError(RuntimeError):
    """One or more required PostgreSQL tables are absent.

    Raised at startup, before the app is handed to `uvicorn` — item 3 of the
    work order: *"Lúc khởi động dịch vụ CHỈ KIỂM bảng đã có; thiếu → từ chối
    khởi động, không tự tạo ngầm."* Run
    `tools/provision/provision_stores.py` once, by hand, first.
    """


def _assert_tables_exist(connection: psycopg.Connection) -> None:
    rows = connection.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = ANY(%s)",
        (list(_REQUIRED_TABLES),),
    ).fetchall()
    found = {row[0] for row in rows}
    missing = [name for name in _REQUIRED_TABLES if name not in found]
    if missing:
        raise MissingTablesError(
            f"Missing PostgreSQL table(s): {', '.join(missing)}. AI Services "
            f"refuses to start rather than create them implicitly (CLAUDE.md "
            f"Mục 4). Run `.venv/bin/python tools/provision/provision_stores.py` "
            f"first."
        )


# --------------------------------------------------------------------------- #
# Readiness — the SAME stamp check, called again on every /v1/meta request
# --------------------------------------------------------------------------- #


def _build_readiness(
    *,
    pg_connection: psycopg.Connection,
    qdrant_client: QdrantClient,
    contract_config: ContractConfig,
    collection_name: str,
) -> Callable[[], ReadinessReport]:
    """docs/10 §3.6 — checked again on EVERY call, not cached from startup.

    `meta.create_meta_router`'s own docstring: *"a store that drifts out from
    under a running service is precisely the case 07 Mục 3.1 is about."* The
    check is the real one, `assert_collection_ready_for_contract` — no
    second, cheaper implementation that could disagree with the one that
    refused to start.
    """

    def probe() -> ReadinessReport:
        try:
            pg_connection.execute("SELECT 1").fetchone()
            assert_collection_ready_for_contract(
                config=contract_config,
                qdrant_client=qdrant_client,
                pg_connection=pg_connection,
                collection_name=collection_name,
            )
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
            return ReadinessReport(ready=False, not_ready_reason=str(exc))
        return ReadinessReport(ready=True, not_ready_reason=None)

    return probe


# --------------------------------------------------------------------------- #
# Lifespan — recover() then worker.start(); worker.stop() on shutdown
# --------------------------------------------------------------------------- #


def _build_lifespan(
    *, pipeline: IngestionPipeline, worker: BackgroundWorker
) -> Callable[[FastAPI], object]:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        recovered = pipeline.recover()
        if recovered:
            logger.warning(
                "Startup recovery requeued %d ingestion job(s).", len(recovered)
            )
        worker.start()
        try:
            yield
        finally:
            worker.stop()

    return lifespan


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# The wiring — already-connected clients + an already-loaded model in,
# a runnable FastAPI app out
# --------------------------------------------------------------------------- #


def build_deployment_app(
    *,
    config_dir: Path,
    environ: Mapping[str, str],
    deployment: DeploymentEnv,
    pg_connection: psycopg.Connection,
    qdrant_client: QdrantClient,
    embedding_model: BgeM3Like,
) -> FastAPI:
    """Wire the live stores into `IngestionPipeline` + `IngestionServices`,
    check what must be checked, and hand the result to `api.app.build_app`.

    Split from `create_app_from_env` so a test can call this directly with a
    disposable (but real) PostgreSQL + Qdrant and a fake model — never with
    any store this function constructs itself.

    Raises:
        MissingTablesError: a required table is absent.
        schema.embedding_registry.EmbeddingRegistryError (and subclasses):
            the Qdrant collection is missing, unstamped, or its stamp
            mismatches `config/contract.yaml`.
        schema.config.ConfigError: any of the three config files is missing
            or malformed (raised again inside `api.app.build_app`).
        api.security.ServiceKeyNotConfigured, TenantIdNotConfigured: the
            matching environment variable is missing or blank.
    """
    contract_config = load_contract_config(config_dir / "contract.yaml")
    ingestion_config = load_ingestion_config(config_dir / "ingestion.yaml")

    _assert_tables_exist(pg_connection)
    assert_collection_ready_for_contract(
        config=contract_config,
        qdrant_client=qdrant_client,
        pg_connection=pg_connection,
        collection_name=deployment.qdrant_collection,
    )

    tenant_id = resolve_tenant_id(env_var=TENANT_ID_ENV_VAR, environ=environ)

    document_store = PgDocumentStore(connection=pg_connection)
    deletion_log = PgDeletionLog(connection=pg_connection)
    space_registry = PgSpaceRegistry(pg_connection)
    ingestion_records = PgIngestionRecordStore(pg_connection)
    pre_approval_buffer = PgPreApprovalBuffer(pg_connection)
    vector_deleter = QdrantVectorStoreDeleter(
        qdrant_client=qdrant_client, collection_name=deployment.qdrant_collection
    )
    vector_writer = QdrantVectorStoreWriter(
        qdrant_client=qdrant_client,
        collection_name=deployment.qdrant_collection,
        contract_config=contract_config,
        pg_connection=pg_connection,
    )
    background_cleanup = PgBackgroundCleanup()
    staging = StagingArea(deployment.staging_dir)
    worker = BackgroundWorker()

    pipeline = IngestionPipeline(
        records=ingestion_records,
        staging=staging,
        space_registry=space_registry,
        profile_store=document_store,
        fingerprint_index=document_store,
        buffer=pre_approval_buffer,
        vector_writer=vector_writer,
        embedding_model=embedding_model,
        # T2.6b (the real Backend space-topology client) is explicitly out of
        # scope for this task — see the module docstring's "What is
        # explicitly NOT here".
        relation_scope=UnavailableSpaceScanScope(
            reason="the Backend space-topology client (docs/10 §7.1) is not built"
        ),
        relation_document_source=document_store,
        chunk_length_cap=ingestion_config.chunk_length_cap,
        saturation_epsilon=ingestion_config.saturation_epsilon,
        saturation_rounds=ingestion_config.saturation_rounds,
        scan_pair_budget=ingestion_config.scan_pair_budget,
        scan_time_budget=ingestion_config.scan_time_budget,
        clock=_utc_now,
    )

    services = IngestionServices(
        space_registry=space_registry,
        document_source=document_store,
        profile_store=document_store,
        vector_store=vector_deleter,
        background_cleanup=background_cleanup,
        deletion_log=deletion_log,
        pre_approval_buffer=pre_approval_buffer,
        pipeline=pipeline,
        worker=worker,
        tenant_id=tenant_id,
        max_upload_bytes=ingestion_config.max_upload_bytes,
        source_download_timeout_seconds=ingestion_config.source_download_timeout_seconds,
        clock=_utc_now,
    )

    readiness = _build_readiness(
        pg_connection=pg_connection,
        qdrant_client=qdrant_client,
        contract_config=contract_config,
        collection_name=deployment.qdrant_collection,
    )
    lifespan = _build_lifespan(pipeline=pipeline, worker=worker)

    return build_app(
        config_dir=config_dir,
        environ=environ,
        service_key_env_var=SERVICE_KEY_ENV_VAR,
        routers=[create_ingestion_router(services=services)],
        exception_handlers=INGESTION_EXCEPTION_HANDLERS,
        readiness=readiness,
        # ⛔ In-memory, by instruction — see the module docstring's "What is
        # explicitly NOT here". A restart forgets in-flight replay keys; every
        # business function behind a write endpoint is independently
        # re-runnable regardless (api.idempotency's own docstring).
        idempotency_store=InMemoryIdempotencyStore(),
        lifespan=lifespan,
    )


def create_app_from_env(environ: Mapping[str, str] | None = None) -> FastAPI:
    """The real thing: read `os.environ`, connect for real, load the real
    model, build the app. This is what `app_factory` calls.

    `environ` is accepted (defaulting to `os.environ`) rather than read
    unconditionally, so nothing here has two ways of reading the same
    variable — the same reasoning `api.app.build_app` gives for taking
    `environ` as a parameter.
    """
    resolved_environ = dict(os.environ if environ is None else environ)
    deployment = resolve_deployment_env(resolved_environ)
    pg_connection = connect_postgres(deployment)
    qdrant_client = connect_qdrant(deployment)
    contract_config = load_contract_config(CONFIG_DIR / "contract.yaml")
    embedding_model = load_embedding_model(deployment, contract_config)

    return build_deployment_app(
        config_dir=CONFIG_DIR,
        environ=resolved_environ,
        deployment=deployment,
        pg_connection=pg_connection,
        qdrant_client=qdrant_client,
        embedding_model=embedding_model,
    )


def app_factory() -> FastAPI:
    """The uvicorn entry point: `uvicorn api.main:app_factory --factory`.

    A factory rather than a module-level `app = create_app_from_env()`
    object, deliberately: a module-level object would connect to PostgreSQL
    and load BGE-M3 the moment anything imports `api.main` — including a
    test that only wants `resolve_deployment_env`. `--factory` defers all of
    that to the moment `uvicorn` actually asks for the app.

    Loads `REPO_ROOT/.env` into the process environment first, if present —
    the same convenience `tests/t0_1_stores/conftest.py`'s `_env` fixture
    already gives test runs. `create_app_from_env` itself stays free of this:
    it reads whatever `environ` it is given (defaulting to `os.environ`),
    with no file I/O of its own, so it stays callable with a hand-built
    mapping in a test.
    """
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        from dotenv import load_dotenv

        load_dotenv(env_file)
    return create_app_from_env()
