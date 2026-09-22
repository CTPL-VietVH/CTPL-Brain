"""T2.7 promote (h) — GĐ7 really runs during the promote, and what it proposes
lands in the relation layer in the same transaction as the profile.

This is the half of 08 dòng 206 that the pre-approval stop deferred: *"Manager
duyệt xong mới CHẠY NỐT và ghi ra ba kho."* The relation arrives `PENDING` —
06 Mục 5.3 keeps Manager approval in the loop, and an unapproved relation is
still pulled into context, only with weaker wording.
"""

from __future__ import annotations

from datetime import date

from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.promotion import (
    InMemorySharedProfileStore,
    InMemoryVectorStoreWriter,
    promote_approved_ingestion,
)
from schema.relation import ApprovalState, RelationOrigin, RelationType

from .conftest import (
    SATURATION_EPSILON,
    SATURATION_ROUNDS,
    SCAN_PAIR_BUDGET,
    SCAN_TIME_BUDGET,
    FakeBgeM3,
    buffer_a_document,
    make_scope,
    make_stored_document,
)

# Same shape as the real citation in
# `data/test-corpus-vn-admin/phap-che-tuan-thu/30_2020_ND_CP.docx`.
CITING_DOCUMENT = """BỘ NỘI VỤ
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM

Số: 15/2021/QĐ-BNV
Hà Nội, ngày 15 tháng 3 năm 2021

QUYẾT ĐỊNH
Về việc ban hành Quy chế quản lý tài liệu nội bộ

Căn cứ Nghị định số 110/2004/NĐ-CP ngày 08 tháng 4 năm 2004 của Chính phủ về công tác văn thư;

CHƯƠNG I
QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
Quyết định này quy định về công tác quản lý tài liệu nội bộ của cơ quan.
"""


def test_stage7_relations_land_in_the_store(tmp_path) -> None:
    store = InMemorySharedProfileStore()
    vectors = InMemoryVectorStoreWriter()
    buffer = InMemoryPreApprovalBuffer()

    # The cited document is already live in the same Space.
    cited = make_stored_document(
        document_id="doc-110",
        version_chain_id="chain-110",
        version_ordinal=1,
        content_fingerprint="fp-110",
        doc_number="110/2004/NĐ-CP",
    )
    cited.issued_date = date(2004, 4, 8)
    store.register(cited)

    entry = buffer_a_document(
        tmp_path,
        buffer=buffer,
        fingerprint_index=store,
        text=CITING_DOCUMENT,
        name="quyet-dinh-15-co-can-cu.txt",
    )

    result = promote_approved_ingestion(
        entry,
        profile_store=store,
        buffer=buffer,
        vector_writer=vectors,
        embedding_model=FakeBgeM3(),
        relation_scope=make_scope(),
        relation_document_source=store,
        saturation_epsilon=SATURATION_EPSILON,
        saturation_rounds=SATURATION_ROUNDS,
        scan_pair_budget=SCAN_PAIR_BUDGET,
        scan_time_budget=SCAN_TIME_BUDGET,
    )

    assert len(result.relations) == 1
    stored_relations = store.relations()
    assert len(stored_relations) == 1

    relation = stored_relations[0]
    assert relation.from_document_id == "doc-promote-1"  # the citing document
    assert relation.to_document_id == "doc-110"
    assert relation.relation_type is RelationType.REFERENCES
    assert relation.origin is RelationOrigin.MACHINE_READ_EXPLICIT_REFERENCE
    assert relation.approval_state is ApprovalState.PENDING
