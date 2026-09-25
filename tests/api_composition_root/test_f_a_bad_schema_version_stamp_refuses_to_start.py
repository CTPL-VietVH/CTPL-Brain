"""SCHEMA-stamp-store, item 2 of the work order: *"Kiểm lúc khởi động service
(composition root)... kho không có dấu, hoặc lệch số phá vỡ → từ chối chạy...
lệch số bổ sung → ghi log cảnh báo, chạy tiếp."*

Same shape as `test_c_a_bad_vector_store_stamp_refuses_to_start.py`, but for
the schema-version stamp (`assert_store_schema_version_compatible`) instead
of the embedding-model stamp (`assert_collection_ready_for_contract`) —
`build_deployment_app` must call BOTH before the app is ever handed to
`uvicorn`.
"""

from __future__ import annotations

import logging

import pytest

from api.main import build_deployment_app
from schema.embedding_registry import (
    SchemaVersionNotStampedError,
    register_embedding_model,
    set_active_embedding_model_for_collection,
    stamp_schema_version_for_collection,
)
from schema.version import (
    LOCAL_SCHEMA_VERSION,
    SchemaBreakingVersionMismatchError,
    SchemaVersion,
)

VERSION_LOGGER = "schema.version"


def test_f_a_collection_with_active_model_but_no_schema_stamp_refuses(
    pg,
    qdrant,
    config_dir,
    unprovisioned_environ,
    unprovisioned_deployment_env,
    fake_model,
    contract_values,
) -> None:
    """'Kho cũ không có dấu': model đã active cho collection này, nhưng
    `stamp_schema_version_for_collection` chưa bao giờ chạy — hai cột số
    phiên bản schema còn NULL. Cùng khuôn với
    `test_c_a_collection_that_exists_but_was_never_stamped_refuses`, nhưng ở
    một bước sau: model ĐÃ đóng dấu, schema version thì CHƯA."""
    from qdrant_client import models

    qdrant.create_collection(
        collection_name=unprovisioned_deployment_env.qdrant_collection,
        vectors_config=models.VectorParams(
            size=contract_values.embedding_dim, distance=models.Distance.COSINE
        ),
    )
    try:
        register_embedding_model(
            pg_connection=pg,
            model_name=contract_values.embedding_model,
            model_version="test",
            embedding_dim=contract_values.embedding_dim,
        )
        set_active_embedding_model_for_collection(
            pg_connection=pg,
            collection_name=unprovisioned_deployment_env.qdrant_collection,
            model_name=contract_values.embedding_model,
            model_version="test",
        )
        # Deliberately no `stamp_schema_version_for_collection` call.

        with pytest.raises(SchemaVersionNotStampedError):
            build_deployment_app(
                config_dir=config_dir,
                environ=unprovisioned_environ,
                deployment=unprovisioned_deployment_env,
                pg_connection=pg,
                qdrant_client=qdrant,
                embedding_model=fake_model,
            )
    finally:
        qdrant.delete_collection(collection_name=unprovisioned_deployment_env.qdrant_collection)


def test_f_a_collection_stamped_with_a_different_breaking_schema_version_refuses(
    pg, qdrant, config_dir, complete_environ, deployment_env, fake_model, stamped_collection
) -> None:
    """`stamped_collection` is correctly stamped by the fixture. Overwrite it
    with a different BREAKING number, as if this Postgres row predates the
    running code's `packages/schema` — must refuse, same as a real deploy
    where Ingestion nâng lên trước, Retrieval nâng lên sau."""
    stale = SchemaVersion(breaking=LOCAL_SCHEMA_VERSION.breaking - 1, additive=0)
    stamp_schema_version_for_collection(
        pg_connection=pg, collection_name=stamped_collection, schema_version=stale
    )

    with pytest.raises(SchemaBreakingVersionMismatchError) as excinfo:
        build_deployment_app(
            config_dir=config_dir,
            environ=complete_environ,
            deployment=deployment_env,
            pg_connection=pg,
            qdrant_client=qdrant,
            embedding_model=fake_model,
        )

    message = str(excinfo.value)
    assert f"breaking={LOCAL_SCHEMA_VERSION.breaking}" in message
    assert f"breaking={stale.breaking}" in message


def test_f_a_collection_stamped_with_a_different_additive_schema_version_still_starts(
    pg, qdrant, config_dir, complete_environ, deployment_env, fake_model, stamped_collection, caplog
) -> None:
    """Lệch số BỔ SUNG không được chặn khởi động — DX3: bên cũ bỏ qua trường
    mới được, dừng cả hệ thống ở đây là cái giá làm người ta ngừng tăng số."""
    stale = SchemaVersion(
        breaking=LOCAL_SCHEMA_VERSION.breaking, additive=LOCAL_SCHEMA_VERSION.additive + 1
    )
    stamp_schema_version_for_collection(
        pg_connection=pg, collection_name=stamped_collection, schema_version=stale
    )

    with caplog.at_level(logging.WARNING, logger=VERSION_LOGGER):
        app = build_deployment_app(
            config_dir=config_dir,
            environ=complete_environ,
            deployment=deployment_env,
            pg_connection=pg,
            qdrant_client=qdrant,
            embedding_model=fake_model,
        )

    assert app is not None
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1


def test_f_the_same_check_runs_again_on_every_meta_request(
    pg, qdrant, config_dir, complete_environ, deployment_env, fake_model, stamped_collection
) -> None:
    """Same difference `test_c` proves for the embedding-model stamp: once
    the app HAS started against a correctly stamped collection, the schema
    version drifting AFTER a healthy start must show up as `ready=false` on
    the next `/v1/meta` call, not crash the process and not stay silently
    `ready=true`."""
    app = build_deployment_app(
        config_dir=config_dir,
        environ=complete_environ,
        deployment=deployment_env,
        pg_connection=pg,
        qdrant_client=qdrant,
        embedding_model=fake_model,
    )
    assert app is not None

    stale = SchemaVersion(breaking=LOCAL_SCHEMA_VERSION.breaking - 1, additive=0)
    stamp_schema_version_for_collection(
        pg_connection=pg, collection_name=stamped_collection, schema_version=stale
    )

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        response = client.get(
            "/v1/meta", headers={"X-Service-Key": complete_environ["CBRAIN_API_SERVICE_KEY"]}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert body["not_ready_reason"]
