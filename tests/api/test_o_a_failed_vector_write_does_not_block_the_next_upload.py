"""VEC-1, end to end: the failure of 25/9/2026 and the thing that made it
permanent.

Two of thirty-six documents ended `failed`/`INTERNAL_ERROR` because one
`upsert` carried the whole document and Qdrant refused the body. That part was
loud. What was silent is what came next: the PostgreSQL profile had already
been committed, the fingerprint index reads that table directly, and so
**re-uploading the same file came back `duplicate`** — pointing at a document
no question could ever reach. The file could not be got into the system again
by any route Backend has.

This case drives the whole HTTP path twice: once with the vector store
refusing, once with it healthy, on the SAME bytes. The second submission has
to end `active`. That is the acceptance criterion; everything else here is
about making sure the first submission really failed where it was supposed to.

The other half of the rule — no `deletion_log` line for a cleanup nobody
ordered — is asserted here too, because this is the only place in the suite
where a real log object is wired to the same world as a real promote.
"""

from __future__ import annotations

import pytest

from conftest import KEEPER_SPACE, SAMPLE_DOCUMENT


class QdrantRefusedTheBody(Exception):
    """What a 32 MB REST limit looks like from inside the client."""


def _submit_same_file(backend, world) -> str:
    """Publish and submit the identical bytes — same `content_fingerprint`
    every time, which is the whole point of the case."""
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


@pytest.fixture
def vector_store_refuses(world, monkeypatch):
    """Qdrant refuses every write, exactly at the gate."""

    def refuse(chunks):
        raise QdrantRefusedTheBody("request body too large")

    monkeypatch.setattr(world.vector_writer, "write", refuse)


def test_a_failed_vector_write_leaves_no_trace_in_either_store(
    backend, world, vector_store_refuses
) -> None:
    backend.register_space(KEEPER_SPACE)

    ingestion_id = _submit_same_file(backend, world)
    world.run_background()

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()
    assert body["status"] == "failed"
    assert body["code"] == "INTERNAL_ERROR"

    # ⭐ The point of the whole task: the half-written document is gone from
    # BOTH stores, not parked in PostgreSQL where the next upload will trip
    # over it.
    assert world.inner_store.documents() == []
    assert world.inner_store.relations() == []
    assert world.vector_writer.count() == 0

    # And the cleanup did not pretend to be a permanent deletion (06 Mục 5.6).
    assert world.log.entries() == []


def test_the_same_file_can_be_submitted_again_after_a_failed_vector_write(
    backend, world, monkeypatch
) -> None:
    """The regression itself. Before VEC-1 this second submission came back
    `duplicate`, naming a document that was in no vector store — and there was
    no way left to ingest that file at all."""
    backend.register_space(KEEPER_SPACE)

    def refuse(chunks):
        raise QdrantRefusedTheBody("request body too large")

    original_write = world.vector_writer.write
    monkeypatch.setattr(world.vector_writer, "write", refuse)

    first_id = _submit_same_file(backend, world)
    world.run_background()
    assert backend.read_ingestion(first_id, space_id=KEEPER_SPACE).json()["status"] == "failed"

    # Qdrant is back.
    monkeypatch.setattr(world.vector_writer, "write", original_write)

    second_id = _submit_same_file(backend, world)
    world.run_background()

    second = backend.read_ingestion(second_id, space_id=KEEPER_SPACE).json()
    assert second["status"] == "active", (
        f"re-uploading the same file after a failed vector write was refused "
        f"as {second['status']!r} — the orphan profile is still blocking it"
    )
    assert second["document_id"] == second_id
    assert len(world.inner_store.documents()) == 1
    assert world.vector_writer.count() > 0
