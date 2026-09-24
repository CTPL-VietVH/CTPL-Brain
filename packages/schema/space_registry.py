"""`space_registry` — the Space register: which `space_id` exists, and in what
state (docs/10 §2, §4.0; 06 Mục 5.6 "Xoá cả một Space"; 08 T2.11).

Lives in PostgreSQL, table `space_registry`
(`store_schema.SPACE_REGISTRY_TABLE`). Backend C.Brain creates Spaces and owns
the tree; this table records ONE fact per Space, and docs/10 §2 states exactly
which: *"Danh sách `space_id` đã đăng ký + trạng thái (đang dùng / đang xoá /
đã xoá) ... **Chỉ sự tồn tại** — không cây, không cờ, không thành viên"*.

⛔ **No column here may describe the Space tree, the inheritance flag, or
membership.** Not one of them is a missing feature: NT3 (*"Không lưu thứ sẽ cũ
đi"*) and the CLAUDE.md table of forbidden fields rule each of them out,
because every one changes when a human clicks something and the copy here
would be the stale one. docs/10 §4.0 says where they still live: *"cấu trúc
vẫn hỏi BE lúc cần (§7.1), vì cờ kế thừa là cờ sống và bản sao sẽ cũ đi"*.

The register is therefore NOT a permission source, and it survives QT1's test
— delete this table and the system still decides correctly who may read what.
Retrieval never reads it: Backend sends `readable_space_ids` per question
(docs/10 §3.3), and *registered* is not *readable*.

Why these two types sit in `packages/schema/` while the Protocol, the
in-memory implementation and the refusals stay in
`packages/ingestion/space_registry.py`: this module is the shape that goes in
the table, the same split `deletion_log.py` makes against
`ingestion/deletion.py`. CLAUDE.md Mục 6 — *"Tên trường định nghĩa đúng một
lần trong `packages/schema/`; không service nào tự khai báo lại"*.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SpaceState(str, Enum):
    """The three states of docs/10 §4.0 — *đang dùng / đang xoá / đã xoá*.

    A `str` Enum like every other enum in this package (`DateSource`,
    `RelationsScanState`, `ApprovalState`), so the value stored in the `state`
    column and the value compared in Python are ONE string, not two that must
    agree. The `state` column of `SPACE_REGISTRY_TABLE_DDL` carries these
    values and nothing else.

    `DELETED` is terminal, and the transition never runs backwards. docs/10
    §4.0 gives the reason a deleted `space_id` is never registered again, and
    it is not tidiness: *"tránh tài liệu cũ trong nhật ký bị hiểu nhầm là
    thuộc Space mới trùng mã"* — `DeletionLogEntry.space_id` keeps that code
    forever (06 Mục 5.6), so reusing it would silently re-attribute history.
    Which transitions are legal is enforced in
    `ingestion/space_registry.py`, where the writes are.
    """

    IN_USE = "in_use"
    BEING_DELETED = "being_deleted"
    DELETED = "deleted"


@dataclass(frozen=True, slots=True, kw_only=True)
class SpaceRegistration:
    """One row of the register: a `space_id`, and what state it is in.

    Two fields, and the reason there are only two is the whole point of this
    module — read the ⛔ paragraph above before adding a third.

    `space_id` is Backend's value, passed through untouched: AI never mints
    one (docs/10 §4.0 — Backend creates the Space, then announces it).
    """

    space_id: str
    state: SpaceState
