"""T2.7 (m) — every column of the buffer tables is either a real field name
from `packages/schema/` or one of two declared bookkeeping columns.

This is the `doc_profile_code` / `profile_code` bug with a SQL accent. A
persistence layer unavoidably spells the field names a second time, in DDL;
CLAUDE.md Mục 6 warns what happens when the two spellings drift — *"hai chuỗi
ký tự ở hai file khác nhau, mọi truy vấn có bộ lọc đó trả về 0 kết quả, im
lặng"*. Pinning the mapping as identity, and testing it, is what makes the
second spelling safe: a column invented here, or a schema field renamed
without the DDL following, turns this red.
"""

from __future__ import annotations

import dataclasses
import re

from ingestion.pre_approval_buffer import (
    PRE_APPROVAL_CHUNK_TABLE_DDL,
    PRE_APPROVAL_DOCUMENT_TABLE_DDL,
)
from schema.chunk import Chunk
from schema.document import Document

# The only columns allowed NOT to be schema fields, each with its reason.
DOCUMENT_BOOKKEEPING = {
    "buffered_at",  # when the entry entered the working area; not a Document field
}
CHUNK_BOOKKEEPING = {
    "chunk_ordinal",  # preserves the cut order a Python list carries implicitly
}

_COLUMN = re.compile(r"^\s{4}([a-z_]+)\s", re.MULTILINE)


def _columns(ddl: str) -> set[str]:
    # Skip the table-level constraint lines, which start with a keyword.
    return {
        name
        for name in _COLUMN.findall(ddl)
        if name not in {"unique", "primary", "foreign", "references", "constraint"}
    }


def _field_names(cls: type) -> set[str]:
    return {field.name for field in dataclasses.fields(cls)}


def test_document_table_columns_are_document_fields() -> None:
    columns = _columns(PRE_APPROVAL_DOCUMENT_TABLE_DDL)
    assert columns, "the column regex must actually be finding columns"

    invented = columns - _field_names(Document) - DOCUMENT_BOOKKEEPING
    assert invented == set(), f"columns with no field of that name in schema: {sorted(invented)}"


def test_chunk_table_columns_are_chunk_fields() -> None:
    columns = _columns(PRE_APPROVAL_CHUNK_TABLE_DDL)
    assert columns

    invented = columns - _field_names(Chunk) - CHUNK_BOOKKEEPING
    assert invented == set(), f"columns with no field of that name in schema: {sorted(invented)}"


def test_official_lifecycle_fields_have_no_column_here() -> None:
    """`removed_as_wrong`, `superseded`, `relations_scan_state` and their trace
    columns mean nothing for a document that is not in the shared store yet —
    and GĐ7, which would set a scan state, has not run."""
    columns = _columns(PRE_APPROVAL_DOCUMENT_TABLE_DDL)
    for field_name in (
        "removed_as_wrong",
        "removed_reason",
        "removed_by",
        "removed_at",
        "superseded",
        "superseded_by",
        "superseded_at",
        "relations_scan_state",
        "labels_confirmed_by",
        "labels_confirmed_at",
    ):
        assert field_name not in columns
