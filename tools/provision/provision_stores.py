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

⛔ **Idempotent is not the same as "upgrades in place".** Before touching
anything, this script REFUSES to run when an existing table has drifted from
the columns `packages/schema/` declares, or when the Qdrant collection still
holds points written by an older `Chunk` shape. It never `ALTER TABLE`s and
never back-fills: 07 Mục 3.1 — a breaking schema bump means the DATA is
stale, not merely the column list, so the only honest repair is drop and
recreate, and the operator has to ask for it.

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
import re
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
from schema.store_schema import CHUNK_PAYLOAD_FIELDS, SHARED_STORE_DDL  # noqa: E402
from schema.version import LOCAL_SCHEMA_VERSION  # noqa: E402

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


class StoreOutOfDateError(SystemExit):
    """An existing table or collection does not match the CURRENT schema.

    ⛔ Deliberately NOT repaired here. `CREATE TABLE IF NOT EXISTS` silently
    does nothing when the table already exists with the wrong columns, and an
    `ALTER TABLE` that quietly adds them would be worse than either: 07 Mục
    3.1 says a breaking schema bump means the DATA is stale, not just the
    column list — a back-filled column holds a value nobody computed. The
    only honest answer is to say so and stop.
    """


_CREATE_TABLE = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+)", re.IGNORECASE)
# Same shape the DDL-coverage tests use: a column line is exactly four spaces
# then the name. Constraint lines and `-- comments` cannot match.
_COLUMN = re.compile(r"^\s{4}([a-z_]+)\s", re.MULTILINE)
_NOT_A_COLUMN = {"unique", "primary", "foreign", "references", "constraint", "on"}


def _expected_columns(ddl: str) -> tuple[str, set[str]] | None:
    """`(table_name, columns)` for a CREATE TABLE statement; `None` for an
    index or anything else in the DDL tuple."""
    match = _CREATE_TABLE.search(ddl)
    if match is None:
        return None
    columns = {name for name in _COLUMN.findall(ddl) if name not in _NOT_A_COLUMN}
    return match.group(1), columns


def assert_existing_tables_match(connection) -> None:
    """Refuse to provision on top of a table whose columns have drifted.

    Runs BEFORE any `CREATE TABLE IF NOT EXISTS`, because that statement is a
    no-op on an existing table and would hide exactly this. A table that does
    not exist yet is fine — it is about to be created correctly.
    """
    stale: list[str] = []
    for ddl in _ALL_DDL:
        expected = _expected_columns(ddl)
        if expected is None:
            continue
        table_name, columns = expected
        rows = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            (table_name,),
        ).fetchall()
        if not rows:
            continue  # not created yet — nothing to be out of date
        actual = {row[0] for row in rows}
        missing = sorted(columns - actual)
        extra = sorted(actual - columns)
        if missing or extra:
            stale.append(
                f"  - {table_name}: "
                + (f"thiếu cột {missing}" if missing else "")
                + (" · " if missing and extra else "")
                + (f"thừa cột {extra}" if extra else "")
            )
    if stale:
        raise StoreOutOfDateError(
            "TỪ CHỐI CHẠY — bảng đã có sẵn nhưng lệch cột so với "
            f"packages/schema/ (phiên bản module schema hiện tại: "
            f"{LOCAL_SCHEMA_VERSION}):\n"
            + "\n".join(stale)
            + "\n\nKhông ALTER TABLE ngầm, không bỏ qua rồi chạy tiếp: 07 Mục 3.1 "
            "— tăng số PHÁ VỠ tương thích nghĩa là chính DỮ LIỆU đã cũ, không "
            "chỉ danh sách cột, nên một cột được thêm vào sau sẽ mang giá trị "
            "không ai tính ra.\nCách dựng lại (mất dữ liệu trong các bảng đó, "
            "đúng như ý định):\n"
            "  psql \"$CBRAIN_PG_DSN\" -c 'DROP TABLE IF EXISTS "
            "ingestion_pre_approval_chunk, ingestion_pre_approval_document, "
            "relation, ingestion_record, deletion_log, space_registry, document "
            "CASCADE;'\n"
            "  rồi chạy lại lệnh này kèm --recreate-collection."
        )


def assert_existing_collection_matches(*, qdrant_client, collection_name: str) -> None:
    """Refuse when the collection already holds points written by an older
    `Chunk` shape.

    The Qdrant stamp carries dimension and metric (and `embedding_model` has
    its own home in PostgreSQL — 07 Mục 3.1), but nothing there describes the
    PAYLOAD shape. So this reads one real point and compares its keys with
    `CHUNK_PAYLOAD_FIELDS`. A point missing a key was written before the
    field existed; mixing it with new points makes Retrieval build the
    reading unit from data that is not there — silently.
    """
    existing = {c.name for c in qdrant_client.get_collections().collections}
    if collection_name not in existing:
        return
    points, _ = qdrant_client.scroll(
        collection_name=collection_name, limit=1, with_payload=True, with_vectors=False
    )
    if not points:
        return  # empty collection — nothing stale in it
    payload = points[0].payload or {}
    missing = sorted(set(CHUNK_PAYLOAD_FIELDS) - set(payload))
    if missing:
        raise StoreOutOfDateError(
            f"TỪ CHỐI CHẠY — collection {collection_name!r} đang chứa mẩu được ghi "
            f"bằng hình dạng `Chunk` CŨ: điểm mẫu thiếu khoá payload {missing} "
            f"(phiên bản module schema hiện tại: {LOCAL_SCHEMA_VERSION}).\n"
            "Không back-fill, không bỏ qua: 07 Mục 3.1 — số PHÁ VỠ tương thích "
            "tăng thì phải NẠP LẠI TOÀN KHO, vì ý nghĩa của trường đã đổi chứ "
            "không chỉ thiếu một ô.\n"
            "Cách dựng lại: chạy lại lệnh này kèm --recreate-collection "
            "(xoá sạch vector của collection đó), rồi nạp lại tài liệu."
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
    # BEFORE any CREATE TABLE IF NOT EXISTS — that statement is a no-op on an
    # existing table and would hide a column drift instead of reporting it.
    assert_existing_tables_match(pg_connection)
    created_tables = create_tables(pg_connection)
    print(f"  {len(created_tables)} DDL statement(s) applied (idempotent).")

    print(f"Qdrant: {deployment.qdrant_host}:{deployment.qdrant_http_port}")
    qdrant_client = connect_qdrant(deployment)
    if not args.recreate_collection:
        # Skipped when the operator has already asked for a clean rebuild —
        # the check exists to stop a SILENT mix of old and new points, and
        # `--recreate-collection` is the explicit opposite of silent.
        assert_existing_collection_matches(
            qdrant_client=qdrant_client, collection_name=deployment.qdrant_collection
        )
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
