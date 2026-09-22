"""T1.1 (c) — Đối chiếu tập tên trường của mỗi entity với bảng ở 07 Mục 2,
và với danh sách cấm ở 07 Mục 5.

Danh sách mong đợi dưới đây được CHÉP TAY từ docs/07 Mục 2.1–2.4 (không suy
diễn thêm trường nào ngoài bảng, đúng ràng buộc của T1.1). Nếu 07 đổi version
và đổi bảng trường, ca thử này phải sửa theo — đó chính là điểm mạnh của nó:
nó buộc bất kỳ ai sửa `packages/schema/` phải đối chiếu lại với 07 Mục 2.
"""

from __future__ import annotations

import dataclasses

from schema.chunk import Chunk
from schema.document import Document
from schema.pending_version_claim import PendingVersionClaim
from schema.relation import Relation

# 07 Mục 2.1 — bảng trường `document`
DOCUMENT_FIELDS = {
    "document_id", "space_id", "tenant_id", "title", "doc_number",
    "issued_date", "issued_date_source", "effective_date", "effective_date_source",
    "ingested_at", "source_format", "content_fingerprint", "extracted_text",
    "removed_as_wrong", "removed_reason", "removed_by", "removed_at",
    "superseded", "superseded_by", "superseded_at",
    "category_labels", "labels_confirmed_by", "labels_confirmed_at",
    "subject_entities",
    "version_chain_id", "version_ordinal", "version_declared_by",
    "relations_scan_state",
}

# 07 Mục 2.2 — bảng trường `chunk` (QT2: whitelist tuyệt đối)
CHUNK_FIELDS = {
    "chunk_id", "document_id", "space_id", "tenant_id",
    "structure_path", "parent_chunk_id", "span_start", "span_end",
    "category_labels", "embedding",
}

# 07 Mục 2.3 — bảng trường `relation`
RELATION_FIELDS = {
    "relation_id", "from_document_id", "to_document_id", "relation_type",
    "confidence", "approval_state", "origin", "approved_by", "approved_at",
}

# 07 Mục 2.4 — bảng trường `pending_version_claim`
PENDING_VERSION_CLAIM_FIELDS = {
    "claim_id", "new_document_id", "candidate_previous_document_id",
    "similarity", "notified_uploader", "notified_manager", "state",
}


def _field_names(entity_cls) -> set[str]:
    return {f.name for f in dataclasses.fields(entity_cls)}


def test_document_fields_match_07_muc_2_1_exactly():
    assert _field_names(Document) == DOCUMENT_FIELDS


def test_chunk_fields_match_07_muc_2_2_exactly():
    assert _field_names(Chunk) == CHUNK_FIELDS


def test_relation_fields_match_07_muc_2_3_exactly():
    assert _field_names(Relation) == RELATION_FIELDS


def test_pending_version_claim_fields_match_07_muc_2_4_exactly():
    assert _field_names(PendingVersionClaim) == PENDING_VERSION_CLAIM_FIELDS


def test_removed_as_wrong_and_superseded_are_two_separate_fields():
    """CLAUDE.md Mục 3 #1 / 06 Mục 6.3 — điều cấm quan trọng nhất của bảng
    `document`: không được gộp thành một trường `status`.
    """
    fields = _field_names(Document)
    assert "removed_as_wrong" in fields
    assert "superseded" in fields
    assert "status" not in fields
    assert "document_state" not in fields


def test_document_has_no_is_latest_version_or_publication_state_flag():
    fields = _field_names(Document)
    assert "is_latest_version" not in fields
    assert "publication_state" not in fields


def test_subject_entities_has_no_confirmed_by_or_at_pair():
    """07 Section 2.1 line 93 callout (LOCKED 2026-09-22): unlike
    `category_labels`, `subject_entities` must NOT get a
    `_confirmed_by`/`_at` pair — it is an internal signal for K3, not
    something an end user confirms directly.
    """
    fields = _field_names(Document)
    assert "subject_entities" in fields
    assert "subject_entities_confirmed_by" not in fields
    assert "subject_entities_confirmed_at" not in fields


def test_relation_has_no_separate_is_certain_field():
    """DX1 — "chắc chắn" suy ra từ `origin`, không phải một ô riêng (07 Mục 2.3)."""
    assert "is_certain" not in _field_names(Relation)
    assert "certain" not in _field_names(Relation)


def test_chunk_never_carries_relation_approval_state():
    """07 Mục 5 — `approval_state` của liên kết TUYỆT ĐỐI cấm đặt cạnh mẩu."""
    assert "approval_state" not in _field_names(Chunk)


def test_chunk_never_carries_read_and_citation_fields_owned_by_document():
    """07 Mục 5 — `title`, `doc_number`, `effective_date`, trạng thái tài
    liệu chỉ ở `Document`; lấy sau từ hồ sơ, không đặt cạnh mẩu.
    """
    forbidden_on_chunk = {
        "title", "doc_number", "effective_date", "issued_date",
        "removed_as_wrong", "superseded",
    }
    assert forbidden_on_chunk.isdisjoint(_field_names(Chunk))


def test_no_entity_carries_frozen_permission_or_membership_lists():
    """07 Mục 5 — NT3 + QT1: không danh sách người/nhóm/dấu hiệu quyền đóng
    băng, không loại Space / cây Space / danh sách thành viên, ở BẤT KỲ
    thực thể nào trong bốn thực thể dùng chung.
    """
    forbidden_substrings = (
        "permission", "quyen", "member", "thanh_vien",
        "space_type", "space_tree", "inherited",
    )
    all_fields = (
        _field_names(Document) | _field_names(Chunk)
        | _field_names(Relation) | _field_names(PendingVersionClaim)
    )
    for name in all_fields:
        for bad in forbidden_substrings:
            assert bad not in name, f"{name} trông như mang dấu hiệu quyền/thành viên"


def test_no_entity_carries_agent_field():
    """07 Mục 5 (chốt cuối) — agent chuyên miền không sinh trường nào trong
    dữ liệu dùng chung Ingestion–Retrieval.
    """
    all_fields = (
        _field_names(Document) | _field_names(Chunk)
        | _field_names(Relation) | _field_names(PendingVersionClaim)
    )
    for name in all_fields:
        assert "agent" not in name
