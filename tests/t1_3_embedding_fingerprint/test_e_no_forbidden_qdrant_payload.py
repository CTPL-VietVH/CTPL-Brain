"""T1.3 (g) — Hai hàm ghi (`register_embedding_model`,
`set_active_embedding_model_for_collection`) KHÔNG được đụng gì tới Qdrant:
không `embedding_model`, không bất kỳ fingerprint nào lọt vào payload của một
point trong collection. Con dấu sống ở Postgres, khoá theo `collection_name`
— KHÔNG nhét vào payload cạnh mẩu.
"""

from __future__ import annotations

from schema.embedding_registry import (
    register_embedding_model,
    set_active_embedding_model_for_collection,
)

MODEL_A = "BAAI/bge-m3"
DIM = 1024
MODEL_VERSION = "v1"


def test_write_functions_never_touch_qdrant_points(pg, qdrant, probe_collection, catalog_rows):
    created_models, created_collections = catalog_rows

    collection_name = probe_collection("nopayload", size=DIM)

    before = qdrant.scroll(collection_name=collection_name, limit=100, with_payload=True)[0]
    assert before == [], "Collection mới tạo phải rỗng, chưa có point nào"

    register_embedding_model(
        pg_connection=pg, model_name=MODEL_A, model_version=MODEL_VERSION, embedding_dim=DIM
    )
    created_models.append((MODEL_A, MODEL_VERSION))

    set_active_embedding_model_for_collection(
        pg_connection=pg, collection_name=collection_name, model_name=MODEL_A, model_version=MODEL_VERSION
    )
    created_collections.append(collection_name)

    after = qdrant.scroll(collection_name=collection_name, limit=100, with_payload=True)[0]
    assert after == [], (
        "Hai hàm ghi catalog KHÔNG được tạo point nào trong Qdrant — "
        "embedding_model sống ở Postgres, không ở payload cạnh mẩu."
    )
