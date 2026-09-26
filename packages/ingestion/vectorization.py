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
2. `write_to_qdrant()` — kiểm con dấu (bắt buộc), rồi `upsert` các điểm THEO
   LÔ (xem docstring của hàm: một lô mang cả tài liệu đã hỏng thật 25/9/2026).

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

──────────────────────────────────────────────────────────────────────
VEC-3 — adaptive batching, so one large document cannot exhaust device
memory (GPU/MPS/CPU), and an out-of-memory failure gets its own name
──────────────────────────────────────────────────────────────────────

`embedding_batch_size` (`config/ingestion.yaml`) is the size `sinh_vector()`
groups chunks into for each call into the model — no default here, the same
CLAUDE.md Mục 4 quy tắc 2 reason `write_to_qdrant`'s `upsert_batch_points`
has none. It used to be a hardcoded engineering constant precisely because
changing it only changed how the library called into itself, never the
result; VEC-3 makes it change the result (whether a batch fits in device
memory), so it needed a real home outside the code.

Two things beyond plain batching:

1. **Chunks are sorted by token count, heaviest first, before batching.**
   An out-of-memory failure then surfaces on the FIRST batch of a document
   instead of the last — every later batch is at least as light as the one
   before it, so once one batch succeeds the rest are no riskier. Sorting
   only changes which chunk each batch AT A TIME carries, never which
   `Chunk` a vector ends up on: the mapping back to the caller's original
   list is done BY INDEX (`_encode_indices` returns `{original_index:
   vector}`), never by the order batches happened to run in. Restoring by
   position instead would be the exact silent mis-pairing this task exists
   to prevent — every chunk would still get *a* vector, just not its own.
2. **A batch that runs out of device memory is halved and retried, down to
   a batch of one.** `_is_out_of_memory_error` recognises both the CUDA
   allocator's own exception (`torch.cuda.OutOfMemoryError`) and the plain
   `RuntimeError` PyTorch raises for the same failure on MPS/CPU — anything
   else propagates unchanged, because only these two shapes mean "smaller
   has a chance". `_free_device_cache` runs before every retry so the
   halved batch gets the best chance of fitting. A batch of ONE chunk that
   still runs out of memory raises `EmbeddingOutOfMemory` — a resource
   ceiling, not an unforeseen bug and not a document-structure problem, so
   it gets its own code (`IngestionFailureCode.EMBEDDING_OUT_OF_MEMORY`,
   docs/10 §3.5) rather than folding into `INTERNAL_ERROR` or
   `DOCUMENT_NOT_STRUCTURABLE`.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Protocol

import torch
from qdrant_client import QdrantClient, models

from schema.chunk import Chunk
from schema.config import ContractConfig
from schema.embedding_registry import PgConnectionLike, assert_collection_ready_for_contract
from schema.store_schema import CHUNK_PAYLOAD_FIELDS

__all__ = [
    "ChunkVuotTranNguCanh",
    "ChunkChuaCoVector",
    "EmbeddingOutOfMemory",
    "BgeM3Like",
    "dem_token",
    "sinh_vector",
    "write_to_qdrant",
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


class EmbeddingOutOfMemory(Exception):
    """The embedding model ran out of device memory (GPU/MPS/CPU) creating
    a vector for a batch of ONE chunk — VEC-3. Halving further is not
    possible, so this is where adaptive batching gives up.

    Deliberately its own exception rather than letting the underlying
    `torch.cuda.OutOfMemoryError` / `RuntimeError` reach the caller as
    `INTERNAL_ERROR`: this is a known resource ceiling, not an unforeseen
    bug, and it is not a document-structure problem either — folding it
    into `DOCUMENT_NOT_STRUCTURABLE` would misname the cause. Mapped by
    `IngestionPipeline` to `IngestionFailureCode.EMBEDDING_OUT_OF_MEMORY`
    with status `FAILED` (docs/10 §3.5).
    """


class BgeM3Like(Protocol):
    """Hình dạng tối thiểu module này cần từ một `SentenceTransformer` đã nạp
    — duck-typed, đúng khớp cách `tests/t0_2_embedding/conftest.py` dùng
    `model.tokenizer.encode(...)`, `model.max_seq_length`, `model.encode(...)`.
    """

    max_seq_length: int
    tokenizer: Any

    def encode(self, sentences: list[str], *, normalize_embeddings: bool, batch_size: int) -> Any: ...


def dem_token(model: BgeM3Like, van_ban: str) -> int:
    """Đếm token THẬT (không cắt, không thêm định dạng) — đúng cách
    `tests/t0_2_embedding/test_bge_m3_contract.py` đã verify
    (`model.tokenizer.encode(...)`), để so với `model.max_seq_length`."""
    return len(model.tokenizer.encode(van_ban))


def _is_out_of_memory_error(exc: BaseException) -> bool:
    """True for a CUDA allocator failure or the generic `RuntimeError`
    PyTorch raises for the same failure on MPS/CPU — VEC-3.

    Anything else (a bad input, a library bug) must propagate unchanged:
    these two shapes are the only ones where "retry smaller" has a chance,
    and swallowing a different error here would hide it behind a batch
    split that can never fix it.
    """
    if isinstance(exc, torch.cuda.OutOfMemoryError):
        return True
    return isinstance(exc, RuntimeError) and "out of memory" in str(exc).lower()


def _free_device_cache() -> None:
    """Release cached (not in-use) device memory after an OOM — best effort,
    VEC-3. A no-op on a machine with neither backend built in or available;
    a halved retry that still does not fit gets another chance here."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()


def _encode_indices(
    model: BgeM3Like, indices: list[int], texts_by_index: list[str]
) -> dict[int, Any]:
    """Encode exactly the chunks named by `indices`, halving and retrying on
    an out-of-memory error down to a batch of one — VEC-3.

    Returns `{original_index: vector}` rather than a plain list: the caller
    restores the chunk↔vector mapping BY INDEX, never by the order batches
    happened to finish in. Halving here can process indices out of the order
    they were handed in relative to sibling batches, so relying on order
    would be exactly the silent mis-pairing this task exists to prevent.

    Raises:
        EmbeddingOutOfMemory: a batch of a single chunk still runs out of
            device memory — halving further is not possible.
    """
    try:
        vectors = model.encode(
            [texts_by_index[index] for index in indices],
            normalize_embeddings=True,
            batch_size=len(indices),
        )
        return dict(zip(indices, vectors))
    except Exception as exc:
        if not _is_out_of_memory_error(exc):
            raise
        _free_device_cache()
        if len(indices) == 1:
            raise EmbeddingOutOfMemory(
                f"out of device memory embedding a single chunk (index "
                f"{indices[0]}) — cannot split the batch further. Original "
                f"error: {exc!r}"
            ) from exc
        midpoint = len(indices) // 2
        left = _encode_indices(model, indices[:midpoint], texts_by_index)
        right = _encode_indices(model, indices[midpoint:], texts_by_index)
        return {**left, **right}


def sinh_vector(
    chunks: list[Chunk],
    *,
    full_text: str,
    model: BgeM3Like,
    embedding_batch_size: int,
) -> list[Chunk]:
    """GĐ6 phần tính toán — KHÔNG chạm Qdrant.

    Trả về danh sách `Chunk` MỚI (`dataclasses.replace`, không sửa đối tượng
    đầu vào) với `embedding` đã điền — chuẩn hoá L2 (07 Mục 3.1, S5), khớp
    đúng cách đã verify ở T0.2 (`model.encode(..., normalize_embeddings=True)`).

    `embedding_batch_size` has no default — it is `embedding_batch_size` in
    `config/ingestion.yaml`, and CLAUDE.md Mục 4 quy tắc 2 gives it no second
    home in code (VEC-3).

    Chunks are grouped into batches of at most `embedding_batch_size`,
    HEAVIEST FIRST by token count — see the module docstring for why. A
    batch that runs out of device memory is halved and retried down to one
    chunk (`_encode_indices`); a batch of one that still runs out raises
    `EmbeddingOutOfMemory`.

    Raises:
        ChunkVuotTranNguCanh: có Chunk vượt trần ngữ cảnh của `model`.
        EmbeddingOutOfMemory: the model ran out of device memory even on a
            batch of a single chunk (VEC-3).
    """
    if embedding_batch_size < 1:
        raise ValueError(
            f"embedding_batch_size must be at least 1, got {embedding_batch_size!r}. "
            f"Its one home is `embedding_batch_size` in config/ingestion.yaml; this "
            f"module has no default for it (CLAUDE.md Mục 4 quy tắc 2)."
        )

    if not chunks:
        return []

    tran = model.max_seq_length
    van_ban_theo_chunk = [full_text[chunk.span_start : chunk.span_end] for chunk in chunks]
    so_token_theo_chunk = [dem_token(model, van_ban) for van_ban in van_ban_theo_chunk]

    vuot_tran = [
        (chunk, so_token)
        for chunk, so_token in zip(chunks, so_token_theo_chunk)
        if so_token > tran
    ]
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

    # VEC-3 — heaviest batch FIRST: an out-of-memory failure then surfaces on
    # the FIRST batch of a document instead of the last.
    order = sorted(range(len(chunks)), key=lambda index: so_token_theo_chunk[index], reverse=True)

    vectors_by_index: dict[int, Any] = {}
    for batch_start in range(0, len(order), embedding_batch_size):
        batch_indices = order[batch_start : batch_start + embedding_batch_size]
        vectors_by_index.update(_encode_indices(model, batch_indices, van_ban_theo_chunk))

    return [
        dataclasses.replace(chunk, embedding=vectors_by_index[index].tolist())
        for index, chunk in enumerate(chunks)
    ]


def _payload_tu_chunk(chunk: Chunk) -> dict[str, Any]:
    """Mọi trường của `Chunk` TRỪ `chunk_id` (thành ID điểm) và `embedding`
    (thành vector của điểm). Tập trường lấy từ `schema.store_schema`, không
    liệt kê lại ở đây: một trường MỚI thêm vào `Chunk` tự động có mặt, và
    quy tắc phủ payload chỉ có MỘT nhà (CLAUDE.md Mục 6)."""
    payload = dataclasses.asdict(chunk)
    return {name: payload[name] for name in CHUNK_PAYLOAD_FIELDS}


def write_to_qdrant(
    chunks: list[Chunk],
    *,
    qdrant_client: QdrantClient,
    collection_name: str,
    contract_config: ContractConfig,
    pg_connection: PgConnectionLike,
    upsert_batch_points: int,
) -> None:
    """GĐ6, the store-writing half — check the stamp FIRST, then upsert IN
    BATCHES of at most `upsert_batch_points` points.

    `assert_collection_ready_for_contract` (T1.3, `schema.embedding_registry`)
    stays the ONE entry point for the stamp check — called, never
    re-implemented here (06 dòng 258, 07 Mục 3.1 ràng buộc 2). It runs once
    per call, not once per batch: it is a check about the collection, and
    repeating it per batch would make a document's cost depend on how it was
    cut up.

    ──────────────────────────────────────────────────────────────────────
    Why the batching, and why `wait=True`
    ──────────────────────────────────────────────────────────────────────

    ⚠️ **One upsert carrying a whole document is what broke on 25/9/2026**:
    2 of 36 documents ended `failed`/`INTERNAL_ERROR` because the request body
    reached 40-43 MB and Qdrant's REST endpoint refused it. The size is not
    exotic — measured 25/9/2026, one 1024-dimension point plus its payload
    serialises to 16.7 KB of JSON, so any document past roughly 1900 chunks
    reaches the 32 MB default on its own. `upsert_batch_points` has no default
    here: it is `qdrant_upsert_batch_points` in `config/ingestion.yaml` and
    the caller passes the live value down (CLAUDE.md Mục 4 quy tắc 2).

    ⭐ **`wait=True` is not a removable performance knob** — the same reason
    `deletion.QdrantVectorStoreDeleter.delete_document_points` states for the
    delete side. It makes each call return only AFTER the batch has applied.
    Without it a refused batch could still be in flight while the caller's
    compensating cleanup (`promotion.promote_approved_ingestion`) deletes this
    document's points, and the late batch would land AFTER that delete —
    resurrecting exactly the orphan the cleanup just removed.

    ⚠️ Batches are NOT one transaction. A failure at batch k leaves batches
    1..k-1 in the collection; this function does not clean them up, because
    the only actor that knows whether those points should exist at all is the
    one that decided to write the document (`promote_approved_ingestion`,
    which deletes by `document_id` filter — that filter catches a partially
    applied write, a list of the ids just sent would not).

    Raises:
        ValueError: `upsert_batch_points` is below 1 — refused before the
            stamp check, so a nonsensical parameter does not need a live store
            to be caught.
        ChunkChuaCoVector: a Chunk still carries `embedding=[]` —
            `sinh_vector()` has not run over this list.
        (everything `assert_collection_ready_for_contract` raises — see
        `schema.embedding_registry` — when the config drifts from the stamp).
    """
    if upsert_batch_points < 1:
        raise ValueError(
            f"upsert_batch_points must be at least 1, got {upsert_batch_points!r}. "
            f"Its one home is `qdrant_upsert_batch_points` in "
            f"config/ingestion.yaml; this module has no default for it "
            f"(CLAUDE.md Mục 4 quy tắc 2)."
        )

    assert_collection_ready_for_contract(
        config=contract_config,
        qdrant_client=qdrant_client,
        pg_connection=pg_connection,
        collection_name=collection_name,
    )

    if not chunks:
        return

    chunks_without_vector = [chunk.chunk_id for chunk in chunks if not chunk.embedding]
    if chunks_without_vector:
        raise ChunkChuaCoVector(
            f"{len(chunks_without_vector)} chunks still carry embedding=[] (the "
            f"placeholder GĐ3 leaves): {chunks_without_vector}. Call sinh_vector() "
            f"before write_to_qdrant()."
        )

    points = [
        models.PointStruct(id=chunk.chunk_id, vector=chunk.embedding, payload=_payload_tu_chunk(chunk))
        for chunk in chunks
    ]
    for batch_start in range(0, len(points), upsert_batch_points):
        qdrant_client.upsert(
            collection_name=collection_name,
            points=points[batch_start : batch_start + upsert_batch_points],
            wait=True,
        )
