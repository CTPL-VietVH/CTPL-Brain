"""Item 1 of the work order: *"kiểm con dấu kho vector (T1.3) trước khi
nhận lời gọi"* — `build_deployment_app` must refuse, before the app is ever
handed to `uvicorn`, when the Qdrant collection named by
`CBRAIN_QDRANT_COLLECTION` does not exist, was never stamped, or is stamped
with a DIFFERENT model than `config/contract.yaml` names.

Reuses `schema.embedding_registry`'s own real refusal classes rather than
re-deriving the logic here — `assert_collection_ready_for_contract` is
already the single, tested entry point (T1.3); this file only proves
`build_deployment_app` actually calls it before anything else can serve
traffic.
"""

from __future__ import annotations

import pytest
from qdrant_client import models

from api.main import build_deployment_app
from schema.embedding_registry import (
    CollectionNotFoundOnQdrantError,
    CollectionNotStampedError,
    register_embedding_model,
    set_active_embedding_model_for_collection,
)


def test_c_a_collection_that_was_never_created_refuses(
    pg, qdrant, config_dir, unprovisioned_environ, fake_model, unprovisioned_deployment_env
) -> None:
    """`CBRAIN_QDRANT_COLLECTION` names a collection nobody provisioned yet —
    `tools/provision/provision_stores.py` was never run. Must refuse, not
    silently create one."""
    with pytest.raises(CollectionNotFoundOnQdrantError):
        build_deployment_app(
            config_dir=config_dir,
            environ=unprovisioned_environ,
            deployment=unprovisioned_deployment_env,
            pg_connection=pg,
            qdrant_client=qdrant,
            embedding_model=fake_model,
        )


def test_c_a_collection_that_exists_but_was_never_stamped_refuses(
    pg,
    qdrant,
    config_dir,
    unprovisioned_environ,
    unprovisioned_deployment_env,
    fake_model,
    contract_values,
) -> None:
    """The collection exists on Qdrant but `embedding_model_collections` has
    no row for it — nobody ran `register_embedding_model` /
    `set_active_embedding_model_for_collection` yet."""
    qdrant.create_collection(
        collection_name=unprovisioned_deployment_env.qdrant_collection,
        vectors_config=models.VectorParams(
            size=contract_values.embedding_dim, distance=models.Distance.COSINE
        ),
    )
    try:
        with pytest.raises(CollectionNotStampedError):
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


def test_c_a_collection_stamped_with_a_different_model_refuses(
    pg,
    qdrant,
    config_dir,
    unprovisioned_environ,
    unprovisioned_deployment_env,
    fake_model,
    contract_values,
) -> None:
    """⚠️ The dangerous case, verbatim from `schema/config.py`'s own
    docstring: same `embedding_dim`, DIFFERENT `embedding_model` — the one
    mismatch a naive "does the dimension match" check would miss."""
    qdrant.create_collection(
        collection_name=unprovisioned_deployment_env.qdrant_collection,
        vectors_config=models.VectorParams(
            size=contract_values.embedding_dim, distance=models.Distance.COSINE
        ),
    )
    other_model = "intfloat/multilingual-e5-large"
    try:
        register_embedding_model(
            pg_connection=pg,
            model_name=other_model,
            model_version="test",
            embedding_dim=contract_values.embedding_dim,  # same dim, different model
        )
        set_active_embedding_model_for_collection(
            pg_connection=pg,
            collection_name=unprovisioned_deployment_env.qdrant_collection,
            model_name=other_model,
            model_version="test",
        )

        from schema.config import StoreStampMismatchError

        with pytest.raises(StoreStampMismatchError) as excinfo:
            build_deployment_app(
                config_dir=config_dir,
                environ=unprovisioned_environ,
                deployment=unprovisioned_deployment_env,
                pg_connection=pg,
                qdrant_client=qdrant,
                embedding_model=fake_model,
            )
        assert other_model in str(excinfo.value)
        assert contract_values.embedding_model in str(excinfo.value)
    finally:
        qdrant.delete_collection(collection_name=unprovisioned_deployment_env.qdrant_collection)


def test_c_the_same_check_runs_again_on_every_meta_request(
    pg, qdrant, config_dir, complete_environ, deployment_env, fake_model, stamped_collection
) -> None:
    """docs/10 §3.6 — the difference between "refuses to start" and
    "degrades `/v1/meta`": once the app HAS started against a correctly
    stamped collection, dropping the collection afterwards must show up as
    `ready=false`, not crash the process and not stay silently `ready=true`.
    """
    app = build_deployment_app(
        config_dir=config_dir,
        environ=complete_environ,
        deployment=deployment_env,
        pg_connection=pg,
        qdrant_client=qdrant,
        embedding_model=fake_model,
    )
    assert app is not None

    # Simulate the collection vanishing after a healthy start.
    qdrant.delete_collection(collection_name=stamped_collection)

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        response = client.get(
            "/v1/meta", headers={"X-Service-Key": complete_environ["CBRAIN_API_SERVICE_KEY"]}
        )
    assert response.status_code == 200  # meta itself never 5xx's on this
    body = response.json()
    assert body["ready"] is False
    assert body["not_ready_reason"]
