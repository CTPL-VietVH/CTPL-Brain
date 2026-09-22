"""Persistent shape of the three shared entities (07 Mục 2, 08 T2.7).

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
    "CHUNK_PAYLOAD_FIELDS",
    "DOCUMENT_ACTIVE_FINGERPRINT_INDEX",
    "DOCUMENT_VERSION_CHAIN_ORDINAL_CONSTRAINT",
    "DOCUMENT_INDEXES_DDL",
    "DOCUMENT_TABLE",
    "DOCUMENT_TABLE_DDL",
    "RELATION_FROM_DOCUMENT_FK",
    "RELATION_INDEXES_DDL",
    "RELATION_PAIR_TYPE_CONSTRAINT",
    "RELATION_TABLE",
    "RELATION_TABLE_DDL",
    "RELATION_TO_DOCUMENT_FK",
    "SHARED_STORE_DDL",
]


#: Hồ sơ tài liệu (07 Mục 2.1). Retrieval reads it AFTER the search, to build
#: the reading unit and the citation — never to filter candidates (QT2).
DOCUMENT_TABLE = "document"

#: Lớp quan hệ (07 Mục 2.3). "Kho đồ thị" is a LOGICAL name; physically it is
#: this table, in the same database as `document` — which is what lets S6
#: delete both in one atomic transaction (07 Mục 2, dòng 65).
RELATION_TABLE = "relation"


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


#: Everything, in dependency order — `relation` references `document`, so the
#: document table must exist first.
SHARED_STORE_DDL = (
    DOCUMENT_TABLE_DDL,
    *DOCUMENT_INDEXES_DDL,
    RELATION_TABLE_DDL,
    *RELATION_INDEXES_DDL,
)
