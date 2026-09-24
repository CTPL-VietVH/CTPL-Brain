"""`CBRAIN_MODEL_HOME` naming a directory that was never populated with
BGE-M3 — `load_embedding_model` must refuse before the (injected) loader is
even called, and the refusal must name the directory.

No real model load happens here either way — `loader` is stubbed to fail the
test if it is ever reached, which is what proves the guard runs BEFORE the
loader, not just that loading eventually fails.
"""

from __future__ import annotations

import pathlib

import pytest

from api.main import ModelHomeNotFound, load_embedding_model


def test_e_a_missing_model_home_refuses_before_the_loader_runs(
    deployment_env, contract_values, tmp_path: pathlib.Path
) -> None:
    never_populated = tmp_path / "does-not-exist"
    assert not never_populated.exists()
    broken_deployment = deployment_env.__class__(
        pg_dsn=deployment_env.pg_dsn,
        qdrant_host=deployment_env.qdrant_host,
        qdrant_http_port=deployment_env.qdrant_http_port,
        qdrant_collection=deployment_env.qdrant_collection,
        staging_dir=deployment_env.staging_dir,
        model_home=never_populated,
    )

    def _loader_that_must_not_run(model_name: str):
        pytest.fail(
            "load_embedding_model must refuse for a missing model_home "
            "BEFORE calling the loader — got model_name="
            f"{model_name!r} instead of a refusal."
        )

    with pytest.raises(ModelHomeNotFound) as excinfo:
        load_embedding_model(
            broken_deployment, contract_values, loader=_loader_that_must_not_run
        )

    assert str(never_populated) in str(excinfo.value)


def test_e_a_present_model_home_calls_the_injected_loader(
    deployment_env, contract_values
) -> None:
    """The control case, and the mechanism the rest of this folder relies on
    to avoid loading the real 2.5GB model: `deployment_env.model_home` (from
    `.env`'s `CBRAIN_MODEL_HOME`) exists on this machine — see
    `tests/t0_2_embedding/README.md` for why it must, to run this suite at
    all — so the guard passes and the INJECTED loader runs instead of the
    real `SentenceTransformer(...)`.
    """
    calls: list[str] = []

    def _fake_loader(model_name: str):
        calls.append(model_name)
        return object()

    load_embedding_model(deployment_env, contract_values, loader=_fake_loader)

    assert calls == [contract_values.embedding_model]
