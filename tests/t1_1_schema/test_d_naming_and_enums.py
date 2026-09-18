"""T1.1 (d) — Quy ước đặt tên (CLAUDE.md Mục 6) và tập giá trị enum đúng như
liệt kê trong Kiểu của từng trường ở 07 Mục 2.
"""

from __future__ import annotations

import dataclasses
import re

from schema.chunk import Chunk
from schema.document import DateSource, Document, RelationsScanState, VersionDeclaredBy
from schema.pending_version_claim import ClaimState, PendingVersionClaim
from schema.relation import ApprovalState, Relation, RelationOrigin, RelationType

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


def test_all_field_names_are_lowercase_snake_case_ascii():
    """CLAUDE.md Mục 6: "chữ thường, nối bằng gạch dưới, tiếng Anh"."""
    for entity_cls in (Document, Chunk, Relation, PendingVersionClaim):
        for f in dataclasses.fields(entity_cls):
            assert SNAKE_CASE.match(f.name), f"{entity_cls.__name__}.{f.name} sai quy ước đặt tên"


def test_date_source_has_exactly_three_documented_values():
    assert {m.value for m in DateSource} == {
        "extracted", "confirmed", "default_ingestion_date",
    }


def test_version_declared_by_has_exactly_three_documented_values():
    assert {m.value for m in VersionDeclaredBy} == {
        "uploader_declared_at_ingestion",
        "uploader_confirmed_suggestion",
        "manager_confirmed_suggestion",
    }


def test_relations_scan_state_has_exactly_two_documented_values():
    assert {m.value for m in RelationsScanState} == {"expanding", "stopped"}


def test_relation_type_has_exactly_four_documented_values():
    assert {m.value for m in RelationType} == {
        "amends_or_replaces", "attachment", "references", "same_topic",
    }


def test_approval_state_has_exactly_three_documented_values():
    assert {m.value for m in ApprovalState} == {"pending", "approved", "rejected"}


def test_relation_origin_has_exactly_three_documented_values():
    assert {m.value for m in RelationOrigin} == {
        "machine_inferred", "machine_read_explicit_reference", "manager_assigned",
    }


def test_claim_state_has_exactly_three_documented_values():
    assert {m.value for m in ClaimState} == {"pending", "confirmed", "rejected"}
