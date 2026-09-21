"""T2.1 (f) — `intake` không được tự đặt tên trường cho `document`.

CLAUDE.md Mục 6: tên trường định nghĩa ĐÚNG MỘT LẦN trong `packages/schema/`.
`IntakeRequest`/`IntakeDecision` chép lại tên trường ra ngoài schema để dựng
`Document(...)` bằng keyword — đây là ca thử ghim lại: đổi tên một trường ở
schema (vd. `doc_number` → `docnumber`) thì test này phải đỏ ngay, thay vì
lệch âm thầm.
"""

from __future__ import annotations

from dataclasses import fields

from ingestion.intake import IntakeDecision, IntakeRequest
from schema.document import Document


def test_intake_request_field_names_all_exist_in_document():
    document_names = {f.name for f in fields(Document)}
    request_names = {f.name for f in fields(IntakeRequest)} - {"declared_previous_version"}
    assert request_names <= document_names, request_names - document_names


def test_intake_decision_version_field_names_all_exist_in_document():
    document_names = {f.name for f in fields(Document)}
    decision_names = {f.name for f in fields(IntakeDecision)} - {"proceed", "duplicate_of"}
    assert decision_names <= document_names, decision_names - document_names
