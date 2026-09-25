"""Fixtures for `packages/api/main.py` — the composition root.

⚠️ Unlike `tests/api/conftest.py` (in-memory stores only, by design — see its
own docstring), this folder connects to a REAL, disposable PostgreSQL and a
REAL Qdrant, the same way `tests/t0_1_stores/conftest.py` and
`tests/t1_3_embedding_fingerprint/conftest.py` already do. The one thing kept
fake is the ~2.5GB BGE-M3 model — item 7 of the work order: *"Test tự động
cho điểm khởi động dùng BGE giả (không nạp 4 GB mô hình trong pytest)"*. Every
other piece of `build_deployment_app` runs against the real thing, which is
the only way a test can prove `_assert_tables_exist` or
`assert_collection_ready_for_contract` actually refuse against a REAL store.

Each test gets its OWN throwaway PostgreSQL schema-worth of tables (dropped
after) and its OWN throwaway Qdrant collection, so nothing here collides with
a developer's manual `cbrain_dev` database or `cbrain_chunks` collection.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import sys
import uuid
from datetime import datetime

import psycopg
import pytest
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from api.main import DeploymentEnv  # noqa: E402
from ingestion.pre_approval_buffer import (  # noqa: E402
    PRE_APPROVAL_CHUNK_TABLE_DDL,
    PRE_APPROVAL_DOCUMENT_TABLE_DDL,
)
from schema.embedding_registry import (  # noqa: E402
    EMBEDDING_MODEL_COLLECTIONS_TABLE,
    EMBEDDING_MODEL_COLLECTIONS_TABLE_DDL,
    EMBEDDING_MODELS_TABLE,
    EMBEDDING_MODELS_TABLE_DDL,
    register_embedding_model,
    set_active_embedding_model_for_collection,
    stamp_schema_version_for_collection,
)
from schema.store_schema import SHARED_STORE_DDL
from schema.version import LOCAL_SCHEMA_VERSION  # noqa: E402

CONFIG_FILENAMES = ("contract.yaml", "ingestion.yaml", "retrieval.yaml")

#: The real DDL, in the real order — never re-typed. Same list
#: `tools/provision/provision_stores.py` runs.
_ALL_DDL = (
    *SHARED_STORE_DDL,
    PRE_APPROVAL_DOCUMENT_TABLE_DDL,
    PRE_APPROVAL_CHUNK_TABLE_DDL,
    EMBEDDING_MODELS_TABLE_DDL,
    EMBEDDING_MODEL_COLLECTIONS_TABLE_DDL,
)


class FakeBgeM3:
    """Satisfies `vectorization.BgeM3Like` without loading 2.5GB.

    Same shape `tests/api/conftest.py` already uses — see that module's own
    docstring for why a fake proves GĐ6 ran without needing the real model.
    """

    def __init__(self, *, max_seq_length: int = 8192) -> None:
        self.max_seq_length = max_seq_length
        self.tokenizer = self
        self.encode_calls = 0

    def encode(self, sentences, *, normalize_embeddings=None, batch_size=None):
        if isinstance(sentences, str):
            return sentences.split()
        self.encode_calls += 1
        import numpy as np

        return np.array(
            [[float(len(text) % 7 + i), 0.5, 0.25, 0.125] for i, text in enumerate(sentences)],
            dtype=float,
        )


def _require(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        pytest.fail(
            f"Missing environment variable {name!r}. No default in code — "
            f"copy .env.example to .env and fill it in."
        )
    return value


@pytest.fixture(scope="session", autouse=True)
def _env() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        pytest.fail(f"Missing {env_file}. Run: cp .env.example .env")
    load_dotenv(env_file)


@pytest.fixture(scope="session")
def real_pg_dsn(_env: None) -> str:
    host = _require("CBRAIN_PG_HOST")
    port = _require("CBRAIN_PG_PORT")
    database = _require("CBRAIN_PG_DATABASE")
    user = _require("CBRAIN_PG_USER")
    password = os.environ.get("CBRAIN_PG_PASSWORD") or ""
    auth = f"{user}:{password}" if password else user
    return f"postgresql://{auth}@{host}:{port}/{database}"


@pytest.fixture
def pg(real_pg_dsn: str):
    """A real connection, with every REQUIRED table freshly created —
    dropped again after the test. A fresh `CREATE TABLE` per test (rather
    than a session-scoped one, like `tests/t1_3_embedding_fingerprint` uses
    for the two catalog tables alone) is what lets `test_b_*` legitimately
    `DROP` one table mid-test to prove `_assert_tables_exist` catches it.
    """
    with psycopg.connect(real_pg_dsn, autocommit=True) as conn:
        for ddl in _ALL_DDL:
            conn.execute(ddl)
        yield conn
        # Drop in dependency-reversed order — relation/chunk tables carry FKs.
        for table in (
            "relation",
            "document",
            "deletion_log",
            "space_registry",
            "ingestion_record",
            "ingestion_pre_approval_chunk",
            "ingestion_pre_approval_document",
            EMBEDDING_MODEL_COLLECTIONS_TABLE,
            EMBEDDING_MODELS_TABLE,
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


@pytest.fixture(scope="session")
def qdrant(_env: None) -> QdrantClient:
    host = _require("CBRAIN_QDRANT_HOST")
    port = int(_require("CBRAIN_QDRANT_HTTP_PORT"))
    client = QdrantClient(host=host, port=port)
    client.get_collections()
    return client


@pytest.fixture
def contract_values():
    """The real `config/contract.yaml` values — read once here so a test can
    stamp a throwaway collection with the SAME model/dim the real config
    file names, without hand-typing a second copy (CLAUDE.md Mục 6)."""
    from schema.config import load_contract_config

    return load_contract_config(REPO_ROOT / "config" / "contract.yaml")


@pytest.fixture
def stamped_collection(qdrant: QdrantClient, pg: psycopg.Connection, contract_values):
    """A throwaway Qdrant collection, correctly stamped active in `pg` —
    the happy-path precondition `assert_collection_ready_for_contract` AND
    `assert_store_schema_version_compatible` check for (both model stamp and
    schema-version stamp, SCHEMA-stamp-store). Deleted after the test, Qdrant
    side and Postgres side both.
    """
    name = f"cbrain_test_composition_root_{uuid.uuid4().hex[:8]}"
    qdrant.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(
            size=contract_values.embedding_dim, distance=models.Distance.COSINE
        ),
    )
    register_embedding_model(
        pg_connection=pg,
        model_name=contract_values.embedding_model,
        model_version="test",
        embedding_dim=contract_values.embedding_dim,
    )
    set_active_embedding_model_for_collection(
        pg_connection=pg,
        collection_name=name,
        model_name=contract_values.embedding_model,
        model_version="test",
    )
    stamp_schema_version_for_collection(
        pg_connection=pg,
        collection_name=name,
        schema_version=LOCAL_SCHEMA_VERSION,
    )
    yield name
    qdrant.delete_collection(collection_name=name)


@pytest.fixture
def config_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """A writable copy of the real `config/` — same reasoning as
    `tests/api/conftest.py`'s fixture of the same name."""
    destination = tmp_path / "config"
    destination.mkdir()
    for filename in CONFIG_FILENAMES:
        shutil.copyfile(REPO_ROOT / "config" / filename, destination / filename)
    return destination


@pytest.fixture
def staging_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "staging"


def _environ_for(*, collection_name: str, staging_dir: pathlib.Path) -> dict[str, str]:
    """Every deployment-location variable `resolve_deployment_env` needs,
    plus the service key and tenant id `api.app.build_app` needs — pointed
    at the real (disposable) PostgreSQL/staging this session's fixtures
    built, with a CALLER-CHOSEN collection name so a test can point at one
    that was never provisioned (see `unprovisioned_environ` below) without
    the `stamped_collection` fixture creating it as a side effect first.
    """
    return {
        "CBRAIN_PG_HOST": _require("CBRAIN_PG_HOST"),
        "CBRAIN_PG_PORT": _require("CBRAIN_PG_PORT"),
        "CBRAIN_PG_DATABASE": _require("CBRAIN_PG_DATABASE"),
        "CBRAIN_PG_USER": _require("CBRAIN_PG_USER"),
        "CBRAIN_PG_PASSWORD": os.environ.get("CBRAIN_PG_PASSWORD") or "",
        "CBRAIN_QDRANT_HOST": _require("CBRAIN_QDRANT_HOST"),
        "CBRAIN_QDRANT_HTTP_PORT": _require("CBRAIN_QDRANT_HTTP_PORT"),
        "CBRAIN_QDRANT_COLLECTION": collection_name,
        "CBRAIN_STAGING_DIR": str(staging_dir),
        "CBRAIN_MODEL_HOME": str(REPO_ROOT / ".runtime" / "models"),
        "CBRAIN_API_SERVICE_KEY": "test-service-key-composition-root",
        "CBRAIN_TENANT_ID": "tenant-test-composition-root",
    }


@pytest.fixture
def complete_environ(stamped_collection: str, staging_dir: pathlib.Path) -> dict[str, str]:
    return _environ_for(collection_name=stamped_collection, staging_dir=staging_dir)


@pytest.fixture
def deployment_env(complete_environ: dict[str, str]) -> DeploymentEnv:
    from api.main import resolve_deployment_env

    return resolve_deployment_env(complete_environ)


@pytest.fixture
def unprovisioned_environ(staging_dir: pathlib.Path) -> dict[str, str]:
    """Points at a Qdrant collection NAME that nothing has created —
    `tools/provision/provision_stores.py` was never run for it. Does not
    depend on `stamped_collection`, so nothing here creates the collection
    as a side effect of building the environment.
    """
    name = f"cbrain_test_unprovisioned_{uuid.uuid4().hex[:8]}"
    return _environ_for(collection_name=name, staging_dir=staging_dir)


@pytest.fixture
def unprovisioned_deployment_env(unprovisioned_environ: dict[str, str]) -> DeploymentEnv:
    from api.main import resolve_deployment_env

    return resolve_deployment_env(unprovisioned_environ)


@pytest.fixture
def fake_model() -> FakeBgeM3:
    return FakeBgeM3()


def utc_clock() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)
