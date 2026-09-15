"""Bốn bộ đọc, một hình dạng cây — điểm cắm GĐ2.

`docs/08` T0.3 chốt thư viện: **Docling** cho PDF có lớp chữ, **python-docx**
cho .docx, parser markdown cho .md, regex cho .txt. Cả bốn đều đổ về
`vn_normalizer.dung_cau_truc`, nên cấu trúc chỉ có **một** chỗ được quyết.

⚠️ **Đừng tin Heading style của .docx.** `docs/08` B2 điểm 1: văn bản hành chính
VN soạn tay rất thường in đậm và đánh số bằng tay chứ không gán style, nên bộ
chuẩn hoá regex là **đường chính**, Heading style chỉ là đường tắt khi may mắn
có. Bộ đọc .docx ở đây vì vậy chỉ rút **văn bản phẳng** rồi giao cho regex —
đúng thứ tự ưu tiên, không ngược lại.

`source_format` được GHI LẠI nhưng **cấm mọi bước sau rẽ nhánh theo nó**
(07 Mục 6, S4).
"""

from __future__ import annotations

import pathlib

from .structure import ReadResult
from .vn_normalizer import dung_cau_truc

DINH_DANG_NHAN = {".pdf", ".docx", ".txt", ".md"}


class DinhDangKhongNhan(Exception):
    """Định dạng ngoài danh sách v1 — từ chối kèm thông báo rõ, không đoán bừa.

    `docs/08` T2.2: *"Bốn định dạng, từ chối phần còn lại kèm thông báo rõ."*
    """


class KhongDocDuocLopChu(Exception):
    """PDF không có lớp chữ (ảnh quét).

    v1 từ chối ảnh quét. Từ chối **ồn ào** là đúng; đọc ra một khối chữ rỗng
    rồi đi tiếp mới là kiểu hỏng 06 Mục 5.2 cảnh báo.
    """


def _doc_txt(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="strict")


def _doc_md(path: pathlib.Path) -> str:
    """Markdown: bỏ dấu `#` của tiêu đề, giữ nguyên chữ và thứ tự dòng.

    Không dùng thư viện dựng cây riêng cho markdown: nếu markdown tự dựng cây
    theo `#` còn các định dạng khác dựng theo regex thì sẽ có **hai** bộ quy tắc
    cấu trúc, và chúng sẽ lệch nhau. Một chỗ quyết cấu trúc, không hai.
    """
    raw = path.read_text(encoding="utf-8")
    dong = []
    trong_khoi_ma = False
    for ln in raw.split("\n"):
        if ln.lstrip().startswith("```"):
            trong_khoi_ma = not trong_khoi_ma
            continue
        if not trong_khoi_ma and ln.lstrip().startswith("#"):
            ln = ln.lstrip().lstrip("#").strip()
        dong.append(ln)
    return "\n".join(dong)


def _doc_docx(path: pathlib.Path) -> str:
    """.docx → văn bản phẳng, mỗi đoạn một dòng. Bảng đọc theo hàng.

    Cố ý **không** đọc `paragraph.style.name` để suy phân cấp — xem ghi chú đầu
    file. Regex quyết cấu trúc.
    """
    import docx  # python-docx

    tai_lieu = docx.Document(str(path))
    dong: list[str] = []

    # Duyệt theo đúng thứ tự xuất hiện trong thân tài liệu (đoạn xen bảng)
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = tai_lieu.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            dong.append(Paragraph(child, tai_lieu).text)
        elif tag == "tbl":
            for row in Table(child, tai_lieu).rows:
                o = [c.text.strip().replace("\n", " ") for c in row.cells]
                dong.append(" | ".join(o))
    return "\n".join(dong)


# Hai dòng cách nhau dưới ngưỡng này thì coi là CÙNG một dòng bố cục.
# Đơn vị là point của PDF; 3pt nhỏ hơn mọi khoảng cách dòng thực tế.
_NGUONG_CUNG_DONG_PT = 3.0

# Khe hở ngang giữa hai ô chữ liền nhau. Dưới ngưỡng này thì NỐI THẲNG, không
# chèn dấu cách.
#
# ⚠️ Vì sao cần: PDF văn bản pháp luật VN thường tách ký tự có dấu thành ô
# RIÊNG (font khác cho phần dấu). Đo thật trên Thông tư 01/2011/TT-BNV:
#   l=188.35 r=266.72 'CÔNG BÁO/S'
#   l=266.73 r=273.23 'ố'              ← khe hở 0.01pt
# Nối mù bằng dấu cách cho ra "CÔNG BÁO/S ố", "B Ộ  N Ộ I V Ụ", "Ngh ị đị nh".
# Khi ấy chuỗi "Điều" KHÔNG BAO GIỜ khớp, và cả tài liệu tụt xuống TIEU_DE với
# 0 Điều — hỏng hoàn toàn im lặng, vì vẫn "dựng ra được một cây".
#
# Bản thân ô đã mang sẵn dấu cách khi PDF có dấu cách thật (' N', ' 93 + 94'),
# nên chỗ nào liền nhau thì nối thẳng là đúng.
_NGUONG_CACH_CHU_PT = 1.5


def _doc_pdf(path: pathlib.Path) -> str:
    """PDF có lớp chữ → văn bản GIỮ NGUYÊN DÒNG, qua backend của Docling.

    ⚠️ **Cố ý KHÔNG dùng `export_to_markdown()`.** Đo thật ở T0.3: tầng phân
    tích bố cục của Docling **gộp các dòng thành đoạn** — "Điều 1. Phạm vi điều
    chỉnh" và "1. Quy chế này..." bị nối thành một dòng, còn "a)" / "b)" bị
    nuốt vào đoạn trước. Với văn bản hành chính VN thì **ngắt dòng CHÍNH LÀ
    tín hiệu cấu trúc**, nên gộp dòng là làm mất thứ ta cần nhất.

    Tầng backend vẫn giữ ô chữ kèm toạ độ, nên ở đây dựng lại dòng theo toạ độ
    y rồi giao cho regex. Vẫn là Docling — công nghệ đã chốt 14/9 không đổi —
    chỉ là dùng đúng tầng.

    Ghi nhận cho PO: `docs/08` T0.3 kỳ vọng Docling *"xuất cây có phân cấp tiêu
    đề"*. Với văn bản hành chính VN thì phần đáng giá của Docling hoá ra là
    **rút chữ kèm toạ độ**, không phải phần suy ra phân cấp. Điều này khớp với
    chính cảnh báo ở B2 điểm 1, chỉ là mở rộng từ .docx sang cả PDF.
    """
    from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.document import InputDocument

    ind = InputDocument(path_or_stream=path, format=InputFormat.PDF,
                        backend=DoclingParseDocumentBackend, filename=path.name)
    backend = DoclingParseDocumentBackend(ind, path)

    def _ghep_dong(o: list[tuple[float, float, str]]) -> str:
        """Ghép các ô trong một dòng, quyết định dấu cách theo KHE HỞ NGANG."""
        o = sorted(o, key=lambda c: c[0])
        ra: list[str] = []
        phai_truoc: float | None = None
        for trai, phai, txt in o:
            if phai_truoc is not None and trai - phai_truoc > _NGUONG_CACH_CHU_PT:
                ra.append(" ")
            ra.append(txt)
            phai_truoc = phai
        return "".join(ra)

    dong_tat_ca: list[str] = []
    for so_trang in range(backend.page_count()):
        trang = backend.load_page(so_trang)
        o_chu: list[tuple[float, float, float, str]] = []
        for cell in trang.get_text_cells():
            if cell.text.strip():
                b = cell.rect.to_bounding_box()
                o_chu.append((b.t, b.l, b.r, cell.text))

        # Gom ô thành dòng theo toạ độ y, rồi ghép trong dòng theo x
        o_chu.sort(key=lambda c: (c[0], c[1]))
        dong_hien_tai: list[tuple[float, float, str]] = []
        y_dong: float | None = None
        for y, trai, phai, txt in o_chu:
            if y_dong is None or abs(y - y_dong) <= _NGUONG_CUNG_DONG_PT:
                dong_hien_tai.append((trai, phai, txt))
                y_dong = y if y_dong is None else y_dong
            else:
                dong_tat_ca.append(_ghep_dong(dong_hien_tai))
                dong_hien_tai = [(trai, phai, txt)]
                y_dong = y
        if dong_hien_tai:
            dong_tat_ca.append(_ghep_dong(dong_hien_tai))

    text = "\n".join(dong_tat_ca)

    if len(text.strip()) < 50:
        raise KhongDocDuocLopChu(
            f"{path.name}: gần như không rút được chữ nào ({len(text.strip())} ký tự). "
            f"Nhiều khả năng là ảnh quét — v1 từ chối ảnh quét. "
            f"KHÔNG đi tiếp với văn bản rỗng.")
    return text


_BO_DOC = {".txt": _doc_txt, ".md": _doc_md, ".docx": _doc_docx, ".pdf": _doc_pdf}


def doc_file(path: str | pathlib.Path) -> ReadResult:
    """Đọc một file bất kỳ trong bốn định dạng v1, trả về cùng một hình dạng cây."""
    path = pathlib.Path(path)
    duoi = path.suffix.lower()

    if duoi not in DINH_DANG_NHAN:
        raise DinhDangKhongNhan(
            f"{path.name}: v1 chỉ nhận {', '.join(sorted(DINH_DANG_NHAN))}. "
            f"Định dạng '{duoi}' bị từ chối — nêu rõ thay vì đọc đại.")
    if not path.is_file():
        raise FileNotFoundError(path)

    raw = _BO_DOC[duoi](path)
    return dung_cau_truc(raw, source_format=duoi.lstrip("."))
