"""`ingestion_record`: one column list, three hand-written copies of it.

`pg_queue_stores.py` spells the column set out three times — the
`_INGESTION_RECORD_COLUMNS` tuple, `_record_params` (dataclass → row) and
`_row_to_record` (row → dataclass). That is an old debt this file does not
pay off; what it does is make forgetting ONE of the three loud.

Why it has to be a test and not care: every way of getting it wrong is quiet
until it is expensive.

* a field added to `IngestionRecord` and to the DDL but not to the tuple —
  the column exists and is never written; the value silently becomes `NULL`
  on every row, and for VEC-2 that means the orphan sweep finds nothing to
  do, forever;
* added to the tuple but not to `_record_params` — a `ProgrammingError` on
  the first INSERT a deployment makes;
* the two lists in a DIFFERENT ORDER — the worst one: every write succeeds
  and lands in the wrong columns.

Scope is `ingestion_record` alone. `document` and `chunk` have the same debt
and their own task; widening this file would be claiming a coverage it does
not have.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import datetime
from enum import Enum

from ingestion.pg_queue_stores import (
    _INGESTION_RECORD_COLUMNS,
    _record_params,
    _row_to_record,
)
from schema.ingestion_record import (
    IngestionFailureCode,
    IngestionRecord,
    IngestionStatus,
)
from schema.store_schema import INGESTION_RECORD_TABLE_DDL


def _ddl_columns() -> list[str]:
    """Column names in declaration order, read out of the real DDL string."""
    body = INGESTION_RECORD_TABLE_DDL.split("(", 1)[1].rsplit(")", 1)[0]
    names = []
    for line in body.splitlines():
        match = re.match(r"\s*([a-z_]+)\s+(text|timestamptz|boolean)", line)
        if match:
            names.append(match.group(1))
    return names


#: Every column filled with a DISTINCT value — an all-`None` record would pass
#: a test that shuffles two nullable columns.
FULL_RECORD = IngestionRecord(
    ingestion_id="ingestion-1",
    space_id="space-1",
    tenant_id="tenant-1",
    status=IngestionStatus.FAILED,
    submitted_by="user-1",
    submitted_at=datetime(2026, 9, 25, 10, 0),
    updated_at=datetime(2026, 9, 25, 10, 5),
    requires_pre_approval=True,
    staged_filename="staged-1.txt",
    declared_previous_document_id="doc-previous",
    document_id="doc-public",
    existing_document_id="doc-twin",
    code=IngestionFailureCode.INTERNAL_ERROR,
    promoting_document_id="doc-being-written",
)


def test_the_dataclass_the_ddl_and_the_column_tuple_hold_the_same_names():
    dataclass_fields = {field.name for field in dataclasses.fields(IngestionRecord)}

    assert set(_INGESTION_RECORD_COLUMNS) == dataclass_fields, (
        "pg_queue_stores._INGESTION_RECORD_COLUMNS and IngestionRecord disagree; "
        "a column in one and not the other is a value that silently never gets "
        "written or read"
    )
    assert set(_ddl_columns()) == dataclass_fields, (
        "store_schema.INGESTION_RECORD_TABLE_DDL and IngestionRecord disagree"
    )


def test_a_record_survives_the_round_trip_through_both_hand_written_halves():
    """`_record_params` → (the row Postgres would store) → `_row_to_record`.

    This is the check that catches ORDER, which name-set equality cannot: the
    params tuple is handed back positionally, exactly as `SELECT
    _INGESTION_RECORD_SELECT_LIST` returns it.
    """
    params = _record_params(FULL_RECORD)

    assert len(params) == len(_INGESTION_RECORD_COLUMNS), (
        "_record_params and _INGESTION_RECORD_COLUMNS are different lengths — "
        "the INSERT would not even parse"
    )

    assert _row_to_record(params) == FULL_RECORD


def test_the_params_tuple_lines_up_positionally_with_the_column_tuple():
    """The gap the round-trip above cannot see: `_record_params` and
    `_row_to_record` are two halves of each other, so shuffling BOTH the same
    way round-trips fine — while the real INSERT (column list from
    `_INGESTION_RECORD_COLUMNS`, values from `_record_params`) puts every
    value in the wrong column. Two `text` columns swapped that way raises
    nothing, ever."""
    stored = dict(zip(_INGESTION_RECORD_COLUMNS, _record_params(FULL_RECORD)))

    for field in dataclasses.fields(IngestionRecord):
        expected = getattr(FULL_RECORD, field.name)
        expected = expected.value if isinstance(expected, Enum) else expected
        assert stored[field.name] == expected, (
            f"column {field.name!r} of the INSERT would receive "
            f"{stored[field.name]!r}, which belongs to another field"
        )


def test_every_column_carries_a_distinct_value_in_the_fixture():
    """Guards the guard: if two columns above ever hold the same value, the
    round-trip case stops being able to see them swapped."""
    text_values = [
        value for value in _record_params(FULL_RECORD) if isinstance(value, str)
    ]
    assert len(text_values) == len(set(text_values))
