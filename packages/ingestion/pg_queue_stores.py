"""PostgreSQL implementations of the three tables this task installs:
`ingestion_record` (the work queue), `space_registry`, and the pre-approval
buffer pair (`ingestion_pre_approval_document` / `ingestion_pre_approval_chunk`).

Companion to the three in-memory stores, which already state the Protocol,
the refusals and every business rule — `ingestion_record_store.py`,
`space_registry.py`, `pre_approval_buffer.py`. This module is deliberately
the smaller half: it re-uses those Protocols, those exceptions and (for
`SpaceRegistry`) the very same `_ALLOWED_TRANSITIONS` table, so the state
machine is defined in exactly one place. What is new here is only the SQL
that makes each operation survive a restart.

Table names and DDL are NOT re-declared: `INGESTION_RECORD_TABLE` and
`SPACE_REGISTRY_TABLE` come from `schema.store_schema`, and the buffer pair
comes from `ingestion.pre_approval_buffer` — the single spelling CLAUDE.md
Mục 6 requires.

──────────────────────────────────────────────────────────────────────────
Connection shape — duck-typed, same idea as `schema.embedding_registry`
──────────────────────────────────────────────────────────────────────────

`schema/embedding_registry.py` accepts anything with `.execute(sql, params)`
returning a cursor with `.fetchone()`, precisely so the shared schema layer
never picks a Postgres driver. This module needs one thing more —
`.transaction()` — because `PreApprovalBuffer.put` must write the document
row and every chunk row atomically (that module's docstring: *"the real
implementation must therefore wrap the whole call in one PostgreSQL
transaction, not one per row"*). `psycopg.Connection` satisfies both, and
does so even under `autocommit=True` — psycopg 3 runs a `transaction()`
block as a real `BEGIN … COMMIT` regardless of the connection's autocommit
setting, which is the same connection shape every other test and tool in
this repo already opens (`tests/t0_1_stores/conftest.py`, `do_substring.py`).

──────────────────────────────────────────────────────────────────────────
`claim_next` — the one statement that MUST be atomic
──────────────────────────────────────────────────────────────────────────

`ingestion_record_store.py`'s `IngestionRecordStore` docstring gives the
exact shape: *"`UPDATE … WHERE ingestion_id = (SELECT … FOR UPDATE SKIP
LOCKED LIMIT 1) RETURNING *`"*. `claim_next` below is exactly that — one
round trip, one lock, one row — because read-then-write in two statements is
the shape that hands one job to two workers.

──────────────────────────────────────────────────────────────────────────
Everything else is a plain two-step read-then-write, same as the in-memory
twin
──────────────────────────────────────────────────────────────────────────

Only the queue's `claim_next` was asked to survive two workers racing for
the SAME row (the work order this module answers to). `register`,
`advance_state`, and the buffer's own duplicate check follow the same
SELECT-then-write shape their in-memory counterparts already use — inventing
a durable claim mechanism for those too would be scope nobody asked for.

──────────────────────────────────────────────────────────────────────────
Datetimes — naive in, naive out
──────────────────────────────────────────────────────────────────────────

Every caller in this codebase writes and compares NAIVE `datetime` values
(see `tests/api/conftest.py`'s `SteppingClock`, or any `INGESTED_AT`
constant across the test suite). The columns these values land in are
`timestamptz`, and Postgres hands a tz-aware value back on read. `_to_naive`
strips the offset Postgres adds so a round trip through the real table still
compares equal to what went in — the in-memory store gets this for free by
never touching a driver; this module has to do it once, explicitly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from schema.chunk import Chunk
from schema.document import DateSource, Document, VersionDeclaredBy
from schema.ingestion_record import (
    ORPHANED_STATUS,
    IngestionFailureCode,
    IngestionRecord,
    IngestionStatus,
)
from schema.space_registry import SpaceRegistration, SpaceState
from schema.store_schema import INGESTION_RECORD_TABLE, SPACE_REGISTRY_TABLE

from .ingestion_record_store import IngestionRecordNotFound
from .pre_approval_buffer import (
    PRE_APPROVAL_CHUNK_TABLE,
    PRE_APPROVAL_DOCUMENT_TABLE,
    BufferedIngestion,
    ChunkDocumentMismatchError,
    DuplicatePreApprovalEntryError,
    EmbeddedChunkInPreApprovalBufferError,
)
from .space_registry import (
    _ALLOWED_TRANSITIONS,
    IllegalSpaceStateTransition,
    SpaceCannotBeRegisteredAgain,
    SpaceNotRegistered,
)

__all__ = [
    "PgConnectionLike",
    "PgIngestionRecordStore",
    "PgPreApprovalBuffer",
    "PgSpaceRegistry",
]


class PgConnectionLike(Protocol):
    """`.execute` for every statement, `.transaction()` for the one call
    (`PreApprovalBuffer.put`) that must not partially apply. See the module
    docstring for why the second method is asked for here and not in
    `schema.embedding_registry.PgConnectionLike`."""

    def execute(self, query: str, params: Any = None) -> Any: ...

    def transaction(self) -> Any: ...


def _to_naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


# --------------------------------------------------------------------------- #
# ingestion_record — the queue
# --------------------------------------------------------------------------- #

_INGESTION_RECORD_COLUMNS = (
    "ingestion_id",
    "space_id",
    "tenant_id",
    "status",
    "submitted_by",
    "submitted_at",
    "updated_at",
    "requires_pre_approval",
    "staged_filename",
    "declared_previous_document_id",
    "document_id",
    "existing_document_id",
    "code",
)


def _record_params(record: IngestionRecord) -> tuple:
    return (
        record.ingestion_id,
        record.space_id,
        record.tenant_id,
        record.status.value,
        record.submitted_by,
        record.submitted_at,
        record.updated_at,
        record.requires_pre_approval,
        record.staged_filename,
        record.declared_previous_document_id,
        record.document_id,
        record.existing_document_id,
        record.code.value if record.code is not None else None,
    )


def _row_to_record(row: tuple) -> IngestionRecord:
    (
        ingestion_id,
        space_id,
        tenant_id,
        status,
        submitted_by,
        submitted_at,
        updated_at,
        requires_pre_approval,
        staged_filename,
        declared_previous_document_id,
        document_id,
        existing_document_id,
        code,
    ) = row
    return IngestionRecord(
        ingestion_id=ingestion_id,
        space_id=space_id,
        tenant_id=tenant_id,
        status=IngestionStatus(status),
        submitted_by=submitted_by,
        submitted_at=_to_naive(submitted_at),
        updated_at=_to_naive(updated_at),
        requires_pre_approval=requires_pre_approval,
        staged_filename=staged_filename,
        declared_previous_document_id=declared_previous_document_id,
        document_id=document_id,
        existing_document_id=existing_document_id,
        code=IngestionFailureCode(code) if code is not None else None,
    )


_INGESTION_RECORD_SELECT_LIST = ", ".join(_INGESTION_RECORD_COLUMNS)
_INGESTION_RECORD_VALUES_PLACEHOLDER = ", ".join(["%s"] * len(_INGESTION_RECORD_COLUMNS))
_INGESTION_RECORD_UPSERT_SET = ", ".join(
    f"{column} = EXCLUDED.{column}"
    for column in _INGESTION_RECORD_COLUMNS
    if column != "ingestion_id"
)
_INGESTION_RECORD_UPDATE_SET = ", ".join(
    f"{column} = %s" for column in _INGESTION_RECORD_COLUMNS if column != "ingestion_id"
)


class PgIngestionRecordStore:
    """`IngestionRecordStore` backed by the real `ingestion_record` table —
    the row IS the queue (Phương án A, PO chốt 24/9/2026), so this class is
    what makes a `202` honest across a restart.

    Behaves exactly like `InMemoryIngestionRecordStore`; the only observable
    difference is durability.
    """

    def __init__(self, connection: PgConnectionLike) -> None:
        self._conn = connection

    def put(self, record: IngestionRecord) -> None:
        # An upsert, not a plain INSERT, to match the in-memory store's dict
        # semantics exactly: `put` on an id already present replaces the row
        # rather than raising.
        self._conn.execute(
            f"""
            INSERT INTO {INGESTION_RECORD_TABLE} ({_INGESTION_RECORD_SELECT_LIST})
            VALUES ({_INGESTION_RECORD_VALUES_PLACEHOLDER})
            ON CONFLICT (ingestion_id) DO UPDATE SET {_INGESTION_RECORD_UPSERT_SET}
            """,
            _record_params(record),
        )

    def get(self, ingestion_id: str) -> IngestionRecord | None:
        row = self._conn.execute(
            f"SELECT {_INGESTION_RECORD_SELECT_LIST} FROM {INGESTION_RECORD_TABLE} "
            f"WHERE ingestion_id = %s",
            (ingestion_id,),
        ).fetchone()
        return _row_to_record(row) if row is not None else None

    def update(self, record: IngestionRecord) -> None:
        params = _record_params(record)
        cursor = self._conn.execute(
            f"UPDATE {INGESTION_RECORD_TABLE} SET {_INGESTION_RECORD_UPDATE_SET} "
            f"WHERE ingestion_id = %s",
            (*params[1:], record.ingestion_id),
        )
        if cursor.rowcount == 0:
            raise IngestionRecordNotFound(
                f"ingestion_id={record.ingestion_id!r} is not in the ingestion "
                f"record table; an update never creates a row"
            )

    def claim_next(self, *, now: datetime) -> IngestionRecord | None:
        """Oldest `QUEUED` row, marked `RUNNING`, in ONE round trip.

        `FOR UPDATE SKIP LOCKED` inside the subquery is what makes this safe
        under concurrent claimants: a row another transaction already has
        locked is skipped, never waited on and never double-claimed. See the
        module docstring's ⛔ for the single-worker assumption this rests on.
        """
        row = self._conn.execute(
            f"""
            UPDATE {INGESTION_RECORD_TABLE}
            SET status = %s, updated_at = %s
            WHERE ingestion_id = (
                SELECT ingestion_id FROM {INGESTION_RECORD_TABLE}
                WHERE status = %s
                ORDER BY submitted_at, ingestion_id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING {_INGESTION_RECORD_SELECT_LIST}
            """,
            (IngestionStatus.RUNNING.value, now, IngestionStatus.QUEUED.value),
        ).fetchone()
        return _row_to_record(row) if row is not None else None

    def recover_orphans(self, *, now: datetime) -> list[IngestionRecord]:
        """Every `RUNNING` row back to `QUEUED` — see `ingestion_record_store.py`
        module docstring for why that is sound only with one worker."""
        rows = self._conn.execute(
            f"""
            UPDATE {INGESTION_RECORD_TABLE}
            SET status = %s, updated_at = %s
            WHERE status = %s
            RETURNING {_INGESTION_RECORD_SELECT_LIST}
            """,
            (IngestionStatus.QUEUED.value, now, ORPHANED_STATUS.value),
        ).fetchall()
        return [_row_to_record(row) for row in rows]

    def unfinished(self) -> list[IngestionRecord]:
        rows = self._conn.execute(
            f"SELECT {_INGESTION_RECORD_SELECT_LIST} FROM {INGESTION_RECORD_TABLE} "
            f"WHERE status = ANY(%s)",
            ([IngestionStatus.QUEUED.value, IngestionStatus.RUNNING.value],),
        ).fetchall()
        return [_row_to_record(row) for row in rows]

    def list_in_space(self, space_id: str) -> list[IngestionRecord]:
        rows = self._conn.execute(
            f"SELECT {_INGESTION_RECORD_SELECT_LIST} FROM {INGESTION_RECORD_TABLE} "
            f"WHERE space_id = %s",
            (space_id,),
        ).fetchall()
        return [_row_to_record(row) for row in rows]


# --------------------------------------------------------------------------- #
# space_registry
# --------------------------------------------------------------------------- #


class PgSpaceRegistry:
    """`SpaceRegistry` backed by the real `space_registry` table.

    Transition legality is imported from `ingestion.space_registry`
    (`_ALLOWED_TRANSITIONS`), not re-typed here — two copies of that table
    is exactly the second spelling CLAUDE.md Mục 6 exists to prevent.
    """

    def __init__(self, connection: PgConnectionLike) -> None:
        self._conn = connection

    def get(self, space_id: str) -> SpaceRegistration | None:
        row = self._conn.execute(
            f"SELECT space_id, state FROM {SPACE_REGISTRY_TABLE} WHERE space_id = %s",
            (space_id,),
        ).fetchone()
        return SpaceRegistration(space_id=row[0], state=SpaceState(row[1])) if row else None

    def register(self, space_id: str) -> SpaceRegistration:
        existing = self.get(space_id)
        if existing is not None:
            if existing.state is not SpaceState.IN_USE:
                raise SpaceCannotBeRegisteredAgain(
                    f"space_id={space_id!r} is in state {existing.state.value!r} and "
                    f"cannot be registered again (docs/10 §4.0). Backend must issue a "
                    f"new space_id rather than reuse this one."
                )
            return existing  # idempotent: same answer as the first call

        self._conn.execute(
            f"INSERT INTO {SPACE_REGISTRY_TABLE} (space_id, state) VALUES (%s, %s)",
            (space_id, SpaceState.IN_USE.value),
        )
        return SpaceRegistration(space_id=space_id, state=SpaceState.IN_USE)

    def advance_state(self, space_id: str, *, to: SpaceState) -> SpaceRegistration:
        existing = self.get(space_id)
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

        self._conn.execute(
            f"UPDATE {SPACE_REGISTRY_TABLE} SET state = %s WHERE space_id = %s",
            (to.value, space_id),
        )
        return SpaceRegistration(space_id=space_id, state=to)

    def registrations(self) -> list[SpaceRegistration]:
        rows = self._conn.execute(
            f"SELECT space_id, state FROM {SPACE_REGISTRY_TABLE}"
        ).fetchall()
        return [SpaceRegistration(space_id=row[0], state=SpaceState(row[1])) for row in rows]


# --------------------------------------------------------------------------- #
# The pre-approval buffer pair
# --------------------------------------------------------------------------- #

#: `buffered_at` last: it is bookkeeping, not a `Document` field (see
#: `pre_approval_buffer.py`'s own DDL comment), split off by position in
#: `get`/`find_in_space_by_fingerprint` rather than named twice.
_DOCUMENT_COLUMNS = (
    "document_id",
    "space_id",
    "tenant_id",
    "title",
    "doc_number",
    "issued_date",
    "issued_date_source",
    "effective_date",
    "effective_date_source",
    "ingested_at",
    "source_format",
    "content_fingerprint",
    "extracted_text",
    "version_chain_id",
    "version_ordinal",
    "version_declared_by",
    "category_labels",
    "subject_entities",
    "buffered_at",
)

#: `chunk_ordinal` last: it preserves the cut order a Python list carries
#: implicitly (see `pre_approval_buffer.py`'s DDL comment) — not a `Chunk`
#: field, so it is never handed to `Chunk(...)`.
_CHUNK_COLUMNS = (
    "chunk_id",
    "document_id",
    "space_id",
    "tenant_id",
    "structure_path",
    "span_start",
    "span_end",
    "parent_chunk_id",
    "category_labels",
    "chunk_ordinal",
)

_DOCUMENT_SELECT_LIST = ", ".join(_DOCUMENT_COLUMNS)
_DOCUMENT_VALUES_PLACEHOLDER = ", ".join(["%s"] * len(_DOCUMENT_COLUMNS))
_DOCUMENT_UPSERT_SET = ", ".join(
    f"{column} = EXCLUDED.{column}" for column in _DOCUMENT_COLUMNS if column != "document_id"
)

_CHUNK_SELECT_LIST = ", ".join(_CHUNK_COLUMNS)
_CHUNK_VALUES_PLACEHOLDER = ", ".join(["%s"] * len(_CHUNK_COLUMNS))


def _document_params(entry: BufferedIngestion) -> tuple:
    document = entry.document
    return (
        document.document_id,
        document.space_id,
        document.tenant_id,
        document.title,
        document.doc_number,
        document.issued_date,
        document.issued_date_source.value,
        document.effective_date,
        document.effective_date_source.value,
        document.ingested_at,
        document.source_format,
        document.content_fingerprint,
        document.extracted_text,
        document.version_chain_id,
        document.version_ordinal,
        document.version_declared_by.value if document.version_declared_by is not None else None,
        list(document.category_labels),
        list(document.subject_entities),
        entry.buffered_at,
    )


def _chunk_params(chunk: Chunk, *, ordinal: int) -> tuple:
    return (
        chunk.chunk_id,
        chunk.document_id,
        chunk.space_id,
        chunk.tenant_id,
        list(chunk.structure_path),
        chunk.span_start,
        chunk.span_end,
        chunk.parent_chunk_id,
        list(chunk.category_labels),
        ordinal,
    )


def _row_to_document(row: tuple) -> Document:
    (
        document_id,
        space_id,
        tenant_id,
        title,
        doc_number,
        issued_date,
        issued_date_source,
        effective_date,
        effective_date_source,
        ingested_at,
        source_format,
        content_fingerprint,
        extracted_text,
        version_chain_id,
        version_ordinal,
        version_declared_by,
        category_labels,
        subject_entities,
    ) = row
    return Document(
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        title=title,
        doc_number=doc_number,
        issued_date=issued_date,
        issued_date_source=DateSource(issued_date_source),
        effective_date=effective_date,
        effective_date_source=DateSource(effective_date_source),
        ingested_at=_to_naive(ingested_at),
        source_format=source_format,
        content_fingerprint=content_fingerprint,
        extracted_text=extracted_text,
        version_chain_id=version_chain_id,
        version_ordinal=version_ordinal,
        version_declared_by=(
            VersionDeclaredBy(version_declared_by) if version_declared_by is not None else None
        ),
        category_labels=list(category_labels) if category_labels is not None else [],
        subject_entities=list(subject_entities) if subject_entities is not None else [],
        # No column here holds these — GĐ7 has not run for a buffered entry —
        # so `Document`'s own defaults are the honest answer (module docstring
        # of `pre_approval_buffer.py`).
    )


def _row_to_chunk(row: tuple) -> Chunk:
    (
        chunk_id,
        document_id,
        space_id,
        tenant_id,
        structure_path,
        span_start,
        span_end,
        parent_chunk_id,
        category_labels,
    ) = row
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        structure_path=list(structure_path) if structure_path is not None else [],
        span_start=span_start,
        span_end=span_end,
        # The pre-approval chunk table has no vector column, by design (06
        # Mục 5.2 GĐ1) — GĐ6 has not run for anything in this buffer.
        embedding=[],
        parent_chunk_id=parent_chunk_id,
        category_labels=list(category_labels) if category_labels is not None else [],
    )


class PgPreApprovalBuffer:
    """`PreApprovalBuffer` backed by the two real tables
    (`ingestion_pre_approval_document`, `ingestion_pre_approval_chunk`) —
    still NOT the official profile store (CLAUDE.md điều cấm #20), just no
    longer lost on restart.
    """

    def __init__(self, connection: PgConnectionLike) -> None:
        self._conn = connection

    def put(self, entry: BufferedIngestion) -> None:
        """Validate everything in Python BEFORE touching the database, same
        order the in-memory store uses, then write the document row and
        every chunk row inside ONE transaction — `put` is the transaction
        boundary (`pre_approval_buffer.py` docstring)."""
        document_id = entry.document.document_id

        for chunk in entry.chunks:
            if chunk.embedding:
                raise EmbeddedChunkInPreApprovalBufferError(
                    f"chunk {chunk.chunk_id!r} of document {document_id!r} carries a "
                    f"{len(chunk.embedding)}-dimension embedding; the pre-approval chain "
                    f"stops before GĐ6 and table {PRE_APPROVAL_CHUNK_TABLE!r} has no "
                    f"column to hold a vector (06 Mục 5.2 GĐ1)"
                )
            if chunk.document_id != document_id:
                raise ChunkDocumentMismatchError(
                    f"chunk {chunk.chunk_id!r} belongs to document "
                    f"{chunk.document_id!r}, not to {document_id!r}"
                )

        with self._conn.transaction():
            clash_row = self._conn.execute(
                f"SELECT document_id FROM {PRE_APPROVAL_DOCUMENT_TABLE} "
                f"WHERE space_id = %s AND content_fingerprint = %s",
                (entry.document.space_id, entry.document.content_fingerprint),
            ).fetchone()
            if clash_row is not None and clash_row[0] != document_id:
                raise DuplicatePreApprovalEntryError(
                    f"document {clash_row[0]!r} is already buffered for space "
                    f"{entry.document.space_id!r} with the same content_fingerprint; "
                    f"UNIQUE (space_id, content_fingerprint) on "
                    f"{PRE_APPROVAL_DOCUMENT_TABLE!r} refuses the second one"
                )

            self._conn.execute(
                f"""
                INSERT INTO {PRE_APPROVAL_DOCUMENT_TABLE} ({_DOCUMENT_SELECT_LIST})
                VALUES ({_DOCUMENT_VALUES_PLACEHOLDER})
                ON CONFLICT (document_id) DO UPDATE SET {_DOCUMENT_UPSERT_SET}
                """,
                _document_params(entry),
            )

            # Full replace, same as the in-memory store's dict assignment: a
            # re-`put` of one document_id carries the chunk list it carries
            # now, not a merge with what was there before.
            self._conn.execute(
                f"DELETE FROM {PRE_APPROVAL_CHUNK_TABLE} WHERE document_id = %s",
                (document_id,),
            )
            for ordinal, chunk in enumerate(entry.chunks):
                self._conn.execute(
                    f"""
                    INSERT INTO {PRE_APPROVAL_CHUNK_TABLE} ({_CHUNK_SELECT_LIST})
                    VALUES ({_CHUNK_VALUES_PLACEHOLDER})
                    """,
                    _chunk_params(chunk, ordinal=ordinal),
                )

    def get(self, document_id: str) -> BufferedIngestion | None:
        doc_row = self._conn.execute(
            f"SELECT {_DOCUMENT_SELECT_LIST} FROM {PRE_APPROVAL_DOCUMENT_TABLE} "
            f"WHERE document_id = %s",
            (document_id,),
        ).fetchone()
        if doc_row is None:
            return None
        *document_fields, buffered_at = doc_row
        document = _row_to_document(tuple(document_fields))

        chunk_rows = self._conn.execute(
            f"""
            SELECT {", ".join(c for c in _CHUNK_COLUMNS if c != "chunk_ordinal")}
            FROM {PRE_APPROVAL_CHUNK_TABLE}
            WHERE document_id = %s
            ORDER BY chunk_ordinal
            """,
            (document_id,),
        ).fetchall()
        chunks = [_row_to_chunk(row) for row in chunk_rows]

        return BufferedIngestion(document=document, buffered_at=_to_naive(buffered_at), chunks=chunks)

    def find_in_space_by_fingerprint(
        self, *, space_id: str, content_fingerprint: str
    ) -> BufferedIngestion | None:
        row = self._conn.execute(
            f"SELECT document_id FROM {PRE_APPROVAL_DOCUMENT_TABLE} "
            f"WHERE space_id = %s AND content_fingerprint = %s",
            (space_id, content_fingerprint),
        ).fetchone()
        return self.get(row[0]) if row is not None else None

    def list_in_space(self, space_id: str) -> list[BufferedIngestion]:
        rows = self._conn.execute(
            f"SELECT document_id FROM {PRE_APPROVAL_DOCUMENT_TABLE} WHERE space_id = %s",
            (space_id,),
        ).fetchall()
        return [self.get(row[0]) for row in rows]

    def discard(self, document_id: str) -> bool:
        """Drop an entry. Chunk rows follow via `ON DELETE CASCADE` — no
        second statement needed."""
        cursor = self._conn.execute(
            f"DELETE FROM {PRE_APPROVAL_DOCUMENT_TABLE} WHERE document_id = %s",
            (document_id,),
        )
        return cursor.rowcount > 0
