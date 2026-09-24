"""The four things every call passes through, in the order it passes them.

    ┌─ RequestIdMiddleware ────────────────────────────────────────────┐
    │ ┌─ UnhandledErrorMiddleware ───────────────────────────────────┐ │
    │ │ ┌─ ServiceAuthMiddleware ──────────────────────────────────┐ │ │
    │ │ │ ┌─ IdempotencyMiddleware ──────────────────────────────┐ │ │ │
    │ │ │ │           FastAPI routing + exception handlers       │ │ │ │
    │ │ │ └──────────────────────────────────────────────────────┘ │ │ │
    │ │ └──────────────────────────────────────────────────────────┘ │ │
    │ └──────────────────────────────────────────────────────────────┘ │
    └──────────────────────────────────────────────────────────────────┘

**The order is a set of decisions, not a style.**

* `X-Request-Id` is outermost so that EVERY response carries it — including a
  `401` that never reached routing and a `500` that came out of a middleware
  below (docs/10 §3.4).
* The catch-all sits directly inside it. Starlette's own `ServerErrorMiddleware`
  is further out still and would answer an unhandled exception ABOVE the
  request-id layer, i.e. without the header; catching here keeps the envelope
  and the header on every single response.
* Authentication comes before idempotency so an unauthenticated caller cannot
  write into the idempotency store — otherwise a stranger who guesses a key
  can poison the answer a legitimate retry receives.
* Idempotency is innermost, immediately around the routes, so a replay returns
  without the route function — and therefore without the business call — ever
  running. That is the whole point of §3.4 (*"không ghi thêm"*), and a cache
  further out would still be correct but would have to know about routing.

──────────────────────────────────────────────────────────────────────────
Why these are raw ASGI middlewares and not `BaseHTTPMiddleware`
──────────────────────────────────────────────────────────────────────────

Two of them must touch things `BaseHTTPMiddleware` hides: the request BODY
before the route reads it (for the idempotency fingerprint) and the response
BODY after it is produced (to store it). Reading the body from a
`BaseHTTPMiddleware` consumes the stream the route is about to read, and the
usual fix is to reach into `request._receive` — a private attribute. At this
layer the raw form is both shorter and honest: the body is buffered once and
replayed downstream through a receive channel this module owns.

⚠️ Buffering means the whole body is in memory, so every endpoint's request
body has to be small. It is — and after 24/9/2026 that is guaranteed by the
contract rather than by luck: docs/10 §4.1 chốt that **the file travels by
reference**, so `POST /v1/ingestions` carries a presigned URL plus a digest,
a few hundred bytes like every other call. (An earlier draft of §4.1 had a
multipart upload, which would have had to be exempted from this middleware —
the fingerprint of a 100 MB upload is not worth 100 MB of RSS. That
exemption is no longer needed and must not be added back without §4.1
changing first.)
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterable
from typing import Any, Final

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.errors import (
    MESSAGE_IDEMPOTENCY_KEY_MISSING,
    MESSAGE_IDEMPOTENCY_KEY_REUSED,
    MESSAGE_INTERNAL_ERROR,
    MESSAGE_UNAUTHENTICATED,
    ErrorCode,
    error_response,
)
from api.idempotency import (
    IdempotencyRecord,
    IdempotencyStore,
    StoredResponse,
    fingerprint_request,
)
from api.security import (
    IDEMPOTENCY_KEY_HEADER,
    REQUEST_ID_HEADER,
    SERVICE_KEY_HEADER,
    presented_key_matches,
)

__all__ = [
    "IDEMPOTENT_METHODS",
    "REQUEST_ID_SCOPE_KEY",
    "IdempotencyMiddleware",
    "RequestIdMiddleware",
    "ServiceAuthMiddleware",
    "UnhandledErrorMiddleware",
    "new_request_id",
]

logger = logging.getLogger(__name__)


#: Methods that carry no write and therefore need no `Idempotency-Key`.
#: docs/10 §3.4 puts the header on *"lời gọi ghi"*; everything else in this
#: set is either a read or a transport-level request.
IDEMPOTENT_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD", "OPTIONS"})

#: Where the request id is parked for anything downstream that wants to log it
#: (`request.state.request_id`). Not used to make decisions — it is a trace,
#: and a caller controls its value.
REQUEST_ID_SCOPE_KEY: Final = "request_id"


def new_request_id() -> str:
    """A fresh id for a call that arrived without one."""
    return uuid.uuid4().hex


async def _send_response(send: Send, response: Any, scope: Scope, receive: Receive) -> None:
    await response(scope, receive, send)


class RequestIdMiddleware:
    """docs/10 §3.4 — every call has an `X-Request-Id`, and always gets it back.

    Backend's own id is kept when it sends one, so one identifier spans both
    sides of an incident; one is minted when it does not, so there is never a
    call in either log that cannot be pointed at.
    """

    def __init__(self, app: ASGIApp, *, generate: Callable[[], str] = new_request_id) -> None:
        self.app = app
        self._generate = generate

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
        request_id = incoming if incoming else self._generate()
        scope.setdefault("state", {})[REQUEST_ID_SCOPE_KEY] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        await self.app(scope, receive, send_with_request_id)


class UnhandledErrorMiddleware:
    """Nothing leaves this service as a traceback — docs/10 §3.5.

    Any exception that no handler claimed becomes `500 INTERNAL_ERROR` with a
    message that says nothing about the failure. The detail goes to the log,
    with the request id, because that is where an operator can use it and the
    caller cannot.

    ⚠️ This layer must never swallow an exception silently: `logger.exception`
    is what keeps NT2's third clause true here — *"chỗ nào bỏ sót gây hại thì
    phải NHÌN THẤY ĐƯỢC"*.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_and_remember(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_and_remember)
        except Exception:
            request_id = scope.get("state", {}).get(REQUEST_ID_SCOPE_KEY)
            logger.exception(
                "Unhandled exception while serving %s %s (%s=%s)",
                scope.get("method"),
                scope.get("path"),
                REQUEST_ID_HEADER,
                request_id,
            )
            if response_started:
                # Bytes are already on the wire; a second response would be a
                # protocol error. Re-raise so the server tears the connection
                # down instead of pretending the call succeeded.
                raise
            await _send_response(
                send,
                error_response(
                    status_code=500,
                    code=ErrorCode.INTERNAL_ERROR,
                    message=MESSAGE_INTERNAL_ERROR,
                ),
                scope,
                receive,
            )


class ServiceAuthMiddleware:
    """docs/10 §1 T1 — only Backend C.Brain gets past this line.

    Applies to EVERY path, `GET /v1/meta` included. §3.6 exempts that endpoint
    from `actor` (*"Không cần `actor`"*) — that is the human identity, which
    `/v1/meta` has no use for. It says nothing about the service credential,
    and T1 says *"Mọi lời gọi"*. An unauthenticated readiness endpoint would
    also be a free monitor of when this deployment is down.
    """

    def __init__(self, app: ASGIApp, *, service_key: str) -> None:
        self.app = app
        self._service_key = service_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        presented = Headers(scope=scope).get(SERVICE_KEY_HEADER)
        if not presented_key_matches(presented, secret=self._service_key):
            # One answer for "no header" and for "wrong key" — see
            # errors.MESSAGE_UNAUTHENTICATED.
            await _send_response(
                send,
                error_response(
                    status_code=401,
                    code=ErrorCode.UNAUTHENTICATED,
                    message=MESSAGE_UNAUTHENTICATED,
                ),
                scope,
                receive,
            )
            return

        await self.app(scope, receive, send)


class IdempotencyMiddleware:
    """docs/10 §3.4 — a repeated write returns the first answer, and re-runs
    nothing.

    Three outcomes for a write call:

    * no `Idempotency-Key` → `400 IDEMPOTENCY_KEY_MISSING`. Refused rather
      than waved through: §3.4 makes the header mandatory, and "no key means
      no protection" is a hole that only shows up as duplicated work long
      after someone dropped the header.
    * key seen before with the SAME request → the stored response, byte for
      byte, without touching the app below.
    * key seen before with a DIFFERENT request → `422 IDEMPOTENCY_KEY_REUSED`.
      Never the stored response: answering a different question with an old
      answer is the silent failure this whole mechanism is supposed to prevent.

    Responses of status ≥ 500 are NOT stored. A server error is not a settled
    outcome, so the same key may be retried; storing it would freeze a
    transient failure into a permanent one for that key.
    """

    def __init__(self, app: ASGIApp, *, store: IdempotencyStore) -> None:
        self.app = app
        self._store = store

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in IDEMPOTENT_METHODS:
            await self.app(scope, receive, send)
            return

        key = Headers(scope=scope).get(IDEMPOTENCY_KEY_HEADER)
        if key is None or not key.strip():
            await _send_response(
                send,
                error_response(
                    status_code=400,
                    code=ErrorCode.IDEMPOTENCY_KEY_MISSING,
                    message=MESSAGE_IDEMPOTENCY_KEY_MISSING,
                ),
                scope,
                receive,
            )
            return

        body = await _read_body(receive)
        fingerprint = fingerprint_request(
            method=scope["method"], path=scope["path"], body=body
        )

        stored = self._store.get(key)
        if stored is not None:
            if stored.request_fingerprint != fingerprint:
                await _send_response(
                    send,
                    error_response(
                        status_code=422,
                        code=ErrorCode.IDEMPOTENCY_KEY_REUSED,
                        message=MESSAGE_IDEMPOTENCY_KEY_REUSED,
                    ),
                    scope,
                    receive,
                )
                return
            await _replay(stored.response, send)
            return

        captured_status: int | None = None
        captured_headers: list[tuple[bytes, bytes]] = []
        captured_body = bytearray()

        async def capture(message: Message) -> None:
            nonlocal captured_status
            if message["type"] == "http.response.start":
                captured_status = message["status"]
                captured_headers.extend(message.get("headers", []))
            elif message["type"] == "http.response.body":
                captured_body.extend(message.get("body", b""))
            await send(message)

        await self.app(scope, _replayable_receive(body), capture)

        if captured_status is not None and captured_status < 500:
            self._store.put(
                key,
                IdempotencyRecord(
                    request_fingerprint=fingerprint,
                    response=StoredResponse(
                        status_code=captured_status,
                        body=bytes(captured_body),
                        media_type=_media_type(captured_headers),
                    ),
                ),
            )


# --------------------------------------------------------------------------- #
# Body plumbing — buffer once, hand the same bytes downstream
# --------------------------------------------------------------------------- #


async def _read_body(receive: Receive) -> bytes:
    """Drain the request body off the ASGI receive channel."""
    body = bytearray()
    more_body = True
    while more_body:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        body.extend(message.get("body", b""))
        more_body = message.get("more_body", False)
    return bytes(body)


def _replayable_receive(body: bytes) -> Receive:
    """A receive channel that hands the buffered body to the app below once.

    After the body, it reports disconnect rather than looping forever on an
    empty message — a route that keeps reading gets an end, not a hang.
    """
    sent = False

    async def receive() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    return receive


async def _replay(response: StoredResponse, send: Send) -> None:
    """Re-send a stored response.

    `content-length` is recomputed from the stored bytes instead of being kept
    from the first call: the two must agree, and recomputing removes the chance
    that they ever do not.
    """
    await send(
        {
            "type": "http.response.start",
            "status": response.status_code,
            "headers": [
                (b"content-type", response.media_type.encode("latin-1")),
                (b"content-length", str(len(response.body)).encode("latin-1")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": response.body})


def _media_type(headers: Iterable[tuple[bytes, bytes]]) -> str:
    """The `content-type` of a captured response.

    The fallback is the media type this API speaks everywhere (docs/10 §3.1:
    *"HTTP + JSON"*) and is a TRANSPORT fact, not a tuning parameter with a
    home in `config/` — a response that reached here without a content-type
    came from inside this package.
    """
    for name, value in headers:
        if name.lower() == b"content-type":
            return value.decode("latin-1")
    return "application/json"
