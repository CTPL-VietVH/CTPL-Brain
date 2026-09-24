"""Reading and writing `ingestion_record` — and, because the table IS the
queue, claiming the next job (docs/10 §4.1, §4.2).

Same split as `space_registry.py` and `deletion.py`: the row's SHAPE lives in
`schema/ingestion_record.py`, and what Ingestion DOES with it lives here —
the Protocol, the refusals, and the two queue operations.

──────────────────────────────────────────────────────────────────────────
⭐ The queue is the table, and that is the whole crash story
──────────────────────────────────────────────────────────────────────────

Phương án A, PO chốt 24/9/2026: the pending work is rows in PostgreSQL, not
a list in memory and not a new piece of infrastructure (v1 has exactly two
physical stores — CLAUDE.md Mục 5). A submission that has been answered
`202` is therefore already durable before the caller gets the answer, which
is what makes `202` honest.

──────────────────────────────────────────────────────────────────────────
⛔ `recover_orphans` is correct ONLY while exactly one worker runs
──────────────────────────────────────────────────────────────────────────

PO chốt 24/9/2026: at startup, EVERY row in `RUNNING` is orphaned and goes
straight back to `QUEUED`. There is no timeout and no heartbeat, and the
absence of one is the point — with a single worker thread in a single
process, "a row says RUNNING while this process is starting up" and "the
process that claimed it is dead" are the same sentence. A threshold would be
one more number to configure and one more thing to set wrong, bought with
nothing.

**The price is explicit: running two replicas of AI Services is FORBIDDEN**
until a durable claim (a worker identity plus a lease, or `SELECT … FOR
UPDATE SKIP LOCKED` with a liveness record) exists. A second replica
starting up would hand the first replica's live job back to the queue, and
the same document would be ingested twice. That work is a separate task
(`API-xoa-space-chay-nen-va-kho-ben`), deliberately not smuggled in here.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Protocol

from schema.ingestion_record import (
    UNFINISHED_STATUSES,
    IngestionRecord,
    IngestionStatus,
    ORPHANED_STATUS,
)

__all__ = [
    "InMemoryIngestionRecordStore",
    "IngestionRecordNotFound",
    "IngestionRecordStore",
    "IngestionRecordStoreError",
]


class IngestionRecordStoreError(Exception):
    """Base for every refusal this store makes."""


class IngestionRecordNotFound(IngestionRecordStoreError):
    """An update names an `ingestion_id` that is not in the table.

    Not softened into an insert: an update that silently creates a row would
    resurrect an ingestion a `DELETE`-of-Space sweep had removed, and the
    resurrected row would carry whatever the caller happened to hold.
    """


class IngestionRecordStore(Protocol):
    """The `ingestion_record` table, narrowed to what this service does.

    `claim_next` and `recover_orphans` are the two operations that are NOT
    plain CRUD, and both must be ATOMIC in a real implementation:

    * `claim_next` reads the oldest `QUEUED` row and marks it `RUNNING` in
      one statement (`UPDATE … WHERE ingestion_id = (SELECT … FOR UPDATE SKIP
      LOCKED LIMIT 1) RETURNING *`). Read-then-write in two statements is the
      shape that hands one job to two workers — and while v1 runs one worker,
      an operator restarting the service before the old process has exited is
      enough to have two for a moment.
    * `recover_orphans` moves every `RUNNING` row back to `QUEUED`. See the
      module docstring for why that is sound, and for the exact condition
      under which it stops being sound.
    """

    def put(self, record: IngestionRecord) -> None: ...

    def get(self, ingestion_id: str) -> IngestionRecord | None: ...

    def update(self, record: IngestionRecord) -> None: ...

    def claim_next(self, *, now: datetime) -> IngestionRecord | None: ...

    def recover_orphans(self, *, now: datetime) -> list[IngestionRecord]: ...

    def unfinished(self) -> list[IngestionRecord]: ...

    def list_in_space(self, space_id: str) -> list[IngestionRecord]: ...


class InMemoryIngestionRecordStore:
    """`IngestionRecordStore` in a dict — tests and single-process runs only.

    Same disclaimer as `InMemoryFingerprintIndex` and
    `InMemorySpaceRegistry`: this is NOT the real table. In particular it
    loses everything on restart, which is exactly the property the real
    implementation exists to provide — so a deployment wired to this class
    would answer `202` to a submission it is about to forget.
    """

    def __init__(self) -> None:
        self._records: dict[str, IngestionRecord] = {}

    def put(self, record: IngestionRecord) -> None:
        self._records[record.ingestion_id] = record

    def get(self, ingestion_id: str) -> IngestionRecord | None:
        return self._records.get(ingestion_id)

    def update(self, record: IngestionRecord) -> None:
        if record.ingestion_id not in self._records:
            raise IngestionRecordNotFound(
                f"ingestion_id={record.ingestion_id!r} is not in the ingestion "
                f"record table; an update never creates a row"
            )
        self._records[record.ingestion_id] = record

    def claim_next(self, *, now: datetime) -> IngestionRecord | None:
        """Oldest `QUEUED` row, marked `RUNNING`. `None` when the queue is
        empty."""
        queued = sorted(
            (
                record
                for record in self._records.values()
                if record.status is IngestionStatus.QUEUED
            ),
            key=lambda record: (record.submitted_at, record.ingestion_id),
        )
        if not queued:
            return None
        claimed = dataclasses.replace(
            queued[0], status=IngestionStatus.RUNNING, updated_at=now
        )
        self._records[claimed.ingestion_id] = claimed
        return claimed

    def recover_orphans(self, *, now: datetime) -> list[IngestionRecord]:
        """Every `RUNNING` row back to `QUEUED` — see the module docstring."""
        recovered: list[IngestionRecord] = []
        for ingestion_id, record in list(self._records.items()):
            if record.status is not ORPHANED_STATUS:
                continue
            requeued = dataclasses.replace(
                record, status=IngestionStatus.QUEUED, updated_at=now
            )
            self._records[ingestion_id] = requeued
            recovered.append(requeued)
        return recovered

    def unfinished(self) -> list[IngestionRecord]:
        """Rows that can still change — the `keep` list of the staging sweep."""
        return [
            record
            for record in self._records.values()
            if record.status in UNFINISHED_STATUSES
        ]

    def list_in_space(self, space_id: str) -> list[IngestionRecord]:
        return [
            record
            for record in self._records.values()
            if record.space_id == space_id
        ]

    def records(self) -> list[IngestionRecord]:
        """Inspection helper for tests."""
        return list(self._records.values())
