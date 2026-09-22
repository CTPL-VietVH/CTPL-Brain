"""GĐ3 — Cắt mẩu (T2.3, 06 Mục 5.2 GĐ3, 07 Mục 2.2, S2).

Cầu nối giữa cây cấu trúc của GĐ2 (`ReadResult.root`, dựng ở T0.3/T2.2) và
danh sách `Chunk` mà kho vector cần (07 Mục 2.2, QT2).

`06` Mục 5.2 GĐ3 định nghĩa GĐ3 gồm HAI bước có thứ tự:

1. **Cấu trúc quyết định ranh giới** — mỗi khối cấu trúc là một mẩu. Ba điều
   cấm: không được GỘP hai khối cấu trúc làm một mẩu; không được cắt NGANG
   ranh giới điều/khoản; khối đủ ngắn thì là một mẩu, hết việc.
2. **Ý nghĩa chia nhỏ TIẾP một khối cấu trúc quá dài** — CHỈ áp dụng cho
   Chunk LÁ (Node không có con). Một Node cha/nội bộ luôn có `char_start`/
   `char_end` BAO TRÙM toàn bộ nội dung con cháu (bất biến kiểm ở
   `structure.py` — `ReadResult.kiem_vi_tri`), nên span dài của một Node nội
   bộ là cộng dồn từ con cháu, KHÔNG PHẢI bằng chứng nội dung riêng của nó
   quá dài — module này TUYỆT ĐỐI không chia nhỏ Node nội bộ.

Trần độ dài (Điểm mở #4, `06` Mục 10) là **tham số bắt buộc, không mặc
định** (`tran_do_dai_mau` của `cat_thanh_mau`) — CLAUDE.md Mục 4 quy tắc 2
cấm giá trị mặc định trong mã. PO đã chốt giá trị sống là **5000 ký tự
Unicode** (21/9/2026), nhưng giá trị đó KHÔNG hardcode ở đây: work-order của
bước này cố ý không cho module chạm `packages/schema/` (nơi ba nhóm cấu hình
sống), nên việc đưa 5000 vào đúng MỘT nhà cấu hình (khả năng: một khoá mới
trong `config/ingestion.yaml`, theo đúng khuôn các tham số khác ở đó) là
việc của bên gọi (nơi lắp ráp pipeline), không phải của module này.

Cơ chế chia bước 2: chỉ cắt tại ranh giới AN TOÀN có sẵn trong văn bản —
đoạn (dòng trống) trước, câu (dấu kết câu) nếu đoạn vẫn quá dài. Các mẩu con
liền kề được đóng gói THAM LAM tới gần trần để tránh sinh nhiều mẩu rất
ngắn, nhưng không bao giờ cắt bên trong một câu. Một đoạn/câu tự nó đã vượt
trần (không còn ranh giới an toàn để chia tiếp — ví dụ bảng số liệu nhúng
trong văn bản) thì module này KHÔNG bịa cách cắt cứng theo số ký tự; nó nổ
`KhoiVuotTranKhongTheChia` để việc đó được người xem trực tiếp, đúng tinh
thần "loại trừ phải nhìn thấy được" (NT2) — không lặng lẽ hạ chuẩn.

**Mỗi Node trong cây (trừ gốc `Level.DOCUMENT`) sinh ra ÍT NHẤT MỘT
`Chunk`** — đúng một, trừ khi là Chunk LÁ vượt trần và được chia thành nhiều
mẩu con. Các mẩu con cùng gốc giữ NGUYÊN `structure_path` của Node lá gốc và
CÙNG một `parent_chunk_id` (chính là `chunk_id` của khối cha một cấp lên,
không đôn thêm tầng nào) — phân biệt nhau chỉ bằng `span_start`/`span_end`.
Đây là cách duy nhất khớp với 07 Mục 2.2: `parent_chunk_id` "con trỏ tới
khối cấu trúc CHA, chính là đơn vị ĐỌC" — muốn tra được vị trí (`span_start`/
`span_end`) của khối cha qua `parent_chunk_id` thì khối cha đó phải có mặt
là một `Chunk` thật, không phải một khái niệm ảo. Gốc `Level.DOCUMENT` không
sinh `Chunk` — `Node.path` của nó luôn rỗng (`vn_normalizer._dung_cay`), và
nó không phải "khối cấu trúc" theo nghĩa 07 Mục 2.2, chỉ là điểm neo của cây.

`embedding` (GĐ6/T2.5, ngoài phạm vi T2.3) được khởi tạo `[]` — placeholder
hợp lệ với kiểu `list[float]` của `Chunk` (07 Mục 2.2 không cho trường này
giá trị mặc định, và việc sửa `Chunk` không thuộc quyền của T2.3). T2.5 điền
vector thật vào sau, cùng đối tượng `Chunk` này (`Chunk` không `frozen`).
"""

from __future__ import annotations

import re
import uuid

from schema.chunk import Chunk

from .reader.structure import Node, ReadResult

__all__ = ["KhongDungDuocCauTruc", "KhoiVuotTranKhongTheChia", "cat_thanh_mau"]


class KhongDungDuocCauTruc(Exception):
    """`ReadResult.dung_duoc` là `False` — GĐ2 không dựng được phân cấp.

    GĐ3 cắt THEO CẤU TRÚC (06 Mục 5.2 GĐ3); không có cấu trúc thì không có
    ranh giới để cắt. Từ chối ồn ào ở đây, KHÔNG lặng lẽ coi toàn văn là một
    mẩu duy nhất — đúng kiểu "im lặng hạ chuẩn" mà 06 Mục 5.2 cấm.
    """


class KhoiVuotTranKhongTheChia(Exception):
    """Bước 2: một khối cấu trúc LÁ vượt trần, và một ĐOẠN hoặc CÂU đơn lẻ
    bên trong nó cũng tự nó đã vượt trần — không còn ranh giới an toàn nào
    (đoạn/câu) để chia tiếp.

    Cố ý KHÔNG rơi về cắt cứng theo số ký tự — đó chính là việc bị cấm
    (06 Mục 5.2, CLAUDE.md Mục 0 điều tuyệt đối #3: không tự quyết điểm mở).
    Nổ ồn ào để người xem trực tiếp khối này, kèm `structure_path` và vị trí
    tuyệt đối trong `extracted_text` để tìm đúng chỗ.
    """


# ---------------------------------------------------------------------------
# Bước 2 — chia nhỏ TIẾP một Chunk LÁ vượt trần, chỉ tại ranh giới an toàn.
# ---------------------------------------------------------------------------

# Ranh giới ĐOẠN: một hay nhiều dòng trống liên tiếp. `full_text` đã qua
# `chuan_hoa_van_ban` (NFC, xuống dòng thống nhất, hết khoảng trắng cuối
# dòng) trước khi tới đây, nên "\n\n+" là ranh giới đoạn an toàn.
_MAU_RANH_GIOI_DOAN = re.compile(r"\n\n+")

# Dấu kết câu — không dùng danh sách từ khoá viết tắt, xem `_tim_diem_cat_cau`.
_KY_TU_KET_CAU = ".!?…"


def _tim_diem_cat_cau(text: str) -> list[int]:
    """Vị trí NGAY SAU mỗi ranh giới câu hợp lệ trong `text` (offset tương đối).

    Một dấu kết câu là ranh giới THẬT khi ký tự tiếp theo (bỏ qua khoảng
    trắng ngang) KHÔNG phải chữ số — đây là cách né bẫy dấu chấm phân cách
    hàng nghìn trong số liệu (ví dụ bảng kế toán "1.234.567") mà không cần
    dò từng mẫu số cụ thể: sau dấu chấm phân cách luôn là một chữ số, sau
    dấu kết câu thật thì không.
    """
    n = len(text)
    diem: list[int] = []
    for i, ch in enumerate(text):
        if ch not in _KY_TU_KET_CAU:
            continue
        j = i + 1
        while j < n and text[j] in " \t":
            j += 1
        if j < n and text[j].isdigit():
            continue
        diem.append(j)
    return diem


def _chia_theo_diem_cat(text: str, diem_cat: list[int]) -> list[tuple[int, int]]:
    """Chia `text` tại các điểm cắt (offset tương đối) thành các đoạn liền
    mạch, không mất ký tự nào — khác `_MAU_RANH_GIOI_DOAN` (loại bỏ phần
    khớp), điểm cắt câu không loại bỏ gì, chỉ tách."""
    bien = sorted(set([0, *diem_cat, len(text)]))
    return [(bien[i], bien[i + 1]) for i in range(len(bien) - 1) if bien[i] < bien[i + 1]]


def _chia_nho_la(
    node: Node,
    full_text: str,
    *,
    tran_do_dai_mau: int,
    structure_path: list[str],
) -> list[tuple[int, int]]:
    """Chia span TUYỆT ĐỐI của một Chunk LÁ vượt `tran_do_dai_mau` thành các
    khoảng con an toàn — đoạn trước, câu nếu đoạn vẫn quá dài, đóng gói tham
    lam để tránh sinh nhiều mẩu rất ngắn.

    Trả về `[(node.char_start, node.char_end)]` (một khoảng, không chia) khi
    khối đã đủ ngắn — GĐ3 bước 1 điều cấm 3: khối đủ ngắn thì là MỘT mẩu.

    Raises:
        KhoiVuotTranKhongTheChia: một đoạn hoặc câu đơn lẻ vẫn vượt trần sau
        khi đã cắt tại ranh giới an toàn nhỏ nhất còn lại.
    """
    if node.char_end - node.char_start <= tran_do_dai_mau:
        return [(node.char_start, node.char_end)]

    text = full_text[node.char_start:node.char_end]

    # `node.char_end` là vị trí BẮT ĐẦU của mốc kế tiếp (structure.py
    # `_dung_cay`), nên đuôi `text` gần như luôn là khoảng trắng/dòng trống
    # trước mốc đó — một trận khớp ranh giới đoạn CHẠM ĐÚNG cuối `text` không
    # có nội dung nào theo sau để tách; loại nó khỏi danh sách ranh giới thay
    # vì để nó nuốt mất khoảng trắng đuôi, tránh mẩu con cuối cùng hụt mất vài
    # ký tự so với `node.char_end` thật.
    ranh_gioi_doan = [
        (m.start(), m.end())
        for m in _MAU_RANH_GIOI_DOAN.finditer(text)
        if m.end() != len(text)
    ]
    don_vi_doan: list[tuple[int, int]] = []
    vi_tri = 0
    for bat_dau, ket_thuc in ranh_gioi_doan:
        if bat_dau > vi_tri:
            don_vi_doan.append((vi_tri, bat_dau))
        vi_tri = ket_thuc
    if vi_tri < len(text):
        don_vi_doan.append((vi_tri, len(text)))

    don_vi: list[tuple[int, int]] = []
    for bat_dau, ket_thuc in don_vi_doan:
        if ket_thuc - bat_dau <= tran_do_dai_mau:
            don_vi.append((bat_dau, ket_thuc))
            continue

        doan_text = text[bat_dau:ket_thuc]
        for cau_bat_dau, cau_ket_thuc in _chia_theo_diem_cat(
            doan_text, _tim_diem_cat_cau(doan_text)
        ):
            do_dai_cau = cau_ket_thuc - cau_bat_dau
            if do_dai_cau > tran_do_dai_mau:
                vi_tri_tuyet_doi_dau = node.char_start + bat_dau + cau_bat_dau
                vi_tri_tuyet_doi_cuoi = node.char_start + bat_dau + cau_ket_thuc
                raise KhoiVuotTranKhongTheChia(
                    f"Một CÂU trong khối lá {' > '.join(structure_path)} dài "
                    f"{do_dai_cau} ký tự (vị trí [{vi_tri_tuyet_doi_dau}, "
                    f"{vi_tri_tuyet_doi_cuoi}) trong extracted_text, vượt trần "
                    f"{tran_do_dai_mau} ký tự. Không còn ranh giới an toàn "
                    "(đoạn/câu) nào để chia tiếp — module này KHÔNG bịa cách "
                    "cắt cứng theo số ký tự (06 Mục 5.2). Cần người xem trực "
                    "tiếp khối này."
                )
            don_vi.append((bat_dau + cau_bat_dau, bat_dau + cau_ket_thuc))

    goi: list[tuple[int, int]] = [don_vi[0]]
    for bat_dau, ket_thuc in don_vi[1:]:
        goi_bat_dau, _ = goi[-1]
        if ket_thuc - goi_bat_dau <= tran_do_dai_mau:
            goi[-1] = (goi_bat_dau, ket_thuc)
        else:
            goi.append((bat_dau, ket_thuc))

    return [(node.char_start + s, node.char_start + e) for s, e in goi]


def _duyet(
    node: Node,
    *,
    duong_dan_cha: list[str],
    parent_chunk_id: str | None,
    document_id: str,
    space_id: str,
    tenant_id: str,
    full_text: str,
    tran_do_dai_mau: int,
    ket_qua: list[Chunk],
) -> None:
    for con in node.children:
        doan = con.path
        if not doan:
            raise AssertionError(
                f"Khối {con.level.nhan} {con.marker!r} (heading={con.heading!r}) "
                f"có structure_path rỗng — mọi Node không phải gốc phải sinh ra "
                f"đúng một đoạn đường dẫn (Node.path)"
            )
        duong_dan_con = duong_dan_cha + doan

        # Bước 2 CHỈ áp dụng cho Chunk LÁ (không con) — một Node nội bộ có
        # span dài là cộng dồn từ con cháu (bất biến containment,
        # structure.py `kiem_vi_tri`), không phải bằng chứng nó cần chia.
        if con.children:
            khoang: list[tuple[int, int]] = [(con.char_start, con.char_end)]
        else:
            khoang = _chia_nho_la(
                con,
                full_text,
                tran_do_dai_mau=tran_do_dai_mau,
                structure_path=duong_dan_con,
            )

        chunk_id_dau_tien: str | None = None
        for span_start, span_end in khoang:
            chunk_id = str(uuid.uuid4())
            if chunk_id_dau_tien is None:
                chunk_id_dau_tien = chunk_id

            ket_qua.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    space_id=space_id,
                    tenant_id=tenant_id,
                    structure_path=duong_dan_con,
                    span_start=span_start,
                    span_end=span_end,
                    embedding=[],
                    parent_chunk_id=parent_chunk_id,
                )
            )

        _duyet(
            con,
            duong_dan_cha=duong_dan_con,
            parent_chunk_id=chunk_id_dau_tien,
            document_id=document_id,
            space_id=space_id,
            tenant_id=tenant_id,
            full_text=full_text,
            tran_do_dai_mau=tran_do_dai_mau,
            ket_qua=ket_qua,
        )


def cat_thanh_mau(
    read_result: ReadResult,
    *,
    document_id: str,
    space_id: str,
    tenant_id: str,
    tran_do_dai_mau: int,
) -> list[Chunk]:
    """GĐ3 — mỗi khối cấu trúc của `read_result.root` → một `Chunk` (bước 1);
    một Chunk LÁ vượt `tran_do_dai_mau` ký tự được chia nhỏ TIẾP tại ranh
    giới đoạn/câu an toàn (bước 2, 06 Mục 5.2, Điểm mở #4).

    `tran_do_dai_mau` KHÔNG có giá trị mặc định — CLAUDE.md Mục 4 quy tắc 2.
    Bên gọi (nơi lắp ráp pipeline, đọc `config/ingestion.yaml`) chịu trách
    nhiệm truyền giá trị sống; PO đã chốt 5000 ký tự Unicode (21/9/2026).

    Duyệt DFS từ gốc, tích luỹ `structure_path` (danh sách các đoạn, ngoài
    vào trong — 07 Mục 2.2) và `parent_chunk_id` (S2, ba quy tắc con):

    1. **Cha đúng một cấp lên**: `parent_chunk_id` truyền xuống là `chunk_id`
       của node CHA trực tiếp trong cây, không phải cấp bất kỳ. Khi một
       Chunk LÁ bị chia thành nhiều mẩu con, TẤT CẢ mẩu con nhận CÙNG một
       `parent_chunk_id` (của khối cha một cấp lên — không đôn thêm tầng
       nào) và CÙNG một `structure_path`, phân biệt nhau chỉ bằng
       `span_start`/`span_end`.
    2. **Khối cấu trúc cao nhất thì không có cha**: con trực tiếp của gốc
       (`Level.DOCUMENT`) nhận `parent_chunk_id=None`, vì gốc không sinh
       `Chunk`.
    3. **Khử trùng cha khi hai mẩu cùng một cha** là việc của T3.5
       (Retrieval, docs/09 dòng 213) — module này KHÔNG cài dedup, chỉ đảm
       bảo các mẩu con của cùng một khối cha được gán CÙNG một
       `parent_chunk_id`, để T3.5 khử trùng đúng.

    Raises:
        KhongDungDuocCauTruc: `read_result.dung_duoc` là `False`.
        KhoiVuotTranKhongTheChia: một Chunk LÁ vượt trần có một đoạn/câu tự
        nó cũng vượt trần, không còn ranh giới an toàn để chia tiếp.
    """
    if not read_result.dung_duoc:
        raise KhongDungDuocCauTruc(
            "ReadResult.outcome=KHONG_DUNG_DUOC — không có cấu trúc để cắt mẩu theo "
            "(06 Mục 5.2 GĐ3 cắt THEO CẤU TRÚC; không có cấu trúc thì không cắt)"
        )

    ket_qua: list[Chunk] = []
    _duyet(
        read_result.root,
        duong_dan_cha=[],
        parent_chunk_id=None,
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        full_text=read_result.full_text,
        tran_do_dai_mau=tran_do_dai_mau,
        ket_qua=ket_qua,
    )
    return ket_qua
