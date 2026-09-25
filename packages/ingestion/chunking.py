"""GĐ3 — Cắt mẩu (T2.3, 06 Mục 5.2 GĐ3, 07 Mục 2.2, S2).

Cầu nối giữa cây cấu trúc của GĐ2 (`ReadResult.root`, dựng ở T0.3/T2.2) và
danh sách `Chunk` mà kho vector cần (07 Mục 2.2, QT2).

`06` Mục 5.2 GĐ3 định nghĩa GĐ3 gồm HAI bước có thứ tự:

1. **Cấu trúc quyết định ranh giới** — mỗi khối cấu trúc là một mẩu. Ba điều
   cấm: không được GỘP hai khối cấu trúc làm một mẩu; không được cắt NGANG
   ranh giới điều/khoản; khối đủ ngắn thì là một mẩu, hết việc.
2. **Ý nghĩa chia nhỏ TIẾP một khối cấu trúc quá dài** — tại ranh giới an
   toàn có sẵn trong văn bản (đoạn, rồi câu).

⭐ **MỘT KHỐI CÓ CON CHỈ MANG PHẦN CHỮ RIÊNG CỦA NÓ — chốt 25/9/2026 (PO),
07 Mục 2.2 v1.11. Đây là thay đổi PHÁ VỠ TƯƠNG THÍCH.**

Bản trước cho mẩu của một Node nội bộ mang span BAO TRÙM toàn bộ con cháu
(`char_start`..`char_end`), với lập luận: span dài của Node nội bộ là cộng
dồn từ con cháu nên không phải bằng chứng nội dung riêng của nó quá dài. Lập
luận đó đúng về mặt cấu trúc và **sai về mặt hậu quả** — đo thật ngày
24/9/2026 trên 36 tài liệu (21 văn bản hành chính + 15 tài liệu doanh
nghiệp):

* **18/36 tài liệu không nạp được**; 47 mẩu vượt trần ngữ cảnh 8192 token
  của BGE-M3, mẩu nặng nhất **233.712 token** (`tt-200-btc` › Chương II);
* **47/48 mẩu vượt trần đều là mẩu của Node nội bộ** — chỉ đúng 1 mẩu lá;
* mỗi ký tự của kho bị đem tạo vector **3,48 lần**, vì nó nằm lại trong span
  của mọi tổ tiên.

Nay: mẩu của một Node CÓ con chỉ mang `[node.char_start,
con_đầu_tiên.char_start)` — dòng tiêu đề cộng câu dẫn, tức đúng phần chữ
thuộc về chính khối đó — và **cũng đi qua bước 2** như mọi mẩu khác, nên nó
chịu `tran_do_dai_mau` thật sự. Phần chữ riêng luôn là MỘT khoảng liền mạch:
đo trên cả 4.132 Node nội bộ của kho thử, không Node nào có khe hở giữa hai
con, không Node nào còn chữ sau con cuối cùng.

Cặp `structure_block_start`/`structure_block_end` giữ lại trọn khối, nên đơn
vị ĐỌC của S2 không mất gì: Retrieval theo `parent_chunk_id` lên mẩu cha rồi
cắt `extracted_text` theo `structure_block_*` **của mẩu cha** — không theo
`span_*` của mẩu cha nữa.

**Khối đầu và khối cuối văn bản cũng là mẩu** (07 Mục 2.2 v1.11). Phần chữ
trước khối cấu trúc cao nhất đầu tiên — tên cơ quan ban hành, số hiệu, phần
*"Căn cứ…"* — đo được **34.195 ký tự trên 35/36 tài liệu**, và trước đây nằm
ngoài mọi mẩu, tức không tìm được. Phần sau khối cuối cùng (nơi ký) xử lý
đối xứng; trên kho thử hiện tại **0/36 tài liệu** có phần này, vì khối cấu
trúc cuối luôn chạy hết văn bản — nhánh đó là phòng thủ, không phải nhánh có
dữ liệu.

Trần độ dài (Điểm mở #4, `06` Mục 10) là **tham số bắt buộc, không mặc
định** (`tran_do_dai_mau` của `cat_thanh_mau`) — CLAUDE.md Mục 4 quy tắc 2
cấm giá trị mặc định trong mã. Giá trị sống do bên gọi truyền vào từ
`config/ingestion.yaml` (`chunk_length_cap`).

Cơ chế chia bước 2: chỉ cắt tại ranh giới AN TOÀN có sẵn trong văn bản —
đoạn (dòng trống) trước, câu (dấu kết câu) nếu đoạn vẫn quá dài, DÒNG ĐƠN
(xuống dòng, thêm 25/9/2026, CHUNK-bang-bieu) nếu câu vẫn quá dài — ca thật:
một bảng phụ lục xuống dòng giữa các hàng nhưng không có dòng trống hay dấu
kết câu thật nào, nên trước đây cả bảng rơi vào đúng MỘT "câu" và nổ ngoại
lệ ngay. Các mẩu con liền kề được đóng gói THAM LAM tới gần trần để tránh
sinh nhiều mẩu rất ngắn, nhưng không bao giờ cắt bên trong một dòng. Một
đoạn/câu/dòng tự nó đã vượt trần (không còn ranh giới an toàn để chia tiếp)
thì module này KHÔNG bịa cách cắt cứng theo số ký tự; nó nổ
`KhoiVuotTranKhongTheChia` để việc đó được người xem trực tiếp, đúng tinh
thần "loại trừ phải nhìn thấy được" (NT2) — không lặng lẽ hạ chuẩn.

**Mỗi Node trong cây (trừ gốc `Level.DOCUMENT`) sinh ra ÍT NHẤT MỘT `Chunk`**
— đúng một, trừ khi phần chữ của nó vượt trần và được chia thành nhiều mảnh.
Các mảnh cùng gốc giữ NGUYÊN `structure_path`, CÙNG `parent_chunk_id`, và
CÙNG `structure_block_*` của khối gốc (E1, PO chốt 25/9/2026) — phân biệt
nhau chỉ bằng `span_start`/`span_end`. Gốc `Level.DOCUMENT` không sinh
`Chunk`: `Node.path` của nó luôn rỗng (`vn_normalizer._dung_cay`), và nó
không phải "khối cấu trúc" theo nghĩa 07 Mục 2.2, chỉ là điểm neo của cây.

`embedding` (GĐ6/T2.5) được khởi tạo `[]` — placeholder; T2.5 điền vector
thật vào sau, cùng đối tượng `Chunk` này (`Chunk` không `frozen`).
"""

from __future__ import annotations

import re
import uuid

from schema.chunk import Chunk

from .reader.structure import Node, ReadResult

__all__ = [
    "InternalBlockHasNoOwnText",
    "KhongDungDuocCauTruc",
    "KhoiVuotTranKhongTheChia",
    "cat_thanh_mau",
]


class KhongDungDuocCauTruc(Exception):
    """`ReadResult.dung_duoc` là `False` — GĐ2 không dựng được phân cấp.

    GĐ3 cắt THEO CẤU TRÚC (06 Mục 5.2 GĐ3); không có cấu trúc thì không có
    ranh giới để cắt. Từ chối ồn ào ở đây, KHÔNG lặng lẽ coi toàn văn là một
    mẩu duy nhất — đúng kiểu "im lặng hạ chuẩn" mà 06 Mục 5.2 cấm.
    """


class KhoiVuotTranKhongTheChia(Exception):
    """Bước 2: một khối vượt trần, và một ĐOẠN, CÂU, hay DÒNG ĐƠN lẻ bên
    trong nó cũng tự nó đã vượt trần — không còn ranh giới an toàn nào
    (đoạn/câu/dòng) để chia tiếp.

    Cố ý KHÔNG rơi về cắt cứng theo số ký tự — đó chính là việc bị cấm
    (06 Mục 5.2). Nổ ồn ào để người xem trực tiếp khối này, kèm
    `structure_path` và vị trí tuyệt đối trong `extracted_text`.

    Đo 24/9/2026 (trước khi có mức "dòng đơn"): 2/36 tài liệu của kho thử rơi
    vào đây, cả hai vì một BẢNG phụ lục (228 dòng, không dòng trống, không
    dấu kết câu) — mức ranh giới "dòng đơn" thêm 25/9/2026 (CHUNK-bang-bieu)
    giải quyết đúng hai ca này: các dòng bảng có xuống dòng đơn giữa các
    hàng dù không có dòng trống hay dấu kết câu thật. Từ nay ngoại lệ này chỉ
    còn nổ khi một DÒNG ĐƠN — không phải cả bảng — tự nó đã vượt trần.
    """


class InternalBlockHasNoOwnText(Exception):
    """A structure block that HAS children begins exactly where its first
    child begins, so it owns no text of its own.

    Refused loudly instead of resolved quietly, because both quiet answers
    are wrong: emitting a zero-length chunk puts a meaningless vector in the
    store, and emitting no chunk at all breaks the `parent_chunk_id` chain
    that S2 needs to build the reading unit — a wrong citation that reports
    no error (07 Mục 2.2).

    Measured on the 36-document corpus (25/9/2026): never fires. The smallest
    own-text region found is 10 characters. This is a tripwire for a tree
    shape nobody has seen yet, not a case the readers are known to produce.
    """


# ---------------------------------------------------------------------------
# Bước 2 — chia nhỏ TIẾP một khối vượt trần, chỉ tại ranh giới an toàn.
# ---------------------------------------------------------------------------

# Ranh giới ĐOẠN: một hay nhiều dòng trống liên tiếp. `full_text` đã qua
# `chuan_hoa_van_ban` (NFC, xuống dòng thống nhất, hết khoảng trắng cuối
# dòng) trước khi tới đây, nên "\n\n+" là ranh giới đoạn an toàn.
_MAU_RANH_GIOI_DOAN = re.compile(r"\n\n+")

# Dấu kết câu — không dùng danh sách từ khoá viết tắt, xem `_find_sentence_cut_points`.
_KY_TU_KET_CAU = ".!?…"


def _find_sentence_cut_points(text: str) -> list[int]:
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


def _find_line_cut_points(text: str) -> list[int]:
    """Vị trí NGAY SAU mỗi ký tự xuống dòng trong `text` — ranh giới DÒNG
    ĐƠN, mức chia thứ BA và cuối cùng (sau đoạn, sau câu).

    Ca cần tới mức này (25/9/2026, CHUNK-bang-bieu): một bảng phụ lục nhúng
    trong một Khoản — mỗi hàng đứng riêng một dòng, nhưng KHÔNG có dòng trống
    giữa các hàng (nên không phải ranh giới đoạn) và số liệu trong bảng
    không mang dấu kết câu thật nào (nên `_find_sentence_cut_points` không tìm được
    điểm cắt nào, cả bảng rơi vào đúng MỘT "câu"). Cùng cách `_find_sentence_cut_points`
    giữ đúng nguyên bản: điểm cắt đứng NGAY SAU ký tự `\\n`, tức chính dấu
    xuống dòng ở lại với dòng ĐỨNG TRƯỚC — không mất, không lặp ký tự nào khi
    ghép lại."""
    return [i + 1 for i, ch in enumerate(text) if ch == "\n"]


def _chia_theo_diem_cat(text: str, diem_cat: list[int]) -> list[tuple[int, int]]:
    """Chia `text` tại các điểm cắt (offset tương đối) thành các đoạn liền
    mạch, không mất ký tự nào — khác `_MAU_RANH_GIOI_DOAN` (loại bỏ phần
    khớp), điểm cắt câu không loại bỏ gì, chỉ tách."""
    bien = sorted(set([0, *diem_cat, len(text)]))
    return [(bien[i], bien[i + 1]) for i in range(len(bien) - 1) if bien[i] < bien[i + 1]]


def _split_block_to_cap(
    block_start: int,
    block_end: int,
    full_text: str,
    *,
    tran_do_dai_mau: int,
    structure_path: list[str],
) -> list[tuple[int, int]]:
    """Chia khoảng TUYỆT ĐỐI `[block_start, block_end)` thành các khoảng
    con an toàn khi nó vượt `tran_do_dai_mau` — đoạn trước, câu nếu đoạn vẫn
    quá dài, DÒNG ĐƠN (thêm 25/9/2026) nếu câu vẫn quá dài, đóng gói tham lam
    để tránh sinh nhiều mẩu rất ngắn.

    Nhận VỊ TRÍ chứ không nhận `Node`: từ 25/9/2026 nó còn được gọi cho phần
    chữ RIÊNG của một Node nội bộ và cho khối đầu/cuối văn bản — cả hai đều
    không phải một Node trọn vẹn.

    Trả về `[(block_start, block_end)]` (một khoảng, không chia) khi
    khối đã đủ ngắn — GĐ3 bước 1 điều cấm 3: khối đủ ngắn thì là MỘT mẩu.

    Raises:
        KhoiVuotTranKhongTheChia: một đoạn, câu, hay dòng đơn vẫn vượt trần
        sau khi đã cắt tại ranh giới an toàn nhỏ nhất còn lại (dòng đơn).
    """
    if block_end - block_start <= tran_do_dai_mau:
        return [(block_start, block_end)]

    text = full_text[block_start:block_end]

    # `block_end` là vị trí BẮT ĐẦU của mốc kế tiếp (structure.py
    # `_dung_cay`), nên đuôi `text` gần như luôn là khoảng trắng/dòng trống
    # trước mốc đó — một trận khớp ranh giới đoạn CHẠM ĐÚNG cuối `text` không
    # có nội dung nào theo sau để tách; loại nó khỏi danh sách ranh giới thay
    # vì để nó nuốt mất khoảng trắng đuôi, tránh mẩu con cuối cùng hụt mất vài
    # ký tự so với `block_end` thật.
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
            doan_text, _find_sentence_cut_points(doan_text)
        ):
            do_dai_cau = cau_ket_thuc - cau_bat_dau
            if do_dai_cau <= tran_do_dai_mau:
                don_vi.append((bat_dau + cau_bat_dau, bat_dau + cau_ket_thuc))
                continue

            # Câu vẫn vượt trần: mức ranh giới CUỐI CÙNG trước khi từ bỏ là
            # DÒNG ĐƠN (25/9/2026) — ca thật: một bảng phụ lục xuống dòng
            # giữa các hàng nhưng không có dòng trống hay dấu kết câu thật,
            # nên cả bảng rơi vào đúng một "câu" ở mức trên. Nếu chính câu
            # này không còn dấu xuống dòng nào (`_find_line_cut_points` rỗng),
            # `_chia_theo_diem_cat` trả nguyên một khoảng bằng cả câu — vòng
            # lặp dưới đây tự nhiên rơi vào nhánh raise, không cần nhánh
            # riêng cho "hết ranh giới".
            cau_text = doan_text[cau_bat_dau:cau_ket_thuc]
            for dong_bat_dau, dong_ket_thuc in _chia_theo_diem_cat(
                cau_text, _find_line_cut_points(cau_text)
            ):
                do_dai_dong = dong_ket_thuc - dong_bat_dau
                if do_dai_dong > tran_do_dai_mau:
                    vi_tri_tuyet_doi_dau = block_start + bat_dau + cau_bat_dau + dong_bat_dau
                    vi_tri_tuyet_doi_cuoi = block_start + bat_dau + cau_bat_dau + dong_ket_thuc
                    raise KhoiVuotTranKhongTheChia(
                        f"Một DÒNG trong khối {' > '.join(structure_path) or '(khối đầu/cuối văn bản)'} "
                        f"dài {do_dai_dong} ký tự (vị trí [{vi_tri_tuyet_doi_dau}, "
                        f"{vi_tri_tuyet_doi_cuoi}) trong extracted_text, vượt trần "
                        f"{tran_do_dai_mau} ký tự. Không còn ranh giới an toàn "
                        "(đoạn/câu/dòng) nào để chia tiếp — module này KHÔNG bịa cách "
                        "cắt cứng theo số ký tự (06 Mục 5.2). Cần người xem trực "
                        "tiếp khối này."
                    )
                don_vi.append((
                    bat_dau + cau_bat_dau + dong_bat_dau,
                    bat_dau + cau_bat_dau + dong_ket_thuc,
                ))

    goi: list[tuple[int, int]] = [don_vi[0]]
    for bat_dau, ket_thuc in don_vi[1:]:
        goi_bat_dau, _ = goi[-1]
        if ket_thuc - goi_bat_dau <= tran_do_dai_mau:
            goi[-1] = (goi_bat_dau, ket_thuc)
        else:
            goi.append((bat_dau, ket_thuc))

    return [(block_start + s, block_start + e) for s, e in goi]


# ---------------------------------------------------------------------------
# Bước 1 — mỗi khối cấu trúc một mẩu, cắt theo ranh giới của cây.
# ---------------------------------------------------------------------------


def _emit_chunks_for_block(
    *,
    spans: list[tuple[int, int]],
    structure_path: list[str],
    block: tuple[int, int],
    parent_chunk_id: str | None,
    document_id: str,
    space_id: str,
    tenant_id: str,
    ket_qua: list[Chunk],
) -> str:
    """Đổ các khoảng con của MỘT khối thành `Chunk`, trả `chunk_id` của mảnh
    đầu tiên (mảnh làm cha cho các khối con — S2 quy tắc con 1).

    Mọi mảnh của cùng một khối nhận CÙNG `structure_block_*` = trọn khối gốc
    (E1, PO chốt 25/9/2026), CÙNG `structure_path`, CÙNG `parent_chunk_id`.
    """
    block_start, block_end = block
    chunk_id_dau_tien: str | None = None
    for span_start, span_end in spans:
        chunk_id = str(uuid.uuid4())
        if chunk_id_dau_tien is None:
            chunk_id_dau_tien = chunk_id
        ket_qua.append(
            Chunk(
                chunk_id=chunk_id,
                document_id=document_id,
                space_id=space_id,
                tenant_id=tenant_id,
                structure_path=structure_path,
                span_start=span_start,
                span_end=span_end,
                structure_block_start=block_start,
                structure_block_end=block_end,
                embedding=[],
                parent_chunk_id=parent_chunk_id,
            )
        )
    assert chunk_id_dau_tien is not None  # `spans` không bao giờ rỗng
    return chunk_id_dau_tien


def _walk_tree(
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

        # Phần chữ RIÊNG của khối: tới ngay trước con đầu tiên nếu có con,
        # còn không thì trọn khối. Trọn khối luôn được giữ nguyên ở
        # `structure_block_*` để đơn vị ĐỌC của S2 không mất gì.
        if con.children:
            own_text_end = con.children[0].char_start
            if not full_text[con.char_start:own_text_end].strip():
                raise InternalBlockHasNoOwnText(
                    f"Khối {' > '.join(duong_dan_con)} có con nhưng không có chữ "
                    f"riêng nào: nó bắt đầu ở {con.char_start} và con đầu tiên "
                    f"cũng bắt đầu ở {own_text_end}. Không thể vừa giữ "
                    "chuỗi parent_chunk_id (S2 cần để dựng đơn vị đọc) vừa "
                    "tránh sinh một mẩu rỗng — cần người xem cây của tài liệu này."
                )
        else:
            own_text_end = con.char_end

        spans = _split_block_to_cap(
            con.char_start,
            own_text_end,
            full_text,
            tran_do_dai_mau=tran_do_dai_mau,
            structure_path=duong_dan_con,
        )
        chunk_id_dau_tien = _emit_chunks_for_block(
            spans=spans,
            structure_path=duong_dan_con,
            block=(con.char_start, con.char_end),
            parent_chunk_id=parent_chunk_id,
            document_id=document_id,
            space_id=space_id,
            tenant_id=tenant_id,
            ket_qua=ket_qua,
        )

        _walk_tree(
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


def _emit_edge_block(
    *,
    block_start: int,
    block_end: int,
    full_text: str,
    tran_do_dai_mau: int,
    document_id: str,
    space_id: str,
    tenant_id: str,
    ket_qua: list[Chunk],
) -> None:
    """Khối đầu hoặc khối cuối văn bản → mẩu (07 Mục 2.2 v1.11).

    `structure_path` là DANH SÁCH RỖNG và `parent_chunk_id` là `None`: khối
    này không nằm ở cấp nào của cây, và nó đã là đơn vị cấu trúc cao nhất
    theo đúng nghĩa quy tắc con 2 của S2, nên đơn vị ĐỌC của nó là trọn khối
    của chính nó.

    Khoảng chỉ có khoảng trắng thì KHÔNG sinh mẩu — một vector của mấy dòng
    trống không trả lời được câu hỏi nào, và ở đây bỏ qua là an toàn: không
    mẩu nào nhận khối này làm cha, nên không có chuỗi `parent_chunk_id` nào
    bị đứt (khác hẳn `InternalBlockHasNoOwnText` ở trên).
    """
    if block_end <= block_start or not full_text[block_start:block_end].strip():
        return
    spans = _split_block_to_cap(
        block_start,
        block_end,
        full_text,
        tran_do_dai_mau=tran_do_dai_mau,
        structure_path=[],
    )
    _emit_chunks_for_block(
        spans=spans,
        structure_path=[],
        block=(block_start, block_end),
        parent_chunk_id=None,
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
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
    """GĐ3 — mỗi khối cấu trúc của `read_result.root` → một `Chunk` mang phần
    chữ RIÊNG của khối (bước 1); phần chữ nào vượt `tran_do_dai_mau` ký tự
    được chia nhỏ TIẾP tại ranh giới đoạn/câu an toàn (bước 2). Khối đầu và
    khối cuối văn bản cũng thành mẩu.

    Mẩu trả về theo đúng THỨ TỰ VĂN BẢN: khối đầu, rồi cây theo DFS, rồi khối
    cuối — `pg_queue_stores` dựa vào thứ tự này để đánh `chunk_ordinal`.

    `tran_do_dai_mau` KHÔNG có giá trị mặc định — CLAUDE.md Mục 4 quy tắc 2.

    Duyệt DFS từ gốc, tích luỹ `structure_path` (danh sách các đoạn, ngoài
    vào trong — 07 Mục 2.2) và `parent_chunk_id` (S2, ba quy tắc con):

    1. **Cha đúng một cấp lên**: `parent_chunk_id` truyền xuống là `chunk_id`
       của MẢNH ĐẦU TIÊN của node CHA trực tiếp. Khi phần chữ của một khối bị
       chia thành nhiều mảnh, TẤT CẢ mảnh nhận CÙNG `parent_chunk_id`, CÙNG
       `structure_path` và CÙNG `structure_block_*`, phân biệt nhau chỉ bằng
       `span_start`/`span_end`.
    2. **Khối cấu trúc cao nhất thì không có cha**: con trực tiếp của gốc
       (`Level.DOCUMENT`), và cả khối đầu/cuối văn bản, nhận
       `parent_chunk_id=None`. Đơn vị đọc khi đó là `structure_block_*` của
       chính mẩu — không phải mảnh `span_*` của nó.
    3. **Khử trùng cha khi hai mẩu cùng một cha** là việc của T3.5
       (Retrieval) — module này KHÔNG cài dedup, chỉ đảm bảo các mảnh của
       cùng một khối cha được gán CÙNG một `parent_chunk_id`.

    Raises:
        KhongDungDuocCauTruc: `read_result.dung_duoc` là `False`, hoặc cây
            dựng được nhưng không có khối cấu trúc cao nhất nào.
        KhoiVuotTranKhongTheChia: một khối vượt trần có một đoạn/câu tự nó
            cũng vượt trần, không còn ranh giới an toàn để chia tiếp.
        InternalBlockHasNoOwnText: một khối có con nhưng không có chữ riêng.
    """
    if not read_result.dung_duoc:
        raise KhongDungDuocCauTruc(
            "ReadResult.outcome=KHONG_DUNG_DUOC — không có cấu trúc để cắt mẩu theo "
            "(06 Mục 5.2 GĐ3 cắt THEO CẤU TRÚC; không có cấu trúc thì không cắt)"
        )

    top_level_blocks = read_result.root.children
    if not top_level_blocks:
        raise KhongDungDuocCauTruc(
            f"ReadResult.outcome={read_result.outcome.name} nói dựng được cấu trúc, "
            "nhưng gốc không có khối cấu trúc con nào. Từ chối thay vì coi toàn văn "
            "là một mẩu duy nhất — đó đúng là đường 'im lặng hạ chuẩn' mà 06 Mục 5.2 "
            "cấm."
        )

    full_text = read_result.full_text
    ket_qua: list[Chunk] = []

    _emit_edge_block(
        block_start=0,
        block_end=top_level_blocks[0].char_start,
        full_text=full_text,
        tran_do_dai_mau=tran_do_dai_mau,
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        ket_qua=ket_qua,
    )

    _walk_tree(
        read_result.root,
        duong_dan_cha=[],
        parent_chunk_id=None,
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        full_text=full_text,
        tran_do_dai_mau=tran_do_dai_mau,
        ket_qua=ket_qua,
    )

    _emit_edge_block(
        block_start=top_level_blocks[-1].char_end,
        block_end=len(full_text),
        full_text=full_text,
        tran_do_dai_mau=tran_do_dai_mau,
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        ket_qua=ket_qua,
    )

    return ket_qua
