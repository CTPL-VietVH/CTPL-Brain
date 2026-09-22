"""T2.5 (c) — `ghi_vao_qdrant` ghi THẬT vào Qdrant, payload đúng whitelist
07 Mục 2.2 (không có `chunk_id`/`embedding` — đã tách thành id/vector của
điểm), và đọc `config/contract.yaml` THẬT qua `load_contract_config`.
"""

from __future__ import annotations

from schema.config import load_contract_config

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc
from ingestion.vectorization import ghi_vao_qdrant, sinh_vector

from .conftest import CONTRACT_PATH, DOC_ID, SPACE_ID, TENANT_ID

VAN_BAN = """Điều 1. Phạm vi điều chỉnh
Quy chế này áp dụng cho toàn thể cán bộ, nhân viên của công ty.

Điều 2. Giải thích từ ngữ
Người đại diện là người được uỷ quyền hợp pháp."""


def test_contract_config_that_khop_bge_m3():
    config = load_contract_config(CONTRACT_PATH)
    assert config.embedding_model == "BAAI/bge-m3"
    assert config.embedding_dim == 1024
    assert config.distance_metric.value == "cosine"


def test_ghi_vao_qdrant_upsert_dung_payload_whitelist(model, qdrant, pg, stamped_collection):
    read_result = dung_cau_truc(VAN_BAN, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=5000,
    )
    chunks_co_vector = sinh_vector(chunks, full_text=read_result.full_text, model=model)
    contract_config = load_contract_config(CONTRACT_PATH)

    ghi_vao_qdrant(
        chunks_co_vector,
        qdrant_client=qdrant,
        collection_name=stamped_collection,
        contract_config=contract_config,
        pg_connection=pg,
    )

    diem = qdrant.retrieve(
        collection_name=stamped_collection,
        ids=[c.chunk_id for c in chunks_co_vector],
        with_payload=True,
        with_vectors=True,
    )
    assert len(diem) == len(chunks_co_vector)

    theo_id = {str(p.id): p for p in diem}
    for chunk in chunks_co_vector:
        p = theo_id[chunk.chunk_id]
        assert p.payload["document_id"] == DOC_ID
        assert p.payload["space_id"] == SPACE_ID
        assert p.payload["tenant_id"] == TENANT_ID
        assert p.payload["structure_path"] == chunk.structure_path
        assert p.payload["span_start"] == chunk.span_start
        assert p.payload["span_end"] == chunk.span_end
        assert p.payload["parent_chunk_id"] == chunk.parent_chunk_id
        assert p.payload["category_labels"] == chunk.category_labels
        assert "chunk_id" not in p.payload, "chunk_id phải là ID điểm, không lặp lại trong payload"
        assert "embedding" not in p.payload, "embedding phải là vector của điểm, không nằm trong payload"
        assert len(p.vector) == 1024
