"""T1.3 (e)+(f) — Hai hàm ghi tối thiểu của catalog.

Ca (e): đăng ký catalog trùng `(model_name, model_version)` với dim KHÁC →
raise; đăng ký lại Y HỆT → không lỗi (idempotent).
Ca (f): gán active cho một `(model_name, model_version)` chưa từng có trong
catalog → raise lỗi rõ ràng, bọc lại vi phạm khoá ngoại của Postgres.
"""

from __future__ import annotations

import uuid

import pytest

from schema.embedding_registry import (
    CatalogEntryConflictError,
    UnknownCatalogEntryError,
    register_embedding_model,
    set_active_embedding_model_for_collection,
)

MODEL_A = "BAAI/bge-m3"
DIM = 1024
MODEL_VERSION = "v1"


def test_register_is_idempotent_for_identical_values(pg, catalog_rows):
    created_models, _ = catalog_rows

    register_embedding_model(
        pg_connection=pg, model_name=MODEL_A, model_version=MODEL_VERSION, embedding_dim=DIM
    )
    created_models.append((MODEL_A, MODEL_VERSION))

    # Đăng ký lại ĐÚNG Y HỆT giá trị cũ — không được raise.
    register_embedding_model(
        pg_connection=pg, model_name=MODEL_A, model_version=MODEL_VERSION, embedding_dim=DIM
    )


def test_register_conflicting_dim_for_same_model_version_raises(pg, catalog_rows):
    created_models, _ = catalog_rows

    register_embedding_model(
        pg_connection=pg, model_name=MODEL_A, model_version=MODEL_VERSION, embedding_dim=DIM
    )
    created_models.append((MODEL_A, MODEL_VERSION))

    with pytest.raises(CatalogEntryConflictError) as excinfo:
        register_embedding_model(
            pg_connection=pg, model_name=MODEL_A, model_version=MODEL_VERSION, embedding_dim=768
        )

    message = str(excinfo.value)
    assert MODEL_A in message and MODEL_VERSION in message


def test_set_active_for_unknown_catalog_entry_raises_clear_error(pg, catalog_rows):
    """Không dùng Qdrant thật ở đây — `set_active_embedding_model_for_collection`
    CHỈ ghi Postgres (ca (g) kiểm riêng ở file khác), nên một tên collection
    bịa cũng đủ để test hành vi FK.
    """
    _, created_collections = catalog_rows
    collection_name = f"t1_3_unknown_model_{uuid.uuid4().hex[:8]}"

    with pytest.raises(UnknownCatalogEntryError) as excinfo:
        set_active_embedding_model_for_collection(
            pg_connection=pg,
            collection_name=collection_name,
            model_name="never/registered",
            model_version=MODEL_VERSION,
        )
    created_collections.append(collection_name)  # phòng hờ — không gì để xoá vì insert đã thất bại

    message = str(excinfo.value)
    assert "never/registered" in message
    assert "register_embedding_model" in message
