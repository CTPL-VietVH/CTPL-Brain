"""T1.3 (a)+(d) — Đọc CON DẤU THẬT từ Qdrant+Postgres và so với hợp đồng.

Ca (a): khớp cả ba trường qua đường THẬT (không dựng tay `StoreStamp`) → im
lặng, không ngoại lệ.

Ca (d) — 08 T1.3: chạy MỘT MÌNH một service với cấu hình lệch con dấu, không
mô phỏng "service kia" — vẫn phải từ chối. Đây là bản THẬT (nối Qdrant +
Postgres) của kỹ thuật đã có ở
`tests/t1_2_config/test_b_store_stamp_mismatch.py::
test_one_service_alone_still_refuses_against_the_store`.
"""

from __future__ import annotations

import pytest

from schema.config import ContractConfig, DistanceMetric, StoreStampMismatchError
from schema.embedding_registry import (
    assert_collection_ready_for_contract,
    register_embedding_model,
    set_active_embedding_model_for_collection,
)

MODEL_A = "BAAI/bge-m3"
MODEL_B = "intfloat/multilingual-e5-large"  # CŨNG 1024 chiều — dùng ở ca khác
DIM = 1024
MODEL_VERSION = "v1"


def _stamp_a_real_collection(pg, probe_collection, catalog_rows, *, model_name: str, dim: int = DIM) -> str:
    """Dựng một collection Qdrant thật + đóng dấu active thật cho nó."""
    created_models, created_collections = catalog_rows

    collection_name = probe_collection("real", size=dim)

    register_embedding_model(
        pg_connection=pg, model_name=model_name, model_version=MODEL_VERSION, embedding_dim=dim
    )
    created_models.append((model_name, MODEL_VERSION))

    set_active_embedding_model_for_collection(
        pg_connection=pg,
        collection_name=collection_name,
        model_name=model_name,
        model_version=MODEL_VERSION,
    )
    created_collections.append(collection_name)

    return collection_name


def test_real_stamp_matches_contract_silently(pg, qdrant, probe_collection, catalog_rows):
    collection_name = _stamp_a_real_collection(pg, probe_collection, catalog_rows, model_name=MODEL_A)

    config = ContractConfig(
        embedding_model=MODEL_A, embedding_dim=DIM, distance_metric=DistanceMetric.COSINE
    )

    result = assert_collection_ready_for_contract(
        config=config,
        qdrant_client=qdrant,
        pg_connection=pg,
        collection_name=collection_name,
    )
    assert result is None


def test_one_service_alone_still_refuses_against_the_real_store(pg, qdrant, probe_collection, catalog_rows):
    """Kho được đóng dấu bằng MODEL_A. Một service (Retrieval) khởi động MỘT
    MÌNH với cấu hình MODEL_B — không có "Ingestion" nào chạy cùng ở đây, và
    hàm vẫn phải từ chối chỉ dựa trên con dấu của kho.
    """
    collection_name = _stamp_a_real_collection(pg, probe_collection, catalog_rows, model_name=MODEL_A)

    retrieval_alone = ContractConfig(
        embedding_model=MODEL_B, embedding_dim=DIM, distance_metric=DistanceMetric.COSINE
    )

    with pytest.raises(StoreStampMismatchError) as excinfo:
        assert_collection_ready_for_contract(
            config=retrieval_alone,
            qdrant_client=qdrant,
            pg_connection=pg,
            collection_name=collection_name,
        )

    message = str(excinfo.value)
    assert MODEL_A in message and MODEL_B in message
    assert collection_name in message, "Phải nêu KHO NÀO (store_name = tên collection)"
