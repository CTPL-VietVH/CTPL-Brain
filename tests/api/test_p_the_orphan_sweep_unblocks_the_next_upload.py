"""VEC-2 — the startup sweep that finishes what a half-written promote left
behind, and the four things it must refuse to touch.

VEC-1 made a promote undo its own PostgreSQL write when the Qdrant write
fails. Two holes it deliberately left open:

* the undo's FIRST step is the vector delete, and when that is the thing
  failing (Qdrant down), `promotion.py` refuses to delete the profile —
  deleting it while points may survive is the dangling pointer of điều cấm
  #17. The profile stays, on purpose.
* a process that dies between step 4 and step 5 runs no undo at all.

Either way PostgreSQL keeps a profile with no vectors: invisible to every
question, and — because `intake.decide_intake` reads that same table through
the fingerprint index — enough to make the next upload of the same file come
back `duplicate`. The file becomes un-ingestable and nothing says so.

`IngestionPipeline.sweep_promotion_orphans`, run at the end of `recover()`,
is what closes that. This file drives it through the real pipeline on the
real `World`, because the claim is about a deployment's two stores, not about
a function in isolation.

⚠️ The sweep DELETES document profiles. Every case below that says "does not
touch" is worth more than the one that says "cleans": a sweep that is too
eager destroys documents nobody asked it to.
"""

from __future__ import annotations

import dataclasses

import pytest

from conftest import KEEPER_SPACE, SAMPLE_DOCUMENT
from schema.ingestion_record import IngestionStatus


class QdrantIsDown(Exception):
    """Refuses both directions — the write AND the compensating delete."""


def _submit_same_file(backend, world) -> str:
    stored = world.object_store.publish(
        content=SAMPLE_DOCUMENT.encode("utf-8"),
        filename="quyet-dinh.txt",
        content_type="text/plain",
    )
    response = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE, space_is_private=False
    )
    assert response.status_code == 202, response.text
    return response.json()["ingestion_id"]


def _break_qdrant(world, monkeypatch) -> None:
    """Qdrant refuses the write and the delete — the exact shape that makes
    VEC-1's inline undo stop, on purpose, with the profile still there."""

    def refuse_write(chunks):
        raise QdrantIsDown("request body too large")

    def refuse_delete(document_id):
        raise QdrantIsDown("connection refused")

    monkeypatch.setattr(world.vector_writer, "write", refuse_write)
    monkeypatch.setattr(world.vector_store, "delete_document_points", refuse_delete)


def _make_orphan(backend, world, monkeypatch) -> str:
    """Drive a real submission into the orphan state and return its id."""
    backend.register_space(KEEPER_SPACE)
    _break_qdrant(world, monkeypatch)

    ingestion_id = _submit_same_file(backend, world)
    world.run_background()

    record = world.records.get(ingestion_id)
    assert record.status is IngestionStatus.FAILED
    assert record.promoting_document_id is not None, (
        "the job did not record which document it was writing — the sweep has "
        "nothing to work from, and the orphan is permanent"
    )
    assert len(world.inner_store.documents()) == 1, (
        "this case is only meaningful if the orphan really is in PostgreSQL"
    )
    return ingestion_id


# --------------------------------------------------------------------------- #
# The regression: an orphan that VEC-1 could not clean up blocks re-uploading
# --------------------------------------------------------------------------- #


def test_a_restart_sweeps_the_orphan_a_failed_cleanup_left(backend, world, monkeypatch):
    ingestion_id = _make_orphan(backend, world, monkeypatch)
    document_id = world.records.get(ingestion_id).promoting_document_id

    # Qdrant is back, and the process restarts.
    monkeypatch.undo()
    swept = world.pipeline.recover()  # noqa: F841 - the sweep runs inside

    assert world.inner_store.documents() == [], (
        f"document {document_id} survived the sweep; the next upload of that "
        f"file will still be refused as a duplicate"
    )
    assert world.inner_store.relations() == []
    assert world.records.get(ingestion_id).promoting_document_id is None, (
        "the pointer was not cleared, so every later start re-does this work"
    )


def test_the_same_file_can_be_submitted_again_after_the_sweep(backend, world, monkeypatch):
    """The user-visible end of it — and the only claim that matters."""
    _make_orphan(backend, world, monkeypatch)
    monkeypatch.undo()
    world.pipeline.recover()

    second_id = _submit_same_file(backend, world)
    world.run_background()

    second = backend.read_ingestion(second_id, space_id=KEEPER_SPACE).json()
    assert second["status"] == "active", (
        f"re-uploading the same file after the sweep came back {second['status']!r} "
        f"— the orphan profile is still blocking it"
    )
    assert world.vector_writer.count() > 0


def test_the_sweep_writes_no_deletion_log_line(backend, world, monkeypatch):
    """⛔ 06 Mục 5.6's log records a permanent deletion a PERSON ordered. This
    is the system finishing its own interrupted write."""
    _make_orphan(backend, world, monkeypatch)
    monkeypatch.undo()
    world.pipeline.recover()

    assert world.log.entries() == []


def test_running_the_sweep_twice_does_nothing_the_second_time(backend, world, monkeypatch):
    ingestion_id = _make_orphan(backend, world, monkeypatch)
    monkeypatch.undo()

    first = world.pipeline.sweep_promotion_orphans()
    second = world.pipeline.sweep_promotion_orphans()

    assert len(first) == 1
    assert second == [], "the second sweep found work that was already done"
    assert world.records.get(ingestion_id).status is IngestionStatus.FAILED


# --------------------------------------------------------------------------- #
# What the sweep must NOT touch
# --------------------------------------------------------------------------- #


def test_the_sweep_never_touches_a_successful_ingestion(backend, world):
    """An `active` row keeps its `promoting_document_id` — it is a trace, not
    a work item. Reading it as one would delete a live document."""
    backend.register_space(KEEPER_SPACE)
    ingestion_id = _submit_same_file(backend, world)
    world.run_background()

    record = world.records.get(ingestion_id)
    assert record.status is IngestionStatus.ACTIVE
    assert record.promoting_document_id is not None
    points_before = world.vector_writer.count()

    assert world.pipeline.sweep_promotion_orphans() == []
    assert len(world.inner_store.documents()) == 1
    assert world.vector_writer.count() == points_before


def test_the_sweep_never_touches_a_job_that_has_not_finished(backend, world, monkeypatch):
    """A `RUNNING` or `QUEUED` row may be between step 4 and step 5 right now.

    Simulated rather than killed: the row is put back into each unfinished
    state with its profile present, which is exactly what a live job looks
    like from the sweep's side.
    """
    ingestion_id = _make_orphan(backend, world, monkeypatch)
    monkeypatch.undo()
    orphan = world.records.get(ingestion_id)

    for status in (IngestionStatus.RUNNING, IngestionStatus.QUEUED):
        world.records.update(dataclasses.replace(orphan, status=status))

        assert world.pipeline.sweep_promotion_orphans() == [], (
            f"the sweep acted on a {status.value!r} row — that is a promote in "
            f"flight, and deleting its profile destroys a document that is "
            f"about to be finished correctly"
        )
        assert len(world.inner_store.documents()) == 1

    # And `recover()` still treats a RUNNING row the way it always has.
    world.records.update(dataclasses.replace(orphan, status=IngestionStatus.RUNNING))
    world.pipeline.recover()
    assert world.records.get(ingestion_id).status is IngestionStatus.QUEUED


# --------------------------------------------------------------------------- #
# Order, and failure of the sweep itself
# --------------------------------------------------------------------------- #


def test_the_sweep_deletes_vectors_before_the_profile_row(backend, world, monkeypatch):
    """S6 order, the same one VEC-1's inline undo follows: reversing it leaves
    findable chunks whose profile is gone (điều cấm #17)."""
    _make_orphan(backend, world, monkeypatch)
    monkeypatch.undo()

    calls: list[str] = []

    class RecordingVectorDeleter:
        def __init__(self, inner):
            self._inner = inner

        def delete_document_points(self, document_id: str) -> int:
            calls.append("vectors")
            return self._inner.delete_document_points(document_id)

    class RecordingProfileDeleter:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def delete_document_and_relations(self, document_id: str):
            calls.append("profile")
            return self._inner.delete_document_and_relations(document_id)

    pipeline = dataclasses.replace(
        world.pipeline,
        vector_deleter=RecordingVectorDeleter(world.vector_store),
        profile_deleter=RecordingProfileDeleter(world.profile_store),
    )

    assert len(pipeline.sweep_promotion_orphans()) == 1
    assert calls == ["vectors", "profile"]


def test_a_sweep_that_fails_does_not_stop_the_service_starting(backend, world, monkeypatch):
    """Startup continues, the case is logged, and the row keeps its pointer so
    the next start tries again."""
    ingestion_id = _make_orphan(backend, world, monkeypatch)
    # Qdrant is still down when the process comes back up.

    # Not wrapped in `pytest.raises`: the claim is that this call RETURNS.
    # A sweep that let its exception out would fail the case right here, and
    # in a deployment it would take the whole startup with it.
    world.pipeline.recover()

    record = world.records.get(ingestion_id)
    assert record.promoting_document_id is not None, (
        "a failed sweep marked the row as cleaned; the orphan would never be "
        "retried and the file stays un-ingestable"
    )
    assert len(world.inner_store.documents()) == 1

    # Next start, with Qdrant back: it finishes.
    monkeypatch.undo()
    assert len(world.pipeline.sweep_promotion_orphans()) == 1
    assert world.inner_store.documents() == []


def test_a_sweep_failure_on_one_job_does_not_stop_the_next(backend, world, monkeypatch):
    """One bad case must not shadow the others — the sweep reports per row."""
    first = _make_orphan(backend, world, monkeypatch)
    monkeypatch.undo()

    # A second failed row pointing at a document that is NOT there: the
    # profile probe answers None, so it is skipped rather than exploding.
    ghost = dataclasses.replace(
        world.records.get(first),
        ingestion_id="ingestion-ghost",
        promoting_document_id="doc-that-never-existed",
    )
    world.records.put(ghost)

    swept = world.pipeline.sweep_promotion_orphans()

    assert len(swept) == 1, "the real orphan was not cleaned"
    assert world.inner_store.documents() == []


# --------------------------------------------------------------------------- #
# The column is INTERNAL
# --------------------------------------------------------------------------- #


def test_promoting_document_id_never_reaches_backend(backend, world, monkeypatch):
    """docs/10 §4.2 owns `document_id`; this column is AI's own bookkeeping.

    Checked on a `failed` submission on purpose: that is the state where the
    two would differ, and where leaking the internal one would tell Backend
    about a document that does not exist.
    """
    ingestion_id = _make_orphan(backend, world, monkeypatch)

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()

    assert "promoting_document_id" not in body
    assert body["document_id"] is None, (
        "a failed submission named a document to Backend — docs/10 §4.2 says "
        "`document_id` is set exactly when the job ended `active`"
    )
    assert world.records.get(ingestion_id).promoting_document_id is not None, (
        "…while AI's own row must still know it, or the sweep has nothing to do"
    )


@pytest.mark.parametrize("field", ["promoting_document_id"])
def test_no_response_model_in_this_service_declares_the_internal_column(field):
    """The wider guard: it is not in any response model at all, so no future
    endpoint can start returning it by accident."""
    from api import models

    for name in dir(models):
        model = getattr(models, name)
        fields = getattr(model, "model_fields", None)
        if fields is None:
            continue
        assert field not in fields, f"{name} would publish {field} to Backend"
