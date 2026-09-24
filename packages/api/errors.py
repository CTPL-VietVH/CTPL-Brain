"""The error envelope of docs/10 §3.5 — `{code, message}`, and nothing else.

§3.5: *"Mọi lỗi có mã máy đọc được (`code`) và thông điệp tiếng Việt cho người
(`message`)"*.

⚠️ **Two languages meet in this file, and the split is deliberate.**

* `code` is a machine identifier — English UPPER_SNAKE, copied character for
  character from the table in §3.5. Backend branches on it.
* `message` is DATA travelling to a human on the other side of the wire, and
  §3.5 requires it in Vietnamese. It is not an exception message in the sense
  of CLAUDE.md Mục 0 điều 4: the exceptions raised inside `packages/ingestion/`
  are English because they are internal code, and this layer writes its own
  Vietnamese sentence rather than forwarding `exc.args` — forwarding would
  leak an internal wording (and often an internal identifier) to a screen, and
  would silently change the public contract the day someone rephrases an
  exception.

──────────────────────────────────────────────────────────────────────────
Codes this repo ADDS to the §3.5 table, and why each one is not in it
──────────────────────────────────────────────────────────────────────────

§3.5 lists the refusals the SPEC could name; it does not cover the transport
itself. Four codes below are additions, marked `# [added]`, and each is
reported to PO in the task report rather than slipped in:

* `UNAUTHENTICATED` (401) — §1 T1 requires service authentication but §3.5 has
  no code for failing it.
* `IDEMPOTENCY_KEY_MISSING` (400) and `IDEMPOTENCY_KEY_REUSED` (422) — §3.4
  states the header is mandatory and that a repeat must return the first
  result; it names no code for a caller that breaks either half.
* `INVALID_REQUEST` (422) — a body that is malformed in a way that has nothing
  to do with scope (wrong type, unknown field). `SCOPE_MISSING` must NOT be
  stretched to cover it: Backend reads `SCOPE_MISSING` as *"I forgot the
  permission scope"*, and a code that also means *"your JSON is wrong"* would
  train them to ignore it.
* `INTERNAL_ERROR` (500) — the catch-all. Without it an unforeseen exception
  reaches the client as a traceback, which is both a leak and an error shape
  Backend cannot parse.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi.responses import JSONResponse

from schema.document import Document

__all__ = [
    "CODE_FIELD",
    "MESSAGE_FIELD",
    "MESSAGE_IDEMPOTENCY_KEY_MISSING",
    "MESSAGE_IDEMPOTENCY_KEY_REUSED",
    "MESSAGE_INTERNAL_ERROR",
    "MESSAGE_INVALID_REQUEST",
    "MESSAGE_INVALID_STATE",
    "MESSAGE_OBJECT_NOT_IN_SPACE",
    "MESSAGE_SCOPE_MISSING",
    "MESSAGE_SPACE_BEING_DELETED",
    "MESSAGE_SPACE_NOT_REGISTERED",
    "MESSAGE_UNAUTHENTICATED",
    "SCOPE_FIELD_NAMES",
    "ErrorCode",
    "error_payload",
    "error_response",
]


#: The two keys of the envelope. Spelled once so a route, a middleware and a
#: test cannot end up with three spellings of the same wire contract.
CODE_FIELD: Final = "code"
MESSAGE_FIELD: Final = "message"


class ErrorCode:
    """Machine-readable codes. Values are the strings docs/10 §3.5 prints.

    A plain namespace of constants rather than an `Enum`: these are compared
    against, serialised and logged as strings, and an `Enum` would add a
    `.value` that half the call sites would forget.
    """

    # -- verbatim from the docs/10 §3.5 table --------------------------- #
    SCOPE_MISSING: Final = "SCOPE_MISSING"
    OBJECT_NOT_IN_SPACE: Final = "OBJECT_NOT_IN_SPACE"
    SPACE_NOT_REGISTERED: Final = "SPACE_NOT_REGISTERED"
    SPACE_BEING_DELETED: Final = "SPACE_BEING_DELETED"
    INVALID_STATE: Final = "INVALID_STATE"

    # -- [added] not in the §3.5 table; see the module docstring -------- #
    UNAUTHENTICATED: Final = "UNAUTHENTICATED"
    IDEMPOTENCY_KEY_MISSING: Final = "IDEMPOTENCY_KEY_MISSING"
    IDEMPOTENCY_KEY_REUSED: Final = "IDEMPOTENCY_KEY_REUSED"
    INVALID_REQUEST: Final = "INVALID_REQUEST"
    INTERNAL_ERROR: Final = "INTERNAL_ERROR"


# --------------------------------------------------------------------------- #
# The Vietnamese sentences — DATA, one per code (docs/10 §3.5)
# --------------------------------------------------------------------------- #

#: ⚠️ ONE message for both "no header" and "wrong key". Telling them apart is
#: free reconnaissance for anyone probing the service: *"header đúng tên nhưng
#: sai giá trị"* confirms the header name, and a difference in wording confirms
#: a guess is getting closer. docs/10 §3.5 uses the same reasoning for
#: `OBJECT_NOT_IN_SPACE` — *"Trả 404 chứ không trả 403, để không tiết lộ đối
#: tượng tồn tại"*.
MESSAGE_UNAUTHENTICATED: Final = (
    "Lời gọi không qua được xác thực dịch vụ. AI Services chỉ nhận lời gọi từ "
    "Backend C.Brain."
)

MESSAGE_SCOPE_MISSING: Final = (
    "Lời gọi thiếu phạm vi bắt buộc (`space_id` hoặc `actor`), hoặc để trống. "
    "Thiếu phạm vi không bao giờ được hiểu là không giới hạn."
)

MESSAGE_OBJECT_NOT_IN_SPACE: Final = (
    "Không tìm thấy đối tượng trong Space được nêu."
)

MESSAGE_SPACE_NOT_REGISTERED: Final = (
    "`space_id` này chưa được Backend đăng ký với AI Services."
)

MESSAGE_SPACE_BEING_DELETED: Final = (
    "Space đang được xoá hoặc đã xoá: không nhận thao tác ghi mới, và một "
    "`space_id` đã xoá không được đăng ký lại."
)

MESSAGE_INVALID_STATE: Final = (
    "Thao tác không hợp với trạng thái hiện tại của đối tượng."
)

MESSAGE_IDEMPOTENCY_KEY_MISSING: Final = (
    "Lời gọi ghi phải mang header `Idempotency-Key`."
)

MESSAGE_IDEMPOTENCY_KEY_REUSED: Final = (
    "`Idempotency-Key` này đã được dùng cho một lời gọi khác nội dung. Gửi lại "
    "đúng nội dung cũ để nhận lại kết quả lần đầu, hoặc dùng khoá mới."
)

MESSAGE_INVALID_REQUEST: Final = (
    "Thân lời gọi không đúng hợp đồng: sai kiểu dữ liệu, hoặc có trường không "
    "thuộc hợp đồng này."
)

#: No detail, on purpose: an unforeseen failure must not describe itself to the
#: caller. The trace goes to the log with the `X-Request-Id` of the call
#: (`middleware.UnhandledErrorMiddleware`), which is what an operator uses.
MESSAGE_INTERNAL_ERROR: Final = (
    "Lỗi nội bộ của AI Services. Hãy nêu `X-Request-Id` của lời gọi khi báo lỗi."
)


#: Field names whose absence — or emptiness — is a SCOPE failure, not a
#: malformed body (docs/10 §3.3: *"Thiếu trường thì trả `400 SCOPE_MISSING`"*,
#: and the ⚠️ that forbids reading `workspace=""` as "no limit").
#:
#: `space_id` is read off the schema dataclass rather than typed again, the
#: same trick `store_schema.CHUNK_DOCUMENT_ID_FIELD` uses: rename the field in
#: `packages/schema/` and this constant follows, instead of quietly pointing at
#: a name that no longer exists (CLAUDE.md Mục 6).
#:
#: `actor` and `readable_space_ids` have no schema home and must not get one —
#: they carry Backend's permission verdict, which QT1 keeps out of AI's data.
#: They are wire-only names, spelled here once.
SCOPE_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        Document.__dataclass_fields__["space_id"].name,
        "actor",
        "readable_space_ids",
    }
)


def error_payload(*, code: str, message: str) -> dict[str, Any]:
    """The body of every refusal — exactly two keys, always these two."""
    return {CODE_FIELD: code, MESSAGE_FIELD: message}


def error_response(*, status_code: int, code: str, message: str) -> JSONResponse:
    """A refusal as an HTTP response.

    Used by both the exception handlers and the middlewares. The middlewares
    cannot raise — they sit OUTSIDE the layer that turns exceptions into
    responses (see `middleware.py`) — so a shared response builder is what
    keeps their output the same shape as a handler's.
    """
    return JSONResponse(
        status_code=status_code, content=error_payload(code=code, message=message)
    )
