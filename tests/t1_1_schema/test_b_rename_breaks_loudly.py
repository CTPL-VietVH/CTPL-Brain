"""T1.1 (b) — ⭐ "Xong khi" của chính hạng mục này (docs/08 T1.1):

    "đổi tên một trường ở module thì cả hai service không biên dịch được,
    thay vì lặng lẽ tìm nhầm tên. Đây chính là con bug `doc_profile_code`/
    `profile_code` mà module này sinh ra để chặn."

Python không có bước biên dịch tách rời, nên "không biên dịch được" ở đây
dịch thành: gọi sai tên trường phải NỔ NGAY LÚC GỌI (`TypeError` khi dựng,
`AttributeError` khi đọc) — không được âm thầm bỏ qua hay trả về rỗng.

Mỗi entity dùng `@dataclass(slots=True, kw_only=True)`:
  - `kw_only=True` buộc mọi nơi gọi phải nêu ĐÚNG TÊN trường — cùng cách một
    consumer thật sẽ viết `Document(document_id=..., title=...)`.
  - `slots=True` chặn luôn việc gán một thuộc tính lạ sau khi đã dựng xong
    (`obj.ten_la = 1` nổ `AttributeError`), không chỉ chặn lúc dựng.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from schema.chunk import Chunk
from schema.document import DateSource, Document
from schema.pending_version_claim import PendingVersionClaim
from schema.relation import ApprovalState, Relation, RelationOrigin, RelationType

_VALID_DOCUMENT_KWARGS = dict(
    document_id="doc-1", space_id="s", tenant_id="t",
    title="x", doc_number="x",
    issued_date=date(2024, 1, 1), issued_date_source=DateSource.EXTRACTED,
    effective_date=date(2024, 1, 1), effective_date_source=DateSource.EXTRACTED,
    ingested_at=datetime(2024, 1, 1), source_format="md",
    content_fingerprint="fp", extracted_text="txt",
    version_chain_id="c", version_ordinal=1,
)


def test_renamed_field_on_construction_raises_immediately_not_silently():
    """Mô phỏng ĐÚNG con bug 07 Mục 0: Ingestion gõ `doc_profile_code` thay vì
    tên thật. Với dữ liệu tự do (dict rời), việc này trả về 0 kết quả im
    lặng. Với dataclass `kw_only`, nó phải nổ TypeError ngay lúc dựng.
    """
    bad_kwargs = dict(_VALID_DOCUMENT_KWARGS)
    bad_kwargs.pop("space_id")
    bad_kwargs["doc_profile_code"] = "should-have-been-space_id"

    with pytest.raises(TypeError):
        Document(**bad_kwargs)


def test_missing_required_field_raises_immediately():
    incomplete = dict(_VALID_DOCUMENT_KWARGS)
    incomplete.pop("content_fingerprint")

    with pytest.raises(TypeError):
        Document(**incomplete)


def test_reading_a_typo_attribute_raises_not_returns_none():
    doc = Document(**_VALID_DOCUMENT_KWARGS)

    with pytest.raises(AttributeError):
        _ = doc.profile_code  # tên trường không tồn tại, khác cả hai vế của bug thật


def test_writing_an_unknown_attribute_after_construction_raises():
    doc = Document(**_VALID_DOCUMENT_KWARGS)

    with pytest.raises(AttributeError):
        doc.doc_profile_code = "x"  # slots=True chặn cả gán sau khi dựng


def test_chunk_rejects_field_that_belongs_to_document():
    """`effective_date` là trường hợp lệ của `Document` nhưng CẤM ở `Chunk`
    (07 Mục 5, QT2). Gõ nhầm nó vào `Chunk` phải nổ ngay, không âm thầm
    chấp nhận rồi tạo lỗ hổng "trường lạ cạnh mẩu".
    """
    with pytest.raises(TypeError):
        Chunk(
            chunk_id="c1", document_id="d1", space_id="s", tenant_id="t",
            structure_path=["Điều 1"], span_start=0, span_end=10,
            embedding=[0.0],
            effective_date=date(2024, 1, 1),
        )


def test_relation_rejects_is_certain_field():
    """DX1 (CHỐT 14/9): không có trường `is_certain` riêng — suy ra từ
    `origin`. Ai thêm nó vào phải bị chặn ngay ở tầng dựng đối tượng.
    """
    with pytest.raises(TypeError):
        Relation(
            relation_id="r1", from_document_id="d2", to_document_id="d1",
            relation_type=RelationType.REFERENCES,
            origin=RelationOrigin.MACHINE_READ_EXPLICIT_REFERENCE,
            approval_state=ApprovalState.PENDING,
            is_certain=True,
        )


def test_pending_version_claim_rejects_unknown_field():
    with pytest.raises(TypeError):
        PendingVersionClaim(
            claim_id="claim-1", new_document_id="d3",
            candidate_previous_document_id="d1", similarity=0.9,
            approval_state=ApprovalState.APPROVED,  # thuộc Relation, không thuộc claim
        )
