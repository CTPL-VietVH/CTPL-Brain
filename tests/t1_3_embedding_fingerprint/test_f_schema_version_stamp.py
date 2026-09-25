"""SCHEMA-stamp-store — con dấu SỐ PHIÊN BẢN SCHEMA trên kho thật, cùng nhà
với con dấu `embedding_model` (bảng `embedding_model_collections`, khoá theo
`collection_name`). Bốn ca của work order, chạy trên Postgres + Qdrant THẬT:

(a) kho đúng dấu → chạy (không raise gì).
(b) lệch số PHÁ VỠ → từ chối (`SchemaBreakingVersionMismatchError`).
(c) lệch số BỔ SUNG → ghi log + chạy (không raise).
(d) kho cũ không có dấu → từ chối — hai hình dạng của "cũ":
    - CHƯA TỪNG active model nào (không có hàng) → `CollectionNotStampedError`
      (cùng lỗi `read_store_stamp` dùng, vì CÙNG một hàng dữ liệu).
    - ĐÃ active model nhưng CHƯA đóng dấu schema version (hàng tồn tại, hai
      cột còn NULL) → `SchemaVersionNotStampedError`.
"""

from __future__ import annotations

import logging

import pytest

from schema.embedding_registry import (
    CollectionNotStampedError,
    SchemaVersionNotStampedError,
    assert_store_schema_version_compatible,
    read_schema_version_stamp,
    register_embedding_model,
    set_active_embedding_model_for_collection,
    stamp_schema_version_for_collection,
)
from schema.version import (
    LOCAL_SCHEMA_VERSION,
    SchemaBreakingVersionMismatchError,
    SchemaVersion,
)

MODEL_A = "BAAI/bge-m3"
DIM = 1024
MODEL_VERSION = "v1"
VERSION_LOGGER = "schema.version"


def _activate_model(pg, probe_collection, catalog_rows, *, name_hint: str) -> str:
    """Dựng một collection Qdrant thật + gán model active thật — CHƯA đóng
    dấu số phiên bản schema (đó là việc riêng của mỗi test)."""
    created_models, created_collections = catalog_rows

    collection_name = probe_collection(name_hint, size=DIM)

    register_embedding_model(
        pg_connection=pg, model_name=MODEL_A, model_version=MODEL_VERSION, embedding_dim=DIM
    )
    created_models.append((MODEL_A, MODEL_VERSION))

    set_active_embedding_model_for_collection(
        pg_connection=pg, collection_name=collection_name, model_name=MODEL_A, model_version=MODEL_VERSION
    )
    created_collections.append(collection_name)

    return collection_name


def test_read_before_any_active_record_refuses_without_guessing(pg, qdrant, probe_collection):
    """Collection MỚI TOANH, chưa ai active model nào cho nó — không có hàng
    nào trong `embedding_model_collections` để đọc số phiên bản schema."""
    collection_name = probe_collection("schemaver_neveractive", size=DIM)

    with pytest.raises(CollectionNotStampedError):
        read_schema_version_stamp(pg_connection=pg, collection_name=collection_name)


def test_stamping_before_model_is_active_refuses(pg, qdrant, probe_collection):
    """`stamp_schema_version_for_collection` là UPDATE, không phải upsert:
    không có hàng active nào để cập nhật vào thì phải từ chối, không tự tạo
    một hàng thiếu `model_name`/`model_version` (NOT NULL)."""
    collection_name = probe_collection("schemaver_stampfirst", size=DIM)

    with pytest.raises(CollectionNotStampedError):
        stamp_schema_version_for_collection(
            pg_connection=pg,
            collection_name=collection_name,
            schema_version=LOCAL_SCHEMA_VERSION,
        )


def test_old_store_with_active_model_but_no_schema_stamp_refuses(
    pg, qdrant, probe_collection, catalog_rows
):
    """Ca (d) — 'kho cũ không có dấu': model đã active (hàng tồn tại) nhưng
    hai cột số phiên bản schema còn NULL, vì `stamp_schema_version_for_collection`
    chưa bao giờ chạy trên collection này."""
    collection_name = _activate_model(
        pg, probe_collection, catalog_rows, name_hint="schemaver_oldstore"
    )

    with pytest.raises(SchemaVersionNotStampedError):
        read_schema_version_stamp(pg_connection=pg, collection_name=collection_name)

    with pytest.raises(SchemaVersionNotStampedError):
        assert_store_schema_version_compatible(pg_connection=pg, collection_name=collection_name)


def test_stamp_then_read_round_trips_and_passes_the_startup_check(
    pg, qdrant, probe_collection, catalog_rows
):
    """Ca (a) — kho đúng dấu → chạy."""
    collection_name = _activate_model(
        pg, probe_collection, catalog_rows, name_hint="schemaver_happy"
    )

    stamp_schema_version_for_collection(
        pg_connection=pg, collection_name=collection_name, schema_version=LOCAL_SCHEMA_VERSION
    )

    stamp = read_schema_version_stamp(pg_connection=pg, collection_name=collection_name)
    assert stamp == LOCAL_SCHEMA_VERSION

    result = assert_store_schema_version_compatible(pg_connection=pg, collection_name=collection_name)
    assert result is None


def test_restamping_is_idempotent_and_overwritable(pg, qdrant, probe_collection, catalog_rows):
    """Gọi lại `stamp_schema_version_for_collection` với số KHÁC là hành vi
    HỢP LỆ (bước "đóng dấu lại" — xem docstring của hàm), không phải một lần
    ghi chỉ-được-một-lần."""
    collection_name = _activate_model(
        pg, probe_collection, catalog_rows, name_hint="schemaver_restamp"
    )

    stamp_schema_version_for_collection(
        pg_connection=pg,
        collection_name=collection_name,
        schema_version=SchemaVersion(breaking=1, additive=0),
    )
    stamp_schema_version_for_collection(
        pg_connection=pg, collection_name=collection_name, schema_version=LOCAL_SCHEMA_VERSION
    )

    assert read_schema_version_stamp(pg_connection=pg, collection_name=collection_name) == (
        LOCAL_SCHEMA_VERSION
    )


def test_breaking_mismatch_refuses(pg, qdrant, probe_collection, catalog_rows):
    """Ca (b) — lệch số PHÁ VỠ → từ chối, không có đường chạy tiếp."""
    collection_name = _activate_model(
        pg, probe_collection, catalog_rows, name_hint="schemaver_breaking"
    )
    stale = SchemaVersion(breaking=LOCAL_SCHEMA_VERSION.breaking - 1, additive=0)
    stamp_schema_version_for_collection(
        pg_connection=pg, collection_name=collection_name, schema_version=stale
    )

    with pytest.raises(SchemaBreakingVersionMismatchError) as excinfo:
        assert_store_schema_version_compatible(pg_connection=pg, collection_name=collection_name)

    message = str(excinfo.value)
    assert f"breaking={LOCAL_SCHEMA_VERSION.breaking}" in message
    assert f"breaking={stale.breaking}" in message
    assert collection_name in message, "Phải nêu KHO NÀO (collection_name)"


def test_additive_mismatch_logs_and_keeps_running(pg, qdrant, probe_collection, catalog_rows, caplog):
    """Ca (c) — lệch số BỔ SUNG → ghi nhật ký, VẪN CHẠY. Không raise."""
    collection_name = _activate_model(
        pg, probe_collection, catalog_rows, name_hint="schemaver_additive"
    )
    stale = SchemaVersion(
        breaking=LOCAL_SCHEMA_VERSION.breaking, additive=LOCAL_SCHEMA_VERSION.additive + 1
    )
    stamp_schema_version_for_collection(
        pg_connection=pg, collection_name=collection_name, schema_version=stale
    )

    with caplog.at_level(logging.WARNING, logger=VERSION_LOGGER):
        result = assert_store_schema_version_compatible(
            pg_connection=pg, collection_name=collection_name
        )

    assert result is None
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1, "Phải ghi đúng một bản ghi cảnh báo — im lặng là mất cơ chế"
