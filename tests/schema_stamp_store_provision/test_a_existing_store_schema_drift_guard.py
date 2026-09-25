"""SCHEMA-stamp-store, yêu cầu 2: *"lúc provision trên kho đã tồn tại"* —
`assert_existing_schema_stamp_compatible` (tools/provision/provision_stores.py)
phải từ chối tái-provision ĐÈ LÊN một active record mang con dấu KHÁC số PHÁ
VỠ, cho một collection MỚI TOANH đi tiếp bình thường, và cho một lệch chỉ ở
số BỔ SUNG đi tiếp (đóng dấu lại tại chỗ, không cần `--recreate-collection`).

Đây là cơ chế bắt một thay đổi PHÁ VỠ thuần Ý NGHĨA (không thêm/bớt cột) mà
`assert_existing_tables_match`/`assert_existing_collection_matches` (kiểm
cột/khoá payload) không thấy được — đúng ca commit 1bcef42 (`span_start`/
`span_end` đổi nghĩa, không đổi cột).
"""

from __future__ import annotations

import pytest

from provision_stores import StoreOutOfDateError, assert_existing_schema_stamp_compatible
from schema.embedding_registry import (
    register_embedding_model,
    set_active_embedding_model_for_collection,
    stamp_schema_version_for_collection,
)
from schema.version import LOCAL_SCHEMA_VERSION, SchemaVersion

MODEL_A = "BAAI/bge-m3"
MODEL_VERSION = "v1"
DIM = 1024


def _activate_model(pg, probe_collection, catalog_rows, *, name_hint: str) -> str:
    created_models, created_collections = catalog_rows

    collection_name = probe_collection(name_hint)

    register_embedding_model(
        pg_connection=pg, model_name=MODEL_A, model_version=MODEL_VERSION, embedding_dim=DIM
    )
    created_models.append((MODEL_A, MODEL_VERSION))

    set_active_embedding_model_for_collection(
        pg_connection=pg, collection_name=collection_name, model_name=MODEL_A, model_version=MODEL_VERSION
    )
    created_collections.append(collection_name)

    return collection_name


def test_a_fresh_collection_never_stamped_passes(pg, qdrant, probe_collection):
    """Collection MỚI TOANH — không có gì để so, cho qua để phần còn lại của
    `main()` đóng dấu lần đầu."""
    collection_name = probe_collection("fresh")

    assert_existing_schema_stamp_compatible(pg_connection=pg, collection_name=collection_name)


def test_a_old_store_with_active_model_but_no_schema_stamp_refuses(
    pg, qdrant, probe_collection, catalog_rows
):
    """'Kho cũ không có dấu' (yêu cầu 3(d)): model đã active nhưng
    `stamp_schema_version_for_collection` chưa bao giờ chạy."""
    collection_name = _activate_model(pg, probe_collection, catalog_rows, name_hint="oldstore")

    with pytest.raises(StoreOutOfDateError) as excinfo:
        assert_existing_schema_stamp_compatible(pg_connection=pg, collection_name=collection_name)

    assert "--recreate-collection" in str(excinfo.value)


def test_a_breaking_drift_on_existing_store_refuses(pg, qdrant, probe_collection, catalog_rows):
    """Lệch số PHÁ VỠ trên một kho đã có active record → từ chối tái-provision
    IN PLACE, không cho phép câu UPDATE cuối `main()` âm thầm ghi đè lên trên."""
    collection_name = _activate_model(pg, probe_collection, catalog_rows, name_hint="breaking")
    stale = SchemaVersion(breaking=LOCAL_SCHEMA_VERSION.breaking - 1, additive=0)
    stamp_schema_version_for_collection(
        pg_connection=pg, collection_name=collection_name, schema_version=stale
    )

    with pytest.raises(StoreOutOfDateError) as excinfo:
        assert_existing_schema_stamp_compatible(pg_connection=pg, collection_name=collection_name)

    message = str(excinfo.value)
    assert "--recreate-collection" in message
    assert f"breaking={LOCAL_SCHEMA_VERSION.breaking}" in message
    assert f"breaking={stale.breaking}" in message


def test_a_additive_drift_on_existing_store_passes(pg, qdrant, probe_collection, catalog_rows):
    """Số bổ sung khác nhau KHÔNG chặn tái-provision — cho phép 'đóng dấu lại'
    tại chỗ mà không cần `--recreate-collection` (DX3: bên cũ bỏ qua trường
    mới được)."""
    collection_name = _activate_model(pg, probe_collection, catalog_rows, name_hint="additive")
    stale = SchemaVersion(
        breaking=LOCAL_SCHEMA_VERSION.breaking, additive=LOCAL_SCHEMA_VERSION.additive + 1
    )
    stamp_schema_version_for_collection(
        pg_connection=pg, collection_name=collection_name, schema_version=stale
    )

    assert_existing_schema_stamp_compatible(pg_connection=pg, collection_name=collection_name)


def test_a_matching_stamp_passes(pg, qdrant, probe_collection, catalog_rows):
    collection_name = _activate_model(pg, probe_collection, catalog_rows, name_hint="matching")
    stamp_schema_version_for_collection(
        pg_connection=pg, collection_name=collection_name, schema_version=LOCAL_SCHEMA_VERSION
    )

    assert_existing_schema_stamp_compatible(pg_connection=pg, collection_name=collection_name)
