"""T2.11 (h) — the two structural guards, so that the forbidden version of
this feature cannot be written without a red test.

08 T2.11 (a): *"lưu danh sách `space_id` Backend đã tạo cùng trạng thái ...
— **chỉ sự tồn tại**, không cây, không cờ kế thừa, không thành viên"*, and
docs/10 §2 bounds the register in the same words: *"**Chỉ sự tồn tại** —
không cây, không cờ, không thành viên"*.

Two ways that promise could quietly break, one test each:

1. **A column creeps in.** `parent_space_id` and `inherits_from_parent` are
   the obvious two, and both are exactly the kind of frozen copy of a live
   flag NT3 forbids — the bug CLAUDE.md records as already having happened
   once in the running system.
2. **The deletion starts choosing by content.** docs/10 §4.0 allows one
   selector and names it: `space_id` on the document profile. Checking this
   at the bytecode level rather than by reading the source keeps the test
   honest — a comment mentioning `content_fingerprint` does not fail it, and
   a line of code reading that field does.
"""

from __future__ import annotations

import dataclasses
import re

from ingestion.space_deletion import _profiles_in, _worklist, delete_space
from schema.space_registry import SpaceRegistration
from schema.store_schema import SPACE_REGISTRY_TABLE_DDL

_COLUMN = re.compile(r"^\s{4}([a-z_]+)\s", re.MULTILINE)
_NOT_A_COLUMN = {"unique", "primary", "foreign", "references", "constraint", "on"}

#: Every field name that would turn the register into a copy of Backend's
#: Space tree or membership — the three things docs/10 §2 excludes.
FORBIDDEN_FIELDS = {
    "parent_space_id",
    "parent_id",
    "inherits_from_parent",
    "space_kind",
    "space_is_private",
    "members",
    "member_ids",
    "group_ids",
    "readable_space_ids",
}


def _columns(ddl: str) -> set[str]:
    return {name for name in _COLUMN.findall(ddl) if name not in _NOT_A_COLUMN}


def test_the_registration_record_carries_nothing_but_existence_and_state() -> None:
    assert {field.name for field in dataclasses.fields(SpaceRegistration)} == {
        "space_id",
        "state",
    }


def test_the_register_table_has_exactly_those_two_columns() -> None:
    columns = _columns(SPACE_REGISTRY_TABLE_DDL)

    assert columns == {"space_id", "state"}
    assert columns & FORBIDDEN_FIELDS == set(), (
        "the Space register must never hold the tree, the inheritance flag or "
        "the member list (docs/10 §2, NT3)"
    )


def _names_touched_by_the_deletion() -> set[str]:
    """Every global and attribute name the deletion's own code touches.

    All three functions, not just `delete_space`: the selection itself lives
    in `_profiles_in` and `_worklist`, so checking the entry point alone
    would stop being a guard the moment the selector moved into a helper —
    which is exactly what happened when the second worklist source was added.
    """
    return {
        name
        for function in (delete_space, _worklist, _profiles_in)
        for name in function.__code__.co_names
    }


def test_the_deletion_selects_by_space_id_and_never_by_content() -> None:
    touched = _names_touched_by_the_deletion()

    assert "space_id" in touched, "the one allowed selector"
    assert "content_fingerprint" not in touched, (
        "docs/10 §4.0: selecting by fingerprint would delete the byte-identical "
        "twin in another Space, silently"
    )
    assert "doc_number" not in touched
    assert "title" not in touched


def test_the_deletion_cannot_walk_to_child_spaces() -> None:
    """docs/10 §4.0: *"AI **không tự suy ra phải xoá Space con**."* There is
    no tree to walk — this asserts the deletion never reaches for one."""
    touched = _names_touched_by_the_deletion()

    assert touched & FORBIDDEN_FIELDS == set()
    assert "children" not in touched
    assert "descendants" not in touched
