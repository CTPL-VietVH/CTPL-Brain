"""End-to-end proof that AI Services runs for real: a live PostgreSQL, a live
Qdrant, the real BGE-M3 model, the real background worker — no fakes, no
in-memory stand-ins.

One command:

    .venv/bin/python tools/e2e/run_e2e.py

What it does, in order (each step timed and printed):

    1. Start a throwaway local HTTP server serving one real document from
       `data/test-corpus-vn-admin/` — standing in for the presigned MinIO URL
       docs/10 §4.1 describes (`source.url`). `sha256`/`size_bytes` are
       computed from the real bytes, exactly as Backend would.
    2. Provision an EPHEMERAL Qdrant collection + PostgreSQL stamp (reusing
       `tools/provision/provision_stores.py`'s functions) so this run never
       touches whatever collection a developer is using for manual testing,
       and can be re-run without cleanup.
    3. Start `packages/api/main.py`'s real `app_factory()` under `uvicorn`,
       ONE worker process, and wait for `GET /v1/meta` to report `ready`.
    4. `POST /v1/spaces` → `POST /v1/ingestions` → poll `GET
       /v1/ingestions/{id}` until `active` → verify the profile is really in
       PostgreSQL and the vectors are really in Qdrant, by querying both
       stores directly (not by trusting the HTTP answer alone).
    5. `DELETE /v1/spaces/{id}` → poll `GET /v1/spaces/{id}` until `deleted`
       → verify both stores are empty again, the same way.
    6. Tear down: stop `uvicorn`, drop the ephemeral collection, remove the
       ephemeral staging directory, stop the local file server.

Prerequisites this script does NOT start (see tools/infra/README.md):
PostgreSQL and Qdrant must already be running, and BGE-M3 must already be
downloaded to `CBRAIN_MODEL_HOME` (see tests/t0_2_embedding/README.md — this
is the REAL model, ~2.5GB, no fake here).

──────────────────────────────────────────────────────────────────────────
Why the sample document is a .docx, not a PDF — reported to PO 24/9/2026
──────────────────────────────────────────────────────────────────────────

The work order asked for a PDF. All 4 reasonably-sized PDFs in
`data/test-corpus-vn-admin/` were tried first and every one of them ends the
real pipeline in `rejected` / `DOCUMENT_NOT_STRUCTURABLE`, including PDFs
that are plain legal prose with no tables or scanned images — PO's
"chỉ đọc PDF trích được chữ, không đụng bảng/hình" guidance does not resolve
it. Root cause, confirmed by direct measurement (not guessed): in
`chunking._duyet`, an internal (non-leaf) structure node's OWN `Chunk` is
given its span verbatim (`con.char_start, con.char_end` — the "containment
invariant", covering that node's ENTIRE subtree), bypassing
`tran_do_dai_mau` entirely, and `promotion.py` sends that Chunk to
`vectorization.sinh_vector` exactly like every leaf Chunk. A `Chương` (or a
multi-Khoản `Điều`) big enough to span several pages therefore produces one
embeddable Chunk of 8,759–13,105 BGE-M3 tokens — over the 8192 ceiling —
regardless of `chunk_length_cap`, in PDF AND in the larger `.docx` files
alike (`Luật-54-2019-QH14.docx`, `Bộ-luật-45-2019-QH14.docx`, … all show the
same failure). This is a gap in the already-closed T2.3/T2.5 modules, not
something this composition-root task may fix (CLAUDE.md Mục 8: read the
reason before changing a decision, report rather than silently work around
it).

⭐ **CẬP NHẬT 25/9/2026 — nguyên nhân trên ĐÃ ĐƯỢC SỬA** (work-order
CHUNK-mau-noi-bo, 07 Mục 2.2 v1.11): mẩu của một khối có con nay chỉ mang
phần chữ RIÊNG của nó và đi qua đúng `tran_do_dai_mau`, còn trọn khối chuyển
sang `structure_block_start`/`structure_block_end`. Đo lại trên cùng 36 tài
liệu: **34/36 nạp được** (trước: 18/36), **0 mẩu vượt trần ngữ cảnh**
(trước: 48), mẩu nặng nhất **2.036 token** (trước: 233.712). Hai tài liệu
còn lại hỏng vì một lý do KHÁC hẳn — một bảng phụ lục không có ranh giới
đoạn/câu nào để chia (`KhoiVuotTranKhongTheChia`), để lại cho work-order
CHUNK-bang-bieu. Đoạn mô tả bên trên được giữ nguyên làm bản ghi lịch sử của
lần chẩn đoán, không phải mô tả hành vi hiện tại.

`30_2020_ND_CP.docx` is small enough that no internal node's full span
crosses the ceiling — verified directly against the real BGE-M3 tokenizer,
every one of its 260 chunks ≤ 3,099 tokens — so it is the sample document
here, with the REAL, unmodified `config/ingestion.yaml` (`chunk_length_cap`
is not widened for this run).
"""

from __future__ import annotations

import hashlib
import http.server
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

import httpx  # noqa: E402
import psycopg  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402

from api.main import (  # noqa: E402
    CONFIG_DIR,
    connect_postgres,
    connect_qdrant,
    resolve_deployment_env,
)
from schema.store_schema import CHUNK_DOCUMENT_ID_FIELD, DOCUMENT_TABLE  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "tools" / "provision"))
from provision_stores import create_tables, ensure_collection  # noqa: E402

#: See the module docstring's "Why the sample document is a .docx, not a
#: PDF" section for why this is not one of the corpus's 4 PDFs.
SAMPLE_DOCUMENT = (
    REPO_ROOT / "data" / "test-corpus-vn-admin" / "phap-che-tuan-thu" / "30_2020_ND_CP.docx"
)

_START = time.monotonic()


def _step(label: str) -> None:
    print(f"[{time.monotonic() - _START:7.2f}s] {label}")


class _Failure(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# 1. A throwaway HTTP server standing in for the presigned MinIO URL
# --------------------------------------------------------------------------- #


class _FileServer:
    """Serves exactly one file, on localhost, on an OS-chosen free port."""

    def __init__(self, path: Path) -> None:
        self._path = path
        directory = str(path.parent)

        class _Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)

            def log_message(self, *args):  # noqa: A003 - silence per-request logging
                pass

        self._httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self) -> str:
        self._thread.start()
        host, port = self._httpd.server_address
        return f"http://{host}:{port}/{self._path.name}"

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def _sha256_and_size(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            hasher.update(block)
            size += len(block)
    return hasher.hexdigest(), size


# --------------------------------------------------------------------------- #
# The run
# --------------------------------------------------------------------------- #


def main() -> int:
    if not SAMPLE_DOCUMENT.is_file():
        raise _Failure(f"Sample document not found: {SAMPLE_DOCUMENT}")

    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        raise _Failure(f"Missing {env_file}. Run: cp .env.example .env")
    from dotenv import load_dotenv

    load_dotenv(env_file)

    run_id = uuid.uuid4().hex[:8]
    service_key = os.environ.get("CBRAIN_API_SERVICE_KEY") or f"e2e-{run_id}"
    tenant_id = os.environ.get("CBRAIN_TENANT_ID") or f"tenant-e2e-{run_id}"
    staging_dir = Path(tempfile.mkdtemp(prefix="cbrain-e2e-staging-"))
    collection_name = f"cbrain_e2e_{run_id}"

    run_environ = dict(os.environ)
    run_environ["CBRAIN_API_SERVICE_KEY"] = service_key
    run_environ["CBRAIN_TENANT_ID"] = tenant_id
    run_environ["CBRAIN_STAGING_DIR"] = str(staging_dir)
    run_environ["CBRAIN_QDRANT_COLLECTION"] = collection_name

    _step(f"run_id={run_id} collection={collection_name} staging_dir={staging_dir}")

    deployment = resolve_deployment_env(run_environ)
    pg_connection = connect_postgres(deployment)
    qdrant_client = connect_qdrant(deployment)

    _step("Provisioning ephemeral collection + PostgreSQL tables (idempotent DDL)")
    create_tables(pg_connection)
    from schema.config import load_contract_config

    contract_config = load_contract_config(CONFIG_DIR / "contract.yaml")
    ensure_collection(
        qdrant_client=qdrant_client,
        deployment=deployment,
        embedding_dim=contract_config.embedding_dim,
        recreate=False,
    )
    from schema.embedding_registry import (
        register_embedding_model,
        set_active_embedding_model_for_collection,
        stamp_schema_version_for_collection,
    )
    from schema.version import LOCAL_SCHEMA_VERSION

    register_embedding_model(
        pg_connection=pg_connection,
        model_name=contract_config.embedding_model,
        model_version="e2e",
        embedding_dim=contract_config.embedding_dim,
    )
    set_active_embedding_model_for_collection(
        pg_connection=pg_connection,
        collection_name=collection_name,
        model_name=contract_config.embedding_model,
        model_version="e2e",
    )
    stamp_schema_version_for_collection(
        pg_connection=pg_connection,
        collection_name=collection_name,
        schema_version=LOCAL_SCHEMA_VERSION,
    )

    file_server = _FileServer(SAMPLE_DOCUMENT)
    uvicorn_process: subprocess.Popen | None = None
    exit_code = 1
    try:
        source_url = file_server.start()
        sha256, size_bytes = _sha256_and_size(SAMPLE_DOCUMENT)
        _step(f"Serving {SAMPLE_DOCUMENT.name} at {source_url} (sha256={sha256[:12]}…, {size_bytes} bytes)")

        port = _free_port()
        base_url = f"http://127.0.0.1:{port}"
        log_path = staging_dir / "uvicorn.log"
        _step(f"Starting AI Services (uvicorn, --workers 1) on {base_url}")
        uvicorn_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "api.main:app_factory",
                "--factory",
                "--app-dir",
                str(REPO_ROOT / "packages"),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--workers",
                "1",
            ],
            cwd=str(REPO_ROOT),
            env=run_environ,
            stdout=log_path.open("w"),
            stderr=subprocess.STDOUT,
        )
        _wait_ready(base_url, service_key, timeout=180)
        _step("AI Services reports ready=true")

        headers = {"X-Service-Key": service_key}
        space_id = f"space-e2e-{run_id}"
        actor = {"user_id": "e2e-tester", "acting_as": "manager"}

        _step(f"POST /v1/spaces (space_id={space_id})")
        _post(
            f"{base_url}/v1/spaces",
            headers,
            key="register",
            body={"space_id": space_id, "actor": actor},
        )

        _step("POST /v1/ingestions")
        submission = _post(
            f"{base_url}/v1/ingestions",
            headers,
            key="submit",
            body={
                "source": {
                    "url": source_url,
                    "sha256": sha256,
                    "size_bytes": size_bytes,
                    "filename": SAMPLE_DOCUMENT.name,
                    "content_type": (
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"
                    ),
                },
                "space_id": space_id,
                "space_is_private": False,
                "actor": {"user_id": "e2e-tester", "acting_as": "contributor"},
            },
            expect_status=202,
        )
        ingestion_id = submission["ingestion_id"]
        _step(f"ingestion_id={ingestion_id}, status={submission['status']}")

        document_id = _poll_until_active(base_url, headers, ingestion_id, space_id)
        _step(f"status=active, document_id={document_id}")

        _verify_document_in_postgres(pg_connection, document_id, space_id)
        _step("verified: profile row present in PostgreSQL")

        chunk_count = _count_chunks(qdrant_client, collection_name, document_id)
        if chunk_count == 0:
            raise _Failure("no vectors found in Qdrant for this document")
        _step(f"verified: {chunk_count} vector(s) present in Qdrant")

        _step(f"DELETE /v1/spaces/{space_id}")
        _delete(
            f"{base_url}/v1/spaces/{space_id}",
            headers,
            key="delete",
            body={"reason": "e2e test cleanup", "actor": actor},
            expect_status=202,
        )

        _poll_until_deleted(base_url, headers, space_id)
        _step("state=deleted")

        if _document_exists_in_postgres(pg_connection, document_id):
            raise _Failure("document profile still present in PostgreSQL after Space deletion")
        _step("verified: profile row gone from PostgreSQL")

        remaining = _count_chunks(qdrant_client, collection_name, document_id)
        if remaining != 0:
            raise _Failure(f"{remaining} vector(s) still present in Qdrant after Space deletion")
        _step("verified: vectors gone from Qdrant")

        _step("PASS — end to end, real stores, real model")
        exit_code = 0
    except _Failure as exc:
        _step(f"FAIL — {exc}")
        exit_code = 1
    finally:
        if uvicorn_process is not None:
            uvicorn_process.terminate()
            try:
                uvicorn_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                uvicorn_process.kill()
        file_server.stop()
        try:
            qdrant_client.delete_collection(collection_name=collection_name)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
        pg_connection.execute(
            "DELETE FROM embedding_model_collections WHERE collection_name = %s",
            (collection_name,),
        )
        pg_connection.close()
        shutil.rmtree(staging_dir, ignore_errors=True)

    return exit_code


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_ready(base_url: str, service_key: str, *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: str = ""
    while time.monotonic() < deadline:
        try:
            response = httpx.get(
                f"{base_url}/v1/meta", headers={"X-Service-Key": service_key}, timeout=5
            )
            if response.status_code == 200 and response.json().get("ready") is True:
                return
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(1)
    raise _Failure(f"AI Services did not become ready within {timeout}s. Last: {last_error}")


def _headers_with_idempotency(headers: dict, key: str) -> dict:
    return {**headers, "Idempotency-Key": f"e2e-{key}-{uuid.uuid4().hex}"}


def _post(url: str, headers: dict, *, key: str, body: dict, expect_status: int = 200) -> dict:
    response = httpx.post(
        url, headers=_headers_with_idempotency(headers, key), json=body, timeout=30
    )
    if response.status_code != expect_status:
        raise _Failure(f"POST {url} → {response.status_code}: {response.text}")
    return response.json()


def _delete(url: str, headers: dict, *, key: str, body: dict, expect_status: int = 200) -> dict:
    response = httpx.request(
        "DELETE", url, headers=_headers_with_idempotency(headers, key), json=body, timeout=30
    )
    if response.status_code != expect_status:
        raise _Failure(f"DELETE {url} → {response.status_code}: {response.text}")
    return response.json()


def _poll_until_active(
    base_url: str, headers: dict, ingestion_id: str, space_id: str, *, timeout: float = 300
) -> str:
    deadline = time.monotonic() + timeout
    seen: set[str] = set()
    while time.monotonic() < deadline:
        response = httpx.get(
            f"{base_url}/v1/ingestions/{ingestion_id}",
            params={"space_id": space_id},
            headers=headers,
            timeout=10,
        )
        if response.status_code != 200:
            raise _Failure(f"GET ingestion status → {response.status_code}: {response.text}")
        body = response.json()
        status = body["status"]
        if status not in seen:
            _step(f"  ingestion status → {status}")
            seen.add(status)
        if status == "active":
            return body["document_id"]
        if status in {"rejected", "failed"}:
            raise _Failure(f"ingestion ended {status}: code={body.get('code')}")
        time.sleep(1)
    raise _Failure(f"ingestion did not reach 'active' within {timeout}s")


def _poll_until_deleted(base_url: str, headers: dict, space_id: str, *, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = httpx.get(f"{base_url}/v1/spaces/{space_id}", headers=headers, timeout=10)
        if response.status_code != 200:
            raise _Failure(f"GET space status → {response.status_code}: {response.text}")
        body = response.json()
        if body["state"] == "deleted":
            return
        time.sleep(1)
    raise _Failure(f"Space did not reach 'deleted' within {timeout}s")


def _verify_document_in_postgres(connection: psycopg.Connection, document_id: str, space_id: str) -> None:
    row = connection.execute(
        f"SELECT space_id FROM {DOCUMENT_TABLE} WHERE document_id = %s", (document_id,)
    ).fetchone()
    if row is None:
        raise _Failure(f"document {document_id!r} not found in PostgreSQL")
    if row[0] != space_id:
        raise _Failure(f"document {document_id!r} has space_id={row[0]!r}, expected {space_id!r}")


def _document_exists_in_postgres(connection: psycopg.Connection, document_id: str) -> bool:
    row = connection.execute(
        f"SELECT 1 FROM {DOCUMENT_TABLE} WHERE document_id = %s", (document_id,)
    ).fetchone()
    return row is not None


def _count_chunks(qdrant_client: QdrantClient, collection_name: str, document_id: str) -> int:
    from qdrant_client import models

    return qdrant_client.count(
        collection_name=collection_name,
        count_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key=CHUNK_DOCUMENT_ID_FIELD, match=models.MatchValue(value=document_id)
                )
            ]
        ),
        exact=True,
    ).count


if __name__ == "__main__":
    sys.exit(main())
