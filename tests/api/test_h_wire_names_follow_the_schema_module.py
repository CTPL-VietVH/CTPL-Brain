"""The wire names and the schema names are ONE set of names.

CLAUDE.md Mục 6: *"Tên trường định nghĩa **đúng một lần** trong
`packages/schema/`; **không service nào tự khai báo lại**. Đây chính là con
bug `doc_profile_code` / `profile_code` mà module này sinh ra để chặn: hai
chuỗi ký tự ở hai file khác nhau, mọi truy vấn có bộ lọc đó trả về **0 kết
quả, im lặng**."*

A pydantic model is a second declaration by construction — the field name is
typed again. What keeps the two from drifting is this file: rename
`Document.space_id` in `packages/schema/` and these cases go red, instead of
an endpoint quietly accepting a field the stores no longer know.

⚠️ Not everything here has a schema home, and must not get one. `actor` and
`acting_as` carry Backend's permission verdict; QT1 keeps that out of AI's
data, so they are wire-only names and are deliberately not checked against
anything in `packages/schema/`.
"""

from __future__ import annotations

import dataclasses

import pytest

from api.models import (
    DocumentDeletionRequest,
    SpaceDeletionResponse,
    SpaceRegistrationRequest,
    SpaceRegistrationResponse,
    SpaceStatusResponse,
)
from ingestion.space_deletion import SpaceDeletionProgress
from schema.document import Document
from schema.space_registry import SpaceRegistration


@pytest.mark.parametrize(
    "model",
    [SpaceRegistrationRequest, DocumentDeletionRequest, SpaceStatusResponse],
)
def test_h_space_id_is_spelled_as_the_schema_spells_it(model):
    assert "space_id" in model.model_fields
    assert "space_id" in Document.__dataclass_fields__, (
        "`Document` no longer has a field called `space_id`. Whatever it is "
        "called now, the API models must follow it — two spellings of one "
        "field return nothing, silently."
    )


def test_h_the_registration_response_says_no_more_than_the_register_holds():
    """docs/10 §2: the register holds *"**Chỉ sự tồn tại** — không cây, không
    cờ, không thành viên"*. An endpoint that published a fourth field would
    mean the table grew one."""
    assert set(SpaceRegistrationResponse.model_fields) == {
        field.name for field in dataclasses.fields(SpaceRegistration)
    }


def test_h_the_deletion_response_publishes_the_whole_progress_object():
    """Every field of `SpaceDeletionProgress`, no more and no fewer.

    Fewer would drop a number Backend needs — `unfinished_purges_remaining` in
    particular has no other trace anywhere in the system (see that dataclass).
    More would be a number this layer invented.
    """
    assert set(SpaceDeletionResponse.model_fields) == {
        field.name for field in dataclasses.fields(SpaceDeletionProgress)
    }


def test_h_no_request_model_accepts_an_unknown_field():
    """`extra="forbid"` everywhere on the way in.

    `{"space_ids": "A"}` must not be read as *"no scope given"* and silently
    accepted as something else — docs/10 §3.3 is explicit that a missing scope
    is never softened, and the same ⚠️ names the old system's `workspace=""`.
    """
    for model in (SpaceRegistrationRequest, DocumentDeletionRequest):
        assert model.model_config.get("extra") == "forbid", model.__name__
