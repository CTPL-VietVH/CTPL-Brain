"""The Ingestion-side endpoints of docs/10: Space register, Space deletion,
permanent document deletion.

⛔ This is the ONLY module in `packages/api/` that imports `ingestion.*`. See
the package docstring: an API package that pulled both services into one file
would become the third meeting point CLAUDE.md Mục 6 does not allow.

Every route below is a translation, never a decision:

    HTTP                          →  business function that already exists
    ─────────────────────────────────────────────────────────────────────
    POST   /v1/spaces             →  space_registry.register
    DELETE /v1/spaces/{id}        →  space_deletion.delete_space
    GET    /v1/spaces/{id}        →  two reads, NO write
    DELETE /v1/documents/{id}     →  deletion.purge_document_permanently

The refusals those functions raise are mapped to the codes of docs/10 §3.5 in
`INGESTION_EXCEPTION_HANDLERS` at the bottom of the file, in one table, so the
mapping can be read in one place instead of being spread across four routes.

──────────────────────────────────────────────────────────────────────────
What these routes do NOT do
──────────────────────────────────────────────────────────────────────────

**No permission check.** docs/10 §1 T2: *"BE quyết quyền, AI thực thi quyền"*.
`actor.acting_as` is recorded, never compared against the operation. §4.0 says
registering and deleting a Space need `acting_as ∈ {manager, admin}` — that
sentence is Backend's obligation, and re-checking it here would be AI
re-deciding Backend's job with none of Backend's data (it knows neither the
person nor the Space tree).

**The one thing AI does check for itself is WHERE** — T4. It is not checked in
this file either: `purge_document_permanently` does it, against the document's
own profile, and raises `ObjectNotInSpace`. A copy of that check here would be
a second implementation of the same rule, free to drift from the audited one.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from fastapi import APIRouter, Request, Response

from api.errors import (
    MESSAGE_INVALID_REQUEST,
    MESSAGE_INVALID_STATE,
    MESSAGE_OBJECT_NOT_IN_SPACE,
    MESSAGE_SPACE_BEING_DELETED,
    MESSAGE_SPACE_NOT_REGISTERED,
    ErrorCode,
    error_response,
)
from api.models import (
    DocumentDeletionOutcome,
    DocumentDeletionRequest,
    DocumentDeletionResponse,
    SpaceDeletionRequest,
    SpaceDeletionResponse,
    SpaceRegistrationRequest,
    SpaceRegistrationResponse,
    SpaceStatusResponse,
)
from ingestion.deletion import (
    BackgroundCleanup,
    DeletableProfileStore,
    DeletionLog,
    DeletionRequestIncomplete,
    ObjectNotInSpace,
    VectorStoreDeleter,
    purge_document_permanently,
)
from ingestion.pre_approval_buffer import PreApprovalBuffer
from ingestion.relations_scan import SpaceDocumentSource
from ingestion.space_deletion import delete_space
from ingestion.space_registry import (
    IllegalSpaceStateTransition,
    SpaceCannotBeRegisteredAgain,
    SpaceNotAcceptingDocuments,
    SpaceNotRegistered,
    SpaceRegistry,
)

__all__ = [
    "INGESTION_EXCEPTION_HANDLERS",
    "IngestionServices",
    "create_ingestion_router",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class IngestionServices:
    """The store-backed ports the Ingestion endpoints need, injected.

    Every one of them is a Protocol from `packages/ingestion/`, so this layer
    is identical whether the implementation behind it is the in-memory pair
    used by the contract tests or a live PostgreSQL + Qdrant. Nothing in
    `packages/api/` constructs any of them — a factory that quietly built an
    in-memory store would produce a deployment that forgets every document on
    restart and reports success while doing it.

    `document_source` and `profile_store` are usually ONE object: in a real
    deployment both are the `document` table. They are two fields because the
    two Protocols are two different sets of promises, and `delete_space`
    already takes them separately for the same reason.
    """

    space_registry: SpaceRegistry
    document_source: SpaceDocumentSource
    profile_store: DeletableProfileStore
    vector_store: VectorStoreDeleter
    background_cleanup: BackgroundCleanup
    deletion_log: DeletionLog
    pre_approval_buffer: PreApprovalBuffer


def create_ingestion_router(*, services: IngestionServices) -> APIRouter:
    """Build the router, closed over the services it calls."""
    router = APIRouter()

    @router.post(
        "/v1/spaces",
        response_model=SpaceRegistrationResponse,
        status_code=200,
    )
    def register_space(body: SpaceRegistrationRequest) -> SpaceRegistrationResponse:
        """docs/10 §4.0 — *"Đăng ký `space_id` ở trạng thái đang dùng"*.

        `200`, not `201`, and the same body every time: §4.0 requires a repeat
        to return *"kết quả như lần đầu"*, and a status code that differs
        between the first call and the second is exactly the difference the
        word idempotent denies. `register` itself is already idempotent
        (T2.11), so this route has no repeat-handling of its own.
        """
        registration = services.space_registry.register(body.space_id)
        return SpaceRegistrationResponse(
            space_id=registration.space_id, state=registration.state.value
        )

    @router.delete(
        "/v1/spaces/{space_id}",
        response_model=SpaceDeletionResponse,
        status_code=202,  # docs/10 §4.0
    )
    def delete_space_endpoint(
        space_id: str, body: SpaceDeletionRequest
    ) -> SpaceDeletionResponse:
        """docs/10 §4.0 — close the Space, purge its documents, then mark it gone.

        ⚠️ **Runs synchronously inside this request**, while §4.0 specifies
        `202` *"và chạy nền"*. There is no task runner in this repo yet, and
        inventing one here would choose an execution model the plan has not
        chosen (`space_deletion.py` says the same about itself). The status
        code stays `202` because the CONTRACT is unchanged from Backend's
        side: the answer may report work still outstanding
        (`completed=false`), and Backend's own procedure — *"gọi AI → đợi AI
        báo đã xoá"* — is to keep asking until it is done.

        What makes that safe to put behind a runner later without touching
        this route: `delete_space` re-derives its worklist from the stores on
        every call, so calling it once per request, or a hundred times from a
        queue, converges to the same end state.

        The response is built from the progress dataclass FIELD BY FIELD via
        `dataclasses.asdict`, and the response model forbids unknown fields.
        So a new field added to `SpaceDeletionProgress` makes this route fail
        loudly instead of silently dropping the one number a future case
        needs — the deliberate opposite of a `**kwargs` that swallows it.
        """
        progress = delete_space(
            space_id,
            reason=body.reason,
            deleted_by=body.actor.user_id,
            space_registry=services.space_registry,
            document_source=services.document_source,
            profile_store=services.profile_store,
            vector_store=services.vector_store,
            background_cleanup=services.background_cleanup,
            deletion_log=services.deletion_log,
            pre_approval_buffer=services.pre_approval_buffer,
        )
        payload = dataclasses.asdict(progress)
        payload["state"] = progress.state.value
        return SpaceDeletionResponse(**payload)

    @router.get("/v1/spaces/{space_id}", response_model=SpaceStatusResponse)
    def read_space(space_id: str) -> SpaceStatusResponse:
        """docs/10 §4.0 — *"trạng thái và tiến độ"*. READ ONLY.

        ⛔ This route must never call `delete_space`, however convenient its
        progress object is: that function advances the Space's state, purges
        documents and writes log lines. A `GET` that deletes is the kind of
        thing a crawler, a health check or a retried request triggers by
        accident, and nothing would ever say it happened.

        So the two numbers are read directly, from the same two sources
        `delete_space` treats as its worklist (see that module: profiles still
        carrying the `space_id`, and deletion-log lines still open).
        """
        registration = services.space_registry.get(space_id)
        if registration is None:
            # Not an exception from the registry: `get` returns None by
            # design, and this route is the place that knows a missing row is
            # a 404 rather than an empty answer.
            raise SpaceNotRegistered(
                f"space_id={space_id!r} is not in the Space register (docs/10 §4.0)."
            )

        remaining = [
            document
            for document in services.document_source.documents_in(frozenset({space_id}))
            # The `space_id` re-test mirrors `space_deletion._profiles_in`:
            # `documents_in` takes a SET, and a store that over-returned would
            # otherwise report another Space's documents as this one's.
            if document.space_id == space_id
        ]
        unfinished = services.deletion_log.open_entries_for_space(space_id)

        return SpaceStatusResponse(
            space_id=registration.space_id,
            state=registration.state.value,
            documents_remaining=len(remaining),
            unfinished_purges_remaining=len(unfinished),
        )

    @router.delete(
        "/v1/documents/{document_id}", response_model=DocumentDeletionResponse
    )
    def delete_document(
        document_id: str, body: DocumentDeletionRequest
    ) -> DocumentDeletionResponse:
        """docs/10 §5.6 — permanent deletion of one document.

        *"Chốt 23/9: chỉ xoá theo `document_id`, và `document_id` phải nằm ở
        đúng `space_id` được nêu"* — the second half is T4, checked inside
        `purge_document_permanently` against the document's own profile (or,
        for a resumed purge, against its open log line).

        `outcome` reports what the log already knew on entry, not what this
        call managed to do: `already_completed` means a finished deletion was
        found, and the steps ran again anyway because each is a no-op when its
        work is done. That is why a second call answers `already_deleted`
        without an error (docs/10 §10: *"Lần hai trả `already_deleted`, không
        lỗi"*).
        """
        outcome = purge_document_permanently(
            document_id,
            space_id=body.space_id,
            deleted_by=body.actor.user_id,
            reason=body.reason,
            profile_store=services.profile_store,
            vector_store=services.vector_store,
            background_cleanup=services.background_cleanup,
            deletion_log=services.deletion_log,
        )
        return DocumentDeletionResponse(
            outcome=(
                DocumentDeletionOutcome.ALREADY_DELETED
                if outcome.already_completed
                else DocumentDeletionOutcome.DELETED
            ),
            background_cleanup_complete=outcome.purge_settled,
        )

    return router


# --------------------------------------------------------------------------- #
# Refusal → HTTP, in one table (docs/10 §3.5)
# --------------------------------------------------------------------------- #


def _space_not_registered(request: Request, exc: Exception) -> Response:
    return error_response(
        status_code=404,
        code=ErrorCode.SPACE_NOT_REGISTERED,
        message=MESSAGE_SPACE_NOT_REGISTERED,
    )


def _space_being_deleted(request: Request, exc: Exception) -> Response:
    """Both `SpaceNotAcceptingDocuments` and `SpaceCannotBeRegisteredAgain`
    land here, and docs/10 §4.0 is why they share one code.

    *"`space_id` đã xoá thì **không được đăng ký lại** (`409
    SPACE_BEING_DELETED`)"* — the spec itself puts "still being emptied" and
    "already gone, never reusable" behind the same answer, because from
    Backend's side both mean the same thing: this code is finished, issue a
    new one. `space_registry.py` refuses `BEING_DELETED` on the same grounds
    plus one more (re-registering mid-deletion races the loop that is still
    emptying the Space).
    """
    return error_response(
        status_code=409,
        code=ErrorCode.SPACE_BEING_DELETED,
        message=MESSAGE_SPACE_BEING_DELETED,
    )


def _object_not_in_space(request: Request, exc: Exception) -> Response:
    """docs/10 §3.5 — 404, *"chứ không trả 403, để không tiết lộ đối tượng tồn
    tại"*. The message says the same thing whether the document is in another
    Space or does not exist at all."""
    return error_response(
        status_code=404,
        code=ErrorCode.OBJECT_NOT_IN_SPACE,
        message=MESSAGE_OBJECT_NOT_IN_SPACE,
    )


def _illegal_state_transition(request: Request, exc: Exception) -> Response:
    return error_response(
        status_code=409,
        code=ErrorCode.INVALID_STATE,
        message=MESSAGE_INVALID_STATE,
    )


def _deletion_request_incomplete(request: Request, exc: Exception) -> Response:
    """A field 06 Mục 5.6 requires the deletion log to carry is blank.

    Reaches this handler only if something got past the request models, which
    already refuse blank `space_id`, `reason` and `actor.user_id`. Kept anyway:
    the business function is the authority on what a loggable deletion needs,
    and if it ever requires one more field, the answer should be a `422` that
    names the contract rather than a `500`.
    """
    return error_response(
        status_code=422,
        code=ErrorCode.INVALID_REQUEST,
        message=MESSAGE_INVALID_REQUEST,
    )


#: Passed to `app.create_app` by the composition root. A mapping rather than a
#: list of decorators so that the whole refusal surface of this module is one
#: readable table — and so `app.py` never imports an Ingestion exception.
INGESTION_EXCEPTION_HANDLERS: Mapping[
    type[Exception], Callable[[Request, Exception], Response]
] = {
    SpaceNotRegistered: _space_not_registered,
    SpaceNotAcceptingDocuments: _space_being_deleted,
    SpaceCannotBeRegisteredAgain: _space_being_deleted,
    IllegalSpaceStateTransition: _illegal_state_transition,
    ObjectNotInSpace: _object_not_in_space,
    DeletionRequestIncomplete: _deletion_request_incomplete,
}
