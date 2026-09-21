"""GĐ2 — Đọc file (T2.2, 06 Mục 5.2 GĐ2 và 5.7, 07 Mục 2.1).

Cầu nối giữa bộ đọc bốn định dạng (`ingestion.reader`, dựng ở T0.3) và hai
trường `document` mà GĐ2 có nghĩa vụ sinh ra:

* `extracted_text` (07 Mục 2.1) — **nguồn chân lý duy nhất của chữ nghĩa**.
* `content_fingerprint` (07 Mục 2.1, 06 Mục 5.7) — băm **sau khi đã đọc được
  chữ ra**, không băm file thô. Đây là điều kiện để T2.1 (GĐ1) quyết trùng
  lặp/bản mới đúng: hai file khác byte nhưng cùng chữ (khác xuống dòng, khác
  định dạng chứa) vẫn phải nhận ra là trùng khít.

`ingestion.reader.readers.doc_file` đã tự lo trọn: từ chối định dạng ngoài
danh sách v1 (`DinhDangKhongNhan`) và từ chối PDF không có lớp chữ
(`KhongDocDuocLopChu`), đều kèm thông báo rõ. Module này không lặp lại logic
đó — chỉ đứng ngay sau điểm cắm để đóng gói kết quả cho GĐ1 (T2.1) dùng và
giữ nguyên cây cấu trúc cho GĐ3 (T2.3, cắt mẩu) dùng tiếp, **không ai phải mở
lại file gốc lần hai**.

⚠️ `source_format` được GHI LẠI trong `ExtractionResult` nhưng không có mặt
trong bất kỳ nhánh rẽ logic nào ở đây — điểm cắm GĐ2 (08 T2.2).
"""

from __future__ import annotations

import hashlib
import pathlib
from dataclasses import dataclass

from .reader.readers import DinhDangKhongNhan, KhongDocDuocLopChu, doc_file
from .reader.structure import ReadResult

__all__ = [
    "DinhDangKhongNhan",
    "KhongDocDuocLopChu",
    "ExtractionResult",
    "compute_content_fingerprint",
    "extract_file",
]


def compute_content_fingerprint(extracted_text: str) -> str:
    """Vân tay nội dung — băm SHA-256 trên `extracted_text` đã đọc ra.

    06 Mục 5.7: *"vân tay nội dung, tính ở GĐ2 sau khi đã đọc được chữ ra"*.
    Cố ý không băm bytes của file gốc — file gốc không phải nguồn chân lý của
    chữ nghĩa, `extracted_text` mới là (07 Mục 2.1).
    """
    return hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractionResult:
    """Đầu ra trọn vẹn của GĐ2 cho một file.

    Đủ để T2.1 đóng gói `IntakeRequest` (`source_format`, `content_fingerprint`,
    `extracted_text`) và để T2.3 cắt mẩu từ `read_result` — không bên nào cần
    mở lại file gốc.
    """

    source_format: str
    content_fingerprint: str
    extracted_text: str
    read_result: ReadResult


def extract_file(path: str | pathlib.Path) -> ExtractionResult:
    """GĐ2 trọn vẹn cho một file: đọc, dựng cấu trúc, sinh `extracted_text` và
    `content_fingerprint`.

    Từ chối kèm thông báo rõ (không đoán bừa, không đọc đại):
    * `DinhDangKhongNhan` — định dạng ngoài bốn định dạng v1.
    * `KhongDocDuocLopChu` — PDF không có lớp chữ (nhiều khả năng ảnh quét).
    """
    read_result = doc_file(path)
    return ExtractionResult(
        source_format=read_result.source_format,
        content_fingerprint=compute_content_fingerprint(read_result.full_text),
        extracted_text=read_result.full_text,
        read_result=read_result,
    )
