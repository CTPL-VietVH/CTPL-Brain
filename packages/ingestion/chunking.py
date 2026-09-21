"""GĐ3 — Cắt mẩu (T2.3, 06 Mục 5.2 GĐ3, 07 Mục 2.2, S2).

Cầu nối giữa cây cấu trúc của GĐ2 (`ReadResult.root`, dựng ở T0.3/T2.2) và
danh sách `Chunk` mà kho vector cần (07 Mục 2.2, QT2).

⚠️ **Phạm vi ĐÃ THU HẸP theo quyết định PO 21/9/2026.** `06` Mục 5.2 GĐ3 định
nghĩa GĐ3 gồm HAI bước có thứ tự: (1) cấu trúc quyết định ranh giới — mỗi
khối cấu trúc là một mẩu; (2) ý nghĩa chia nhỏ TIẾP một khối cấu trúc **quá
dài**. Module này CHỈ làm bước (1). Bước (2) chạm thẳng vào **Điểm mở #4**
của `06` Mục 10 ("Trần và sàn độ dài đơn vị cắt") — chưa có ngưỡng "quá dài
là bao nhiêu" được chốt ở bất kỳ đâu, kể cả `config/ingestion.yaml`. Theo
`CLAUDE.md` Mục 0 điều tuyệt đối #3, chạm điểm mở phải dừng và hỏi PO thay vì
tự chọn một con số — PO đã xác nhận (21/9/2026): làm bước (1) trước, bước (2)
để một work-order riêng sau khi điểm mở #4 được chốt.

**Mỗi Node trong cây (trừ gốc `Level.DOCUMENT`) sinh ra ĐÚNG MỘT `Chunk`.**
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

import uuid

from schema.chunk import Chunk

from .reader.structure import Node, ReadResult

__all__ = ["KhongDungDuocCauTruc", "cat_thanh_mau"]


class KhongDungDuocCauTruc(Exception):
    """`ReadResult.dung_duoc` là `False` — GĐ2 không dựng được phân cấp.

    GĐ3 cắt THEO CẤU TRÚC (06 Mục 5.2 GĐ3); không có cấu trúc thì không có
    ranh giới để cắt. Từ chối ồn ào ở đây, KHÔNG lặng lẽ coi toàn văn là một
    mẩu duy nhất — đúng kiểu "im lặng hạ chuẩn" mà 06 Mục 5.2 cấm.
    """


def _duyet(
    node: Node,
    *,
    duong_dan_cha: list[str],
    parent_chunk_id: str | None,
    document_id: str,
    space_id: str,
    tenant_id: str,
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
        chunk_id = str(uuid.uuid4())

        ket_qua.append(
            Chunk(
                chunk_id=chunk_id,
                document_id=document_id,
                space_id=space_id,
                tenant_id=tenant_id,
                structure_path=duong_dan_con,
                span_start=con.char_start,
                span_end=con.char_end,
                embedding=[],
                parent_chunk_id=parent_chunk_id,
            )
        )

        _duyet(
            con,
            duong_dan_cha=duong_dan_con,
            parent_chunk_id=chunk_id,
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
) -> list[Chunk]:
    """GĐ3 bước (1): mỗi khối cấu trúc của `read_result.root` → một `Chunk`.

    Duyệt DFS từ gốc, tích luỹ `structure_path` (danh sách các đoạn, ngoài
    vào trong — 07 Mục 2.2) và `parent_chunk_id` (S2, ba quy tắc con):

    1. **Cha đúng một cấp lên**: `parent_chunk_id` truyền xuống là `chunk_id`
       của node CHA trực tiếp trong cây, không phải cấp bất kỳ.
    2. **Khối cấu trúc cao nhất thì không có cha**: con trực tiếp của gốc
       (`Level.DOCUMENT`) nhận `parent_chunk_id=None`, vì gốc không sinh
       `Chunk`.
    3. **Khử trùng cha khi hai mẩu cùng một cha** là việc của T3.5
       (Retrieval, docs/09 dòng 213) — module này KHÔNG cài dedup, chỉ đảm
       bảo các mẩu con của cùng một khối cha được gán CÙNG một
       `parent_chunk_id`, để T3.5 khử trùng đúng.

    Raises:
        KhongDungDuocCauTruc: `read_result.dung_duoc` là `False`.
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
        ket_qua=ket_qua,
    )
    return ket_qua
