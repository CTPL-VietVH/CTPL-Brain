"""Bộ chuẩn hoá cây cấu trúc theo quy chuẩn hành chính Việt Nam.

**Đây là ĐƯỜNG CHÍNH, không phải dự phòng.** `docs/08` T0.3 và B2 điểm 1 nói
rõ: văn bản hành chính Việt Nam soạn tay rất thường in đậm và đánh số bằng tay
chứ không gán Heading style, nên *"bộ chuẩn hoá regex nhiều khả năng là đường
chính cho cả .docx, và Heading style chỉ là đường tắt khi may mắn có"*.

Bậc nhận diện: **Phần › Chương › Mục › Điều › Khoản › Điểm**.

⛔ Khi không dựng được phân cấp, hàm ở đây trả `Outcome.KHONG_DUNG_DUOC` và
**không bao giờ** tự cắt theo độ dài. Bên gọi phải xử lý; im lặng hạ chuẩn là
đường bị cấm (`docs/06` Mục 5.2, `docs/08` T0.3).
"""

from __future__ import annotations

import re
import unicodedata

from .structure import Level, Node, Outcome, ReadResult

# --- Bảng chữ cái tiếng Việt dùng đánh Điểm: a, b, c, d, đ, e, ê, g, ... ---
CHU_CAI_DIEM = "abcdđeêghiklmnoôơpqrstuưvxy"

# Số La Mã hoặc số Ả Rập — văn bản thật dùng lẫn cả hai
_SO = r"(?:[IVXLCDM]+|\d+)"

# Mỗi mẫu phải neo ở ĐẦU DÒNG. Đây là điều giữ cho bộ nhận diện không bắt nhầm
# một cụm giữa câu (ví dụ "... quy định tại Điều 7 của Nghị định này ...").
MAU = {
    Level.PHAN: re.compile(
        rf"^[ \t]*PHẦN\s+(?:THỨ\s+)?({_SO}|[A-ZĐ]|MỘT|HAI|BA|BỐN|NĂM|SÁU|BẢY|TÁM|CHÍN|MƯỜI)\b[ \t]*[:.．]?[ \t]*(.*)$",
        re.IGNORECASE | re.MULTILINE),
    Level.CHUONG: re.compile(
        rf"^[ \t]*CHƯƠNG\s+({_SO})\b[ \t]*[:.．]?[ \t]*(.*)$",
        re.IGNORECASE | re.MULTILINE),
    Level.MUC: re.compile(
        rf"^[ \t]*MỤC\s+({_SO})\b[ \t]*[:.．]?[ \t]*(.*)$",
        re.IGNORECASE | re.MULTILINE),
    Level.DIEU: re.compile(
        r"^[ \t]*Điều\s+(\d+[a-zđ]?)\b[ \t]*[.．:]?[ \t]*(.*)$",
        re.IGNORECASE | re.MULTILINE),
    Level.KHOAN: re.compile(
        r"^[ \t]*(\d+)[ \t]*[.)．][ \t]+(.*)$",
        re.MULTILINE),
    Level.DIEM: re.compile(
        rf"^[ \t]*([{CHU_CAI_DIEM}])[ \t]*[)．.][ \t]+(.*)$",
        re.MULTILINE),
}

# Tiêu đề tự do cho tài liệu KHÔNG theo điều khoản (quy trình, biên bản, báo cáo):
# "1.2.3 Tiêu đề" hoặc "III. Tiêu đề"
MAU_TIEU_DE_SO = re.compile(
    r"^[ \t]*((?:\d+\.){1,4}\d*|[IVXLCDM]+\.)[ \t]+(\S.*)$", re.MULTILINE)


def chuan_hoa_van_ban(raw: str) -> str:
    """Chuẩn hoá NFC và thống nhất xuống dòng — làm MỘT LẦN, trước mọi phép đếm.

    ⚠️ Bắt buộc phải chạy trước khi tính bất kỳ vị trí nào. Tiếng Việt có hai
    cách mã hoá dấu (tổ hợp và dựng sẵn); cùng một chữ có thể dài 1 hoặc 2 ký
    tự Unicode tuỳ nguồn. Không chuẩn hoá thì `char_start` tính ở Ingestion và
    `SUBSTRING` chạy ở Retrieval đếm ra hai con số khác nhau — và **không lỗi
    nào báo**, y hệt cái bẫy byte-vs-ký-tự ở điều cấm số 4.
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    # Bỏ khoảng trắng cuối dòng — không đổi nghĩa, nhưng giữ vị trí ổn định
    return "\n".join(line.rstrip() for line in text.split("\n"))


def _la_dong_tieu_de_thuc(text: str, m: re.Match, level: Level) -> bool:
    """Lọc bớt bắt nhầm.

    Chặn hai kiểu nhầm hay gặp nhất:
      * "Khoản" bắt nhầm một dòng trong bảng số liệu hoặc một mốc ngày tháng.
      * "Điểm" bắt nhầm một gạch đầu dòng trong đoạn văn xuôi.
    """
    noi_dung = (m.group(2) or "").strip()
    if level in (Level.KHOAN, Level.DIEM):
        if not noi_dung:
            return False
        # "1. 2. 3." liền nhau kiểu mục lục thì bỏ
        if re.fullmatch(r"[\d.\s]+", noi_dung):
            return False
    return True


class Moc:
    """Một dấu hiệu bậc tìm thấy trong văn bản.

    `depth` (độ sâu trong cây) tách khỏi `level` (nhãn ngữ nghĩa) có chủ ý: với
    văn bản theo điều khoản hai thứ trùng nhau, nhưng với tài liệu đánh số kiểu
    "1.2.3" thì độ sâu suy từ số dấu chấm và có thể sâu tuỳ ý, trong khi nhãn
    vẫn chỉ là *Tiêu đề*. Nhồi cả hai vào một enum là chỗ bản nháp trước sai.
    """

    __slots__ = ("pos", "depth", "level", "marker", "heading")

    def __init__(self, pos: int, depth: int, level: Level, marker: str, heading: str):
        self.pos, self.depth, self.level = pos, depth, level
        self.marker, self.heading = marker, heading


def _thu_thap(text: str) -> list[Moc]:
    """Gom mọi dấu hiệu bậc, sắp theo vị trí. Chỗ trùng thì bậc NGOÀI thắng."""
    found: dict[int, Moc] = {}
    for level, mau in MAU.items():
        for m in mau.finditer(text):
            if not _la_dong_tieu_de_thuc(text, m, level):
                continue
            pos = m.start()
            cu = found.get(pos)
            if cu is None or level < cu.level:
                found[pos] = Moc(pos, int(level), level, m.group(1),
                                 (m.group(2) or "").strip())
    return sorted(found.values(), key=lambda x: x.pos)


def _dung_cay(text: str, moc: list[Moc]) -> Node:
    """Dựng cây từ danh sách mốc đã sắp.

    Vị trí cuối của một khối là đầu của mốc kế tiếp có độ sâu **nông hơn hoặc
    bằng** — nhờ vậy khối con luôn nằm trọn trong khối cha, điều mà
    `ReadResult.kiem_vi_tri()` kiểm lại ngay sau đó.
    """
    root = Node(Level.DOCUMENT, "", "", 0, len(text))
    ngan_xep: list[tuple[int, Node]] = [(0, root)]

    for i, m in enumerate(moc):
        ket_thuc = len(text)
        for sau in moc[i + 1:]:
            if sau.depth <= m.depth:
                ket_thuc = sau.pos
                break

        node = Node(m.level, m.marker, m.heading, m.pos, ket_thuc)
        while len(ngan_xep) > 1 and ngan_xep[-1][0] >= m.depth:
            ngan_xep.pop()
        ngan_xep[-1][1].children.append(node)
        ngan_xep.append((m.depth, node))

    return root


def dung_cau_truc(raw: str, source_format: str) -> ReadResult:
    """Dựng cây cấu trúc từ văn bản thô. Không dựng được thì NÓI RA."""
    text = chuan_hoa_van_ban(raw)
    notes: list[str] = []

    moc = _thu_thap(text)
    so_dieu = sum(1 for m in moc if m.level is Level.DIEU)
    so_chuong = sum(1 for m in moc if m.level is Level.CHUONG)

    # Đường 1 — văn bản theo điều khoản. `Điều` là neo: có Điều thì coi là
    # văn bản quy phạm, vì "Điều N." ở đầu dòng gần như không xuất hiện ngẫu nhiên.
    if so_dieu >= 1:
        root = _dung_cay(text, moc)
        notes.append(f"{so_chuong} Chương, {so_dieu} Điều")
        kq = ReadResult(text, root, Outcome.DIEU_KHOAN, source_format, notes)
        kq.kiem_vi_tri()
        return kq

    # Đường 2 — tài liệu không có điều khoản: chuỗi tiêu đề lồng nhau (07 Mục 2.2)
    moc_tieu_de: list[Moc] = []
    for m in MAU_TIEU_DE_SO.finditer(text):
        marker = m.group(1).rstrip(".")
        # Độ sâu suy từ số dấu chấm: "1"→1, "1.2"→2, "1.2.3"→3; La Mã luôn bậc 1
        do_sau = marker.count(".") + 1 if marker[0].isdigit() else 1
        moc_tieu_de.append(Moc(m.start(), do_sau, Level.HEADING, marker,
                               m.group(2).strip()))
    if len(moc_tieu_de) >= 2:
        root = _dung_cay(text, moc_tieu_de)
        sau_nhat = max(m.depth for m in moc_tieu_de)
        notes.append(f"{len(moc_tieu_de)} tiêu đề đánh số, lồng sâu nhất {sau_nhat} bậc")
        kq = ReadResult(text, root, Outcome.TIEU_DE, source_format, notes)
        kq.kiem_vi_tri()
        return kq

    # Đường 3 — tiêu đề chữ HOA KHÔNG đánh số. Rất phổ biến ở biên bản, tờ
    # trình, báo cáo VN ("CĂN CỨ NGHIỆM THU", "THÔNG TIN CÁC BÊN").
    #
    # ⚠️ Đây là PHỎNG ĐOÁN, không phải sự kiện như số hiệu. Vì vậy nó xếp SAU
    # hai đường trên (NT2: sự kiện lọc trước, phán đoán đứng sau) và mang một
    # giá trị `Outcome` riêng để chỗ phán đoán nhìn thấy được.
    moc_hoa = _thu_thap_tieu_de_chu_hoa(text)
    if len(moc_hoa) >= 2:
        root = _dung_cay(text, moc_hoa)
        notes.append(f"{len(moc_hoa)} tiêu đề chữ HOA không đánh số")
        notes.append("⚠️ Cấu trúc này dựng bằng PHỎNG ĐOÁN (chữ HOA), không phải "
                     "bằng số hiệu. Đơn vị đọc suy ra từ đây kém chắc chắn hơn.")
        kq = ReadResult(text, root, Outcome.TIEU_DE_PHONG_DOAN, source_format, notes)
        kq.kiem_vi_tri()
        return kq

    # ⛔ Không dựng được. KHÔNG cắt theo độ dài. Nói ra và để bên gọi quyết.
    notes.append(
        "Không tìm thấy dấu hiệu Chương/Điều/Khoản/Điểm, không có chuỗi tiêu đề "
        "đánh số, cũng không có tiêu đề chữ HOA. KHÔNG rơi về cắt theo độ dài — "
        "docs/06 Mục 5.2 cấm.")
    return ReadResult(text, Node(Level.DOCUMENT, "", "", 0, len(text)),
                      Outcome.KHONG_DUNG_DUOC, source_format, notes)


# Dòng nghi thức đầu văn bản hành chính VN — là quốc hiệu, KHÔNG phải tiêu đề mục.
_QUOC_HIEU = (
    "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM",
    "ĐỘC LẬP - TỰ DO - HẠNH PHÚC", "ĐỘC LẬP – TỰ DO – HẠNH PHÚC",
)
_DAI_TIEU_DE_HOA = 80   # tiêu đề mục hiếm khi dài hơn chừng này


def _thu_thap_tieu_de_chu_hoa(text: str) -> list[Moc]:
    """Nhận tiêu đề mục viết HOA, không đánh số. Cố ý DÈ DẶT.

    Dè dặt hơn là bắt trượt, vì một cây SAI sinh ra đơn vị đọc sai trong im
    lặng — còn bắt trượt thì rơi xuống `KHONG_DUNG_DUOC`, tức là nhìn thấy được.
    """
    moc: list[Moc] = []
    vi_tri = 0
    dong_list = text.split("\n")

    for i, dong in enumerate(dong_list):
        dau_dong = vi_tri
        vi_tri += len(dong) + 1  # +1 cho ký tự xuống dòng

        s = dong.strip()
        if not (2 <= len(s) <= _DAI_TIEU_DE_HOA):
            continue
        if s.upper().rstrip(" .:-–—") in [q.upper() for q in _QUOC_HIEU]:
            continue
        chu = [c for c in s if c.isalpha()]
        if len(chu) < 3:
            continue
        if not all(c.isupper() for c in chu):
            continue
        # Phải có nội dung thường theo sau, nếu không thì đây là dòng trang trí
        con_lai = [d.strip() for d in dong_list[i + 1:i + 4] if d.strip()]
        if not con_lai:
            continue
        moc.append(Moc(dau_dong, 1, Level.HEADING, "", s))

    return moc
