"""T2.7 promote (i) — the DDL really is the FULL shape of the three entities,
not a convenient subset.

The buffer tables of the first half of T2.7 were deliberately reduced — the
official-lifecycle fields mean nothing before approval. These tables are the
opposite: a `Document` field with no column is data that silently stops
existing the moment it is written, and CLAUDE.md Mục 6 describes what a
name that exists on one side and not the other costs — *"mọi truy vấn có bộ
lọc đó trả về 0 kết quả, im lặng."*

`Chunk` is checked against the Qdrant payload rather than a table: 07 Mục 2.2
gives it a home in the vector store, and a `chunk` table beside it would be a
second copy of the same facts. See `store_schema.py` and the T2.7 report.
"""

from __future__ import annotations

import dataclasses
import re

from schema.chunk import Chunk
from schema.document import Document
from schema.relation import Relation
from schema.store_schema import (
    CHUNK_PAYLOAD_FIELDS,
    DOCUMENT_TABLE_DDL,
    RELATION_TABLE_DDL,
    SHARED_STORE_DDL,
)

_COLUMN = re.compile(r"^\s{4}([a-z_]+)\s", re.MULTILINE)
_NOT_A_COLUMN = {"unique", "primary", "foreign", "references", "constraint", "on"}


def _columns(ddl: str) -> set[str]:
    return {name for name in _COLUMN.findall(ddl) if name not in _NOT_A_COLUMN}


def _field_names(cls: type) -> set[str]:
    return {field.name for field in dataclasses.fields(cls)}


def test_document_table_has_a_column_for_every_document_field() -> None:
    assert _field_names(Document) == _columns(DOCUMENT_TABLE_DDL)


def test_relation_table_has_a_column_for_every_relation_field() -> None:
    assert _field_names(Relation) == _columns(RELATION_TABLE_DDL)


def test_chunk_payload_covers_every_chunk_field_but_id_and_vector() -> None:
    assert set(CHUNK_PAYLOAD_FIELDS) == _field_names(Chunk) - {"chunk_id", "embedding"}


def test_both_owed_unique_constraints_are_present() -> None:
    """08 dòng 210, the two that had no home until now."""
    all_ddl = " ".join(" ".join(statement.lower().split()) for statement in SHARED_STORE_DDL)

    assert "unique (version_chain_id, version_ordinal)" in all_ddl
    # The second one is a PARTIAL index — a plain constraint would refuse the
    # legitimate re-upload over a `removed_as_wrong` twin (see test f).
    assert (
        "create unique index if not exists document_space_fingerprint_active_unique "
        "on document (space_id, content_fingerprint) where not removed_as_wrong" in all_ddl
    )


def test_content_fingerprint_has_an_index_of_its_own() -> None:
    """07 Mục 7 yêu cầu 1 — *"phải đánh chỉ mục để tra ngược từ vân tay ra danh
    sách tài liệu"*. The partial unique index cannot serve it: `space_id` leads
    it, while `find_by_fingerprint` searches on the fingerprint alone and across
    Spaces, and its WHERE clause hides the `removed_as_wrong` rows
    `decide_intake` still has to see."""
    all_ddl = " ".join(" ".join(statement.lower().split()) for statement in SHARED_STORE_DDL)
    assert "on document (content_fingerprint)" in all_ddl


def test_relations_are_cascaded_from_both_endpoints() -> None:
    """S6 deletes a document's relations with it, in one transaction."""
    normalized = " ".join(RELATION_TABLE_DDL.lower().split())
    assert normalized.count("references document (document_id) on delete cascade") == 2
