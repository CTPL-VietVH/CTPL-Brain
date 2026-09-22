"""T2.7 (l) — the guarantees live in the DDL, not only in Python.

Three things are asserted against the exported DDL constants, because these
are what a real deployment actually gets:

1. The chunk table has NO vector column — the structural form of "dừng trước
   GĐ6" (06 Mục 5.2 GĐ1).
2. The document table carries `UNIQUE (space_id, content_fingerprint)` — the
   storage-level constraint 08's 21/9 update asks for by name.
3. The tables are NOT the official profile/chunk tables. 08 T2.7: *"Vùng làm
   việc của Ingestion phải tách khỏi bảng hồ sơ chính thức"*, which is
   CLAUDE.md điều cấm #20 — a status flag on the shared table is the version
   that must not exist.
"""

from __future__ import annotations

from ingestion.pre_approval_buffer import (
    PRE_APPROVAL_CHUNK_TABLE,
    PRE_APPROVAL_CHUNK_TABLE_DDL,
    PRE_APPROVAL_DOCUMENT_TABLE,
    PRE_APPROVAL_DOCUMENT_TABLE_DDL,
)


def test_chunk_table_has_no_vector_column() -> None:
    ddl = PRE_APPROVAL_CHUNK_TABLE_DDL.lower()
    assert "embedding" not in ddl
    assert "vector" not in ddl


def test_document_table_carries_the_fingerprint_unique_constraint() -> None:
    normalized = " ".join(PRE_APPROVAL_DOCUMENT_TABLE_DDL.lower().split())
    assert "unique (space_id, content_fingerprint)" in normalized


def test_chunk_rows_are_cascaded_from_their_document() -> None:
    normalized = " ".join(PRE_APPROVAL_CHUNK_TABLE_DDL.lower().split())
    assert f"references {PRE_APPROVAL_DOCUMENT_TABLE} (document_id) on delete cascade" in normalized


def test_buffer_tables_are_not_the_official_tables() -> None:
    # The official profile table is `document` (07 Mục 2.1) and the vector
    # payload lives in Qdrant; neither name may be reused here.
    assert PRE_APPROVAL_DOCUMENT_TABLE != "document"
    assert PRE_APPROVAL_CHUNK_TABLE != "chunk"
    for table in (PRE_APPROVAL_DOCUMENT_TABLE, PRE_APPROVAL_CHUNK_TABLE):
        assert table.startswith("ingestion_pre_approval_")

    # And no status/approval flag smuggled in — that is điều cấm #20.
    for ddl in (PRE_APPROVAL_DOCUMENT_TABLE_DDL, PRE_APPROVAL_CHUNK_TABLE_DDL):
        lowered = ddl.lower()
        assert "publication_state" not in lowered
        assert "approval_state" not in lowered
