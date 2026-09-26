"""T2.5 (b) — Chunk vượt trần ngữ cảnh 8192 token PHẢI bị TỪ CHỐI ồn ào, đúng
ràng buộc kế thừa từ T0.2 (`test_above_the_ceiling_the_tail_IS_cut_and_only_warns`):
vượt trần thì thư viện chỉ CẢNH BÁO rồi vẫn chạy trên phần bị cắt — GĐ6 không
được để lọt hành vi đó qua trong im lặng.
"""

from __future__ import annotations

import uuid

import pytest
from schema.chunk import Chunk

from ingestion.vectorization import ChunkVuotTranNguCanh, dem_token, sinh_vector

from .conftest import DOC_ID, EMBEDDING_BATCH_SIZE, KHOAN_DAI, SPACE_ID, TENANT_ID


def _chunk(*, span_start: int, span_end: int, chunk_id: str | None = None) -> Chunk:
    return Chunk(
        chunk_id=chunk_id or str(uuid.uuid4()),
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        structure_path=["Điều 12"],
        span_start=span_start,
        span_end=span_end,
        structure_block_start=span_start,
        structure_block_end=span_end,
        embedding=[],
    )


def test_tu_thu_van_ban_vuot_tran_that(model):
    qua_tran = KHOAN_DAI * 130
    n_tokens = dem_token(model, qua_tran)
    assert n_tokens > model.max_seq_length, (
        f"Phép thử tự hỏng: mới {n_tokens} token, chưa vượt {model.max_seq_length}"
    )


def test_chunk_vuot_tran_bi_tu_choi_neu_ro_chunk_id(model):
    qua_tran = KHOAN_DAI * 130
    chunk = _chunk(span_start=0, span_end=len(qua_tran), chunk_id="chunk-qua-tran")

    with pytest.raises(ChunkVuotTranNguCanh) as exc_info:
        sinh_vector(
            [chunk], full_text=qua_tran, model=model, embedding_batch_size=EMBEDDING_BATCH_SIZE
        )

    assert "chunk-qua-tran" in str(exc_info.value)


def test_mot_chunk_vuot_tran_chan_ca_lo_khong_sinh_vector_mot_phan(model):
    """TỪ CHỐI TOÀN BỘ lô nếu có bất kỳ Chunk nào vượt trần — không lặng lẽ
    sinh vector cho phần "an toàn" rồi bỏ qua phần vượt trần."""
    qua_tran = KHOAN_DAI * 130
    van_ban_ngan = "Điều 1. Một điều rất ngắn."
    full_text = van_ban_ngan + "\n\n" + qua_tran

    chunk_ngan = _chunk(span_start=0, span_end=len(van_ban_ngan), chunk_id="chunk-ngan")
    chunk_dai = _chunk(
        span_start=len(van_ban_ngan) + 2,
        span_end=len(full_text),
        chunk_id="chunk-dai-qua-tran",
    )

    with pytest.raises(ChunkVuotTranNguCanh) as exc_info:
        sinh_vector(
            [chunk_ngan, chunk_dai],
            full_text=full_text,
            model=model,
            embedding_batch_size=EMBEDDING_BATCH_SIZE,
        )

    assert "chunk-dai-qua-tran" in str(exc_info.value)


def test_chunk_duoi_tran_khong_bi_tu_choi(model):
    van_ban = "Điều 1. Một điều ngắn, không vượt trần ngữ cảnh nào cả."
    chunk = _chunk(span_start=0, span_end=len(van_ban))
    ket_qua = sinh_vector(
        [chunk], full_text=van_ban, model=model, embedding_batch_size=EMBEDDING_BATCH_SIZE
    )
    assert len(ket_qua[0].embedding) == 1024
