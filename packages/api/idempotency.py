"""Idempotency for write calls — docs/10 §3.4.

§3.4: *"Mọi lời gọi ghi mang header `Idempotency-Key`. Gửi lại cùng khoá thì
nhận lại đúng kết quả lần đầu, không ghi thêm."*

Three pieces: what a stored response is, what proves two calls are "the same
call", and the store itself behind a Protocol.

──────────────────────────────────────────────────────────────────────────
Why the fingerprint covers the METHOD and the PATH, not just the body
──────────────────────────────────────────────────────────────────────────

`{"reason": "...", "actor": {...}}` is a legal body for `DELETE
/v1/spaces/A` and for `DELETE /v1/spaces/B` alike. Keyed on the body alone, a
Backend that reuses one key across two Spaces would be handed the FIRST
Space's result for the second Space — an answer saying "deleted" about a Space
nothing touched. Hashing method and path with the body turns that into a
visible `IDEMPOTENCY_KEY_REUSED` refusal instead.

──────────────────────────────────────────────────────────────────────────
What this in-memory implementation is NOT
──────────────────────────────────────────────────────────────────────────

⚠️ `InMemoryIdempotencyStore` is per-process and unbounded. That is honest for
a single-process test run and WRONG for a real deployment, in two ways a real
store must fix: two replicas of AI Services would each have their own memory
(so a retry routed to the other replica re-runs the work), and nothing ever
expires. Both are properties of the STORE, not of the middleware, which is why
the Protocol exists — the same shape `SpaceRegistry` and `DeletionLog` use.

Note what does NOT depend on that fix: the business functions behind every
write endpoint here are individually re-runnable (T2.8, T2.11). Idempotency
keys make a repeat CHEAP and make its answer IDENTICAL; they are not what
makes a repeat SAFE.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

__all__ = [
    "IdempotencyRecord",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "StoredResponse",
    "fingerprint_request",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredResponse:
    """A response held for replay.

    Headers are deliberately NOT stored. The one header that matters per call
    is `X-Request-Id`, and a replay must carry the id of the call being made
    now, not the id of the call that happened yesterday — otherwise two
    distinct calls share one id in Backend's logs and in ours.
    """

    status_code: int
    body: bytes
    media_type: str


@dataclass(frozen=True, slots=True, kw_only=True)
class IdempotencyRecord:
    """What one `Idempotency-Key` has already been used for."""

    request_fingerprint: str
    response: StoredResponse


class IdempotencyStore(Protocol):
    """Where used keys live. See the module docstring for what a real one owes."""

    def get(self, key: str) -> IdempotencyRecord | None: ...

    def put(self, key: str, record: IdempotencyRecord) -> None: ...


class InMemoryIdempotencyStore:
    """`IdempotencyStore` in a dict — tests and single-process runs only."""

    def __init__(self) -> None:
        self._records: dict[str, IdempotencyRecord] = {}

    def get(self, key: str) -> IdempotencyRecord | None:
        return self._records.get(key)

    def put(self, key: str, record: IdempotencyRecord) -> None:
        # First write wins. A second `put` for one key can only come from a
        # racing duplicate of the same call; keeping the first response is the
        # same rule `DeletionLog.record_started` follows.
        self._records.setdefault(key, record)

    def keys(self) -> list[str]:
        """Inspection helper for tests."""
        return list(self._records)


def fingerprint_request(*, method: str, path: str, body: bytes) -> str:
    """What makes two calls "the same call" for replay purposes.

    SHA-256 over method, path and the RAW body bytes. Raw, not parsed: two
    bodies that differ only in key order are the same request semantically,
    but proving that would mean a canonical JSON form here, and a canonical
    form that disagrees with the parser is a second reader of the request. A
    Backend that retries by resending the bytes it kept — which is what a
    retry is — hashes identically.
    """
    digest = hashlib.sha256()
    digest.update(method.upper().encode("utf-8"))
    digest.update(b"\n")
    digest.update(path.encode("utf-8"))
    digest.update(b"\n")
    digest.update(body)
    return digest.hexdigest()
