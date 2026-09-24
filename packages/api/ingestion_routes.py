"""The Ingestion-side endpoints of docs/10: Space register, Space deletion,
permanent document deletion.

⛔ This is the ONLY module in `packages/api/` that imports `ingestion.*`. See
the package docstring: an API package that pulled both services into one file
would become the third meeting point CLAUDE.md Mục 6 does not allow.

Every route below is a translation, never a decision:

    HTTP                          →  business function that already exists
    ─────────────────────────────────────────────────────────────────────
    POST   /v1/spaces             →  space_registry.register
    DELETE /v1/spaces/{id}        →  space_deletion.begin_space_deletion,
                                     then delete_space in the background
    GET    /v1/spaces/{id}        →  two reads, NO write
    POST   /v1/ingestions         →  fetch the file, write a QUEUED row,
                                     wake the worker — the pipeline itself
                                     is ingestion_pipeline.IngestionPipeline
    GET    /v1/ingestions/{id}    →  one read, NO write
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

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request, Response

from api.background import BackgroundWorker
from api.errors import (
    MESSAGE_FILE_TOO_LARGE,
    MESSAGE_INVALID_REQUEST,
    MESSAGE_INVALID_STATE,
    MESSAGE_OBJECT_NOT_IN_SPACE,
    MESSAGE_SOURCE_INTEGRITY_MISMATCH,
    MESSAGE_SOURCE_UNREACHABLE,
    MESSAGE_SPACE_BEING_DELETED,
    MESSAGE_SPACE_NOT_REGISTERED,
    ErrorCode,
    error_response,
)
from api.models import (
    DocumentDeletionOutcome,
    DocumentDeletionRequest,
    DocumentDeletionResponse,
    IngestionStatusResponse,
    IngestionSubmissionRequest,
    IngestionSubmissionResponse,
    IngestionSuggestions,
    SpaceDeletionRequest,
    SpaceRegistrationRequest,
    SpaceRegistrationResponse,
    SpaceStatusResponse,
)
from api.source_fetch import (
    ClientFactory,
    FileTooLarge,
    SourceIntegrityMismatch,
    SourceUnreachable,
    default_http_client,
    fetch_source_to_staging,
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
from ingestion.ingestion_pipeline import IngestionPipeline
from ingestion.pre_approval_buffer import PreApprovalBuffer
from ingestion.relations_scan import SpaceDocumentSource
from ingestion.space_deletion import begin_space_deletion, delete_space
from api.security import TENANT_ID_ENV_VAR
from ingestion.space_registry import (
    IllegalSpaceStateTransition,
    SpaceCannotBeRegisteredAgain,
    SpaceNotAcceptingDocuments,
    SpaceNotRegistered,
    SpaceRegistry,
    assert_space_accepts_documents,
)
from schema.document import Document
from schema.ingestion_record import (
    IngestionRecord,
    IngestionStatus,
    wire_status,
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

    #: Everything `POST /v1/ingestions` hands off. The pipeline owns the
    #: record store, the staging area and the five config numbers — this
    #: layer never reads any of them twice.
    pipeline: IngestionPipeline

    #: ONE thread for the whole service (see `api.background`). Both `202`
    #: endpoints put their work on it, which is what keeps the single-worker
    #: invariant true across the two of them rather than per endpoint.
    worker: BackgroundWorker

    #: R6 — one install, one customer (docs/10 §2). Resolved from
    #: `CBRAIN_TENANT_ID` at startup; ⛔ never taken from a request, or one
    #: call could file a document under another customer's `tenant_id`.
    tenant_id: str

    #: The two ceilings of the fetch, from `config/ingestion.yaml` (07 Mục
    #: 3.2). Held here rather than inside `source_fetch` because that module
    #: must have no home for a number — CLAUDE.md Mục 4 quy tắc 2 — and held
    #: here rather than on the pipeline because the fetch happens in the
    #: REQUEST, not in the job (§4.1: the queue would outlive the link).
    max_upload_bytes: int
    source_download_timeout_seconds: float

    #: Injected so a test can serve the presigned URL from a local fixture
    #: without a socket, and so a deployment behind a proxy can supply its
    #: own client.
    http_client_factory: ClientFactory = default_http_client

    #: Injected for the same reason every other module in this repo injects
    #: one: a test must be able to know what `submitted_at` will be.
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

    #: `ingestion_id` generator. AI mints it — Backend has no say, because
    #: the id names AI's own row (docs/10 §4.1 returns it).
    new_ingestion_id: Callable[[], str] = lambda: uuid.uuid4().hex

    def __post_init__(self) -> None:
        """Refuse a blank `tenant_id` at construction — i.e. at startup.

        The composition root is expected to obtain the value through
        `api.security.resolve_tenant_id`, which refuses a missing or blank
        `CBRAIN_TENANT_ID`. This second check is not redundant: it closes the
        path where a caller passes `""` from somewhere else entirely, and it
        fails where the value is USED rather than where it was read.

        ⛔ There is no fallback, here or anywhere: `tenant_id` is immutable on
        every `document` it reaches (07 Mục 2.1), so a made-up value is not
        something a later release can quietly correct.
        """
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError(
                "IngestionServices.tenant_id is blank. Every document and every "
                "chunk this service writes carries it and can never be moved "
                "(07 Mục 2.1), so there is no default — resolve it from "
                f"{TENANT_ID_ENV_VAR} at startup (docs/10 §2)."
            )


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
        response_model=SpaceStatusResponse,
        status_code=202,  # docs/10 §4.0
    )
    def delete_space_endpoint(
        space_id: str, body: SpaceDeletionRequest
    ) -> SpaceStatusResponse:
        """docs/10 §4.0 — close the door now, empty the room in the background.

        ⭐ **The door closes inside this request** and only the emptying is
        deferred. §4.0 step 1 is *"Từ lúc này mọi lời gọi nộp tài liệu hay
        thao tác ghi vào Space trả `409 SPACE_BEING_DELETED`"* — "từ lúc
        này" has to mean the moment Backend gets its `202`, or a document
        submitted a millisecond later could land in a Space the loop has
        already walked past, and nothing would ever mention it again.

        The body is the SAME body `GET /v1/spaces/{space_id}` returns (PO
        chốt 24/9, §4.0: *"để BE chỉ phải hiểu một dạng"*), read AFTER the
        job was queued and therefore describing the world as it is now — in
        practice `state = being_deleted` and the counts not yet moved.

        Calling it twice is safe and is meant to be: `delete_space`
        re-derives its worklist from the stores on every run, so two queued
        jobs for one Space converge on the same end state (§4.0: *"Gọi
        `DELETE` lần hai: trả tiến độ hiện tại, không lỗi, không xoá lặp"*).
        """
        begin_space_deletion(space_id, space_registry=services.space_registry)

        def job() -> None:
            delete_space(
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

        services.worker.submit(job)
        return _space_status(space_id, services=services)

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
        carrying the `space_id`, and deletion-log lines still open). The same
        reader serves `DELETE`'s `202` body — one shape, one code path.
        """
        return _space_status(space_id, services=services)

    @router.post(
        "/v1/ingestions",
        response_model=IngestionSubmissionResponse,
        status_code=202,  # docs/10 §4.1
    )
    def submit_ingestion(
        body: IngestionSubmissionRequest,
    ) -> IngestionSubmissionResponse:
        """docs/10 §4.1 — the six steps, in this order, before `202`.

        §4.1, verbatim: *"xác thực → kiểm thân → kiểm Space (§4.0) **trước
        khi tải byte nào** → tải thẳng ra file tạm, đếm byte khi ghi, vượt cỡ
        tối đa thì ngừng ngay (`413 FILE_TOO_LARGE`) → so `sha256` và
        `size_bytes` (lệch → `SOURCE_INTEGRITY_MISMATCH`) → tạo đối tượng nạp
        → trả 202."*

        Steps 1–2 happened before this function: the service key in
        `ServiceAuthMiddleware`, the body in `IngestionSubmissionRequest`.
        What is left is the order of 3–6, and each boundary is a decision:

        * **Space before bytes.** Downloading first and then discovering the
          Space is gone would have spent the transfer, filled the disk, and
          handed the caller a `409` anyway.
        * **`declared_previous_document_id` before bytes too**, for the same
          reason and one more: PO chốt 24/9 (K11) that a declaration which
          cannot be resolved is a refusal, never silence. Refusing at the
          door makes the refusal synchronous, where Backend can act on it,
          instead of a `rejected` row discovered minutes later.
        * **The download stays in the request**, not in the worker: §4.1 —
          *"Tải trong lời gọi chứ không để cho bộ chạy nền, vì hàng đợi dài
          sẽ làm đường dẫn hết hạn."*
        * **The row is written before `202`.** The answer promises the work
          will happen; a row in PostgreSQL is what makes that promise
          survive a restart. Waking the worker comes last, after the promise
          is durable.
        """
        # ---- 3. The Space gate — before a single byte is fetched ---------
        assert_space_accepts_documents(
            body.space_id, space_registry=services.space_registry
        )
        previous = _resolve_declared_previous(body, services=services)

        ingestion_id = services.new_ingestion_id()

        # ---- 4/5. Fetch, counting and hashing as it writes ---------------
        fetched = fetch_source_to_staging(
            url=body.source.url,
            sha256=body.source.sha256,
            size_bytes=body.source.size_bytes,
            source_filename=body.source.filename,
            ingestion_id=ingestion_id,
            staging=services.pipeline.staging,
            max_upload_bytes=services.max_upload_bytes,
            timeout_seconds=services.source_download_timeout_seconds,
            client_factory=services.http_client_factory,
        )

        # ---- 6. The durable row, then the wake-up ------------------------
        now = services.clock()
        record = IngestionRecord(
            ingestion_id=ingestion_id,
            space_id=body.space_id,
            tenant_id=services.tenant_id,
            status=IngestionStatus.QUEUED,
            submitted_by=body.actor.user_id,
            submitted_at=now,
            updated_at=now,
            # Backend's statement about the Space is consumed HERE and stored
            # as the branch this job takes — see `IngestionRecord`, which
            # explains at length why that is not `space_is_private` renamed.
            requires_pre_approval=body.space_is_private,
            staged_filename=fetched.staged_filename,
            declared_previous_document_id=(
                None if previous is None else previous.document_id
            ),
        )
        services.pipeline.records.put(record)
        services.worker.submit(services.pipeline.drain)

        return IngestionSubmissionResponse(
            ingestion_id=record.ingestion_id, status=wire_status(record.status)
        )

    @router.get(
        "/v1/ingestions/{ingestion_id}", response_model=IngestionStatusResponse
    )
    def read_ingestion(
        ingestion_id: str,
        space_id: str = Query(min_length=1),
    ) -> IngestionStatusResponse:
        """docs/10 §4.2 — where one submission got to. READ ONLY.

        `space_id` is a REQUIRED query parameter, and it is T4 (§1): Backend
        says who is asking, AI checks for itself that the object is in the
        Space named. A row in another Space answers `404
        OBJECT_NOT_IN_SPACE` — the same answer as a row that does not exist,
        *"để không tiết lộ đối tượng tồn tại"* (§3.5).
        """
        record = services.pipeline.records.get(ingestion_id)
        if record is None or record.space_id != space_id:
            raise ObjectNotInSpace(
                f"ingestion_id={ingestion_id!r} is not in space {space_id!r} "
                f"(docs/10 §1 T4)."
            )
        return _ingestion_status(record, services=services)

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
# Reads shared by more than one route — written once so two routes cannot
# come to disagree about what the same question answers.
# --------------------------------------------------------------------------- #


def _space_status(space_id: str, *, services: IngestionServices) -> SpaceStatusResponse:
    """The body of BOTH `GET /v1/spaces/{id}` and `DELETE /v1/spaces/{id}`.

    docs/10 §4.0, chốt 24/9: the two bodies are identical, so there is one
    function. Two builders would be two chances for the `202` to describe a
    slightly different world than the poll that follows it.
    """
    registration = services.space_registry.get(space_id)
    if registration is None:
        # Not an exception from the registry: `get` returns None by design,
        # and this layer is where a missing row is a 404 rather than an empty
        # answer.
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


def _resolve_declared_previous(
    body: IngestionSubmissionRequest, *, services: IngestionServices
) -> Document | None:
    """*"đây là bản mới của X"* — resolve X, or refuse.

    docs/10 §4.1: *"`declared_previous_document_id` không tồn tại hoặc không
    nằm ở `space_id` này → từ chối `OBJECT_NOT_IN_SPACE`. **Không được** im
    lặng coi như tài liệu mới."* The silent branch is the dangerous one: the
    submission would succeed, a fresh version chain would start, and the two
    versions of one document would never be linked — with a `202` in front
    of it.

    The job re-resolves the same id when it runs (the document can be deleted
    in between) and refuses again there. Both checks are needed: this one so
    Backend hears it synchronously, that one so the pipeline cannot proceed
    on a stale answer.
    """
    declared = body.declared_previous_document_id
    if declared is None:
        return None
    previous = services.profile_store.get_document(declared)
    if previous is None or previous.space_id != body.space_id:
        raise ObjectNotInSpace(
            f"declared_previous_document_id={declared!r} is not in space "
            f"{body.space_id!r} (docs/10 §4.1)."
        )
    return previous


def _ingestion_status(
    record: IngestionRecord, *, services: IngestionServices
) -> IngestionStatusResponse:
    """docs/10 §4.2 — the row, plus what only the stores know.

    `suggestions` and `relations_scan_state` are NOT columns of
    `ingestion_record`; they are read fresh from wherever the document
    actually is. That is NT3 applied to a read: GĐ7 keeps running after the
    row went terminal, and a Manager can edit labels through §4.3, so a copy
    on the row would be the stale one.
    """
    document: Document | None = None
    if record.status is IngestionStatus.ACTIVE and record.document_id is not None:
        document = services.profile_store.get_document(record.document_id)
    elif record.status is IngestionStatus.AWAITING_APPROVAL:
        entry = services.pre_approval_buffer.get(record.ingestion_id)
        document = None if entry is None else entry.document

    return IngestionStatusResponse(
        ingestion_id=record.ingestion_id,
        status=wire_status(record.status),
        code=None if record.code is None else record.code.value,
        document_id=record.document_id,
        existing_document_id=record.existing_document_id,
        suggestions=None if document is None else _suggestions(document),
        relations_scan_state=(
            document.relations_scan_state.value
            if document is not None and record.status is IngestionStatus.ACTIVE
            else None
        ),
    )


def _suggestions(document: Document) -> IngestionSuggestions:
    """The GĐ5 output Backend shows on the *"máy gợi ý, người xác nhận"*
    screen (06 §5.2 GĐ5).

    `title` and `doc_number` are projected from the empty string to `null`:
    no extractor for either exists (T2.4b), the columns are NOT NULL (07
    §2.1), and docs/10 §4.2 requires the ANSWER to be `null` rather than
    anything that could be mistaken for a suggestion. ⛔ The filename is not
    a fallback — that is the specific substitution §4.2 forbids by name.
    """
    return IngestionSuggestions(
        category_labels=list(document.category_labels),
        issued_date=document.issued_date,
        issued_date_source=document.issued_date_source.value,
        effective_date=document.effective_date,
        effective_date_source=document.effective_date_source.value,
        title=document.title or None,
        doc_number=document.doc_number or None,
    )


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


def _source_unreachable(request: Request, exc: Exception) -> Response:
    """docs/10 §3.5 — `422`. ⛔ The message must not repeat the presigned
    link, and it does not: `errors.MESSAGE_SOURCE_UNREACHABLE` is a fixed
    sentence and `exc` is never formatted into the answer (§4.1)."""
    return error_response(
        status_code=422,
        code=ErrorCode.SOURCE_UNREACHABLE,
        message=MESSAGE_SOURCE_UNREACHABLE,
    )


def _source_integrity_mismatch(request: Request, exc: Exception) -> Response:
    return error_response(
        status_code=422,
        code=ErrorCode.SOURCE_INTEGRITY_MISMATCH,
        message=MESSAGE_SOURCE_INTEGRITY_MISMATCH,
    )


def _file_too_large(request: Request, exc: Exception) -> Response:
    """docs/10 §3.5 — `413`, and the download has ALREADY been abandoned by
    the time this runs (`source_fetch` stops at the byte that crosses the
    ceiling, not at the end of the body)."""
    return error_response(
        status_code=413,
        code=ErrorCode.FILE_TOO_LARGE,
        message=MESSAGE_FILE_TOO_LARGE,
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
    SourceUnreachable: _source_unreachable,
    SourceIntegrityMismatch: _source_integrity_mismatch,
    FileTooLarge: _file_too_large,
}
