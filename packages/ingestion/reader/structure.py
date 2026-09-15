"""Hình dạng cây mà MỌI bộ đọc phải trả ra — điểm cắm GĐ2.

`docs/08` T2.2: *"Đây là **điểm cắm**: mọi bước sau chỉ nhận văn bản, cấu trúc,
vị trí; **không bước nào được rẽ nhánh theo định dạng gốc**."* Vì vậy bốn bộ đọc
khác nhau đều đổ về đúng một kiểu dữ liệu ở đây.

⚠️ **Tên trường trong file này là tên CỤC BỘ của tầng đọc, không phải hợp đồng
dữ liệu dùng chung.** `structure_path`, `span_start`, `span_end`,
`parent_chunk_id` là tên của module `packages/schema/` và được định nghĩa **đúng
một lần** ở đó — việc đó là T1.1, chưa làm. Tầng đọc cố ý dùng tên khác
(`char_start`, `char_end`, `path`) để không ai tưởng nó đã là hợp đồng; việc ánh
xạ sang hợp đồng nằm ở T2.2 và chỉ được viết ở **một** chỗ.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Level(enum.IntEnum):
    """Bậc trong quy chuẩn hành chính Việt Nam, từ ngoài vào trong.

    Giá trị tăng dần theo độ sâu để so sánh bậc là phép so sánh số.
    `HEADING` dành cho tài liệu không có điều khoản (quy trình, biên bản, báo
    cáo) — 07 Mục 2.2 nói rõ khi đó đơn vị là *chuỗi tiêu đề lồng nhau*.
    """

    DOCUMENT = 0
    PHAN = 1
    CHUONG = 2
    MUC = 3
    DIEU = 4
    KHOAN = 5
    DIEM = 6
    HEADING = 7   # tiêu đề tự do, dùng cho tài liệu không theo điều khoản
    BODY = 8      # đoạn văn thường, không phải tiêu đề

    @property
    def nhan(self) -> str:
        return {
            Level.DOCUMENT: "Tài liệu", Level.PHAN: "Phần", Level.CHUONG: "Chương",
            Level.MUC: "Mục", Level.DIEU: "Điều", Level.KHOAN: "Khoản",
            Level.DIEM: "Điểm", Level.HEADING: "Tiêu đề", Level.BODY: "Đoạn",
        }[self]


@dataclass
class Node:
    """Một khối cấu trúc, kèm vị trí ĐẦU/CUỐI trong toàn văn.

    ⚠️ `char_start` / `char_end` đếm theo **KÝ TỰ UNICODE**, không phải byte —
    `CLAUDE.md` Mục 5 và điều cấm số 4. Tiếng Việt có dấu, đếm nhầm thì đoạn cắt
    sai mà không lỗi nào báo.
    """

    level: Level
    marker: str          # "I", "12", "a" — số hiệu của khối, rỗng nếu không có
    heading: str         # nguyên văn dòng tiêu đề, rỗng nếu là đoạn thường
    char_start: int
    char_end: int
    children: list[Node] = field(default_factory=list)

    @property
    def path(self) -> list[str]:
        """Chuỗi đoạn từ ngoài vào trong, ví dụ ['Chương II', 'Điều 7', 'Khoản 3'].

        **Là danh sách các đoạn, KHÔNG phải một chuỗi nối lại** — 07 Mục 2.2 nói
        rõ vì quy tắc "cha là đúng một cấp lên" cần đọc được từng cấp mà không
        phải tách chuỗi.
        """
        doan = f"{self.level.nhan} {self.marker}".strip() if self.marker else self.heading.strip()
        return [doan] if doan else []

    def walk(self):
        yield self
        for con in self.children:
            yield from con.walk()

    def text(self, full_text: str) -> str:
        """Cắt nguyên văn của khối này theo vị trí ký tự."""
        return full_text[self.char_start:self.char_end]


class Outcome(enum.Enum):
    """Kết cục của một lần dựng cấu trúc.

    ⛔ Cố ý KHÔNG có giá trị nào nghĩa là *"không dựng được nên cắt theo độ dài"*.
    `docs/06` Mục 5.2 và `docs/08` T0.3 cấm rõ kiểu hỏng đó: bộ đọc không dựng
    được cấu trúc thì tài liệu **lặng lẽ rơi về cắt theo độ dài** trong khi mọi
    thứ khác tưởng vẫn bình thường. **Đường bị cấm là im lặng hạ chuẩn.**
    """

    DIEU_KHOAN = "dựng được theo Chương/Điều/Khoản/Điểm"
    TIEU_DE = "dựng được theo chuỗi tiêu đề ĐÁNH SỐ"
    TIEU_DE_PHONG_DOAN = "dựng được theo tiêu đề chữ HOA không đánh số — PHỎNG ĐOÁN"
    KHONG_DUNG_DUOC = "KHÔNG dựng được phân cấp — phải từ chối, không được cắt theo độ dài"

    @property
    def la_phong_doan(self) -> bool:
        """Cấu trúc này dựng bằng phán đoán hay bằng sự kiện?

        NT2: *sự kiện lọc trước; phán đoán đứng sau và chấp nhận bỏ sót; chỗ
        nào bỏ sót gây hại thì phải NHÌN THẤY ĐƯỢC.* Số hiệu (Điều 7, Khoản 3,
        mục 1.2) là **sự kiện** — gần như không thể xuất hiện ngẫu nhiên. Tiêu
        đề nhận ra nhờ viết HOA là **phán đoán** — và phán đoán sai sinh ra một
        cây SAI, tức đơn vị đọc sai, trong im lặng.

        Tách thành một giá trị riêng để chỗ phán đoán nhìn thấy được ở tầng
        kiểu dữ liệu, thay vì chìm trong một dòng ghi chú.
        """
        return self is Outcome.TIEU_DE_PHONG_DOAN


@dataclass
class ReadResult:
    """Đầu ra của mọi bộ đọc. Bốn định dạng, một hình dạng."""

    full_text: str
    root: Node
    outcome: Outcome
    source_format: str            # ghi lại (S4), nhưng CẤM mọi bước sau rẽ nhánh theo nó
    notes: list[str] = field(default_factory=list)

    @property
    def dung_duoc(self) -> bool:
        return self.outcome is not Outcome.KHONG_DUNG_DUOC

    def blocks(self, level: Level) -> list[Node]:
        return [n for n in self.root.walk() if n.level is level]

    def kiem_vi_tri(self) -> None:
        """Tự kiểm: mọi vị trí phải nằm trong văn bản và con phải nằm trong cha.

        Đây là loại sai lệch không bao giờ báo lỗi lúc chạy — nó chỉ làm dẫn
        nguồn trỏ sai chỗ. Nên kiểm ngay tại nguồn.
        """
        n = len(self.full_text)
        for node in self.root.walk():
            if not (0 <= node.char_start <= node.char_end <= n):
                raise ValueError(
                    f"Vị trí sai ở {node.level.nhan} {node.marker!r}: "
                    f"[{node.char_start}, {node.char_end}] ngoài [0, {n}]")
            for con in node.children:
                if con.char_start < node.char_start or con.char_end > node.char_end:
                    raise ValueError(
                        f"Khối con {con.level.nhan} {con.marker!r} tràn ra ngoài cha "
                        f"{node.level.nhan} {node.marker!r}")
