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

from api.errors import ErrorCode
from api.models import (
    DocumentDeletionRequest,
    IngestionStatusResponse,
    IngestionSubmissionRequest,
    SpaceRegistrationRequest,
    SpaceRegistrationResponse,
    SpaceStatusResponse,
)
from schema.document import Document
from schema.ingestion_record import IngestionFailureCode, IngestionRecord
from schema.space_registry import SpaceRegistration


@pytest.mark.parametrize(
    "model",
    [
        SpaceRegistrationRequest,
        DocumentDeletionRequest,
        SpaceStatusResponse,
        IngestionSubmissionRequest,
    ],
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


def test_h_the_ingestion_status_names_the_two_identifiers_apart():
    """docs/10 §4.2, chốt 24/9: *"`ingestion_id` và `document_id` là hai định
    danh khác nhau"*.

    Both names must reach the wire, and both must be the names the row uses.
    A response that published only `document_id` would force Backend to
    invent a correspondence that does not exist for `rejected`, `duplicate`
    and `failed` submissions — none of which has a document at all.
    """
    row_fields = {field.name for field in dataclasses.fields(IngestionRecord)}

    assert {"ingestion_id", "document_id"} <= set(IngestionStatusResponse.model_fields)
    assert {"ingestion_id", "document_id", "existing_document_id"} <= row_fields


def test_h_the_stored_failure_codes_are_the_http_codes():
    """One spelling per code, even though a code has two homes.

    `OBJECT_NOT_IN_SPACE` is both an HTTP answer (`api.errors.ErrorCode`) and
    a value stored in `ingestion_record.code`. Two literals would be the
    `doc_profile_code`/`profile_code` bug with a `404` on it: Backend
    branching on the HTTP spelling would silently never match the stored one.
    """
    assert ErrorCode.OBJECT_NOT_IN_SPACE == IngestionFailureCode.OBJECT_NOT_IN_SPACE.value
    # `INTERNAL_ERROR` has the same two homes and is still spelled twice —
    # once in each module. Pinned here rather than wired together because the
    # two meanings are genuinely different (a `500` on the wire vs. a job that
    # ended badly), and collapsing them would invite a future edit to give one
    # of them an HTTP status the other does not have.
    assert ErrorCode.INTERNAL_ERROR == IngestionFailureCode.INTERNAL_ERROR.value


def test_h_every_stored_failure_code_appears_in_the_docs_10_table(repo_root):
    """⭐ The codes are read back out of docs/10 §3.5, not out of a copy.

    docs/10 §3.5 is the published list Backend writes its branches against.
    A code this service can store but that is not in that table is a code
    Backend has never been told about — it would arrive in a `GET
    /v1/ingestions` body as an unrecognised string, and the screen would show
    nothing at all.
    """
    document = (
        repo_root / "docs" / "10_Hop_Dong_API_Backend_AI_Services.md"
    ).read_text(encoding="utf-8")
    section = document.split("### 3.5")[1].split("### 3.6")[0]

    for code in IngestionFailureCode:
        assert f"`{code.value}`" in section, (
            f"{code.value} can be stored in ingestion_record.code but is not in "
            f"the docs/10 §3.5 table"
        )


def test_h_no_request_model_accepts_an_unknown_field():
    """`extra="forbid"` everywhere on the way in.

    `{"space_ids": "A"}` must not be read as *"no scope given"* and silently
    accepted as something else — docs/10 §3.3 is explicit that a missing scope
    is never softened, and the same ⚠️ names the old system's `workspace=""`.
    """
    for model in (
        SpaceRegistrationRequest,
        DocumentDeletionRequest,
        IngestionSubmissionRequest,
    ):
        assert model.model_config.get("extra") == "forbid", model.__name__


def test_h_the_submission_asks_for_no_title_and_no_doc_number():
    """PO chốt 24/9/2026 (E3), docs/10 §4.2: *"`title` và `doc_number` do AI
    gợi ý ... BE **không** gửi chúng khi nộp"*.

    A red test here is the only thing standing between "we added two
    convenient optional fields" and 07 §2.1 becoming wrong about who writes
    those two columns.
    """
    forbidden = {"title", "doc_number"} & set(IngestionSubmissionRequest.model_fields)
    assert not forbidden, (
        f"POST /v1/ingestions accepts {sorted(forbidden)} from Backend. Those two "
        "fields belong to Ingestion (07 §2.1, docs/10 §4.2)."
    )
