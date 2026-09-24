"""The application factory — assembles the surface, refuses to start when it
cannot be assembled honestly.

Two entry points, and the split matters:

* `build_app` is the one a deployment calls. It READS: the three config files
  (CLAUDE.md Mục 4) and the environment variable holding the service key. Any
  of them missing is a refusal to start, naming what is missing.
* `create_app` takes everything already resolved. It is what makes the
  refusals above testable one at a time, and what lets a future composition
  root get its values from somewhere else entirely without this module
  growing a second reader.

⛔ Neither of them constructs a store, a clock, or an idempotency store. Those
arrive from the caller (`routers`, `exception_handlers`, `idempotency_store`,
`readiness`). The rule is CLAUDE.md Mục 4 quy tắc 2 applied to objects rather
than numbers: a stand-in created inside the factory is a second home for a
decision the deployment is supposed to make, and this particular second home
would be a process that quietly serves traffic out of a dict.

⛔ This module imports `schema.*` only. The service-specific routers are
passed in — see the package docstring for why an API package that imported
both services at once would undo CLAUDE.md Mục 6.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError

from api.errors import (
    MESSAGE_INVALID_REQUEST,
    MESSAGE_SCOPE_MISSING,
    SCOPE_FIELD_NAMES,
    ErrorCode,
    error_response,
)
from api.idempotency import IdempotencyStore
from api.meta import create_meta_router
from api.middleware import (
    IdempotencyMiddleware,
    RequestIdMiddleware,
    ServiceAuthMiddleware,
    UnhandledErrorMiddleware,
    new_request_id,
)
from api.security import resolve_service_key
from api.settings import (
    CONTRACT_CONFIG_FILENAME,
    INGESTION_CONFIG_FILENAME,
    RETRIEVAL_CONFIG_FILENAME,
    ApiLimits,
    ReadinessCheck,
    api_limits_from_ingestion_config,
)
from schema.config import (
    load_contract_config,
    load_ingestion_config,
    load_retrieval_config,
)

__all__ = ["build_app", "create_app"]

ExceptionHandler = Callable[[Request, Exception], Response]


# --------------------------------------------------------------------------- #
# Validation → the codes of docs/10 §3.5
# --------------------------------------------------------------------------- #


def _validation_error_handler(request: Request, exc: Exception) -> Response:
    """Turn FastAPI's validation report into `{code, message}`.

    ⛔ FastAPI's own `{"detail": [...]}` must never reach Backend: docs/10 §3.5
    says *"Mọi lỗi có mã máy đọc được"*, and a body with no `code` is one
    Backend cannot branch on — it would end up matching on English prose.

    **Which code.** A scope field that is ABSENT — in any of the three ways a
    field can be absent — is `400 SCOPE_MISSING` (§3.3). Everything else,
    including a scope field that is present but malformed, is `422
    INVALID_REQUEST`. Two reasons the line is drawn exactly there:

    * §3.3 carries an explicit ⚠️ about the old system reading `workspace=""`
      as "no filter". An absent field, a `null` and an empty string are the
      same mistake wearing three hats, and all three must produce the answer
      that names scope.
    * `SCOPE_MISSING` is the only code whose meaning Backend acts on
      automatically (send the scope). An `acting_as` spelled `"owner"` is not
      a missing scope — it is a vocabulary disagreement — and answering
      "send me the scope" would send Backend looking in the wrong place.
    """
    errors = exc.errors() if isinstance(exc, RequestValidationError) else []
    if any(_is_absent_scope(error) for error in errors):
        # 400 — docs/10 §3.5, the `SCOPE_MISSING` row.
        return error_response(
            status_code=400,
            code=ErrorCode.SCOPE_MISSING,
            message=MESSAGE_SCOPE_MISSING,
        )
    return error_response(
        status_code=422,
        code=ErrorCode.INVALID_REQUEST,
        message=MESSAGE_INVALID_REQUEST,
    )


def _is_absent_scope(error: Mapping[str, object]) -> bool:
    """Is this validation error a scope field that is not really there?

    The location is matched anywhere along the path, so `("body", "actor",
    "user_id")` counts: an `actor` whose `user_id` is blank is an actor
    Backend did not really send.
    """
    if not _touches_scope(error.get("loc", ())):  # type: ignore[arg-type]
        return False
    if error.get("type") == "missing":
        return True
    value = error.get("input")
    if value is None:  # `"space_id": null`, `"actor": null`
        return True
    return isinstance(value, str) and not value.strip()


def _touches_scope(location: Sequence[object]) -> bool:
    return any(part in SCOPE_FIELD_NAMES for part in location if isinstance(part, str))


# --------------------------------------------------------------------------- #
# The factory
# --------------------------------------------------------------------------- #


def create_app(
    *,
    routers: Sequence[APIRouter],
    exception_handlers: Mapping[type[Exception], ExceptionHandler],
    limits: ApiLimits,
    readiness: ReadinessCheck,
    service_key: str,
    idempotency_store: IdempotencyStore,
    generate_request_id: Callable[[], str] = new_request_id,
    lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]] | None = None,
) -> FastAPI:
    """Assemble the FastAPI application from already-resolved parts.

    `service_key` is the resolved SECRET, not a variable name: reading the
    environment is `build_app`'s job, and doing it in two places would be two
    chances to disagree about which variable holds it.

    Middleware order is decided in `middleware.py`; the calls below add them
    inner-to-outer because `add_middleware` puts the most recently added one
    outermost. Changing this order changes behaviour — read that module's
    diagram before touching it.

    `lifespan` is passed straight through to `FastAPI(...)` and defaults to
    `None` (FastAPI's own no-op). This factory still constructs no store and
    no worker — the composition root (`packages/api/main.py`) builds
    `recover()` + `worker.start()`/`stop()` into an async context manager and
    hands it in here, so THIS module still never touches a live store.
    """
    app = FastAPI(
        title="C.Brain AI Services",
        # docs/10 §3.1: *"tiền tố phiên bản `/v1`"*. The prefix is part of each
        # route's path rather than a mount point, so the paths in this repo read
        # exactly like the paths in docs/10.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    for router in routers:
        app.include_router(router)
    app.include_router(create_meta_router(limits=limits, readiness=readiness))

    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    for exception_type, handler in exception_handlers.items():
        app.add_exception_handler(exception_type, handler)

    app.add_middleware(IdempotencyMiddleware, store=idempotency_store)
    app.add_middleware(ServiceAuthMiddleware, service_key=service_key)
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(RequestIdMiddleware, generate=generate_request_id)

    return app


def build_app(
    *,
    config_dir: Path,
    environ: Mapping[str, str],
    service_key_env_var: str,
    routers: Sequence[APIRouter],
    exception_handlers: Mapping[type[Exception], ExceptionHandler],
    readiness: ReadinessCheck,
    idempotency_store: IdempotencyStore,
    generate_request_id: Callable[[], str] = new_request_id,
    lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]] | None = None,
) -> FastAPI:
    """Read configuration and the service key, then build the app.

    **All three config groups are loaded, not just the ones today's endpoints
    read.** This process is the single door into AI Services (docs/10 §0), and
    docs/10 §3.5 puts *"thiếu khoá cấu hình"* behind `SERVICE_MISCONFIGURED`:
    a deployment missing `document_cap` must not come up serving Space
    deletions and then fail on the first question. Loading all three here is
    also what makes 08 T1.2's acceptance test true of the API layer — remove
    any one key from any one file and the service does not start.

    `config_dir` has no default for the reason `schema.config`'s loaders have
    none: where `config/` lives is a per-install deployment fact (R6).

    ⚠️ **`CBRAIN_TENANT_ID` is NOT read here**, and the asymmetry with the
    service key is deliberate. The service key is used by a middleware this
    factory installs, so this factory has to hold it. `tenant_id` is used by
    a ROUTER, and routers arrive already built — so reading it here would
    give the value two readers and two chances to disagree. The composition
    root resolves it with `api.security.resolve_tenant_id` (which refuses a
    missing or blank variable with the same force as the service key) and
    hands it to `IngestionServices`, which refuses a blank value in turn.

    Raises:
        schema.config.ConfigError: any of the three files is missing, empty,
            missing a key, carrying an unknown key, or carrying a value of the
            wrong type. The message names the file and the key.
        api.security.ServiceKeyNotConfigured: the environment variable holding
            the service key is absent or blank.
    """
    load_contract_config(config_dir / CONTRACT_CONFIG_FILENAME)
    ingestion_config = load_ingestion_config(config_dir / INGESTION_CONFIG_FILENAME)
    load_retrieval_config(config_dir / RETRIEVAL_CONFIG_FILENAME)

    service_key = resolve_service_key(env_var=service_key_env_var, environ=environ)

    return create_app(
        routers=routers,
        exception_handlers=exception_handlers,
        limits=api_limits_from_ingestion_config(ingestion_config),
        readiness=readiness,
        service_key=service_key,
        idempotency_store=idempotency_store,
        generate_request_id=generate_request_id,
        lifespan=lifespan,
    )
