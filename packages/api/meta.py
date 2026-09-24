"""`GET /v1/meta` — docs/10 §3.6.

*"BE gọi lúc khởi động và định kỳ, để **không phải đoán K** và biết AI đang từ
chối phục vụ trước khi người dùng gặp lỗi `503`."*

Imports `schema.*` only. Neither service's code is reachable from here, which
is what lets a deployment that runs one of them still answer this endpoint
(see the package docstring).
"""

from __future__ import annotations

from fastapi import APIRouter

from api.models import MetaResponse
from api.settings import ApiLimits, ReadinessCheck
from schema.version import LOCAL_SCHEMA_VERSION

__all__ = ["CONTRACT_VERSION", "create_meta_router"]


#: docs/10 §3.6 `contract_version`.
#:
#: This is the version of the SHARED DATA CONTRACT — the two numbers
#: `packages/schema/version.py` carries (07 Mục 3.1, DX3) — rendered as
#: `"<breaking>.<additive>"`. It is the only version number in this repo that
#: describes a deployed artifact: docs/10's own "v0.4" is the version of a
#: draft DOCUMENT, and `/v1` in the path is the API's major version, which by
#: construction never changes within this contract.
#:
#: What Backend can rely on, and it is exactly what DX3 already promises: the
#: first number changing means a field was renamed, removed or redefined and
#: both sides must be brought up together; the second changing means fields
#: were added that an older reader may ignore.
#:
#: ⚠️ Reported to PO as a decision to confirm: if docs/10 ever gets a version
#: number of its own once it leaves draft, it needs its own home — reusing
#: this one for two different contracts would be one field with two meanings.
CONTRACT_VERSION = str(LOCAL_SCHEMA_VERSION)


def create_meta_router(*, limits: ApiLimits, readiness: ReadinessCheck) -> APIRouter:
    """The meta endpoint, closed over the values it may publish.

    `readiness` is called PER REQUEST, not once at build time: *"biết AI đang
    từ chối phục vụ"* is only useful if it can change after startup — a store
    that drifts out from under a running service is precisely the case 07 Mục
    3.1 is about.
    """
    router = APIRouter()

    @router.get("/v1/meta", response_model=MetaResponse)
    def read_meta() -> MetaResponse:
        report = readiness()
        return MetaResponse(
            ready=report.ready,
            not_ready_reason=report.not_ready_reason,
            contract_version=CONTRACT_VERSION,
            limits=limits.as_payload(),
        )

    return router
