"""Backend C.Brain, faked — docs/10 §10.

PO chốt 23/9/2026, nguyên văn: *"phía AI tự dựng một **Backend giả** đóng vai
BE ở cả hai chiều ..., rồi chạy các ca dưới như kiểm thử hợp đồng — không chờ
đội BE. Khi Backend thật sẵn sàng thì chạy lại đúng các ca này với Backend
thật. Backend giả phải tuân đúng hợp đồng này, **không được "dễ dãi" hơn** (ví
dụ: không bao giờ gửi thiếu `readable_space_ids`, trừ ca kiểm đúng lỗi đó)."*

⛔ **That last clause is the design rule of this file.** Every convenience
method below sends a complete, contract-legal call: the service key (§1 T1),
an `Idempotency-Key` on every write (§3.4), an `X-Request-Id`, and a full
`actor` (§3.2). There is no "skip the header for now" flag on any of them.

A case that needs an ILLEGAL call — the whole point of half the suite — uses
`call()`, the low-level door, and says in one line exactly which rule it is
breaking. That way an omission is always visible in the test that wants it,
and can never be inherited by a test that did not ask for it. A fake Backend
that quietly omitted a header would turn every other case into a test of a
Backend nobody is building.

This slice has no `readable_space_ids` anywhere — that field belongs to the
read endpoints (§5.1, §6.1), which do not exist yet. The same rule is applied
to what this slice does have: `space_id` and `actor`.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from fastapi.testclient import TestClient

__all__ = ["DEFAULT_ACTOR", "FakeBackend", "actor"]


def actor(*, user_id: str = "manager-lan", acting_as: str = "manager") -> dict[str, str]:
    """An `actor` block — docs/10 §3.2.

    Defaults to a Manager because every endpoint in this slice is one §4.0 and
    §5.6 give to *"`manager` của `space_id`"* or to `admin`. AI does not check
    that (§1 T2 — Backend decides), which is exactly why the fake Backend has
    to send the truthful thing: a test suite whose calls all carried
    `acting_as: "viewer"` would look like it proved AI accepts anything, when
    all it proved is that AI records what it is told.
    """
    return {"user_id": user_id, "acting_as": acting_as}


DEFAULT_ACTOR = actor()


class FakeBackend:
    """The caller on the other side of docs/10, driving the app in-process.

    Uses `TestClient` (httpx) rather than a live server: the contract being
    tested is the HTTP contract, and a socket adds a second thing that can
    fail without adding a rule that can be broken.
    """

    def __init__(self, app: Any, *, service_key: str) -> None:
        self._client = TestClient(app)
        self._service_key = service_key

    def __enter__(self) -> FakeBackend:
        self._client.__enter__()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._client.__exit__(*exc_info)

    # -- the low-level door, for cases that break a rule on purpose ------- #

    def call(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        service_key: str | None = None,
        send_service_key: bool = True,
        idempotency_key: str | None = None,
        send_idempotency_key: bool = True,
        request_id: str | None = None,
    ) -> httpx.Response:
        """One HTTP call, with every header individually controllable.

        Defaults are the contract-legal ones. A case that wants an illegal
        call passes `send_service_key=False` (or a wrong key, or no
        idempotency key) and thereby names the rule it is breaking, right at
        the call site.
        """
        headers: dict[str, str] = {}
        if send_service_key:
            headers["X-Service-Key"] = (
                service_key if service_key is not None else self._service_key
            )
        if request_id is not None:
            headers["X-Request-Id"] = request_id
        if send_idempotency_key and method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            headers["Idempotency-Key"] = (
                idempotency_key if idempotency_key is not None else uuid.uuid4().hex
            )
        return self._client.request(method, path, json=json, headers=headers)

    # -- the contract-legal calls ---------------------------------------- #

    def register_space(
        self,
        space_id: str,
        *,
        actor_block: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        """`POST /v1/spaces` — docs/10 §4.0."""
        return self.call(
            "POST",
            "/v1/spaces",
            json={"space_id": space_id, "actor": actor_block or DEFAULT_ACTOR},
            idempotency_key=idempotency_key,
        )

    def delete_space(
        self,
        space_id: str,
        *,
        reason: str = "Phòng Nhân sự giải thể, Space không còn chủ",
        actor_block: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        """`DELETE /v1/spaces/{space_id}` — docs/10 §4.0.

        `reason` has a value here rather than being required of every caller
        because it is Backend's free text, and the point of the default is
        that it is REAL free text a Manager might type — Vietnamese, with a
        cause in it — so the log line written from it looks like the ones
        06 Mục 5.6 describes.
        """
        return self.call(
            "DELETE",
            f"/v1/spaces/{space_id}",
            json={"reason": reason, "actor": actor_block or DEFAULT_ACTOR},
            idempotency_key=idempotency_key,
        )

    def read_space(self, space_id: str) -> httpx.Response:
        """`GET /v1/spaces/{space_id}` — docs/10 §4.0."""
        return self.call("GET", f"/v1/spaces/{space_id}")

    def delete_document(
        self,
        document_id: str,
        *,
        space_id: str,
        reason: str = "Tài liệu đưa nhầm vào kho, Manager yêu cầu xoá vĩnh viễn",
        actor_block: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        """`DELETE /v1/documents/{document_id}` — docs/10 §5.6."""
        return self.call(
            "DELETE",
            f"/v1/documents/{document_id}",
            json={
                "space_id": space_id,
                "reason": reason,
                "actor": actor_block or DEFAULT_ACTOR,
            },
            idempotency_key=idempotency_key,
        )

    def submit_ingestion(
        self,
        *,
        source: dict[str, Any],
        space_id: str,
        space_is_private: bool = False,
        declared_previous_document_id: str | None = None,
        actor_block: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        """`POST /v1/ingestions` — docs/10 §4.1.

        ⛔ No `title` and no `doc_number` are sent, and there is no parameter
        for them: §4.2 makes both AI's to suggest (*"BE **không** gửi chúng
        khi nộp"*). A fake Backend that could send them would let a case pass
        that a real Backend could never produce.

        `space_is_private` defaults to `False` because that is the path that
        writes to the shared stores — the one worth exercising by default.
        The private path is opted into, so a case that means to test
        pre-approval says so at the call site.
        """
        body: dict[str, Any] = {
            "source": source,
            "space_id": space_id,
            "space_is_private": space_is_private,
            "actor": actor_block or actor(acting_as="contributor"),
        }
        if declared_previous_document_id is not None:
            body["declared_previous_document_id"] = declared_previous_document_id
        return self.call(
            "POST", "/v1/ingestions", json=body, idempotency_key=idempotency_key
        )

    def read_ingestion(self, ingestion_id: str, *, space_id: str) -> httpx.Response:
        """`GET /v1/ingestions/{ingestion_id}?space_id=` — docs/10 §4.2.

        `space_id` is required here because it is required there: it is what
        AI checks for itself under T4, and a convenience default would let
        every case skip the one field that makes the check possible.
        """
        return self.call(
            "GET", f"/v1/ingestions/{ingestion_id}?space_id={space_id}"
        )

    def read_meta(self, *, send_service_key: bool = True) -> httpx.Response:
        """`GET /v1/meta` — docs/10 §3.6."""
        return self.call("GET", "/v1/meta", send_service_key=send_service_key)
