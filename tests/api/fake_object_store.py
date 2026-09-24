"""Backend's object store, faked — the other half of docs/10 §4.1.

`fake_backend.FakeBackend` plays Backend calling INTO AI. This plays the
MinIO that Backend hands AI a presigned link to. Both are needed for §4.1,
because the submission is the one call where AI reaches outward.

⚠️ **No socket.** The store is reached through an `httpx.MockTransport`, so
the real `httpx` client code in `api.source_fetch` runs — streaming, chunked
reads, `raise_for_status`, timeouts — against a transport that answers from
a dict. `fake_backend` gives the same reasoning for using `TestClient`: a
socket adds a second thing that can fail without adding a rule that can be
broken. It also lets the size case below assert something a socket makes
awkward: that the download STOPPED, counted in blocks the store was asked
for.

The store is deliberately able to misbehave in the three ways §4.1 names —
an expired link, a body that does not match the declared digest, and a body
larger than the ceiling — because those are the cases the endpoint exists to
refuse.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import httpx

__all__ = ["FakeObjectStore", "StoredObject"]

#: Size of one streamed block. Small enough that a "too large" body is many
#: blocks, so "stopped early" is observable; it is a property of this fake,
#: not of the service (`source_fetch` never chooses a block size — it takes
#: whatever `httpx.iter_bytes()` hands it).
BLOCK_SIZE = 64


@dataclass
class StoredObject:
    """One file, and the link Backend would sign for it."""

    url: str
    content: bytes
    filename: str
    content_type: str
    expired: bool = False
    #: Blocks the store was actually asked to produce. The `FILE_TOO_LARGE`
    #: case asserts on this: refusing after reading the whole body would be a
    #: refusal with the damage already done (docs/10 §3.5 — *"Ngừng tải ngay
    #: khi vượt, không tải hết rồi mới kiểm"*).
    blocks_served: int = 0

    @property
    def block_count(self) -> int:
        return max(1, -(-len(self.content) // BLOCK_SIZE))

    def source_block(
        self, *, sha256: str | None = None, size_bytes: int | None = None
    ) -> dict:
        """The `source` object of `POST /v1/ingestions` (docs/10 §4.1).

        `sha256` and `size_bytes` can be overridden so a case can describe
        the file WRONGLY on purpose — that is the whole of the
        `SOURCE_INTEGRITY_MISMATCH` case, and it has to come from Backend's
        side to be realistic.
        """
        return {
            "url": self.url,
            "sha256": sha256
            if sha256 is not None
            else hashlib.sha256(self.content).hexdigest(),
            "size_bytes": size_bytes if size_bytes is not None else len(self.content),
            "filename": self.filename,
            "content_type": self.content_type,
        }


@dataclass
class FakeObjectStore:
    """Every object Backend could hand out a link to, keyed by URL."""

    objects: dict[str, StoredObject] = field(default_factory=dict)
    #: Set by a case to make the next read time out — docs/10 §3.5 folds
    #: *"quá thời gian"* into `SOURCE_UNREACHABLE` with expiry and refusal.
    time_out: bool = False

    def publish(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        url = f"https://object-store.invalid/{filename}?signature=fake-{len(self.objects)}"
        stored = StoredObject(
            url=url, content=content, filename=filename, content_type=content_type
        )
        self.objects[url] = stored
        return stored

    def expire(self, stored: StoredObject) -> None:
        """What a short-lived presigned link does on its own after a while."""
        stored.expired = True

    # -- the transport --------------------------------------------------- #

    def client_factory(self, timeout_seconds: float) -> httpx.Client:
        """A `ClientFactory` for `api.source_fetch`.

        `timeout_seconds` is accepted and ignored: the fake does not wait, it
        raises `httpx.ReadTimeout` when a case asks it to. What matters for
        the contract is that AI treats a timeout as `SOURCE_UNREACHABLE`, not
        how many seconds it waited first.
        """
        return httpx.Client(transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        if self.time_out:
            raise httpx.ReadTimeout("fake object store: timed out", request=request)

        stored = self.objects.get(str(request.url))
        if stored is None:
            return httpx.Response(404, text="no such object")
        if stored.expired:
            # What MinIO answers for a presigned URL past its expiry.
            return httpx.Response(403, text="request has expired")

        def blocks():
            for start in range(0, max(len(stored.content), 1), BLOCK_SIZE):
                stored.blocks_served += 1
                yield stored.content[start : start + BLOCK_SIZE]

        return httpx.Response(200, content=blocks())
