"""One-shot, idempotent provisioning for a fresh install — the ONE place in
this repo allowed to `CREATE TABLE` and `create_collection`.

`packages/api/main.py` deliberately does the opposite: it only CHECKS that
the tables and the Qdrant collection already exist and are correctly stamped
(CLAUDE.md Mục 4 quy tắc 2, applied to store provisioning — "thiếu thì từ
chối khởi động, không tự tạo ngầm"). This script is what an operator (or this
task's end-to-end test) runs once, by hand, BEFORE the service is started for
the first time.

Run:  .venv/bin/python tools/provision/provision_stores.py
      [--model-version v1] [--recreate-collection]

Idempotent: every `CREATE TABLE` is `IF NOT EXISTS`
(`schema/store_schema.py`, `ingestion/pre_approval_buffer.py`,
`schema/embedding_registry.py`); `register_embedding_model` and
`set_active_embedding_model_for_collection` are themselves idempotent
upserts (see their own docstrings). Running this twice against an
already-provisioned install changes nothing.

`--model-version` has no home in `config/` — it is not one of 07 Mục 3.2's
eleven tuning parameters, and `schema/embedding_registry.py`'s own docstring
explains why the catalog needs a version at all (history/audit, never read
back into `StoreStamp`). A CLI default for a ONE-SHOT TOOL's own bookkeeping
column is not the same thing as a hidden default for a service's runtime
behaviour (CLAUDE.md Mục 4 quy tắc 5) — nothing here governs what the running
service does.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

import os  # noqa: E402

from api.main import (  # noqa: E402
    DeploymentEnv,
    connect_postgres,
    connect_qdrant,
    resolve_deployment_env,
)
from ingestion.pre_approval_buffer import (  # noqa: E402
    PRE_APPROVAL_CHUNK_TABLE_DDL,
    PRE_APPROVAL_DOCUMENT_TABLE_DDL,
)
from qdrant_client import models as qdrant_models  # noqa: E402
from schema.config import load_contract_config  # noqa: E402
from schema.embedding_registry import (  # noqa: E402
    EMBEDDING_MODEL_COLLECTIONS_TABLE_DDL,
    EMBEDDING_MODELS_TABLE_DDL,
    register_embedding_model,
    set_active_embedding_model_for_collection,
)
from schema.store_schema import SHARED_STORE_DDL  # noqa: E402

CONFIG_DIR = REPO_ROOT / "config"

#: Dependency order: `document` before `relation` (FK), the two catalog
#: tables before nothing else references them yet. Every statement is
#: `CREATE TABLE IF NOT EXISTS` — see the module docstring.
_ALL_DDL: tuple[str, ...] = (
    *SHARED_STORE_DDL,
    PRE_APPROVAL_DOCUMENT_TABLE_DDL,
    PRE_APPROVAL_CHUNK_TABLE_DDL,
    EMBEDDING_MODELS_TABLE_DDL,
    EMBEDDING_MODEL_COLLECTIONS_TABLE_DDL,
)


def _load_env_file() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        raise SystemExit(f"Missing {env_file}. Run: cp .env.example .env")
    from dotenv import load_dotenv

    load_dotenv(env_file)


def create_tables(connection) -> list[str]:
    created: list[str] = []
    for ddl in _ALL_DDL:
        connection.execute(ddl)
        created.append(ddl.strip().splitlines()[0])
    return created


def ensure_collection(
    *, qdrant_client, deployment: DeploymentEnv, embedding_dim: int, recreate: bool
) -> bool:
    """Returns whether a collection was created (False = already existed)."""
    existing = {c.name for c in qdrant_client.get_collections().collections}
    if deployment.qdrant_collection in existing:
        if recreate:
            qdrant_client.delete_collection(collection_name=deployment.qdrant_collection)
        else:
            return False
    qdrant_client.create_collection(
        collection_name=deployment.qdrant_collection,
        vectors_config=qdrant_models.VectorParams(
            size=embedding_dim, distance=qdrant_models.Distance.COSINE
        ),
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-version",
        default="v1",
        help="Catalog bookkeeping version for embedding_models (default: v1). "
        "Not a config/ parameter — see the module docstring.",
    )
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        help="Drop and recreate the Qdrant collection if it already exists "
        "(destroys every vector in it — use only for a throwaway install).",
    )
    args = parser.parse_args()

    _load_env_file()
    deployment = resolve_deployment_env(os.environ)
    contract_config = load_contract_config(CONFIG_DIR / "contract.yaml")

    print(f"PostgreSQL: {deployment.pg_dsn.split('@')[-1]}")  # never print the DSN's auth part
    pg_connection = connect_postgres(deployment)
    created_tables = create_tables(pg_connection)
    print(f"  {len(created_tables)} DDL statement(s) applied (idempotent).")

    print(f"Qdrant: {deployment.qdrant_host}:{deployment.qdrant_http_port}")
    qdrant_client = connect_qdrant(deployment)
    created_collection = ensure_collection(
        qdrant_client=qdrant_client,
        deployment=deployment,
        embedding_dim=contract_config.embedding_dim,
        recreate=args.recreate_collection,
    )
    print(
        f"  collection {deployment.qdrant_collection!r}: "
        + ("created" if created_collection else "already existed, left as is")
    )

    register_embedding_model(
        pg_connection=pg_connection,
        model_name=contract_config.embedding_model,
        model_version=args.model_version,
        embedding_dim=contract_config.embedding_dim,
    )
    set_active_embedding_model_for_collection(
        pg_connection=pg_connection,
        collection_name=deployment.qdrant_collection,
        model_name=contract_config.embedding_model,
        model_version=args.model_version,
    )
    print(
        f"  stamped active: {contract_config.embedding_model!r} "
        f"(version {args.model_version!r}, dim {contract_config.embedding_dim}) "
        f"for collection {deployment.qdrant_collection!r}"
    )

    print("Provisioning complete. AI Services may now be started.")


if __name__ == "__main__":
    main()
