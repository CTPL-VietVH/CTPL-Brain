"""PostgreSQL implementations of the write/delete-path Protocols (KHO-PG-A):
`promotion.SharedProfileStore`, `deletion.DeletableProfileStore`,
`deletion.DeletionLog`, `deletion.BackgroundCleanup`, `intake.FingerprintIndex`
and `relations_scan.SpaceDocumentSource`.

Every InMemory stand-in these Protocols already have (`InMemorySharedProfileStore`
in `promotion.py`, `InMemoryDeletableProfileStore`/`InMemoryDeletionLog`/
`InMemoryBackgroundCleanup` in `deletion.py`, `InMemoryFingerprintIndex` in
`intake.py`) enforces every constraint `schema/store_schema.py` declares by
hand, in a dict. This module makes PostgreSQL enforce the SAME constraints for
real, and translates its refusals back into the SAME exception classes the
InMemory stores already raise — so a caller (or a test) written against the
Protocol cannot tell which one it is talking to, except that this one survives
a restart.

──────────────────────────────────────────────────────────────────────────
One class carries four Protocols, on purpose
──────────────────────────────────────────────────────────────────────────

`PgDocumentStore` implements `SharedProfileStore`, `DeletableProfileStore`,
`FingerprintIndex` and `SpaceDocumentSource` together, exactly the way
`InMemorySharedProfileStore`'s own docstring explains: *"not a convenience: in
a real deployment those readers ARE the same `document` table, and modelling
them as separate objects in tests would hide the fact that a promote makes a
document visible to all of them at once."* One PostgreSQL table backs all
four reads here for the identical reason.

──────────────────────────────────────────────────────────────────────────
Why this module imports `psycopg` directly, unlike `schema/embedding_registry.py`
──────────────────────────────────────────────────────────────────────────

`embedding_registry.py` lives in `packages/schema/` — the module BOTH services
import — so it duck-types its connection parameter (`PgConnectionLike`) rather
than force a specific driver on a shared contract layer. This module lives in
`packages/ingestion/`, which already depends on `psycopg` elsewhere in the
codebase (`space_registry.py`, `pre_approval_buffer.py`), and needs real
transaction control (`Connection.transaction()`) that a two-method duck type
cannot express. Importing `psycopg` here is not the second home of a decision
the schema layer already made once — it is a service-local choice about how
Ingestion talks to its own store.

──────────────────────────────────────────────────────────────────────────
Column names come from the dataclasses, never typed twice
──────────────────────────────────────────────────────────────────────────

CLAUDE.md Mục 6: field names are defined exactly once, in `packages/schema/`,
and nothing else re-declares them. `_DOCUMENT_FIELDS` / `_RELATION_FIELDS` /
`_DELETION_LOG_FIELDS` below are read off `dataclasses.fields(...)` rather
than typed out, the same technique `store_schema.CHUNK_PAYLOAD_FIELDS` already
uses for `Chunk`. A handful of individual column names ARE referenced by name
in `WHERE`/`ON CONFLICT` clauses (`document_id`, `space_id`, ...); each of
those is looked up exactly once via `<Dataclass>.__dataclass_fields__[name]`
— the same guarded idiom `store_schema.CHUNK_DOCUMENT_ID_FIELD` already uses —
so a rename raises `KeyError` here instead of silently matching nothing.

──────────────────────────────────────────────────────────────────────────
The transaction boundary — matches 07 Mục 2 dòng 65, one Postgres database
──────────────────────────────────────────────────────────────────────────

`write_document_and_relations` and `delete_document_and_relations` each wrap
their whole body in `with self._connection.transaction():`. Under an
autocommit connection this opens a real `BEGIN`/`COMMIT`; under a connection
already inside a transaction (the per-test fixture pattern this module's own
tests use, so a test can `ROLLBACK` everything it did) `psycopg` opens a
`SAVEPOINT` instead — both are "one transaction" in the sense 07 Mục 2 means:
every statement inside commits together, or none of them do. An exception
raised anywhere inside the block rolls the whole thing back before it reaches
the `except` clause that translates it, so a refused write leaves the store
exactly as it was — the same guarantee the InMemory stores document ("A
refusal must leave the store untouched, which a check-as-you-write loop would
quietly lose").

Write order inside the transaction is fixed: the `document` row first, THEN
every `relation` row — because each relation carries a foreign key to
`document`, the same order `SharedProfileStore`'s own docstring requires.

──────────────────────────────────────────────────────────────────────────
Constraint violations, translated, not re-derived
──────────────────────────────────────────────────────────────────────────

Three PostgreSQL refusals map onto the three errors `InMemorySharedProfileStore`
already raises for the identical situations — nobody has to remember what a
`UniqueViolation` on `document_version_chain_ordinal_unique` MEANS twice:

* `document_version_chain_ordinal_unique` violated → `VersionChainOrdinalConflictError`
* `document_space_fingerprint_active_unique` violated → `DuplicateActiveFingerprintError`
* a relation's `from_document_id`/`to_document_id` foreign key violated →
  `UnknownRelationEndpointError`

Every other database error is re-raised unchanged — this module does not
swallow anything it does not have a name for.

⭐ **The "a machine rescan never un-decides a relation" rule (07 Mục 2.3,
`promotion.InMemorySharedProfileStore.write_document_and_relations`) is
enforced by ONE upsert, not a read-then-branch.** `ON CONFLICT ON CONSTRAINT
relation_pair_type_unique DO UPDATE SET ... WHERE relation.approval_state =
'pending'` replaces the existing row only when it is still PENDING; an
APPROVED or REJECTED row is left untouched by the very shape of the
statement, with no separate `SELECT` that could race against a concurrent
write.

──────────────────────────────────────────────────────────────────────────
`PgBackgroundCleanup` holds no PostgreSQL state — by design, not oversight
──────────────────────────────────────────────────────────────────────────

`deletion.BackgroundCleanup.purge()` stands in for step 3 of S6, *"dọn nền"*
— the moment the vector store's bytes are actually reclaimed, as opposed to
merely marked gone. But `deletion.QdrantVectorStoreDeleter.delete_document_points`
(step 1, already built) deletes with `wait=True`, and its own docstring
states why: that flag is *"what makes this call return only AFTER the delete
has applied across the collection"* — there is no further reclaim to wait for
by the time step 1 returns. Nothing in 06/07 defines a durable row for
"cleanup in progress" (no such table exists, and this work order may not add
one — DDL changes are KHO-PG-B's territory), so there is no state to persist:
`PgBackgroundCleanup` behaves byte-for-byte like `InMemoryBackgroundCleanup`,
which is the honest shape of "the same Protocol, backed by nothing, because
its real backing already discharged the obligation one step earlier."
Flagged in the T2.8/KHO-PG-A report for PO to confirm or correct.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from enum import Enum
from typing import Any

import psycopg

# The three write-path errors this module raises are the SAME classes
# `InMemorySharedProfileStore` raises — imported, never re-declared, so a
# caller written against one store's exceptions works against the other
# unchanged.
from ingestion.promotion import (
    DuplicateActiveFingerprintError,
    UnknownRelationEndpointError,
    VersionChainOrdinalConflictError,
)
from ingestion.deletion import ProfileDeletionCounts
from schema.deletion_log import DeletionLogEntry
from schema.document import DateSource, Document, RelationsScanState, VersionDeclaredBy
from schema.relation import ApprovalState, Relation, RelationOrigin, RelationType
from schema.store_schema import (
    DELETION_LOG_TABLE,
    DOCUMENT_ACTIVE_FINGERPRINT_INDEX,
    DOCUMENT_TABLE,
    DOCUMENT_VERSION_CHAIN_ORDINAL_CONSTRAINT,
    RELATION_FROM_DOCUMENT_FK,
    RELATION_PAIR_TYPE_CONSTRAINT,
    RELATION_TABLE,
    RELATION_TO_DOCUMENT_FK,
)

__all__ = [
    "PgBackgroundCleanup",
    "PgDeletionLog",
    "PgDocumentStore",
]


# --------------------------------------------------------------------------- #
# Column names — read off the dataclasses, never typed out (CLAUDE.md Mục 6)
# --------------------------------------------------------------------------- #

_DOCUMENT_FIELDS: tuple[str, ...] = tuple(f.name for f in dataclasses.fields(Document))
_RELATION_FIELDS: tuple[str, ...] = tuple(f.name for f in dataclasses.fields(Relation))
_DELETION_LOG_FIELDS: tuple[str, ...] = tuple(f.name for f in dataclasses.fields(DeletionLogEntry))

# Individual columns referenced BY NAME in WHERE/ON CONFLICT clauses below —
# each looked up once, guarded, same idiom as `store_schema.CHUNK_DOCUMENT_ID_FIELD`.
_DOC_ID = Document.__dataclass_fields__["document_id"].name
_DOC_SPACE_ID = Document.__dataclass_fields__["space_id"].name
_DOC_VERSION_CHAIN_ID = Document.__dataclass_fields__["version_chain_id"].name
_DOC_VERSION_ORDINAL = Document.__dataclass_fields__["version_ordinal"].name
_DOC_CONTENT_FINGERPRINT = Document.__dataclass_fields__["content_fingerprint"].name

_REL_FROM = Relation.__dataclass_fields__["from_document_id"].name
_REL_TO = Relation.__dataclass_fields__["to_document_id"].name
_REL_APPROVAL_STATE = Relation.__dataclass_fields__["approval_state"].name

_LOG_DOC_ID = DeletionLogEntry.__dataclass_fields__["document_id"].name
_LOG_SPACE_ID = DeletionLogEntry.__dataclass_fields__["space_id"].name
_LOG_PURGE_COMPLETED_AT = DeletionLogEntry.__dataclass_fields__["purge_completed_at"].name

# Fields that hold an Enum value in Python but `text` in PostgreSQL — dumped
# via `.value` on write, wrapped via the Enum constructor on read.
_DOCUMENT_ENUM_FIELDS: dict[str, type[Enum]] = {
    "issued_date_source": DateSource,
    "effective_date_source": DateSource,
    "version_declared_by": VersionDeclaredBy,
    "relations_scan_state": RelationsScanState,
}
_RELATION_ENUM_FIELDS: dict[str, type[Enum]] = {
    "relation_type": RelationType,
    "origin": RelationOrigin,
    "approval_state": ApprovalState,
}
_NO_ENUM_FIELDS: dict[str, type[Enum]] = {}


def _dump(instance: Any, field_names: tuple[str, ...], enum_fields: dict[str, type[Enum]]) -> tuple:
    values = []
    for name in field_names:
        value = getattr(instance, name)
        if value is not None and name in enum_fields:
            value = value.value
        values.append(value)
    return tuple(values)


def _load(cls: type, field_names: tuple[str, ...], enum_fields: dict[str, type[Enum]], row: tuple) -> Any:
    kwargs: dict[str, Any] = {}
    for name, raw in zip(field_names, row):
        if raw is not None and name in enum_fields:
            raw = enum_fields[name](raw)
        kwargs[name] = raw
    return cls(**kwargs)


# --------------------------------------------------------------------------- #
# PostgreSQL error translation — SQLSTATE + constraint name, no driver-specific
# exception classes imported (same technique `embedding_registry.py` uses).
# --------------------------------------------------------------------------- #

_UNIQUE_VIOLATION_SQLSTATE = "23505"
_FOREIGN_KEY_VIOLATION_SQLSTATE = "23503"


def _sqlstate(exc: BaseException) -> str | None:
    return getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)


def _constraint_name(exc: BaseException) -> str | None:
    diag = getattr(exc, "diag", None)
    return getattr(diag, "constraint_name", None) if diag is not None else None


def _looks_like_foreign_key_violation(exc: BaseException) -> bool:
    if _sqlstate(exc) == _FOREIGN_KEY_VIOLATION_SQLSTATE:
        return True
    return "ForeignKeyViolation" in type(exc).__name__


def _translate_write_error(exc: BaseException, *, document: Document) -> Exception | None:
    """Returns the exception to raise instead of `exc`, or `None` if `exc` is
    not one of the three refusals this module knows how to name."""
    if _sqlstate(exc) == _UNIQUE_VIOLATION_SQLSTATE:
        constraint = _constraint_name(exc)
        if constraint == DOCUMENT_VERSION_CHAIN_ORDINAL_CONSTRAINT:
            return VersionChainOrdinalConflictError(
                f"document {document.document_id!r} could not take ordinal "
                f"{document.version_ordinal} of chain {document.version_chain_id!r} — "
                f"{DOCUMENT_VERSION_CHAIN_ORDINAL_CONSTRAINT} refuses the second one"
            )
        if constraint == DOCUMENT_ACTIVE_FINGERPRINT_INDEX:
            return DuplicateActiveFingerprintError(
                f"an active document already holds content_fingerprint "
                f"{document.content_fingerprint!r} in space {document.space_id!r} — "
                f"{DOCUMENT_ACTIVE_FINGERPRINT_INDEX} refuses the second one"
            )
    if _looks_like_foreign_key_violation(exc):
        return UnknownRelationEndpointError(
            f"a relation for document {document.document_id!r} points at a document "
            f"that is not in the store ({RELATION_FROM_DOCUMENT_FK} / "
            f"{RELATION_TO_DOCUMENT_FK} are declared in schema/store_schema.py)"
        )
    return None


# --------------------------------------------------------------------------- #
# SQL — built once, from the field-name tuples above, never re-typed per call
# --------------------------------------------------------------------------- #

_DOCUMENT_COLUMNS_SQL = ", ".join(_DOCUMENT_FIELDS)
_DOCUMENT_UPSERT_SQL = f"""
INSERT INTO {DOCUMENT_TABLE} ({_DOCUMENT_COLUMNS_SQL})
VALUES ({", ".join(["%s"] * len(_DOCUMENT_FIELDS))})
ON CONFLICT ({_DOC_ID}) DO UPDATE SET
    {", ".join(f"{name} = EXCLUDED.{name}" for name in _DOCUMENT_FIELDS if name != _DOC_ID)}
"""
_DOCUMENT_SELECT_SQL = f"SELECT {_DOCUMENT_COLUMNS_SQL} FROM {DOCUMENT_TABLE}"

_RELATION_COLUMNS_SQL = ", ".join(_RELATION_FIELDS)
# The "never un-decide" rule, as one statement: the row is replaced ONLY when
# the WHERE clause sees it still PENDING at the moment of conflict.
_RELATION_UPSERT_SQL = f"""
INSERT INTO {RELATION_TABLE} ({_RELATION_COLUMNS_SQL})
VALUES ({", ".join(["%s"] * len(_RELATION_FIELDS))})
ON CONFLICT ON CONSTRAINT {RELATION_PAIR_TYPE_CONSTRAINT} DO UPDATE SET
    {", ".join(f"{name} = EXCLUDED.{name}" for name in _RELATION_FIELDS)}
WHERE {RELATION_TABLE}.{_REL_APPROVAL_STATE} = %s
"""
_RELATION_SELECT_SQL = f"SELECT {_RELATION_COLUMNS_SQL} FROM {RELATION_TABLE}"

_DELETION_LOG_COLUMNS_SQL = ", ".join(_DELETION_LOG_FIELDS)
_DELETION_LOG_INSERT_IF_ABSENT_SQL = f"""
INSERT INTO {DELETION_LOG_TABLE} ({_DELETION_LOG_COLUMNS_SQL})
VALUES ({", ".join(["%s"] * len(_DELETION_LOG_FIELDS))})
ON CONFLICT ({_LOG_DOC_ID}) DO NOTHING
"""
_DELETION_LOG_SELECT_SQL = f"SELECT {_DELETION_LOG_COLUMNS_SQL} FROM {DELETION_LOG_TABLE}"


# --------------------------------------------------------------------------- #
# PgDocumentStore — SharedProfileStore + DeletableProfileStore +
# FingerprintIndex + SpaceDocumentSource, all four, one `document` table.
# --------------------------------------------------------------------------- #


class PgDocumentStore:
    """The `document` + `relation` tables, live.

    Behaves exactly like `promotion.InMemorySharedProfileStore` composed with
    `deletion.InMemoryDeletableProfileStore` — same methods, same exceptions,
    same "never un-decide a PENDING relation" rule — except every write
    survives a process restart, because it never lived in a Python dict.
    """

    def __init__(self, *, connection: psycopg.Connection) -> None:
        self._connection = connection

    # -- SharedProfileStore (promotion.py) ------------------------------- #

    def get_document(self, document_id: str) -> Document | None:
        row = self._connection.execute(
            f"{_DOCUMENT_SELECT_SQL} WHERE {_DOC_ID} = %s", (document_id,)
        ).fetchone()
        return _load(Document, _DOCUMENT_FIELDS, _DOCUMENT_ENUM_FIELDS, row) if row is not None else None

    def max_version_ordinal_in_chain(self, version_chain_id: str) -> int | None:
        row = self._connection.execute(
            f"SELECT MAX({_DOC_VERSION_ORDINAL}) FROM {DOCUMENT_TABLE} WHERE {_DOC_VERSION_CHAIN_ID} = %s",
            (version_chain_id,),
        ).fetchone()
        return row[0] if row is not None else None

    def write_document_and_relations(self, *, document: Document, relations: list[Relation]) -> None:
        """The transaction boundary — see the module docstring for the full
        argument. Document row first (relations carry a FK to it), then every
        relation, all inside one `with self._connection.transaction():`
        block: any refusal rolls back everything this call attempted."""
        try:
            with self._connection.transaction():
                self._connection.execute(
                    _DOCUMENT_UPSERT_SQL, _dump(document, _DOCUMENT_FIELDS, _DOCUMENT_ENUM_FIELDS)
                )
                for relation in relations:
                    params = _dump(relation, _RELATION_FIELDS, _RELATION_ENUM_FIELDS) + (
                        ApprovalState.PENDING.value,
                    )
                    self._connection.execute(_RELATION_UPSERT_SQL, params)
        except Exception as exc:
            translated = _translate_write_error(exc, document=document)
            if translated is not None:
                raise translated from exc
            raise

    # -- DeletableProfileStore (deletion.py) ------------------------------ #

    def delete_document_and_relations(self, document_id: str) -> ProfileDeletionCounts:
        """The transaction boundary for S6 step 2 — relations counted, then
        the document row removed; the two `ON DELETE CASCADE` foreign keys
        declared in `schema/store_schema.py` remove every relation touching
        this document (either direction) as part of the SAME `DELETE`
        statement, inside the SAME transaction. Idempotent: a document
        already gone deletes zero rows, not an error."""
        with self._connection.transaction():
            count_row = self._connection.execute(
                f"SELECT COUNT(*) FROM {RELATION_TABLE} WHERE {_REL_FROM} = %s OR {_REL_TO} = %s",
                (document_id, document_id),
            ).fetchone()
            relations_deleted = count_row[0] if count_row is not None else 0

            delete_cursor = self._connection.execute(
                f"DELETE FROM {DOCUMENT_TABLE} WHERE {_DOC_ID} = %s", (document_id,)
            )
            profile_rows_deleted = delete_cursor.rowcount

        return ProfileDeletionCounts(
            relations_deleted=relations_deleted, profile_rows_deleted=profile_rows_deleted
        )

    # -- FingerprintIndex (intake.py) ------------------------------------- #

    def find_by_fingerprint(self, content_fingerprint: str) -> list[Document]:
        rows = self._connection.execute(
            f"{_DOCUMENT_SELECT_SQL} WHERE {_DOC_CONTENT_FINGERPRINT} = %s", (content_fingerprint,)
        ).fetchall()
        return [_load(Document, _DOCUMENT_FIELDS, _DOCUMENT_ENUM_FIELDS, row) for row in rows]

    def register(self, document: Document) -> None:
        self.write_document_and_relations(document=document, relations=[])

    # -- SpaceDocumentSource (relations_scan.py) --------------------------- #

    def documents_in(self, space_ids: frozenset[str]) -> list[Document]:
        if not space_ids:
            return []
        rows = self._connection.execute(
            f"{_DOCUMENT_SELECT_SQL} WHERE {_DOC_SPACE_ID} = ANY(%s)", (list(space_ids),)
        ).fetchall()
        return [_load(Document, _DOCUMENT_FIELDS, _DOCUMENT_ENUM_FIELDS, row) for row in rows]

    # -- Inspection, mirroring InMemorySharedProfileStore.documents()/relations() -- #

    def documents(self) -> list[Document]:
        rows = self._connection.execute(_DOCUMENT_SELECT_SQL).fetchall()
        return [_load(Document, _DOCUMENT_FIELDS, _DOCUMENT_ENUM_FIELDS, row) for row in rows]

    def relations(self) -> list[Relation]:
        rows = self._connection.execute(_RELATION_SELECT_SQL).fetchall()
        return [_load(Relation, _RELATION_FIELDS, _RELATION_ENUM_FIELDS, row) for row in rows]


# --------------------------------------------------------------------------- #
# PgDeletionLog — deletion_log, live
# --------------------------------------------------------------------------- #


class PgDeletionLog:
    """`deletion.DeletionLog` over the real `deletion_log` table."""

    def __init__(self, *, connection: psycopg.Connection) -> None:
        self._connection = connection

    def get(self, document_id: str) -> DeletionLogEntry | None:
        row = self._connection.execute(
            f"{_DELETION_LOG_SELECT_SQL} WHERE {_LOG_DOC_ID} = %s", (document_id,)
        ).fetchone()
        return _load(DeletionLogEntry, _DELETION_LOG_FIELDS, _NO_ENUM_FIELDS, row) if row is not None else None

    def record_started(self, entry: DeletionLogEntry) -> DeletionLogEntry:
        """INSERT-IF-ABSENT via `ON CONFLICT (document_id) DO NOTHING` — a
        retry meets the first row and leaves it alone, the same
        "first line names who ordered the deletion" guarantee
        `InMemoryDeletionLog` documents."""
        self._connection.execute(
            _DELETION_LOG_INSERT_IF_ABSENT_SQL, _dump(entry, _DELETION_LOG_FIELDS, _NO_ENUM_FIELDS)
        )
        stored = self.get(entry.document_id)
        assert stored is not None, "just inserted or already present — never absent here"
        return stored

    def mark_purged(self, document_id: str, *, at: datetime) -> DeletionLogEntry:
        """Closes the line only if it is still open — a second call after the
        line is already closed is a no-op UPDATE, so the first completion
        time stands, matching `InMemoryDeletionLog`."""
        self._connection.execute(
            f"UPDATE {DELETION_LOG_TABLE} SET {_LOG_PURGE_COMPLETED_AT} = %s "
            f"WHERE {_LOG_DOC_ID} = %s AND {_LOG_PURGE_COMPLETED_AT} IS NULL",
            (at, document_id),
        )
        stored = self.get(document_id)
        assert stored is not None, "mark_purged is only ever called after record_started"
        return stored

    def open_entries_for_space(self, space_id: str) -> list[DeletionLogEntry]:
        rows = self._connection.execute(
            f"{_DELETION_LOG_SELECT_SQL} WHERE {_LOG_SPACE_ID} = %s AND {_LOG_PURGE_COMPLETED_AT} IS NULL",
            (space_id,),
        ).fetchall()
        return [_load(DeletionLogEntry, _DELETION_LOG_FIELDS, _NO_ENUM_FIELDS, row) for row in rows]

    # -- Inspection, mirroring InMemoryDeletionLog.entries() -------------- #

    def entries(self) -> list[DeletionLogEntry]:
        rows = self._connection.execute(_DELETION_LOG_SELECT_SQL).fetchall()
        return [_load(DeletionLogEntry, _DELETION_LOG_FIELDS, _NO_ENUM_FIELDS, row) for row in rows]


# --------------------------------------------------------------------------- #
# PgBackgroundCleanup — see the module docstring for why this holds no
# PostgreSQL state at all.
# --------------------------------------------------------------------------- #


class PgBackgroundCleanup:
    """`deletion.BackgroundCleanup` — behaviourally identical to
    `InMemoryBackgroundCleanup`. No connection, no table: see the module
    docstring's "`PgBackgroundCleanup` holds no PostgreSQL state" section for
    why v1's own design (`QdrantVectorStoreDeleter`'s `wait=True`) leaves
    nothing here to persist.
    """

    def __init__(self, *, settles: bool = True) -> None:
        self._settles = settles
        self.calls: list[str] = []

    def purge(self, document_id: str) -> bool:
        self.calls.append(document_id)
        return self._settles
