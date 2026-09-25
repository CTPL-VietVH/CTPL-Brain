"""Hai số phiên bản của chính module schema dùng chung — 07 Mục 3.1, DX3.

| Số | Tăng khi | Hai bên lệch thì |
|---|---|---|
| **Số phá vỡ tương thích** | đổi tên trường, xoá trường, đổi ý nghĩa của trường | **từ chối chạy** |
| **Số bổ sung tương thích** | thêm trường mới mà bên cũ bỏ qua được | **ghi nhật ký, vẫn chạy** |

⛔ HAI số, không phải một. 07 Mục 3.1: "nếu chỉ có một số thì mỗi lần thêm một
trường là một lần phải dừng cả hai service — và người ta sẽ nhanh chóng ngừng
tăng số, tức là mất luôn cơ chế" (CLAUDE.md Mục 3 #22).

⭐ **Số phá vỡ tăng thì số bổ sung VỀ 0** (07 Mục 3.1, quy ước chốt 25/9/2026).
Số bổ sung đếm các lần thêm trường tính từ MỘT hình dạng dữ liệu cụ thể; hình
dạng đổi thì cái đếm cũ hết nghĩa.

Vì sao hai số này nằm TRONG MÃ chứ không trong `config/`, dù quy tắc 5 của
CLAUDE.md Mục 4 cấm con số cứng trong mã: quy tắc đó nói về **tham số điều
chỉnh** — thứ người vận hành đổi để hệ thống chạy khác đi. Hai số dưới đây
không phải tham số: chúng MÔ TẢ chính bản mã đang chạy, y như tên trường trong
`document.py`. Đặt chúng ra file cấu hình là cho phép khai sai hình dạng của
mã — đúng thứ cơ chế này sinh ra để chặn.

Vì sao cần so phiên bản dù hai service nằm chung một repo: R6 — mỗi khách hàng
một bản cài đặt độc lập, và hai service **triển khai độc lập** (CLAUDE.md Mục 6:
hai service độc lập ở mức mã nguồn). Một bản cài nâng Retrieval trước, Ingestion
sau, thì hai bên đang chạy hai bản `packages/schema` khác nhau — đó là lúc hàm
dưới đây phải lên tiếng.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

__all__ = [
    "SCHEMA_BREAKING_VERSION",
    "SCHEMA_ADDITIVE_VERSION",
    "SchemaVersion",
    "LOCAL_SCHEMA_VERSION",
    "SchemaVersionError",
    "SchemaBreakingVersionMismatchError",
    "assert_schema_versions_compatible",
]

logger = logging.getLogger(__name__)


# Tăng khi: đổi tên trường, xoá trường, đổi ý nghĩa của trường.
# Hai bên lệch số này → TỪ CHỐI CHẠY.
# 1 → 2 (25/9/2026, CHUNK-mau-noi-bo): `Chunk.span_start`/`span_end` ĐỔI Ý
# NGHĨA trên mẩu của một khối CÓ con — trước: trọn khối gồm cả con cháu; sau:
# chỉ phần chữ riêng của khối. Kèm theo, `parent_chunk_id` đổi cách được dùng
# để dựng đơn vị đọc: đọc `structure_block_*` của mẩu cha, không đọc `span_*`
# của mẩu cha (07 Mục 2.2 v1.11, S2). Hai trường mới `structure_block_start` /
# `structure_block_end` tự chúng chỉ là thêm trường, NHƯNG việc đổi ý nghĩa
# của `span_*` mới là thứ quyết định nhánh: đây là PHÁ VỠ TƯƠNG THÍCH.
# Hệ quả bắt buộc, không có đường vòng: **nạp lại toàn kho**. Mẩu cắt theo
# luật cũ và mẩu cắt theo luật mới không dùng chung được, và không có bước
# nâng cấp tại chỗ nào biến cái cũ thành cái mới.
SCHEMA_BREAKING_VERSION = 2

# Tăng khi: thêm trường mới mà bên cũ bỏ qua được.
# Hai bên lệch số này → GHI NHẬT KÝ, VẪN CHẠY.
# ⭐ QUY ƯỚC (E2, PO chốt 25/9/2026, ghi thành văn ở 07 Mục 3.1): khi số PHÁ
# VỠ tương thích tăng thì số này **về 0**. Lý do: số này đếm các lần thêm
# trường TÍNH TỪ một hình dạng dữ liệu cụ thể; hình dạng đó vừa đổi, nên cái
# đếm cũ không còn nghĩa. Giữ nguyên số cũ sẽ làm hai bản cài khác nhánh phá
# vỡ nhưng trùng số bổ sung trông như đang tương thích một phần — trong khi
# thực tế chúng không nói chuyện được với nhau chút nào.
# 0 → 1 (22/9/2026, T2.4-add-subject-entities): thêm `Document.subject_entities`
# (07 Mục 2.1 dòng 93) — trường mới có mặc định, bên cũ bỏ qua được.
# 1 → 0 (25/9/2026, CHUNK-mau-noi-bo): reset theo quy ước trên, vì
# SCHEMA_BREAKING_VERSION vừa tăng 1 → 2.
SCHEMA_ADDITIVE_VERSION = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class SchemaVersion:
    """Một cặp số phiên bản của module schema — 07 Mục 3.1 (DX3).

    `frozen=True` vì đây là mô tả của một bản mã đã chạy, không phải trạng thái
    sửa được lúc chạy. `kw_only=True` để không ai gọi `SchemaVersion(1, 0)` rồi
    một ngày đảo thứ tự hai số mà không lỗi nào báo — cùng lý do bốn thực thể ở
    Mục 2 dùng `kw_only` (T1.1).
    """

    breaking: int
    additive: int

    def __str__(self) -> str:  # để thông báo lỗi đọc được
        return f"{self.breaking}.{self.additive}"


#: Phiên bản của chính bản `packages/schema/` này.
LOCAL_SCHEMA_VERSION = SchemaVersion(
    breaking=SCHEMA_BREAKING_VERSION,
    additive=SCHEMA_ADDITIVE_VERSION,
)


class SchemaVersionError(Exception):
    """Gốc cho mọi lỗi so khớp phiên bản module schema."""


class SchemaBreakingVersionMismatchError(SchemaVersionError):
    """Hai bên lệch số PHÁ VỠ tương thích → từ chối chạy (07 Mục 3.1, DX3)."""


def assert_schema_versions_compatible(
    local: SchemaVersion,
    other: SchemaVersion,
    *,
    local_name: str,
    other_name: str,
) -> None:
    """So hai bộ số phiên bản của module schema — 07 Mục 3.1, ràng buộc 3.

    - Lệch số **phá vỡ tương thích** → raise
      `SchemaBreakingVersionMismatchError`. Không có chế độ cảnh báo rồi chạy
      tiếp: một bên hiểu sai ý nghĩa của một trường là loại trừ im lặng ở tầng
      thấp nhất, cùng loại với việc cắt bớt ngầm khi tràn ngữ cảnh mà 06 Mục 6.5
      đã cấm.
    - Lệch số **bổ sung tương thích** → ghi nhật ký mức WARNING và **vẫn chạy**.
      Bên cũ bỏ qua trường mới được, nên dừng cả hệ thống ở đây là cái giá làm
      người ta ngừng tăng số.
    - Khớp cả hai → im lặng trả về `None`.

    Hàm nhận thẳng hai đối tượng phiên bản: T1.2 không có việc "hai service thật
    nói chuyện với nhau" — nơi lấy `other` (đọc từ kho, từ một điểm cuối tình
    trạng, hay từ siêu dữ liệu triển khai) là việc của bước tích hợp sau. Tách
    như vậy để phần QUYẾT ĐỊNH này test được mà không cần dựng hai service.

    `local_name` / `other_name` bắt buộc nêu tên, không có giá trị mặc định —
    một thông báo lỗi không nói rõ BÊN NÀO lệch thì người trực đêm không dùng
    được.
    """
    if local.breaking != other.breaking:
        raise SchemaBreakingVersionMismatchError(
            "Lệch SỐ PHÁ VỠ TƯƠNG THÍCH của module schema dùng chung → TỪ CHỐI CHẠY. "
            f"{local_name}: breaking={local.breaking} (phiên bản đầy đủ {local}); "
            f"{other_name}: breaking={other.breaking} (phiên bản đầy đủ {other}). "
            "Số này chỉ tăng khi đổi tên trường, xoá trường, hoặc đổi ý nghĩa "
            "của trường (07 Mục 3.1, DX3) — hai bên đang hiểu khác nhau về cùng "
            "một dữ liệu. Nâng bên cũ lên trước khi chạy tiếp."
        )

    if local.additive != other.additive:
        logger.warning(
            "Lệch SỐ BỔ SUNG TƯƠNG THÍCH của module schema dùng chung — vẫn chạy tiếp. "
            "%s: additive=%d (phiên bản đầy đủ %s); %s: additive=%d (phiên bản đầy đủ %s). "
            "Bên có số nhỏ hơn sẽ bỏ qua các trường được thêm sau (07 Mục 3.1, DX3).",
            local_name,
            local.additive,
            local,
            other_name,
            other.additive,
            other,
        )
