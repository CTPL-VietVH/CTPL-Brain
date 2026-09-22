"""GĐ6 — Sinh biểu diễn vector và ghi vào Qdrant (T2.5, 06 Mục 5.2 dòng 258-259).

`06` dòng 258: *"GĐ6 — Tạo biểu diễn vector. Ràng buộc bắt buộc: cấu hình mô
hình biểu diễn phải dùng chung một nguồn với Retrieval, hoặc được kiểm tra
khớp lúc khởi động."* Module này thực thi đúng ràng buộc đó bằng cách gọi
`schema.embedding_registry.assert_collection_ready_for_contract` (T1.3, đã
xây sẵn) **trước khi ghi bất kỳ điểm nào** — không viết lại logic so khớp ở
đây, chỉ gọi.

Chia hai bước rõ ràng, TÁCH RỜI phần tính toán (không I/O) khỏi phần ghi kho:

1. `sinh_vector()` — nhận `list[Chunk]` (mỗi Chunk hiện có `embedding=[]`
   placeholder từ `chunking.cat_thanh_mau`, T2.3) + `full_text` (từ
   `ReadResult.full_text`/`ExtractionResult.extracted_text`, T2.2 — **Chunk
   không tự mang chữ**, 07 Mục 2.2), cắt substring theo `span_start`/
   `span_end` (chỉ số KÝ TỰ UNICODE), gọi BGE-M3 THEO LÔ (docs/09 hàng T2.5),
   trả về `list[Chunk]` MỚI với `embedding` đã điền. Không chạm Qdrant.
2. `ghi_vao_qdrant()` — kiểm con dấu (bắt buộc), rồi `upsert` các điểm.

⚠️ **Trần ngữ cảnh 8192 token — TỪ CHỐI, không cắt bớt.** `tests/t0_2_embedding/
test_bge_m3_contract.py::test_above_the_ceiling_the_tail_IS_cut_and_only_warns`
đã đo thật: vượt trần thì `sentence-transformers` chỉ CẢNH BÁO rồi vẫn chạy
tiếp trên phần đã bị cắt — không exception, sai lệch âm thầm. Vì T2.3 bước
2/2 (chia nhỏ khối cấu trúc quá dài) đang HOÃN (chạm Điểm mở #4, `06` Mục 10
— PO quyết định 21/9/2026 để một work-order riêng), một số Chunk hiện tại CÓ
THỂ đã vượt trần thật. `sinh_vector()` tự đếm token bằng
`model.tokenizer.encode(...)` (đúng cách T0.2 đã verify) và raise
`ChunkVuotTranNguCanh` nêu rõ chunk nào — cùng nguyên tắc "không loại trừ/lỗi
im lặng" đã dùng ở `BanMoiKhacSpace` (T2.1) và `KhongDungDuocCauTruc` (T2.3).

⚠️ **Đọc cấu hình từ nhóm HỢP ĐỒNG (`config/contract.yaml`), KHÔNG đọc biến
môi trường riêng cho `embedding_model`/`embedding_dim`/`distance_metric`** —
ba khoá đó có ĐÚNG MỘT NHÀ theo CLAUDE.md Mục 4 quy tắc 1 và `07` Mục 3.3.
Biến môi trường `CBRAIN_QDRANT_*` trong `.env` CHỈ dùng cho tham số KẾT NỐI
hạ tầng (host/port) — bên gọi (không phải module này) chịu trách nhiệm dựng
`QdrantClient` từ đó, đúng ranh giới `.env.example` đã ghi.

Model BGE-M3 (~2.5GB) được NẠP MỘT LẦN bởi bên gọi (giống fixture
`scope="session"` ở `tests/t0_2_embedding/conftest.py`) rồi truyền vào —
module này không tự `SentenceTransformer(...)`, tránh nạp lại model cho mỗi
tài liệu.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Protocol

from qdrant_client import QdrantClient, models

from schema.chunk import Chunk
from schema.config import ContractConfig
from schema.embedding_registry import PgConnectionLike, assert_collection_ready_for_contract
from schema.store_schema import CHUNK_PAYLOAD_FIELDS

__all__ = [
    "ChunkVuotTranNguCanh",
    "ChunkChuaCoVector",
    "BgeM3Like",
    "dem_token",
    "sinh_vector",
    "ghi_vao_qdrant",
]


class ChunkVuotTranNguCanh(Exception):
    """Một hoặc nhiều Chunk có số token VƯỢT trần ngữ cảnh của model.

    KHÔNG tự cắt bớt/truncate — chỉ từ chối và nêu rõ chunk nào, đúng
    `docs/06` "không loại trừ im lặng" (NT2) áp dụng cho GĐ6.
    """


class ChunkChuaCoVector(Exception):
    """Cố ghi vào Qdrant một Chunk mà `embedding` vẫn là `[]` placeholder —
    nghĩa là `sinh_vector()` chưa chạy qua, hoặc chạy trên một danh sách
    Chunk khác. Từ chối thay vì ghi một vector rỗng vào kho."""


class BgeM3Like(Protocol):
    """Hình dạng tối thiểu module này cần từ một `SentenceTransformer` đã nạp
    — duck-typed, đúng khớp cách `tests/t0_2_embedding/conftest.py` dùng
    `model.tokenizer.encode(...)`, `model.max_seq_length`, `model.encode(...)`.
    """

    max_seq_length: int
    tokenizer: Any

    def encode(self, sentences: list[str], *, normalize_embeddings: bool, batch_size: int) -> Any: ...


# Hằng số ENGINEERING thuần tuý — KHÔNG phải tham số của ba nhóm cấu hình
# (07 Mục 3.3): không đổi hành vi/kết quả, chỉ đổi cách gọi thư viện bên
# dưới, cùng loại với `_NGUONG_CUNG_DONG_PT` ở `reader/readers.py`. Trùng giá
# trị mặc định của chính `sentence_transformers.SentenceTransformer.encode`.
_BATCH_SIZE_MAC_DINH = 32


def dem_token(model: BgeM3Like, van_ban: str) -> int:
    """Đếm token THẬT (không cắt, không thêm định dạng) — đúng cách
    `tests/t0_2_embedding/test_bge_m3_contract.py` đã verify
    (`model.tokenizer.encode(...)`), để so với `model.max_seq_length`."""
    return len(model.tokenizer.encode(van_ban))


def sinh_vector(
    chunks: list[Chunk],
    *,
    full_text: str,
    model: BgeM3Like,
    batch_size: int = _BATCH_SIZE_MAC_DINH,
) -> list[Chunk]:
    """GĐ6 phần tính toán — KHÔNG chạm Qdrant.

    Trả về danh sách `Chunk` MỚI (`dataclasses.replace`, không sửa đối tượng
    đầu vào) với `embedding` đã điền — chuẩn hoá L2 (07 Mục 3.1, S5), khớp
    đúng cách đã verify ở T0.2 (`model.encode(..., normalize_embeddings=True)`).

    Raises:
        ChunkVuotTranNguCanh: có Chunk vượt trần ngữ cảnh của `model`.
    """
    if not chunks:
        return []

    tran = model.max_seq_length
    van_ban_theo_chunk = [full_text[chunk.span_start : chunk.span_end] for chunk in chunks]

    vuot_tran: list[tuple[Chunk, int]] = []
    for chunk, van_ban in zip(chunks, van_ban_theo_chunk):
        so_token = dem_token(model, van_ban)
        if so_token > tran:
            vuot_tran.append((chunk, so_token))

    if vuot_tran:
        chi_tiet = "; ".join(
            f"chunk_id={chunk.chunk_id!r} structure_path={chunk.structure_path!r} "
            f"({so_token} token > trần {tran})"
            for chunk, so_token in vuot_tran
        )
        raise ChunkVuotTranNguCanh(
            f"{len(vuot_tran)} mẩu vượt trần ngữ cảnh {tran} token của model — TỪ "
            "CHỐI, không cắt bớt. T0.2 đã đo thật: vượt trần thì thư viện chỉ CẢNH "
            "BÁO rồi vẫn chạy tiếp trên phần bị cắt (sai lệch âm thầm). GĐ3 hiện "
            "chưa chia nhỏ khối cấu trúc quá dài (Điểm mở #4, docs/06 Mục 10, PO "
            "hoãn 21/9/2026) — đây là hệ quả trực tiếp đã lường trước. "
            f"Chi tiết: {chi_tiet}"
        )

    # GỌI THEO LÔ: một lệnh `encode` trên toàn bộ danh sách, để thư viện tự
    # chia lô con theo `batch_size` — không gọi `encode` riêng lẻ cho từng
    # Chunk (docs/09 hàng T2.5).
    vectors = model.encode(van_ban_theo_chunk, normalize_embeddings=True, batch_size=batch_size)

    return [
        dataclasses.replace(chunk, embedding=vector.tolist())
        for chunk, vector in zip(chunks, vectors)
    ]


def _payload_tu_chunk(chunk: Chunk) -> dict[str, Any]:
    """Mọi trường của `Chunk` TRỪ `chunk_id` (thành ID điểm) và `embedding`
    (thành vector của điểm). Tập trường lấy từ `schema.store_schema`, không
    liệt kê lại ở đây: một trường MỚI thêm vào `Chunk` tự động có mặt, và
    quy tắc phủ payload chỉ có MỘT nhà (CLAUDE.md Mục 6)."""
    payload = dataclasses.asdict(chunk)
    return {name: payload[name] for name in CHUNK_PAYLOAD_FIELDS}


def ghi_vao_qdrant(
    chunks: list[Chunk],
    *,
    qdrant_client: QdrantClient,
    collection_name: str,
    contract_config: ContractConfig,
    pg_connection: PgConnectionLike,
) -> None:
    """GĐ6 phần ghi kho — kiểm con dấu TRƯỚC, rồi `upsert`.

    `assert_collection_ready_for_contract` (T1.3, `schema.embedding_registry`)
    là ĐIỂM VÀO DUY NHẤT đã chốt cho việc này — gọi nguyên, không viết lại
    logic so khớp ở đây (06 dòng 258, 07 Mục 3.1 ràng buộc 2).

    Raises:
        ChunkChuaCoVector: có Chunk còn `embedding=[]` — `sinh_vector()` chưa
            chạy qua danh sách này.
        (mọi lỗi từ `assert_collection_ready_for_contract`, xem
        `schema.embedding_registry`, khi cấu hình lệch con dấu trên kho).
    """
    assert_collection_ready_for_contract(
        config=contract_config,
        qdrant_client=qdrant_client,
        pg_connection=pg_connection,
        collection_name=collection_name,
    )

    if not chunks:
        return

    thieu_vector = [chunk.chunk_id for chunk in chunks if not chunk.embedding]
    if thieu_vector:
        raise ChunkChuaCoVector(
            f"{len(thieu_vector)} mẩu vẫn còn embedding=[] (placeholder từ GĐ3): "
            f"{thieu_vector}. Gọi sinh_vector() trước ghi_vao_qdrant()."
        )

    points = [
        models.PointStruct(id=chunk.chunk_id, vector=chunk.embedding, payload=_payload_tu_chunk(chunk))
        for chunk in chunks
    ]
    qdrant_client.upsert(collection_name=collection_name, points=points)
