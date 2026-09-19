"""T1.3 (b) — CA KHÓ NHẤT: đổi mô hình mà GIỮ NGUYÊN số chiều, qua đường THẬT.

Cộng: ánh xạ thước đo Qdrant → `DistanceMetric` nội bộ, và ca `Manhattan`
không map được (phải raise rõ ràng, không âm thầm coi như một giá trị khác).
"""

from __future__ import annotations

import pytest
from qdrant_client import models

from schema.config import ContractConfig, DistanceMetric, StoreStampMismatchError
from schema.embedding_registry import (
    UnsupportedQdrantDistanceError,
    assert_collection_ready_for_contract,
    read_store_stamp,
    register_embedding_model,
    set_active_embedding_model_for_collection,
)

MODEL_A = "BAAI/bge-m3"
MODEL_B = "intfloat/multilingual-e5-large"  # CŨNG 1024 chiều — đó là cái bẫy
DIM = 1024
MODEL_VERSION = "v1"


def test_hardest_case_same_dim_different_model_refuses_via_real_stores(
    pg, qdrant, probe_collection, catalog_rows
):
    """Kho THẬT (Qdrant + Postgres) được đóng dấu bằng MODEL_A ở 1024 chiều.
    Service khởi động với MODEL_B, CÙNG 1024 chiều — số chiều khớp hoàn hảo,
    Qdrant sẽ không hề phàn nàn. Chỉ con dấu mang tên mô hình mới bắt được.
    """
    created_models, created_collections = catalog_rows

    collection_name = probe_collection("hard", size=DIM)

    register_embedding_model(
        pg_connection=pg, model_name=MODEL_A, model_version=MODEL_VERSION, embedding_dim=DIM
    )
    created_models.append((MODEL_A, MODEL_VERSION))

    set_active_embedding_model_for_collection(
        pg_connection=pg, collection_name=collection_name, model_name=MODEL_A, model_version=MODEL_VERSION
    )
    created_collections.append(collection_name)

    # Service khởi động với mô hình KHÁC, CÙNG số chiều với kho đã đóng dấu.
    service_config = ContractConfig(
        embedding_model=MODEL_B, embedding_dim=DIM, distance_metric=DistanceMetric.COSINE
    )

    with pytest.raises(StoreStampMismatchError) as excinfo:
        assert_collection_ready_for_contract(
            config=service_config,
            qdrant_client=qdrant,
            pg_connection=pg,
            collection_name=collection_name,
        )

    message = str(excinfo.value)
    assert "embedding_model" in message
    assert "embedding_dim" not in message, "Số chiều khớp thì không được báo là lệch"
    assert "SỐ CHIỀU KHỚP" in message, "Ca nguy hiểm nhất phải được gọi tên trong thông báo"


def test_qdrant_manhattan_distance_has_no_mapping(pg, qdrant, probe_collection, catalog_rows):
    """`Manhattan` không có ánh xạ sang `DistanceMetric` nội bộ — phải raise,
    không được lặng lẽ trả về một giá trị nào đó.
    """
    created_models, created_collections = catalog_rows

    collection_name = probe_collection("manhattan", size=DIM, distance=models.Distance.MANHATTAN)

    register_embedding_model(
        pg_connection=pg, model_name=MODEL_A, model_version=MODEL_VERSION, embedding_dim=DIM
    )
    created_models.append((MODEL_A, MODEL_VERSION))

    set_active_embedding_model_for_collection(
        pg_connection=pg, collection_name=collection_name, model_name=MODEL_A, model_version=MODEL_VERSION
    )
    created_collections.append(collection_name)

    with pytest.raises(UnsupportedQdrantDistanceError) as excinfo:
        read_store_stamp(qdrant_client=qdrant, pg_connection=pg, collection_name=collection_name)

    assert "Manhattan" in str(excinfo.value)
