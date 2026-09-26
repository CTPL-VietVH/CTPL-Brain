"""VEC-3 — an out-of-memory failure during GĐ6 ends its own way: `failed` +
`EMBEDDING_OUT_OF_MEMORY`, not `INTERNAL_ERROR` and not
`DOCUMENT_NOT_STRUCTURABLE`, and neither store was ever written to.

VEC-3b threaded `embedding_batch_size` through `promote_approved_ingestion()`
into `sinh_vector()` (the same way `qdrant_upsert_batch_points` already
reaches `write_to_qdrant`), so
`test_n_a_real_oom_drives_the_full_pipeline_to_the_same_code` below drives
the REAL recursive-halving path end to end — no monkeypatched
`promote_approved_ingestion`, a fake model that runs out of memory at every
batch size down to one.

The two mapping-only cases that follow it are kept: they pin the
`ingestion_pipeline.py` mapping in isolation, cheaply, independent of
`sinh_vector`'s own halving arithmetic (already covered directly by
`tests/t2_5_vectorization/test_g_*`) — the same reason `test_m` proves the
one-write-path property without needing a real crash.
"""

from __future__ import annotations

from conftest import KEEPER_SPACE, SAMPLE_DOCUMENT
from ingestion import ingestion_pipeline
from ingestion.vectorization import EmbeddingOutOfMemory
from schema.ingestion_record import IngestionFailureCode


def _publish(world, *, filename: str = "quyet-dinh.txt"):
    return world.object_store.publish(
        content=SAMPLE_DOCUMENT.encode("utf-8"),
        filename=filename,
        content_type="text/plain",
    )


def _always_out_of_memory_on_a_list(sentences, *, normalize_embeddings=None, batch_size=None):
    """Stands in for `FakeBgeM3.encode`, set directly on `world.model` (same
    convention `test_k` uses for `world.model.max_seq_length = 2`).

    `model.tokenizer` IS `model` (see `tests/api/conftest.py`'s `FakeBgeM3`),
    so this same function also serves `dem_token`'s `model.tokenizer.encode
    (a_string)` calls — the `isinstance` branch keeps token counting (and so
    the context-ceiling check `sinh_vector` runs FIRST) working normally.
    Only the actual embedding call, on a LIST of texts, runs out of memory —
    at every batch size `sinh_vector`'s recursive halving tries, down to one.
    """
    if isinstance(sentences, str):
        return sentences.split()
    raise RuntimeError("MPS backend out of memory (allocated 8.00 GiB)")


def test_n_a_real_oom_drives_the_full_pipeline_to_the_same_code(backend, world):
    """No monkeypatched `promote_approved_ingestion` here: this goes through
    the REAL function, the REAL `sinh_vector`, and its REAL recursive
    halving all the way down to a batch of one — proving VEC-3b's wiring, not
    just VEC-3's exception mapping."""
    world.model.encode = _always_out_of_memory_on_a_list

    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    ingestion_id = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    ).json()["ingestion_id"]
    world.run_background()

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()

    assert body["status"] == "failed"
    assert body["code"] == IngestionFailureCode.EMBEDDING_OUT_OF_MEMORY.value
    assert world.inner_store.documents() == [], (
        "a document that ran out of memory before PostgreSQL was ever written "
        "still ended up with a profile"
    )
    assert world.vector_writer.count() == 0


def test_n_embedding_out_of_memory_ends_as_its_own_failed_code(backend, world, monkeypatch):
    def always_out_of_memory(entry, **kwargs):
        raise EmbeddingOutOfMemory(
            "out of device memory embedding a single chunk (index 0) — cannot "
            "split the batch further."
        )

    monkeypatch.setattr(ingestion_pipeline, "promote_approved_ingestion", always_out_of_memory)

    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    ingestion_id = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    ).json()["ingestion_id"]
    world.run_background()

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()

    assert body["status"] == "failed"
    assert body["code"] == IngestionFailureCode.EMBEDDING_OUT_OF_MEMORY.value
    assert world.inner_store.documents() == [], (
        "a document that ran out of memory before PostgreSQL was ever written "
        "still ended up with a profile"
    )
    assert world.vector_writer.count() == 0


def test_n_embedding_out_of_memory_is_not_rejected(backend, world, monkeypatch):
    """⛔ Not `rejected`: the submission itself was not wrong — the machine
    running the model was the limit, and Backend resubmitting the exact same
    file does not fix that (unlike `DOCUMENT_NOT_STRUCTURABLE`/`rejected`,
    which IS about the submission)."""

    def always_out_of_memory(entry, **kwargs):
        raise EmbeddingOutOfMemory("out of device memory")

    monkeypatch.setattr(ingestion_pipeline, "promote_approved_ingestion", always_out_of_memory)

    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    ingestion_id = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    ).json()["ingestion_id"]
    world.run_background()

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()

    assert body["status"] != "rejected"
    assert body["code"] not in (
        IngestionFailureCode.DOCUMENT_NOT_STRUCTURABLE.value,
        IngestionFailureCode.INTERNAL_ERROR.value,
    )
