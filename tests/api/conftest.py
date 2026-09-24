"""Shared fixtures for the docs/10 §10 contract cases run against a fake
Backend — inserts `packages/` into `sys.path` for `api.*` / `ingestion.*` /
`schema.*`.

Same shape as `tests/t2_11_space_registry/conftest.py`, and for the same
reason: the in-memory stores come from the modules that own them, so one test
acts on ONE world exactly as a deployment does. No live PostgreSQL, no live
Qdrant, no network.

⚠️ Two departures from the other test folders, both forced by the name of the
package under test:

* **this folder has no `__init__.py`**, unlike every other `tests/*` folder.
  With one, `tests/api/` would BE the importable package `api`, and would
  shadow `packages/api/` — the suite would test itself. pytest imports these
  modules by file path instead, which is why their names are unique across
  the whole suite.
* **`tests/` is deliberately NOT added to `sys.path`** (the other folders add
  it for `fault_injection`). On the path it would expose `tests/api/` as a
  namespace package called `api`, re-creating the same shadowing risk by a
  quieter route. Nothing here needs `fault_injection`: cutting a purge in the
  middle is T2.8's and T2.11's case, not the HTTP layer's.

──────────────────────────────────────────────────────────────────────────
Two things these fixtures deliberately do NOT share with the real deployment
──────────────────────────────────────────────────────────────────────────

* The stores are in-memory. What is being tested here is the HTTP layer's
  behaviour — refusals, envelopes, idempotency, and the fact that a call
  reaches the real business function — not the stores themselves, which have
  their own suites (T2.8, T2.11).
* The config files are COPIES of the real ones in `config/`, made per test
  into `tmp_path`. Copies, not literals: a test that typed `accepted_formats`
  in would be a third home for the parameter (07 Mục 3.3 quy tắc 2), and a
  test that read the repo's files directly could not remove a key to prove the
  service refuses to start.
"""

from __future__ import annotations

import pathlib
import shutil
import sys
from datetime import date, datetime, timedelta

import numpy as np
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from api.app import build_app  # noqa: E402
from api.background import BackgroundWorker  # noqa: E402
from api.idempotency import InMemoryIdempotencyStore  # noqa: E402
from api.ingestion_routes import (  # noqa: E402
    INGESTION_EXCEPTION_HANDLERS,
    IngestionServices,
    create_ingestion_router,
)
from api.security import SERVICE_KEY_ENV_VAR  # noqa: E402
from api.settings import ReadinessReport  # noqa: E402
from fake_backend import FakeBackend  # noqa: E402
from fake_object_store import FakeObjectStore  # noqa: E402
from ingestion.deletion import (  # noqa: E402
    InMemoryBackgroundCleanup,
    InMemoryDeletableProfileStore,
    InMemoryDeletionLog,
    InMemoryVectorStoreDeleter,
)
from ingestion.ingestion_pipeline import IngestionPipeline  # noqa: E402
from ingestion.ingestion_record_store import (  # noqa: E402
    InMemoryIngestionRecordStore,
)
from ingestion.pre_approval_buffer import (  # noqa: E402
    BufferedIngestion,
    InMemoryPreApprovalBuffer,
)
from ingestion.promotion import (  # noqa: E402
    InMemorySharedProfileStore,
    InMemoryVectorStoreWriter,
)
from ingestion.relations_scan import UnavailableSpaceScanScope  # noqa: E402
from ingestion.space_registry import InMemorySpaceRegistry  # noqa: E402
from ingestion.staging import StagingArea  # noqa: E402
from schema.chunk import Chunk  # noqa: E402
from schema.config import load_ingestion_config  # noqa: E402
from schema.document import DateSource, Document  # noqa: E402

#: The two Spaces every case uses. One is the subject of the call, the other
#: is the bystander that must come out untouched — docs/10 §10: *"tài liệu
#: Space khác không đổi"*.
DOOMED_SPACE = "space-doomed"
KEEPER_SPACE = "space-keeper"

CONFIG_FILENAMES = ("contract.yaml", "ingestion.yaml", "retrieval.yaml")

INGESTED_AT = datetime(2026, 9, 24, 9, 0)

#: Real Vietnamese text: `span_start`/`span_end` count Unicode characters, and
#: a corpus of plain ASCII would never notice if they stopped.
BODY = "Điều 1. Phạm vi điều chỉnh. Quyết định này quy định về công tác văn thư."

#: The secret the fake Backend presents. A test value, generated nowhere near
#: a real install — and the only place in this repo any service key exists.
TEST_SERVICE_KEY = "test-service-key-3f9c1d"

#: R6 — one install, one customer. In a deployment this comes from
#: `CBRAIN_TENANT_ID` (docs/10 §2); here it is the test install's value.
TEST_TENANT_ID = "tenant-test"

#: A real administrative document, structured the way the VN normaliser
#: expects: numbered Điều, a doc number, a date. Plain `.txt` so no reader
#: dependency (Docling, python-docx) is dragged into an HTTP test.
SAMPLE_DOCUMENT = """BỘ NỘI VỤ
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: 15/2021/QĐ-BNV
Hà Nội, ngày 15 tháng 3 năm 2021

QUYẾT ĐỊNH
Về việc ban hành Quy chế quản lý tài liệu nội bộ

Điều 1. Phạm vi điều chỉnh
1. Quyết định này quy định về công tác quản lý tài liệu nội bộ của cơ quan.
2. Mọi cán bộ, công chức phải chịu trách nhiệm bảo quản tài liệu được giao.

Điều 2. Hiệu lực thi hành
Quyết định này có hiệu lực thi hành kể từ ngày 01 tháng 5 năm 2021.
"""


class FakeBgeM3:
    """Satisfies `vectorization.BgeM3Like` without loading 2.5GB.

    Copied in shape from `tests/t2_7_promote/conftest.py`, and for the same
    reason: GĐ6's real behaviour is T2.5's subject, tested there against the
    real model. What these cases need is that GĐ6 RAN before anything was
    written, and a fake proves that as well as 2.5GB would.
    """

    def __init__(self, *, max_seq_length: int = 8192) -> None:
        self.max_seq_length = max_seq_length
        self.tokenizer = self
        self.encode_calls = 0

    def encode(self, sentences, *, normalize_embeddings=None, batch_size=None):
        if isinstance(sentences, str):  # used as `model.tokenizer.encode(...)`
            return sentences.split()
        self.encode_calls += 1
        return np.array(
            [
                [float(len(text) % 7 + index), 0.5, 0.25, 0.125]
                for index, text in enumerate(sentences)
            ],
            dtype=float,
        )


class SteppingClock:
    """A clock that moves one second per read.

    Not `datetime.now`: the queue is ordered by `submitted_at`, and two
    submissions in the same microsecond would make "oldest first" a coin
    toss — in a test that is a flake, and in a review it is a claim nobody
    can check.
    """

    def __init__(self, start: datetime = INGESTED_AT) -> None:
        self._now = start

    def __call__(self) -> datetime:
        self._now += timedelta(seconds=1)
        return self._now


def make_document(
    *, document_id: str, space_id: str, content_fingerprint: str | None = None
) -> Document:
    return Document(
        document_id=document_id,
        space_id=space_id,
        tenant_id="tenant-1",
        title="Quyết định về công tác văn thư",
        doc_number="15/2021/QĐ-BNV",
        issued_date=date(2021, 3, 1),
        issued_date_source=DateSource.EXTRACTED,
        effective_date=date(2021, 4, 1),
        effective_date_source=DateSource.EXTRACTED,
        ingested_at=INGESTED_AT,
        source_format="docx",
        content_fingerprint=content_fingerprint or f"fingerprint-{document_id}",
        extracted_text=BODY,
        version_chain_id=f"chain-{document_id}",
        version_ordinal=1,
    )


def make_chunk(
    *, chunk_id: str, document: Document, span: tuple[int, int], embedded: bool = True
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=document.document_id,
        space_id=document.space_id,
        tenant_id=document.tenant_id,
        structure_path=["Điều 1"],
        span_start=span[0],
        span_end=span[1],
        embedding=[0.1, 0.2, 0.3, 0.4] if embedded else [],
    )


class World:
    """One deployment's worth of stores, empty until a case seeds it.

    Seeding goes STRAIGHT INTO THE STORES, not through HTTP: there is no
    submission endpoint in this slice (docs/10 §4.1 is not built), and a case
    about deletion must not be blocked on one about ingestion.
    """

    def __init__(self, *, staging_dir: pathlib.Path, config_dir: pathlib.Path) -> None:
        self.inner_store = InMemorySharedProfileStore()
        self.vector_writer = InMemoryVectorStoreWriter()
        self.buffer = InMemoryPreApprovalBuffer()
        self.registry = InMemorySpaceRegistry()
        self.profile_store = InMemoryDeletableProfileStore(self.inner_store)
        self.vector_store = InMemoryVectorStoreDeleter(self.vector_writer)
        self.cleanup = InMemoryBackgroundCleanup()
        self.log = InMemoryDeletionLog()

        # -- the submission half (docs/10 §4.1) -------------------------- #
        self.records = InMemoryIngestionRecordStore()
        self.staging = StagingArea(staging_dir)
        self.worker = BackgroundWorker()
        self.object_store = FakeObjectStore()
        self.model = FakeBgeM3()
        self.clock = SteppingClock()

        # The five numbers come from the config file this app is built from —
        # never typed in here, which would be a third home for them (07 Mục
        # 3.3 quy tắc 2).
        self.ingestion_config = load_ingestion_config(config_dir / "ingestion.yaml")

        self.pipeline = IngestionPipeline(
            records=self.records,
            staging=self.staging,
            space_registry=self.registry,
            profile_store=self.inner_store,
            fingerprint_index=self.inner_store,
            buffer=self.buffer,
            vector_writer=self.vector_writer,
            embedding_model=self.model,
            # ⭐ The scope a real v1 install has: the Backend topology client
            # of docs/10 §7.1 is NOT built, so GĐ7 may not conclude and every
            # freshly ingested document keeps saying *"chưa đối chiếu xong"*
            # (PO chốt 24/9, K5). A scope that returned a fixed point instead
            # would stamp `stopped` on a scan that never widened.
            relation_scope=UnavailableSpaceScanScope(
                reason="the Backend space-topology client (docs/10 §7.1) is not built"
            ),
            relation_document_source=self.inner_store,
            chunk_length_cap=self.ingestion_config.chunk_length_cap,
            saturation_epsilon=self.ingestion_config.saturation_epsilon,
            saturation_rounds=self.ingestion_config.saturation_rounds,
            scan_pair_budget=self.ingestion_config.scan_pair_budget,
            scan_time_budget=self.ingestion_config.scan_time_budget,
            clock=self.clock,
        )

    # -- driving the background ------------------------------------------ #

    def run_background(self) -> int:
        """Let the single worker finish what the last call queued.

        Called EXPLICITLY by every case that needs it, never hidden inside
        `FakeBackend`: docs/10 §4.1 and §4.0 both answer `202`, and a test
        that could not tell the difference between "done" and "queued" would
        not be testing the contract that was written.
        """
        return self.worker.run_pending()

    # -- seeding --------------------------------------------------------- #

    def seed_document(
        self, *, document_id: str, space_id: str, content_fingerprint: str | None = None
    ) -> Document:
        """A document in both physical stores, as a promoted one would be."""
        document = make_document(
            document_id=document_id,
            space_id=space_id,
            content_fingerprint=content_fingerprint,
        )
        self.inner_store.write_document_and_relations(document=document, relations=[])
        self.vector_writer.write(
            [
                make_chunk(chunk_id=f"chunk-{document_id}-1", document=document, span=(0, 28)),
                make_chunk(chunk_id=f"chunk-{document_id}-2", document=document, span=(28, 72)),
            ]
        )
        return document

    def seed_buffered_document(self, *, document_id: str, space_id: str) -> Document:
        """A document still waiting for a Manager (06 Mục 5.6, 08 T2.7)."""
        document = make_document(document_id=document_id, space_id=space_id)
        self.buffer.put(
            BufferedIngestion(
                document=document,
                buffered_at=INGESTED_AT,
                chunks=[
                    make_chunk(
                        chunk_id=f"chunk-{document_id}-1",
                        document=document,
                        span=(0, 28),
                        embedded=False,
                    )
                ],
            )
        )
        return document

    # -- inspection ------------------------------------------------------ #

    def document_ids(self) -> set[str]:
        return {document.document_id for document in self.inner_store.documents()}

    def point_ids(self) -> set[str]:
        return set(self.vector_writer.points)

    def buffered_ids(self) -> set[str]:
        return {
            entry.document.document_id
            for entry in (
                *self.buffer.list_in_space(DOOMED_SPACE),
                *self.buffer.list_in_space(KEEPER_SPACE),
            )
        }

    def deletion_log_document_ids(self) -> set[str]:
        return {entry.document_id for entry in self.log.entries()}

    def snapshot(self) -> tuple[set[str], set[str], set[str], set[str]]:
        """Every store that must be able to come out unchanged, in one value."""
        return (
            self.document_ids(),
            self.point_ids(),
            self.buffered_ids(),
            self.deletion_log_document_ids(),
        )


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    """For the cases that read a source-of-truth document back out of
    `docs/` instead of copying a list into the test."""
    return REPO_ROOT


@pytest.fixture
def config_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """A copy of the repo's real `config/`, writable by the case."""
    destination = tmp_path / "config"
    destination.mkdir()
    for filename in CONFIG_FILENAMES:
        shutil.copyfile(REPO_ROOT / "config" / filename, destination / filename)
    return destination


@pytest.fixture
def staging_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Where downloaded bytes land. Per-test, and INJECTED — there is no
    `tempfile.gettempdir()` anywhere in the ingestion path (see
    `ingestion.staging`)."""
    return tmp_path / "staging"


@pytest.fixture
def world(staging_dir: pathlib.Path, config_dir: pathlib.Path) -> World:
    return World(staging_dir=staging_dir, config_dir=config_dir)


@pytest.fixture
def services(world: World) -> IngestionServices:
    """`document_source` and `profile_store` are the SAME object here, as they
    are in a deployment: both are the `document` table."""
    return IngestionServices(
        space_registry=world.registry,
        document_source=world.profile_store,
        profile_store=world.profile_store,
        vector_store=world.vector_store,
        background_cleanup=world.cleanup,
        deletion_log=world.log,
        pre_approval_buffer=world.buffer,
        pipeline=world.pipeline,
        worker=world.worker,
        tenant_id=TEST_TENANT_ID,
        max_upload_bytes=world.ingestion_config.max_upload_bytes,
        source_download_timeout_seconds=(
            world.ingestion_config.source_download_timeout_seconds
        ),
        http_client_factory=world.object_store.client_factory,
        clock=world.clock,
        new_ingestion_id=_sequential_ingestion_ids(),
    )


def _sequential_ingestion_ids():
    """Predictable `ingestion_id`s, so a case can name the row it submitted.

    A deployment uses `uuid4`; the id's only job is uniqueness, and a test
    that had to parse a uuid out of a response before it could assert on the
    store would be testing its own plumbing.
    """
    counter = iter(range(1, 1_000))
    return lambda: f"ing-{next(counter):03d}"


@pytest.fixture
def environ() -> dict[str, str]:
    """The process environment as the app factory sees it — passed in, never
    read from `os.environ`, so a case can remove the service key without
    touching the machine it runs on."""
    return {SERVICE_KEY_ENV_VAR: TEST_SERVICE_KEY}


@pytest.fixture
def idempotency_store() -> InMemoryIdempotencyStore:
    return InMemoryIdempotencyStore()


@pytest.fixture
def readiness():
    """A probe that reports this deployment serving.

    Honest here and only here: the real probe compares the contract config
    against the store stamp (07 Mục 3.1), and there is no store to ask.
    """

    def probe() -> ReadinessReport:
        return ReadinessReport(ready=True, not_ready_reason=None)

    return probe


@pytest.fixture
def app(config_dir, environ, services, readiness, idempotency_store):
    return build_app(
        config_dir=config_dir,
        environ=environ,
        service_key_env_var=SERVICE_KEY_ENV_VAR,
        routers=[create_ingestion_router(services=services)],
        exception_handlers=INGESTION_EXCEPTION_HANDLERS,
        readiness=readiness,
        idempotency_store=idempotency_store,
    )


@pytest.fixture
def backend(app) -> FakeBackend:
    """Backend C.Brain, faked — docs/10 §10."""
    with FakeBackend(app, service_key=TEST_SERVICE_KEY) as fake:
        yield fake
