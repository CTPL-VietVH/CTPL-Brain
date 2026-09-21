"""T2.5 (d) — `ghi_vao_qdrant` từ chối ghi Chunk còn `embedding=[]` (GĐ3 chưa
qua GĐ6) — không âm thầm đẩy một vector rỗng vào Qdrant.
"""

from __future__ import annotations

import uuid

import pytest
from schema.chunk import Chunk
from schema.config import load_contract_config

from ingestion.vectorization import ChunkChuaCoVector, ghi_vao_qdrant

from .conftest import CONTRACT_PATH, DOC_ID, SPACE_ID, TENANT_ID


def test_chunk_chua_co_vector_bi_tu_choi(qdrant, pg, stamped_collection):
    # ID phải là UUID hợp lệ — đúng hình dạng `cat_thanh_mau` (T2.3) thật sự
    # sinh ra (`str(uuid.uuid4())`), không phải chuỗi tuỳ ý.
    chunk_id = str(uuid.uuid4())
    chunk_chua_embed = Chunk(
        chunk_id=chunk_id,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        structure_path=["Điều 1"],
        span_start=0,
        span_end=10,
        embedding=[],
    )
    contract_config = load_contract_config(CONTRACT_PATH)

    with pytest.raises(ChunkChuaCoVector) as exc_info:
        ghi_vao_qdrant(
            [chunk_chua_embed],
            qdrant_client=qdrant,
            collection_name=stamped_collection,
            contract_config=contract_config,
            pg_connection=pg,
        )
    assert chunk_id in str(exc_info.value)

    con_lai = qdrant.retrieve(
        collection_name=stamped_collection, ids=[chunk_id], with_payload=False
    )
    assert con_lai == [], "Không được ghi gì vào Qdrant khi bị từ chối"
