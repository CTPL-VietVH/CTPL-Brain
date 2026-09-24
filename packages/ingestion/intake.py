"""GĐ1 — Nhận và xác thực (T2.1, 06 Mục 5.7, 07 Mục 2.1).

Phạm vi ĐÃ THU HẸP theo hai cập nhật 19/9 (PO, N9) trong `docs/08` mục T2.1:

1. `content_fingerprint` do GĐ2 (T2.2) tính **sau khi** đọc chữ ra — module
   này KHÔNG tự băm file, chỉ nhận vân tay đã tính sẵn rồi quyết trùng/
   không-trùng dựa trên nó. Gọi module này trước khi GĐ2 chạy xong là gọi sai
   thứ tự, không phải lỗi của module.
2. Nhánh "người upload không khai thì máy tự phân tích đề xuất" thuộc T2.4
   (GĐ5), không phải ở đây. Module này CHỈ xử lý khai báo TƯỜNG MINH của
   người upload ("đây là bản mới của X") — không tạo `PendingVersionClaim`.

Bảng CHỐT trùng lặp (06 Mục 5.7):

| Tình huống                  | v1 làm gì                                    |
|------------------------------|-----------------------------------------------|
| Trùng khít, cùng Space        | Báo trùng, không nạp lại — trỏ tới bản đã có  |
| Trùng khít, khác Space        | Hợp lệ, không cảnh báo — tạo tài liệu mới     |
| Gần giống, cùng Space          | Không phải trùng lặp — đi đường "bản mới"     |

`FingerprintIndex` chỉ là GIAO DIỆN tra ngược vân tay → tài liệu (06 Mục 5.7
cuối: "vân tay nội dung... cần được đánh chỉ mục"). Nơi cư trú thật của chỉ
mục (cột `content_fingerprint` có index trong bảng `document` ở PostgreSQL)
là việc triển khai kho của T2.2+, không phải phạm vi T2.1.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from ingestion.space_registry import SpaceRegistry, assert_space_accepts_documents
from schema.document import DateSource, Document, VersionDeclaredBy


class BanMoiKhacSpace(Exception):
    """`declared_previous_version` ở khác Space với request (audit T2.1 #3).

    Không kiểm điều này thì một chuỗi phiên bản có thể vắt qua ranh giới
    Space — hai Space có thể có tập người đọc khác nhau, nên đó là một cách
    rò rỉ cấu trúc tài liệu ra ngoài Space gốc.
    """


class VanTayNoiDungRong(Exception):
    """`content_fingerprint` rỗng hoặc chỉ toàn khoảng trắng (audit T2.1 #5).

    Đây là khoá tra trùng-lặp duy nhất (07 Mục 2.1) — một giá trị rỗng lọt
    qua sẽ khiến mọi tài liệu "không vân tay" bị coi là trùng nhau trong
    cùng một Space.
    """


def _active_match_in_space(matches: list[Document], space_id: str) -> Document | None:
    """Tài liệu ĐẦU TIÊN cùng Space và CHƯA `removed_as_wrong` trong danh sách
    trùng vân tay — dùng chung ở cả `decide_intake` và `receive_and_validate`.

    Trước sửa audit T2.1 #1 (CRITICAL): hai chỗ tra trùng dùng hai bộ lọc
    lệch nhau — `decide_intake` loại `removed_as_wrong`, còn lần tra lại thứ
    hai trong `receive_and_validate` thì không. Khi bản `removed_as_wrong`
    đăng ký TRƯỚC bản đang hoạt động trong cùng Space, `IntakeResult.document`
    trỏ nhầm về bản đã gỡ vì sai. Gộp về một hàm thì không còn chỗ để hai bộ
    lọc lệch nhau nữa.
    """
    for d in matches:
        if d.space_id == space_id and not d.removed_as_wrong:
            return d
    return None


class FingerprintIndex(Protocol):
    """Tra ngược vân tay nội dung ra danh sách tài liệu đã có, và ghi nhận
    tài liệu mới. T2.1 không chọn nơi cư trú thật — xem docstring module."""

    def find_by_fingerprint(self, content_fingerprint: str) -> list[Document]: ...

    def register(self, document: Document) -> None: ...


class InMemoryFingerprintIndex:
    """Cài đặt tối thiểu của `FingerprintIndex` — dùng cho test và cho tiến
    trình một máy. KHÔNG phải kho dùng chung thật (đó là PostgreSQL, T2.2+)."""

    def __init__(self) -> None:
        self._by_fingerprint: dict[str, list[Document]] = {}

    def find_by_fingerprint(self, content_fingerprint: str) -> list[Document]:
        return list(self._by_fingerprint.get(content_fingerprint, []))

    def register(self, document: Document) -> None:
        self._by_fingerprint.setdefault(document.content_fingerprint, []).append(document)


@dataclass(frozen=True, slots=True, kw_only=True)
class IntakeDecision:
    """Quyết định của GĐ1 cho một lượt nạp — chưa phải `Document`.

    `proceed=False` nghĩa là "báo trùng, không nạp lại": không được tạo
    `Document` mới, chỉ trỏ về `duplicate_of`.
    """

    proceed: bool
    duplicate_of: str | None = None
    version_chain_id: str | None = None
    version_ordinal: int | None = None
    version_declared_by: VersionDeclaredBy | None = None


def decide_intake(
    *,
    space_id: str,
    content_fingerprint: str,
    fingerprint_index: FingerprintIndex,
    space_registry: SpaceRegistry,
    declared_previous_version: Document | None = None,
) -> IntakeDecision:
    """Quyết định trùng lặp + gán chuỗi phiên bản cho một lượt nạp (06 Mục 5.7).

    `declared_previous_version`: tài liệu người upload khai "đây là bản mới
    của X", đã tra sẵn theo `document_id` họ chọn. `None` nghĩa là không khai
    — module này KHÔNG tự đoán, nhánh máy đề xuất thuộc T2.4.

    Tài liệu đã `removed_as_wrong` bị loại khỏi việc tra trùng-cùng-Space:
    Retrieval đã lọc cứng nó khỏi mọi câu trả lời (NT4), nên trỏ upload mới
    về nó coi như trỏ vào hư không — phải coi như "không tồn tại" và cho
    tạo tài liệu mới, không phải báo trùng.

    `declared_previous_version` phải cùng Space với request, nếu không raise
    `BanMoiKhacSpace` (audit T2.1 #3). Nếu nó đã `removed_as_wrong`, coi như
    KHÔNG khai báo — rơi về nhánh "không khai báo" (chuỗi phiên bản mới),
    KHÔNG raise lỗi (audit T2.1 #4, PO chốt Phương án A 21/9: `removed_as_wrong`
    là nguyên tắc "coi như không tồn tại" xuyên suốt module này, không riêng
    nhánh chống-trùng).

    `space_registry` (T2.11, docs/10 §4.0/§4.1) KHÔNG có giá trị mặc định —
    cùng lý do `chunk_length_cap` không có: một mặc định ở đây là một đường
    vòng qua cổng chặn, và đường vòng đó im lặng. Cổng đặt ở `decide_intake`
    chứ không ở `receive_and_validate` vì đây là chỗ CẢ HAI đường nộp đi qua:
    đường chính thức (`receive_and_validate`) và đường tiền kiểm của Space
    riêng (`pre_approval_runner.run_pre_approval_ingestion`) — đúng khuôn mà
    `VanTayNoiDungRong` đã dùng (xem `tests/t2_1_intake/test_k`).

    Raises:
        SpaceNotRegistered: `space_id` chưa từng được Backend đăng ký.
        SpaceNotAcceptingDocuments: Space đang xoá hoặc đã xoá — docs/10 §4.0
            bước 1, *"mọi lời gọi nộp tài liệu ... trả 409
            SPACE_BEING_DELETED"*.
        VanTayNoiDungRong: `content_fingerprint` rỗng.
        BanMoiKhacSpace: `declared_previous_version` ở Space khác.
    """
    # Cổng Space đứng TRƯỚC mọi thứ khác: tra vân tay, tra chuỗi phiên bản đều
    # là việc đọc kho dùng chung nhân danh một Space — làm chúng trước rồi mới
    # hỏi "Space này có tồn tại không" là làm việc cho một Space không có thật.
    assert_space_accepts_documents(space_id, space_registry=space_registry)

    if not content_fingerprint or not content_fingerprint.strip():
        raise VanTayNoiDungRong(f"content_fingerprint rỗng hoặc toàn khoảng trắng: {content_fingerprint!r}")

    exact_matches = fingerprint_index.find_by_fingerprint(content_fingerprint)
    active_match = _active_match_in_space(exact_matches, space_id)
    if active_match is not None:
        return IntakeDecision(proceed=False, duplicate_of=active_match.document_id)

    if declared_previous_version is not None:
        if declared_previous_version.space_id != space_id:
            raise BanMoiKhacSpace(
                f"declared_previous_version ở Space {declared_previous_version.space_id!r}, "
                f"khác Space của request {space_id!r}"
            )
        if not declared_previous_version.removed_as_wrong:
            return IntakeDecision(
                proceed=True,
                version_chain_id=declared_previous_version.version_chain_id,
                version_ordinal=declared_previous_version.version_ordinal + 1,
                version_declared_by=VersionDeclaredBy.UPLOADER_DECLARED_AT_INGESTION,
            )

    return IntakeDecision(
        proceed=True,
        version_chain_id=str(uuid.uuid4()),
        version_ordinal=1,
        version_declared_by=None,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class IntakeRequest:
    """Các trường `Document` đã sẵn sàng từ thượng nguồn (GĐ2+), NGOẠI TRỪ
    `version_chain_id` / `version_ordinal` / `version_declared_by` — ba
    trường này do GĐ1 quyết (06 Mục 5.7), không phải đầu vào."""

    document_id: str
    space_id: str
    tenant_id: str
    title: str
    doc_number: str
    issued_date: date
    issued_date_source: DateSource
    effective_date: date
    effective_date_source: DateSource
    ingested_at: datetime
    source_format: str
    content_fingerprint: str
    extracted_text: str
    declared_previous_version: Document | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class IntakeResult:
    document: Document
    created: bool
    duplicate_of: str | None = None


def receive_and_validate(
    request: IntakeRequest,
    *,
    fingerprint_index: FingerprintIndex,
    space_registry: SpaceRegistry,
) -> IntakeResult:
    """GĐ1 trọn vẹn: quyết định rồi (nếu hợp lệ) dựng `Document` và ghi vào
    chỉ mục vân tay. Ca thử "Xong khi" của T2.1 (docs/08): nạp cùng một file
    hai lần vào một Space chỉ ra một tài liệu; vào hai Space ra hai tài liệu,
    không cảnh báo.

    `space_registry` chỉ đi thẳng xuống `decide_intake` — cổng Space nằm ở đó,
    không lặp lại ở đây (một lần kiểm, một chỗ kiểm).
    """
    decision = decide_intake(
        space_id=request.space_id,
        content_fingerprint=request.content_fingerprint,
        fingerprint_index=fingerprint_index,
        space_registry=space_registry,
        declared_previous_version=request.declared_previous_version,
    )

    if not decision.proceed:
        existing = fingerprint_index.find_by_fingerprint(request.content_fingerprint)
        matched = _active_match_in_space(existing, request.space_id)
        if matched is None:
            raise AssertionError(
                "decide_intake báo trùng (proceed=False) nhưng tra lại không thấy bản "
                "active cùng Space — chỉ mục vân tay đã đổi giữa hai lần đọc trong cùng "
                "một lượt nạp"
            )
        return IntakeResult(document=matched, created=False, duplicate_of=decision.duplicate_of)

    if decision.version_chain_id is None:
        raise AssertionError(
            "decide_intake trả proceed=True nhưng version_chain_id là None — bất biến "
            "nội bộ vi phạm"
        )
    if decision.version_ordinal is None:
        raise AssertionError(
            "decide_intake trả proceed=True nhưng version_ordinal là None — bất biến "
            "nội bộ vi phạm"
        )
    document = Document(
        document_id=request.document_id,
        space_id=request.space_id,
        tenant_id=request.tenant_id,
        title=request.title,
        doc_number=request.doc_number,
        issued_date=request.issued_date,
        issued_date_source=request.issued_date_source,
        effective_date=request.effective_date,
        effective_date_source=request.effective_date_source,
        ingested_at=request.ingested_at,
        source_format=request.source_format,
        content_fingerprint=request.content_fingerprint,
        extracted_text=request.extracted_text,
        version_chain_id=decision.version_chain_id,
        version_ordinal=decision.version_ordinal,
        version_declared_by=decision.version_declared_by,
    )
    fingerprint_index.register(document)
    return IntakeResult(document=document, created=True, duplicate_of=None)
