"""T1.3 (c) — Collection CHƯA TỪNG được đóng dấu active trong Postgres →
raise, KHÔNG suy đoán.

Cộng hai ca liền kề trong cùng đường đọc: collection không tồn tại trên
Qdrant, và catalog Postgres tự mâu thuẫn (dim ghi trong `embedding_models`
lệch với dim thật của Qdrant).
"""

from __future__ import annotations

import pytest

from schema.embedding_registry import (
    CatalogDimensionConflictError,
    CollectionNotFoundOnQdrantError,
    CollectionNotStampedError,
    read_store_stamp,
    register_embedding_model,
    set_active_embedding_model_for_collection,
)

MODEL_A = "BAAI/bge-m3"
DIM = 1024
MODEL_VERSION = "v1"


def test_collection_never_stamped_refuses_without_guessing(pg, qdrant, probe_collection):
    """Collection MỚI TOANH trên Qdrant, chưa ai gán model nào cho nó trong
    Postgres — TỪ CHỐI CHẠY, không suy đoán bằng cách nào khác.
    """
    collection_name = probe_collection("unstamped", size=DIM)  # KHÔNG gán active

    with pytest.raises(CollectionNotStampedError):
        read_store_stamp(qdrant_client=qdrant, pg_connection=pg, collection_name=collection_name)


def test_collection_missing_on_qdrant_refuses(pg, qdrant):
    """Collection nêu tên không hề tồn tại trên Qdrant."""
    with pytest.raises(CollectionNotFoundOnQdrantError):
        read_store_stamp(
            qdrant_client=qdrant,
            pg_connection=pg,
            collection_name="t1_3_does_not_exist_ever_a1b2c3",
        )


def test_catalog_dimension_conflict_is_caught(pg, qdrant, probe_collection, catalog_rows):
    """Catalog Postgres ghi `embedding_dim` SAI so với dim thật của Qdrant →
    raise, KHÔNG lặng lẽ dùng dim thật của Qdrant thay cho catalog.
    """
    created_models, created_collections = catalog_rows

    real_dim = DIM
    wrong_catalog_dim = 768
    collection_name = probe_collection("dimconflict", size=real_dim)

    register_embedding_model(
        pg_connection=pg, model_name=MODEL_A, model_version=MODEL_VERSION, embedding_dim=wrong_catalog_dim
    )
    created_models.append((MODEL_A, MODEL_VERSION))

    set_active_embedding_model_for_collection(
        pg_connection=pg, collection_name=collection_name, model_name=MODEL_A, model_version=MODEL_VERSION
    )
    created_collections.append(collection_name)

    with pytest.raises(CatalogDimensionConflictError) as excinfo:
        read_store_stamp(qdrant_client=qdrant, pg_connection=pg, collection_name=collection_name)

    message = str(excinfo.value)
    assert str(wrong_catalog_dim) in message and str(real_dim) in message
