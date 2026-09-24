"""T2.11 (a) — reading and writing the Space register (docs/10 §2, §4.0;
06 Mục 5.6 "Xoá cả một Space"; 08 T2.11).

The two types that go IN the table — `SpaceState` and `SpaceRegistration` —
live in `schema/space_registry.py` and are imported below, the same split
`ingestion/deletion.py` makes against `schema/deletion_log.py`. What stays
here is what Ingestion DOES with them: the Protocol, the refusals, the legal
transitions, and the gate every upload passes through.

Read `schema/space_registry.py` first for the ⛔ bound on this table: docs/10
§2 — *"**Chỉ sự tồn tại** — không cây, không cờ, không thành viên"*.

──────────────────────────────────────────────────────────────────────────
Three states, and the one transition that never runs backwards
──────────────────────────────────────────────────────────────────────────

    register()                advance_state(BEING_DELETED)   advance_state(DELETED)
   ─────────────►  IN_USE  ──────────────────────────────►  BEING_DELETED  ────────►  DELETED
                     ▲                                            │                     │
                     └── register() again: idempotent             └── idempotent        └── idempotent

`DELETED` is terminal and a `space_id` that reaches it can never be
registered again — docs/10 §4.0 gives the reason, and it is not tidiness:
*"tránh tài liệu cũ trong nhật ký bị hiểu nhầm là thuộc Space mới trùng
mã"*. The deletion log keeps `space_id` forever (06 Mục 5.6), so reusing a
code would silently re-attribute history.

──────────────────────────────────────────────────────────────────────────
Why a Protocol with an in-memory implementation, and no psycopg here
──────────────────────────────────────────────────────────────────────────

Same shape as `FingerprintIndex` (T2.1), `SpaceScanScope` (T2.6) and
`PreApprovalBuffer` (T2.7): this module names the reads and writes the
ingestion path needs and leaves the live connection to the assembling layer.
The table's persistent shape is written down once, in
`schema/store_schema.py` (`SPACE_REGISTRY_TABLE_DDL`), for the same reason
every other table is: real code and tests must share one spelling.
"""

from __future__ import annotations

from typing import Protocol

from schema.space_registry import SpaceRegistration, SpaceState
from schema.store_schema import SPACE_REGISTRY_TABLE

__all__ = [
    "IllegalSpaceStateTransition",
    "InMemorySpaceRegistry",
    "SpaceCannotBeRegisteredAgain",
    "SpaceNotAcceptingDocuments",
    "SpaceNotRegistered",
    "SpaceRegistration",
    "SpaceRegistry",
    "SpaceRegistryError",
    "SpaceState",
    "assert_space_accepts_documents",
]


#: Forward-only. Each state maps to what it may become NEXT, itself included
#: so that every transition is idempotent: a resumed Space deletion re-marks
#: `BEING_DELETED`, and a second `DELETE` call re-marks `DELETED`, neither of
#: which is an error (docs/10 §4.0: *"Gọi `DELETE` lần hai: trả tiến độ hiện
#: tại, không lỗi, không xoá lặp"*).
_ALLOWED_TRANSITIONS: dict[SpaceState, frozenset[SpaceState]] = {
    SpaceState.IN_USE: frozenset({SpaceState.IN_USE, SpaceState.BEING_DELETED}),
    SpaceState.BEING_DELETED: frozenset({SpaceState.BEING_DELETED, SpaceState.DELETED}),
    SpaceState.DELETED: frozenset({SpaceState.DELETED}),
}


# --------------------------------------------------------------------------- #
# Errors — one per refusal the API contract names, so the caller that will
# eventually map them to HTTP codes (docs/10 §3.5) can tell them apart.
# --------------------------------------------------------------------------- #


class SpaceRegistryError(Exception):
    """Base for every refusal this module makes."""


class SpaceNotRegistered(SpaceRegistryError):
    """No `space_id` row at all — docs/10 §3.5 `SPACE_NOT_REGISTERED` (404).

    ⛔ An unknown Space is refused, never auto-created. Registering on first
    use would make the register describe whatever arrived instead of what
    Backend announced, and the *"tài liệu vào Space chưa đăng ký"* case —
    a typo in `space_id`, or a Space deleted a moment ago — would land the
    document in a Space nobody can reach.
    """


class SpaceNotAcceptingDocuments(SpaceRegistryError):
    """The Space exists but is not `IN_USE` — docs/10 §3.5
    `SPACE_BEING_DELETED` (409).

    docs/10 §4.0 step 1: *"Từ lúc này mọi lời gọi nộp tài liệu hay thao tác
    ghi vào Space trả `409 SPACE_BEING_DELETED`"*. Accepting one while the
    deletion loop is running would leave a document behind in a Space that is
    about to be reported gone.
    """


class SpaceCannotBeRegisteredAgain(SpaceRegistryError):
    """`register` on a Space that is being deleted or already deleted.

    docs/10 §4.0: *"`space_id` đã xoá thì không được đăng ký lại (`409
    SPACE_BEING_DELETED`) — tránh tài liệu cũ trong nhật ký bị hiểu nhầm là
    thuộc Space mới trùng mã"*. `BEING_DELETED` is refused on the same
    grounds and for one more: re-registering mid-deletion would race the
    deletion loop, which is still emptying that Space.
    """


class IllegalSpaceStateTransition(SpaceRegistryError):
    """A state change that runs backwards — `DELETED` → anything else, or
    `BEING_DELETED` → `IN_USE`.

    There is no "undelete": by the time a Space is marked `DELETED` its
    documents are gone from both stores (06 Mục 5.6), so a state that walked
    back would describe data that no longer exists.
    """


# --------------------------------------------------------------------------- #
# The Protocol
# --------------------------------------------------------------------------- #


class SpaceRegistry(Protocol):
    """Reads and writes the Space register.

    `register` and `advance_state` are both idempotent, because both sit
    behind API calls Backend is explicitly allowed to repeat (docs/10 §4.0:
    *"Gọi lại cùng `space_id` đang dùng → trả kết quả như lần đầu"*, and a
    `DELETE` that is called twice).
    """

    def get(self, space_id: str) -> SpaceRegistration | None: ...

    def register(self, space_id: str) -> SpaceRegistration: ...

    def advance_state(self, space_id: str, *, to: SpaceState) -> SpaceRegistration: ...


# --------------------------------------------------------------------------- #
# The gate every ingestion path goes through
# --------------------------------------------------------------------------- #


def assert_space_accepts_documents(
    space_id: str, *, space_registry: SpaceRegistry
) -> SpaceRegistration:
    """Refuse a Space that is unknown or no longer taking documents.

    docs/10 §4.1 puts this on every submission: *"`space_id` phải đã đăng ký
    và đang dùng (§4.0), nếu không trả `404 SPACE_NOT_REGISTERED` / `409
    SPACE_BEING_DELETED`"*. Two distinct exceptions, not one — the caller
    that maps them to HTTP status codes must be able to tell "never existed"
    from "on its way out".

    Returns the registration so a caller that needs the state does not read
    it twice.

    Raises:
        SpaceNotRegistered: no row for `space_id`.
        SpaceNotAcceptingDocuments: the row exists but is not `IN_USE`.
    """
    registration = space_registry.get(space_id)
    if registration is None:
        raise SpaceNotRegistered(
            f"space_id={space_id!r} was never registered by Backend "
            f"(table {SPACE_REGISTRY_TABLE!r}, docs/10 §4.0). A document is not "
            f"accepted into a Space that does not exist, and an unknown Space is "
            f"never created on first use."
        )
    if registration.state is not SpaceState.IN_USE:
        raise SpaceNotAcceptingDocuments(
            f"space_id={space_id!r} is in state {registration.state.value!r}; only "
            f"{SpaceState.IN_USE.value!r} accepts new documents (docs/10 §4.0 step 1)."
        )
    return registration


# --------------------------------------------------------------------------- #
# In-memory implementation — tests and single-process runs, NOT the real store
# (same disclaimer as `InMemoryFingerprintIndex`).
# --------------------------------------------------------------------------- #


class InMemorySpaceRegistry:
    """`SpaceRegistry` in a dict, enforcing what the DDL enforces.

    The dict key IS the primary key of `SPACE_REGISTRY_TABLE`: one row per
    `space_id`, so a second `register` of the same code finds the first row
    rather than creating a twin.
    """

    def __init__(self) -> None:
        self._registrations: dict[str, SpaceRegistration] = {}

    def get(self, space_id: str) -> SpaceRegistration | None:
        return self._registrations.get(space_id)

    def register(self, space_id: str) -> SpaceRegistration:
        """Record a Space as `IN_USE`. Idempotent while it stays `IN_USE`.

        Raises:
            SpaceCannotBeRegisteredAgain: the Space is `BEING_DELETED` or
                `DELETED`. A deleted code is never reused — see the exception's
                docstring for the history-mixing this prevents.
        """
        existing = self._registrations.get(space_id)
        if existing is not None:
            if existing.state is not SpaceState.IN_USE:
                raise SpaceCannotBeRegisteredAgain(
                    f"space_id={space_id!r} is in state {existing.state.value!r} and "
                    f"cannot be registered again (docs/10 §4.0). Backend must issue a "
                    f"new space_id rather than reuse this one."
                )
            return existing  # idempotent: same answer as the first call

        registration = SpaceRegistration(space_id=space_id, state=SpaceState.IN_USE)
        self._registrations[space_id] = registration
        return registration

    def advance_state(self, space_id: str, *, to: SpaceState) -> SpaceRegistration:
        """Move a registered Space forward to `to`. Idempotent on a no-op move.

        Raises:
            SpaceNotRegistered: nothing to move.
            IllegalSpaceStateTransition: the move runs backwards.
        """
        existing = self._registrations.get(space_id)
        if existing is None:
            raise SpaceNotRegistered(
                f"space_id={space_id!r} was never registered, so its state cannot be "
                f"changed to {to.value!r} (table {SPACE_REGISTRY_TABLE!r})."
            )
        if to not in _ALLOWED_TRANSITIONS[existing.state]:
            raise IllegalSpaceStateTransition(
                f"space_id={space_id!r} cannot move from {existing.state.value!r} to "
                f"{to.value!r}; allowed next states are "
                f"{sorted(state.value for state in _ALLOWED_TRANSITIONS[existing.state])}. "
                f"There is no undelete: the documents of a deleted Space are already "
                f"gone from both stores (06 Mục 5.6)."
            )
        if to is existing.state:
            return existing

        moved = SpaceRegistration(space_id=space_id, state=to)
        self._registrations[space_id] = moved
        return moved

    def registrations(self) -> list[SpaceRegistration]:
        """Inspection helper — the register is small by nature (one row per
        Space), so there is no paged read to design here."""
        return list(self._registrations.values())
