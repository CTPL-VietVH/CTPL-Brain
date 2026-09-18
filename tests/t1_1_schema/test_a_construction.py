"""T1.1 (a) — Bốn thực thể dựng được đúng hình dạng đã đặc tả ở 07 Mục 2.

Đây là ca thử "chạy trôi" — cần thiết nhưng không đủ. Ca thử quan trọng hơn
(hệ thống LÊN TIẾNG khi sai) nằm ở test_b/c/d.
"""

from __future__ import annotations

from datetime import date, datetime

from schema.chunk import Chunk
from schema.document import DateSource, Document, RelationsScanState, VersionDeclaredBy
from schema.pending_version_claim import ClaimState, PendingVersionClaim
from schema.relation import ApprovalState, Relation, RelationOrigin, RelationType


def test_document_constructs_with_only_documented_fields():
    doc = Document(
        document_id="doc-1",
        space_id="space-1",
        tenant_id="tenant-1",
        title="Quyết định về việc ban hành quy chế",
        doc_number="15/2024/QĐ-TGĐ",
        issued_date=date(2024, 1, 10),
        issued_date_source=DateSource.EXTRACTED,
        effective_date=date(2024, 2, 1),
        effective_date_source=DateSource.CONFIRMED,
        ingested_at=datetime(2024, 1, 12, 9, 0),
        source_format="pdf",
        content_fingerprint="sha256:abc",
        extracted_text="Toàn văn ở đây.",
        version_chain_id="chain-1",
        version_ordinal=1,
    )
    assert doc.removed_as_wrong is False
    assert doc.superseded is False
    assert doc.category_labels == []
    assert doc.version_declared_by is None
    assert doc.relations_scan_state is RelationsScanState.EXPANDING


def test_document_version_declared_by_accepts_manager_confirmed_path():
    doc = Document(
        document_id="doc-2", space_id="s", tenant_id="t",
        title="x", doc_number="x",
        issued_date=date(2024, 1, 1), issued_date_source=DateSource.DEFAULT_INGESTION_DATE,
        effective_date=date(2024, 1, 1), effective_date_source=DateSource.DEFAULT_INGESTION_DATE,
        ingested_at=datetime(2024, 1, 1), source_format="md",
        content_fingerprint="fp", extracted_text="txt",
        version_chain_id="c", version_ordinal=2,
        version_declared_by=VersionDeclaredBy.MANAGER_CONFIRMED_SUGGESTION,
    )
    assert doc.version_declared_by is VersionDeclaredBy.MANAGER_CONFIRMED_SUGGESTION


def test_chunk_constructs_with_only_documented_fields():
    chunk = Chunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        space_id="space-1",
        tenant_id="tenant-1",
        structure_path=["Chương II", "Điều 7", "Khoản 3"],
        span_start=0,
        span_end=120,
        embedding=[0.1, 0.2, 0.3],
    )
    assert chunk.parent_chunk_id is None
    assert chunk.category_labels == []


def test_relation_constructs_machine_inferred():
    rel = Relation(
        relation_id="rel-1",
        from_document_id="doc-2",
        to_document_id="doc-1",
        relation_type=RelationType.AMENDS_OR_REPLACES,
        origin=RelationOrigin.MACHINE_INFERRED,
        approval_state=ApprovalState.PENDING,
        confidence=0.72,
    )
    assert rel.approved_by is None
    assert rel.approved_at is None


def test_relation_constructs_manually_tagged_with_confidence_left_empty():
    rel = Relation(
        relation_id="rel-2",
        from_document_id="doc-2",
        to_document_id="doc-1",
        relation_type=RelationType.REFERENCES,
        origin=RelationOrigin.MANAGER_ASSIGNED,
        approval_state=ApprovalState.APPROVED,
        approved_by="manager-1",
        approved_at=datetime(2024, 3, 1),
    )
    assert rel.confidence is None, "Liên kết người gắn: confidence phải TRỐNG, không phải 0 (07 Mục 2.3)"


def test_pending_version_claim_constructs_and_defaults_to_pending():
    claim = PendingVersionClaim(
        claim_id="claim-1",
        new_document_id="doc-3",
        candidate_previous_document_id="doc-1",
        similarity=0.94,
    )
    assert claim.state is ClaimState.PENDING
    assert claim.notified_uploader is False
    assert claim.notified_manager is False
