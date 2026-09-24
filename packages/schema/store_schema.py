"""Persistent shape of the three shared entities (07 Mục 2, 08 T2.7), plus the
Ingestion-owned tables that were added to PostgreSQL after them:
`deletion_log` (06 Mục 5.6), `space_registry` and `ingestion_record` (docs/10
§4.0, §4.1 — listed in 07 Mục 4 as living outside the shared contract).

Table names, column names and DDL for the OFFICIAL stores — the first time
this project writes any of them down. Exported as constants for the same
reason `embedding_registry.py` does it: real code and tests must share one
spelling, and a test that re-types the SQL it checks is checking itself.

This lives in `packages/schema/` and not in either service because both read
these tables: Ingestion writes a profile, Retrieval reads it to build the
reading unit and the citation (07 Mục 2.1), and both touch the relation
layer. CLAUDE.md Mục 6 — *"Tên trường định nghĩa đúng một lần trong
`packages/schema/`; không service nào tự khai báo lại"* — so a table name
spelled in `packages/retrieval/` would be the second spelling that rule
exists to prevent.

──────────────────────────────────────────────────────────────────────────
Two tables, not three — `chunk` has no row anywhere
──────────────────────────────────────────────────────────────────────────

07 Mục 2.2 assigns `Chunk` a home: *"Nơi cư trú: kho vector (Qdrant)."* A
chunk IS a Qdrant point — `chunk_id` is the point id, `embedding` is the
vector, every remaining field is the payload, and
`ingestion.vectorization._payload_tu_chunk` already builds exactly that from
`dataclasses.asdict`. A `chunk` table in PostgreSQL beside it would be a
second copy of the same facts, free to drift from the first — the reasoning
of điều cấm #3, which keeps chunk text in exactly one place for exactly this
reason. `CHUNK_PAYLOAD_FIELDS` below pins the Qdrant-side coverage instead,
and `tests/t2_7_promote/` asserts it against `schema.chunk.Chunk`.

──────────────────────────────────────────────────────────────────────────
The two UNIQUE constraints owed since 21/9/2026
──────────────────────────────────────────────────────────────────────────

08 dòng 210 (PO, gộp T2.1-E2 + audit #2) asks for both AT THE STORAGE LAYER,
*"không chỉ kiểm tra ở tầng ứng dụng"* — an application check loses the race
when two writers act at once, which is the whole point of the escalation that
produced it. Neither had a home until this module.

1. `(version_chain_id, version_ordinal)` — a plain table constraint. Two
   people both declaring "bản mới của v1" both compute ordinal 2; one of the
   two INSERTs must fail rather than both succeed (T2.1-E2).

2. `(space_id, content_fingerprint)` — a PARTIAL unique index, `WHERE NOT
   removed_as_wrong`. It cannot be a plain constraint: `intake.decide_intake`
   deliberately lets a new document be created in a Space that already holds
   a `removed_as_wrong` twin, because *"removed_as_wrong là nguyên tắc 'coi
   như không tồn tại' xuyên suốt module này"* (PO chốt Phương án A, 21/9).
   A plain UNIQUE would refuse that legitimate re-upload; the partial index
   matches T2.1's actual behaviour exactly.
"""

from __future__ import annotations

import dataclasses

from .chunk import Chunk

__all__ = [
    "CHUNK_DOCUMENT_ID_FIELD",
    "CHUNK_PAYLOAD_FIELDS",
    "DELETION_LOG_INDEXES_DDL",
    "DELETION_LOG_TABLE",
    "DELETION_LOG_TABLE_DDL",
    "DOCUMENT_ACTIVE_FINGERPRINT_INDEX",
    "DOCUMENT_VERSION_CHAIN_ORDINAL_CONSTRAINT",
    "DOCUMENT_INDEXES_DDL",
    "DOCUMENT_TABLE",
    "DOCUMENT_TABLE_DDL",
    "INGESTION_RECORD_INDEXES_DDL",
    "INGESTION_RECORD_TABLE",
    "INGESTION_RECORD_TABLE_DDL",
    "RELATION_FROM_DOCUMENT_FK",
    "RELATION_INDEXES_DDL",
    "RELATION_PAIR_TYPE_CONSTRAINT",
    "RELATION_TABLE",
    "RELATION_TABLE_DDL",
    "RELATION_TO_DOCUMENT_FK",
    "SHARED_STORE_DDL",
    "SPACE_REGISTRY_TABLE",
    "SPACE_REGISTRY_TABLE_DDL",
]


#: Hồ sơ tài liệu (07 Mục 2.1). Retrieval reads it AFTER the search, to build
#: the reading unit and the citation — never to filter candidates (QT2).
DOCUMENT_TABLE = "document"

#: Lớp quan hệ (07 Mục 2.3). "Kho đồ thị" is a LOGICAL name; physically it is
#: this table, in the same database as `document` — which is what lets S6
#: delete both in one atomic transaction (07 Mục 2, dòng 65).
RELATION_TABLE = "relation"

#: The permanent-deletion log (06 Mục 5.6). Keeps the EVENT, never the
#: content: *"Nhật ký giữ lại: Việc đã xoá: ai, khi nào, tài liệu nào, lý
#: do. Không giữ nội dung"* (06 Mục 5.6).
#: ⚠️ NO foreign key to `document`, deliberately: this row must OUTLIVE the
#: document it describes, and a cascading FK would delete the very record
#: the deletion exists to leave behind.
DELETION_LOG_TABLE = "deletion_log"

#: The Space register (docs/10 §2, §4.0; T2.11). ⛔ TWO columns, and the
#: second one is a state — *"**Chỉ sự tồn tại** — không cây, không cờ, không
#: thành viên"* (docs/10 §2). A `parent_space_id` or an
#: `inherits_from_parent` column here would be the frozen copy of a live flag
#: that NT3 forbids and that `schema/space_registry.py` explains at length.
SPACE_REGISTRY_TABLE = "space_registry"

#: One row per `POST /v1/ingestions` (docs/10 §4.1, §4.2) — and the work queue
#: the single background worker reads. ⛔ FOUR things this table may never
#: carry, each for its own reason: the presigned `url`, any permission signal
#: of the caller, `space_is_private`, and document content. The full argument
#: is in `schema/ingestion_record.py`; read it before adding a column.
INGESTION_RECORD_TABLE = "ingestion_record"


# Constraint names, exported for the same reason the table names are: an error
# message in `packages/ingestion/` that re-types one of these is the second
# spelling CLAUDE.md Mục 6 exists to prevent — and a foreign key left unnamed
# gets whatever PostgreSQL generates, which is a convention, not a contract.
DOCUMENT_VERSION_CHAIN_ORDINAL_CONSTRAINT = "document_version_chain_ordinal_unique"
DOCUMENT_ACTIVE_FINGERPRINT_INDEX = "document_space_fingerprint_active_unique"
RELATION_PAIR_TYPE_CONSTRAINT = "relation_pair_type_unique"
RELATION_FROM_DOCUMENT_FK = "relation_from_document_id_fkey"
RELATION_TO_DOCUMENT_FK = "relation_to_document_id_fkey"


# Every `Chunk` field except `chunk_id` (the Qdrant point id) and `embedding`
# (the vector itself) travels as Qdrant payload. Derived, never typed out, so
# a field added to `Chunk` cannot be silently left behind.
CHUNK_PAYLOAD_FIELDS = tuple(
    field.name
    for field in dataclasses.fields(Chunk)
    if field.name not in {"chunk_id", "embedding"}
)

# The payload key every document-scoped Qdrant operation filters on (S6 step 1
# deletes by filter, not by point id). Looked up from `Chunk` rather than
# typed out a second time: renaming the field must raise a KeyError here, not
# silently match nothing (CLAUDE.md Mục 6).
CHUNK_DOCUMENT_ID_FIELD = Chunk.__dataclass_fields__["document_id"].name


DOCUMENT_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {DOCUMENT_TABLE} (
    document_id           text        NOT NULL PRIMARY KEY,
    space_id              text        NOT NULL,
    tenant_id             text        NOT NULL,
    title                 text        NOT NULL,
    doc_number            text        NOT NULL,
    issued_date           date        NOT NULL,
    issued_date_source    text        NOT NULL,
    effective_date        date        NOT NULL,
    effective_date_source text        NOT NULL,
    ingested_at           timestamptz NOT NULL,
    source_format         text        NOT NULL,
    content_fingerprint   text        NOT NULL,
    extracted_text        text        NOT NULL,
    version_chain_id      text        NOT NULL,
    version_ordinal       integer     NOT NULL,
    removed_as_wrong      boolean     NOT NULL,
    removed_reason        text,
    removed_by            text,
    removed_at            timestamptz,
    superseded            boolean     NOT NULL,
    superseded_by         text,
    superseded_at         timestamptz,
    category_labels       text[]      NOT NULL,
    labels_confirmed_by   text,
    labels_confirmed_at   timestamptz,
    subject_entities      text[]      NOT NULL,
    version_declared_by   text,
    relations_scan_state  text        NOT NULL,
    CONSTRAINT {DOCUMENT_VERSION_CHAIN_ORDINAL_CONSTRAINT}
        UNIQUE (version_chain_id, version_ordinal)
)
"""

DOCUMENT_INDEXES_DDL = (
    # The (space_id, content_fingerprint) constraint owed since 21/9 — PARTIAL,
    # see the module docstring for why a plain UNIQUE would be wrong.
    f"""
CREATE UNIQUE INDEX IF NOT EXISTS {DOCUMENT_ACTIVE_FINGERPRINT_INDEX}
    ON {DOCUMENT_TABLE} (space_id, content_fingerprint)
    WHERE NOT removed_as_wrong
""",
    # T0.1's operational note, recorded there after measuring: *"Cần đánh chỉ
    # mục trên trường Space và theo dõi khi có người dùng quyền hẹp"* — the
    # Space filter runs on every single query.
    f"""
CREATE INDEX IF NOT EXISTS document_space_idx ON {DOCUMENT_TABLE} (space_id)
""",
    # S7's exclusion list is computed fresh per query from this flag. The list
    # is small by nature, so only the removed rows are worth indexing.
    f"""
CREATE INDEX IF NOT EXISTS document_removed_as_wrong_idx
    ON {DOCUMENT_TABLE} (document_id) WHERE removed_as_wrong
""",
    # Version chains are walked to answer "which is the newest" — there is no
    # `is_latest_version` flag to read instead (điều cấm #11).
    f"""
CREATE INDEX IF NOT EXISTS document_version_chain_idx
    ON {DOCUMENT_TABLE} (version_chain_id, version_ordinal)
""",
    # 07 Mục 7 yêu cầu 1: `content_fingerprint` *"phải đánh chỉ mục để tra
    # ngược từ vân tay ra danh sách tài liệu"*. The partial unique index above
    # cannot serve that lookup: `space_id` leads it, while
    # `FingerprintIndex.find_by_fingerprint` searches on the fingerprint ALONE
    # and across Spaces; and its WHERE clause hides exactly the
    # `removed_as_wrong` rows `intake.decide_intake` still has to see.
    f"""
CREATE INDEX IF NOT EXISTS document_content_fingerprint_idx
    ON {DOCUMENT_TABLE} (content_fingerprint)
""",
)


RELATION_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {RELATION_TABLE} (
    relation_id       text NOT NULL PRIMARY KEY,
    from_document_id  text NOT NULL,
    to_document_id    text NOT NULL,
    relation_type     text NOT NULL,
    origin            text NOT NULL,
    approval_state    text NOT NULL,
    confidence        double precision,
    approved_by       text,
    approved_at       timestamptz,
    CONSTRAINT {RELATION_FROM_DOCUMENT_FK}
        FOREIGN KEY (from_document_id) REFERENCES {DOCUMENT_TABLE} (document_id)
        ON DELETE CASCADE,
    CONSTRAINT {RELATION_TO_DOCUMENT_FK}
        FOREIGN KEY (to_document_id) REFERENCES {DOCUMENT_TABLE} (document_id)
        ON DELETE CASCADE,
    CONSTRAINT {RELATION_PAIR_TYPE_CONSTRAINT}
        UNIQUE (from_document_id, to_document_id, relation_type)
)
"""

RELATION_INDEXES_DDL = (
    # Kéo họ hàng (06 Mục 6.2) walks outward from the documents just found,
    # and S6 deletes a document's relations — both go by endpoint.
    f"""
CREATE INDEX IF NOT EXISTS relation_from_idx ON {RELATION_TABLE} (from_document_id)
""",
    f"""
CREATE INDEX IF NOT EXISTS relation_to_idx ON {RELATION_TABLE} (to_document_id)
""",
)


DELETION_LOG_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {DELETION_LOG_TABLE} (
    document_id         text        NOT NULL PRIMARY KEY,
    space_id            text,
    tenant_id           text,
    deleted_by          text        NOT NULL,
    reason              text        NOT NULL,
    requested_at        timestamptz NOT NULL,
    purge_completed_at  timestamptz
)
"""

DELETION_LOG_INDEXES_DDL = (
    # R3 — the log must be searchable and exportable, and the natural lookup
    # is by time ("who deleted what last month").
    f"""
CREATE INDEX IF NOT EXISTS deletion_log_requested_at_idx
    ON {DELETION_LOG_TABLE} (requested_at)
""",
    # Source 2 of `space_deletion.delete_space`'s worklist: deletions that
    # STARTED and never reported `dọn nền` done. The log itself is
    # append-only and grows forever — 06 Mục 5.6 keeps every line — but the
    # OPEN subset stays tiny, and the WHERE clause is what keeps the index
    # that size: scanning this index end to end IS enumerating the open rows.
    #
    # ONE reader — `deletion.DeletionLog.open_entries_for_space` — called
    # twice per `delete_space` run: once to build the worklist, once at the
    # end to re-read it and decide `completed`. It wants the open rows OF ONE
    # SPACE, yet `space_id` is deliberately NOT in this index: the partial
    # predicate is the whole point, `space_id` is rechecked per row, and
    # `document_id` is already the primary key. Do not read this as "lookup
    # by space_id", and do not add columns to make it one before measuring.
    #
    # Why the open rows must be findable at all: a purge cut after step 2 has
    # already destroyed the profile, so nothing reading the `document` table
    # can see that document any more — this row is the only trace left that
    # work remains (S6: the obligation is discharged only once dọn nền ran).
    f"""
CREATE INDEX IF NOT EXISTS deletion_log_unfinished_idx
    ON {DELETION_LOG_TABLE} (document_id) WHERE purge_completed_at IS NULL
""",
)


SPACE_REGISTRY_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {SPACE_REGISTRY_TABLE} (
    space_id text NOT NULL PRIMARY KEY,
    state    text NOT NULL
)
"""
# `space_id` is the primary key, which is the whole of "register the same
# Space twice and nothing happens" AND of "a deleted code is never reused"
# (docs/10 §4.0): the second INSERT has to meet the first row.
#
# `state` is plain `text`, no CHECK constraint, the same way
# `document.relations_scan_state` and `relation.approval_state` are: the
# allowed values live in exactly one place — `SpaceState` in
# `schema/space_registry.py`, beside the two enums just named — and a CHECK
# listing them here would be the second spelling CLAUDE.md Mục 6 exists to
# prevent.
#
# No index beside the primary key: this table holds one row per Space — tens,
# maybe hundreds — and every read is a point lookup by `space_id`.


INGESTION_RECORD_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {INGESTION_RECORD_TABLE} (
    ingestion_id                  text        NOT NULL PRIMARY KEY,
    space_id                      text        NOT NULL,
    tenant_id                     text        NOT NULL,
    status                        text        NOT NULL,
    submitted_by                  text        NOT NULL,
    submitted_at                  timestamptz NOT NULL,
    updated_at                    timestamptz NOT NULL,
    requires_pre_approval         boolean     NOT NULL,
    staged_filename               text,
    declared_previous_document_id text,
    document_id                   text,
    existing_document_id          text,
    code                          text
)
"""
# ⚠️ **NO foreign key on `document_id`**, and it is the same decision
# `DELETION_LOG_TABLE` makes: this row must OUTLIVE the document it names. A
# document ingested here can be permanently deleted later (06 Mục 5.6), and a
# cascading FK would erase the record that the ingestion ever happened.
# `declared_previous_document_id` and `existing_document_id` are unreferenced
# for the same reason, plus one more — both may name a document that was
# already gone when the row was written, and the honest answer then is the
# refusal in `code`, not a failed INSERT.
#
# `status` and `code` are plain `text`, no CHECK constraint, exactly as
# `space_registry.state` and `document.relations_scan_state` are: the allowed
# values live in ONE place — `IngestionStatus` / `IngestionFailureCode` in
# `schema/ingestion_record.py` — and a CHECK listing them here would be the
# second spelling CLAUDE.md Mục 6 exists to prevent.
#
# ⛔ There is no `url` column, no `acting_as`, no `space_is_private` and no
# `extracted_text`. Each of those four is forbidden for its own reason — see
# `schema/ingestion_record.py`, which states them.

INGESTION_RECORD_INDEXES_DDL = (
    # The queue read, and the ONLY one the worker makes: oldest unfinished job
    # first. `status` leads because both readers start from it — the worker
    # claiming the next `queued` row, and the startup sweep that finds every
    # `running` row left by a process that died (PO chốt 24/9: with exactly one
    # worker, such a row is orphaned by definition).
    f"""
CREATE INDEX IF NOT EXISTS ingestion_record_queue_idx
    ON {INGESTION_RECORD_TABLE} (status, submitted_at)
""",
    # docs/10 §4.5 — *"Danh sách chờ duyệt"* per Space, and the T4 check on
    # `GET /v1/ingestions/{{id}}?space_id=`. Both read by Space first.
    f"""
CREATE INDEX IF NOT EXISTS ingestion_record_space_idx
    ON {INGESTION_RECORD_TABLE} (space_id, status)
""",
)


#: Everything, in dependency order — `relation` references `document`, so the
#: document table must exist first.
SHARED_STORE_DDL = (
    DOCUMENT_TABLE_DDL,
    *DOCUMENT_INDEXES_DDL,
    RELATION_TABLE_DDL,
    *RELATION_INDEXES_DDL,
    DELETION_LOG_TABLE_DDL,
    *DELETION_LOG_INDEXES_DDL,
    SPACE_REGISTRY_TABLE_DDL,
    INGESTION_RECORD_TABLE_DDL,
    *INGESTION_RECORD_INDEXES_DDL,
)
