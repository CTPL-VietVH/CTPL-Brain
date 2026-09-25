"""The two properties of this slice that no comment can keep true.

**Rủi ro 1 — ONE write path.** docs/10 §4.1 gives one submission endpoint and
two destinations. PO chốt 24/9/2026 that the two must not become two
pipelines: the ordinary Space and the approved pre-approval entry have to
reach the shared stores through the SAME function, in the same order (07 Mục
6 S6 backwards — profile + relations in one transaction, THEN the vector
gate). The first half of this file watches the call, because a second write
path is the kind of thing that is introduced by someone being helpful and is
noticed by nobody.

**One worker, and the orphan rule that rests on it.** PO chốt 24/9/2026: at
startup every `RUNNING` row is orphaned by definition — with one worker,
"the row says RUNNING" and "the process that claimed it died" are the same
sentence — so it goes straight back to `QUEUED`, with no timeout and no
heartbeat. The second half of this file kills a process in the middle and
checks the three things that follow: the job is revived, a job whose file
was already consumed FAILS OUT LOUD rather than ingesting nothing, and
leaked staged files are swept.
"""

from __future__ import annotations

import dataclasses
import os
import pathlib
from datetime import datetime

import pytest

from conftest import KEEPER_SPACE, SAMPLE_DOCUMENT, TEST_TENANT_ID
from ingestion import ingestion_pipeline
from ingestion.ingestion_record_store import InMemoryIngestionRecordStore
from ingestion.pg_queue_stores import PgIngestionRecordStore
from schema.ingestion_record import IngestionRecord, IngestionStatus
from schema.store_schema import INGESTION_RECORD_TABLE, INGESTION_RECORD_TABLE_DDL

# --------------------------------------------------------------------------- #
# KHO-PG-B — the queue portion of this file, parametrized over InMemory and
# the real `ingestion_record` table (task KHO-PG-B-hang-doi-dang-ky-vung-dem).
# Same shape as `tests/t2_11_space_registry/conftest.py` and
# `tests/t2_7_pre_approval/conftest.py`'s factory fixtures — kept local to
# THIS file rather than in `tests/api/conftest.py`, because that conftest is
# shared by every other case in this folder (test_a..test_n) and none of them
# is this task's to touch.
# --------------------------------------------------------------------------- #

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _require_pg_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        pytest.fail(
            f"Missing config key '{name}'. No default in code — copy .env.example "
            f"to .env and fill it in before running the postgresql-parametrized case."
        )
    return value


def _pg_dsn() -> str:
    host = _require_pg_env("CBRAIN_PG_HOST")
    port = _require_pg_env("CBRAIN_PG_PORT")
    database = _require_pg_env("CBRAIN_PG_DATABASE")
    user = _require_pg_env("CBRAIN_PG_USER")
    password = os.environ.get("CBRAIN_PG_PASSWORD") or ""
    auth = f"{user}:{password}" if password else user
    return f"postgresql://{auth}@{host}:{port}/{database}"


def _connect_pg():
    import psycopg
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
    connection = psycopg.connect(_pg_dsn(), autocommit=True)
    connection.execute(INGESTION_RECORD_TABLE_DDL)
    return connection


@pytest.fixture(params=["in_memory", "postgresql"])
def record_store_factory(request):
    """A zero-argument callable that returns a FRESH `IngestionRecordStore`.

    `in_memory` never touches the network or `.env`. `postgresql` connects to
    the real `ingestion_record` table, deletes whatever a previous run of
    THIS fixture left behind, and cleans up again afterwards — the same
    shape as the `space_registry_factory` / `buffer_factory` fixtures in
    `tests/t2_11_space_registry/` and `tests/t2_7_pre_approval/`.
    """
    if request.param == "in_memory":
        yield InMemoryIngestionRecordStore
        return

    connection = _connect_pg()
    connection.execute(f"DELETE FROM {INGESTION_RECORD_TABLE}")
    yield lambda: PgIngestionRecordStore(connection)
    connection.execute(f"DELETE FROM {INGESTION_RECORD_TABLE}")
    connection.close()


def _publish(world, *, filename: str = "quyet-dinh.txt"):
    return world.object_store.publish(
        content=SAMPLE_DOCUMENT.encode("utf-8"),
        filename=filename,
        content_type="text/plain",
    )


def _submit(backend, world, *, private: bool, filename: str = "quyet-dinh.txt") -> str:
    stored = _publish(world, filename=filename)
    return backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE, space_is_private=private
    ).json()["ingestion_id"]


# --------------------------------------------------------------------------- #
# Rủi ro 1 — one write path
# --------------------------------------------------------------------------- #


@pytest.fixture
def promote_spy(monkeypatch):
    """Watch `promote_approved_ingestion` without replacing it.

    The real function still runs — the stores must really be written, or the
    case would prove only that a name was mentioned. What is recorded is
    that the call happened and which entry it carried.
    """
    calls: list[str] = []
    real = ingestion_pipeline.promote_approved_ingestion

    def spy(entry, **kwargs):
        calls.append(entry.document.document_id)
        return real(entry, **kwargs)

    monkeypatch.setattr(ingestion_pipeline, "promote_approved_ingestion", spy)
    return calls


def test_m_the_ordinary_space_path_writes_through_promote(backend, world, promote_spy):
    """⭐ The ordinary path does NOT have a write of its own.

    If it did, this document would be in both stores and `promote_spy` would
    be empty — which is exactly the state a second, parallel implementation
    would produce, and exactly the state nothing else in the suite would
    notice.
    """
    backend.register_space(KEEPER_SPACE)

    ingestion_id = _submit(backend, world, private=False)
    world.run_background()

    assert promote_spy == [ingestion_id], (
        "the ordinary Space path reached the shared stores without going "
        "through promote_approved_ingestion — that is a second write path"
    )
    assert len(world.inner_store.documents()) == 1
    assert world.vector_writer.count() > 0


def test_m_the_pre_approval_path_uses_the_same_function_on_approval(
    backend, world, promote_spy
):
    """The other end of the same claim: the entry that waited in the buffer
    is promoted by the SAME function the ordinary path just used.

    There is no approve endpoint yet (docs/10 §4.4 is not built in this
    slice), so the Manager's action is performed directly against the
    business function — which is the point: the function is the meeting
    place, not the route.
    """
    backend.register_space(KEEPER_SPACE)

    ingestion_id = _submit(backend, world, private=True)
    world.run_background()
    assert promote_spy == [], "the private path wrote to the shared stores early"

    entry = world.buffer.get(ingestion_id)
    ingestion_pipeline.promote_approved_ingestion(
        entry,
        profile_store=world.inner_store,
        profile_deleter=world.profile_store,
        buffer=world.buffer,
        vector_writer=world.vector_writer,
        vector_deleter=world.vector_store,
        embedding_model=world.model,
        relation_scope=world.pipeline.relation_scope,
        relation_document_source=world.inner_store,
        saturation_epsilon=world.ingestion_config.saturation_epsilon,
        saturation_rounds=world.ingestion_config.saturation_rounds,
        scan_pair_budget=world.ingestion_config.scan_pair_budget,
        scan_time_budget=world.ingestion_config.scan_time_budget,
    )

    assert len(world.inner_store.documents()) == 1
    assert world.vector_writer.count() > 0
    assert world.buffered_ids() == set(), "promote did not release the buffer entry"


def test_m_both_paths_write_in_the_same_order(backend, world, monkeypatch):
    """07 Mục 6 S6, backwards: PostgreSQL first, Qdrant LAST.

    The vector store is the gate — *"Cổng chặn nằm ở KHO VECTOR"* — so a
    crash between the two must leave a profile nobody can find, never a
    findable chunk whose profile is missing. One shared write path is what
    makes one assertion here cover both destinations.
    """
    backend.register_space(KEEPER_SPACE)
    order: list[str] = []

    real_write = world.inner_store.write_document_and_relations

    def record_profile(**kwargs):
        order.append("postgresql")
        return real_write(**kwargs)

    real_vector = world.vector_writer.write

    def record_vector(chunks):
        order.append("qdrant")
        return real_vector(chunks)

    monkeypatch.setattr(world.inner_store, "write_document_and_relations", record_profile)
    monkeypatch.setattr(world.vector_writer, "write", record_vector)

    _submit(backend, world, private=False)
    world.run_background()

    assert order == ["postgresql", "qdrant"], (
        "the vector gate opened before the profile existed (07 Mục 6 S6)"
    )


# --------------------------------------------------------------------------- #
# One worker, and what a restart may conclude from that
# --------------------------------------------------------------------------- #


def test_m_a_running_row_is_requeued_at_startup_with_no_timeout(backend, world):
    """⭐ PO chốt 24/9/2026 — the orphan rule.

    The row below is left `RUNNING` with a timestamp that is NOT old: no
    threshold was crossed, and none is consulted. What makes the conclusion
    sound is that there is exactly one worker, so nobody can be running it.
    """
    backend.register_space(KEEPER_SPACE)
    _submit(backend, world, private=False)
    claimed = world.records.claim_next(now=world.clock())
    assert claimed.status is IngestionStatus.RUNNING

    # …and here the process dies. A new one starts:
    recovered = world.pipeline.recover()

    assert [record.ingestion_id for record in recovered] == [claimed.ingestion_id]
    assert world.records.get(claimed.ingestion_id).status is IngestionStatus.QUEUED


def test_m_a_job_cut_before_it_read_the_file_finishes_on_the_next_run(backend, world):
    """The requeued job still has its staged file, so it simply runs.

    This is the common cut: the process died between `claim_next` and GĐ2,
    which is where the queue spends most of its life.
    """
    backend.register_space(KEEPER_SPACE)
    ingestion_id = _submit(backend, world, private=False)
    world.records.claim_next(now=world.clock())  # claimed, then the process dies

    world.pipeline.recover()
    world.pipeline.drain()

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()
    assert body["status"] == "active"
    assert len(world.inner_store.documents()) == 1


def test_m_a_job_whose_file_is_already_gone_fails_out_loud(backend, world, caplog):
    """⛔ The one case that CANNOT be resumed, and must not be silent.

    docs/10 §4.1 deletes the staged file the moment GĐ2 finishes, and AI
    never stores the presigned URL (it is a temporary permission). A process
    cut between those two points leaves a job with nothing to read. The
    honest end is `failed` — Backend can submit again — and the forbidden
    end is an `active` document with no text in it.
    """
    backend.register_space(KEEPER_SPACE)
    ingestion_id = _submit(backend, world, private=False)
    record = world.records.get(ingestion_id)
    # Exactly the state `_read_out`'s `finally` leaves behind when the process
    # is killed immediately after it: file gone, row still unfinished.
    world.staging.discard(record.staged_filename)
    world.records.update(dataclasses.replace(record, staged_filename=None))

    world.pipeline.recover()
    world.pipeline.drain()

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()
    assert body["status"] == "failed"
    assert body["code"] == "INTERNAL_ERROR"
    assert world.inner_store.documents() == [], (
        "a job with no file to read produced a document anyway"
    )
    assert world.vector_writer.count() == 0


def test_m_startup_sweeps_staged_files_no_row_still_wants(backend, world):
    """The staging area is not a file store, so leftovers are deleted.

    A file whose row is terminal is residue of a process that died between
    writing bytes and finishing — it holds customer document content on disk
    and nothing will ever read it again (docs/10 §2: *"Không lưu file gốc"*).

    ⚠️ The file that a LIVE row still names must survive the same sweep, or
    the recovery in the case above would delete its own input.
    """
    backend.register_space(KEEPER_SPACE)
    live = _submit(backend, world, private=False)
    leaked = world.staging.directory / "ing-leaked-from-a-dead-process.txt"
    leaked.write_text("nội dung còn sót lại", encoding="utf-8")

    world.pipeline.recover()

    assert not leaked.exists(), "a staged file no row wants is still on disk"
    assert world.staging.path_for(world.records.get(live).staged_filename).is_file(), (
        "the sweep deleted the input of a job that is still queued"
    )


def test_m_the_queue_is_drained_oldest_first(record_store_factory):
    """`submitted_at` orders the queue. Not decoration: with one worker the
    order is the only fairness there is, and a Space deletion waiting behind
    a hundred uploads is a different (visible) problem than uploads served
    at random.

    Parametrized over `InMemoryIngestionRecordStore` and the real
    `ingestion_record` table: `claim_next`'s ordering is a property of the
    STORE, not of anything the HTTP layer adds on top, so this drives the
    store directly rather than through `backend`/`world`.
    """
    store = record_store_factory()
    now = datetime(2026, 9, 24, 9, 0)
    for index, offset in enumerate([2, 0, 1]):
        store.put(
            IngestionRecord(
                ingestion_id=f"ing-order-{index}",
                space_id=KEEPER_SPACE,
                tenant_id=TEST_TENANT_ID,
                status=IngestionStatus.QUEUED,
                submitted_by="u1",
                submitted_at=now.replace(microsecond=offset),
                updated_at=now,
                requires_pre_approval=False,
            )
        )

    claimed = [
        store.claim_next(now=now).ingestion_id,
        store.claim_next(now=now).ingestion_id,
        store.claim_next(now=now).ingestion_id,
    ]

    assert claimed == ["ing-order-1", "ing-order-2", "ing-order-0"]
    assert store.claim_next(now=now) is None, "an empty queue must answer None"


def test_m_the_queue_survives_closing_and_reopening_the_connection():
    """⭐ PG-only — Phương án A's whole point (module docstring of
    `ingestion_record_store.py`): the pending work is rows in PostgreSQL, so
    a submission answered `202` must still be there after the process that
    accepted it is gone. This is the one case `InMemoryIngestionRecordStore`
    cannot even express — it loses everything on the SAME process, let alone
    a restart — so unlike every other case in this file it does not take
    `record_store_factory`: it always needs the real store, and FAILS LOUDLY
    (not skips) when PostgreSQL is not reachable, matching every other
    PG-parametrized case in this task.
    """
    connection_one = _connect_pg()
    connection_one.execute(f"DELETE FROM {INGESTION_RECORD_TABLE}")
    now = datetime(2026, 9, 24, 9, 0)
    try:
        store_one = PgIngestionRecordStore(connection_one)
        store_one.put(
            IngestionRecord(
                ingestion_id="ing-reconnect",
                space_id=KEEPER_SPACE,
                tenant_id=TEST_TENANT_ID,
                status=IngestionStatus.QUEUED,
                submitted_by="u1",
                submitted_at=now,
                updated_at=now,
                requires_pre_approval=False,
            )
        )
        claimed = store_one.claim_next(now=now)
        assert claimed is not None
        assert claimed.status is IngestionStatus.RUNNING
    finally:
        connection_one.close()  # the connection dies here — a real restart

    connection_two = _connect_pg()
    try:
        store_two = PgIngestionRecordStore(connection_two)
        reread = store_two.get("ing-reconnect")

        assert reread is not None, "the row did not survive closing the connection"
        assert reread.status is IngestionStatus.RUNNING, (
            "the row survived, but not the state claim_next left it in"
        )

        # And the orphan sweep a fresh process runs at startup still finds it,
        # exactly as `recover_orphans`' docstring promises for a single worker.
        recovered = store_two.recover_orphans(now=now)
        assert [record.ingestion_id for record in recovered] == ["ing-reconnect"]
        assert store_two.get("ing-reconnect").status is IngestionStatus.QUEUED
    finally:
        connection_two.execute(f"DELETE FROM {INGESTION_RECORD_TABLE}")
        connection_two.close()


def test_m_the_worker_thread_really_runs_the_queue(backend, world):
    """Every other case drives the worker synchronously, which is what makes
    them deterministic. This one starts the actual thread once, so the
    wiring that a deployment depends on — submit, wake, drain, stop — is not
    the only part of the design nothing exercises.
    """
    backend.register_space(KEEPER_SPACE)
    ingestion_id = _submit(backend, world, private=False)

    world.worker.start()
    try:
        with pytest.raises(RuntimeError, match="EXACTLY ONE"):
            # ⛔ A second worker breaks the orphan rule silently. Refused, not
            # ignored: somebody doing this believes they are adding capacity.
            world.worker.start()
    finally:
        world.worker.stop(timeout=5)

    assert world.records.get(ingestion_id).status is IngestionStatus.ACTIVE
    assert len(world.inner_store.documents()) == 1
