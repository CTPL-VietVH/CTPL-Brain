"""`chunk` — đơn vị cắt và vector (07 Mục 2.2).

Nơi cư trú: kho vector (Qdrant). Đây là đơn vị để TÌM, không phải đơn vị để
ĐỌC (Mục 6.1 của 06).

⚠️ QT2 — payload cạnh mẩu CHỈ được chứa các trường dưới đây, không hơn. Đây
là whitelist tuyệt đối: bất kỳ trường nào khác — kể cả trường hợp lệ ở
`Document` như `title`, `effective_date`, hay `approval_state` của
`Relation` — đặt vào đây đều là vi phạm (07 Mục 5).

Whitelist hiện là **mười hai** trường (07 Mục 2.2 v1.11, 25/9/2026 — trước đó
là mười).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, kw_only=True)
class Chunk:
    """Mẩu cắt — 07 Mục 2.2.

    `span_start`/`span_end` đếm theo KÝ TỰ UNICODE, không phải byte — lệch
    cách đếm thì đoạn cắt sai, không lỗi nào báo, chỉ là dẫn nguồn sai chỗ
    (07 Mục 2.2, CLAUDE.md Mục 3 #4).

    Mẩu KHÔNG giữ bản sao chữ của mình; chữ nằm ở `Document.extracted_text`
    duy nhất, mẩu chỉ giữ vị trí. Nó giữ **HAI cặp vị trí, không phải một**
    (07 Mục 2.2 v1.11, chốt 25/9/2026):

    * `span_start`/`span_end` — đúng đoạn chữ ĐÃ ĐƯỢC ĐEM TẠO VECTOR.
    * `structure_block_start`/`structure_block_end` — TRỌN khối cấu trúc mà
      mẩu này thuộc về.

    Ba ca, đủ để không phải đoán:

    | Mẩu của | `span_*` | `structure_block_*` |
    |---|---|---|
    | Khối CÓ con (Chương, Mục, Điều có Khoản) | phần chữ RIÊNG: từ đầu khối tới ngay trước con đầu tiên | trọn khối, gồm cả con cháu |
    | Khối KHÔNG con, không bị chia | trọn khối | **bằng đúng** `span_*` |
    | Một mảnh của khối KHÔNG con bị chia vì vượt `chunk_length_cap` | mảnh đó | **trọn khối gốc** — mọi mảnh cùng một giá trị (E1, PO chốt 25/9/2026) |

    Bất biến, kiểm ở `tests/t2_3_chunking/`:

    1. `structure_block_start <= span_start < span_end <= structure_block_end`
       cho chính mẩu đó; và
    2. `structure_block_*` của một mẩu CHA bao trọn `span_*` **và**
       `structure_block_*` của MỌI mẩu con cháu, không chỉ của chính nó (E3,
       PO chốt 25/9/2026).

    ⚠️ **Vì sao phải tách hai cặp — và vì sao đây là thay đổi PHÁ VỠ TƯƠNG
    THÍCH.** Bản trước để `span_*` của một khối CÓ con bao trùm toàn bộ con
    cháu. Đo thật 24/9/2026 trên 36 tài liệu (21 văn bản hành chính + 15 tài
    liệu doanh nghiệp): cách đó làm **18/36 tài liệu không nạp được** — 47 mẩu
    vượt trần ngữ cảnh 8192 token của mô hình biểu diễn, mẩu nặng nhất
    **233.712 token**, và **47/48 mẩu vượt trần đều là mẩu của khối có con**;
    mỗi ký tự của kho còn bị đem tạo vector **3,48 lần**. Sửa xong: mẩu vượt
    trần còn 1, token đem tạo vector còn 1,02 lần kho, 34/36 tài liệu nạp
    được. Nhưng `span_*` trên mẩu của khối có con **ĐỔI Ý NGHĨA**, nên theo 07
    Mục 3.1 đây là nhánh PHÁ VỠ tương thích: mẩu cũ trong kho và mẩu mới không
    dùng chung được, bắt buộc **nạp lại toàn kho**, không có đường nâng cấp
    tại chỗ.

    Đơn vị ĐỌC (S2) lấy được bằng cách theo `parent_chunk_id` rồi cắt
    `extracted_text` theo `structure_block_start`/`structure_block_end` **CỦA
    MẨU CHA** — không phải theo `span_*` của mẩu cha. `parent_chunk_id` để
    trống nếu mẩu đã là đơn vị cấu trúc cao nhất của tài liệu; khi đó đơn vị
    đọc là trọn khối của CHÍNH NÓ, tức `structure_block_*` của nó (S2 quy tắc
    con 2) — không phải mảnh `span_*`, để một khối dài bị chia nhỏ vẫn được
    đọc trọn vẹn.

    `category_labels` là NGOẠI LỆ DUY NHẤT của QT2: một bản sao để xếp hạng
    nhanh, chấp nhận phải gán lại toàn bộ mẩu khi đổi cách phân loại.
    """

    chunk_id: str
    document_id: str
    space_id: str
    tenant_id: str
    structure_path: list[str]
    span_start: int
    span_end: int
    # ⛔ CỐ Ý KHÔNG CÓ GIÁ TRỊ MẶC ĐỊNH. Một mẩu không biết khối của mình nằm
    # đâu thì đơn vị ĐỌC không dựng được — và một mặc định (0, hay None) biến
    # việc đó thành một đoạn đọc rỗng hoặc sai chỗ mà KHÔNG lỗi nào báo, đúng
    # loại hỏng im lặng mà cặp vị trí này sinh ra để chặn. Thiếu thì phải nổ
    # ngay lúc dựng đối tượng.
    structure_block_start: int
    structure_block_end: int
    embedding: list[float]

    parent_chunk_id: str | None = None
    category_labels: list[str] = field(default_factory=list)
