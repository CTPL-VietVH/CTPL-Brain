"""T2.7 promote (k) — VEC-1: what a failed step 5 must undo, and what it must
NOT touch.

The incident (25/9/2026): a document's whole chunk set went into ONE `upsert`,
the body reached 40-43 MB, Qdrant refused it, and the job ended `failed` —
with the PostgreSQL profile already committed. `tests/.../test_b` covers the
plain case; this file covers the four ways the cleanup can be got wrong, each
of which fails silently in production:

1. the write applied PARTIALLY before failing — the leftovers must go too, and
   only a delete BY `document_id` FILTER finds them;
2. a promote re-run over a document an EARLIER promote already committed must
   never be rolled back (that would turn a retry into data loss);
3. the cleanup runs in S6 order — vectors first, profile second (điều cấm #17);
4. if the vector delete fails, the profile is LEFT ALONE rather than deleted
   into a dangling pointer.

And one structural guard: the promote may not grow a `deletion_log` port. That
log belongs to a permanent deletion a person ordered (06 Mục 5.6), not to the
system undoing its own half-finished write.
"""

from __future__ import annotations

import inspect

import pytest
from ingestion.deletion import InMemoryDeletionLog
from ingestion.pre_approval_buffer import InMemoryPreApprovalBuffer
from ingestion.promotion import InMemoryVectorStoreWriter, promote_approved_ingestion
from schema.chunk import Chunk

from .conftest import (
    SATURATION_EPSILON,
    SATURATION_ROUNDS,
    SCAN_PAIR_BUDGET,
    SCAN_TIME_BUDGET,
    FakeBgeM3,
    buffer_a_document,
    make_scope,
    vector_deleter_for,
)

DOCUMENT_ID = "doc-promote-1"


class QdrantIsDown(Exception):
    pass


class HalfWritingVectorStoreWriter:
    """Writes the first `applied` chunks, then fails — a batched upsert whose
    batch k was refused after batches 1..k-1 had already landed."""

    def __init__(self, backing: InMemoryVectorStoreWriter, *, applied: int) -> None:
        self._backing = backing
        self._applied = applied

    def write(self, chunks: list[Chunk]) -> None:
        self._backing.write(chunks[: self._applied])
        raise QdrantIsDown("request body too large")


class RecordingVectorDeleter:
    """Wraps the real in-memory deleter and notes WHEN it ran."""

    def __init__(self, inner, calls: list[str]) -> None:
        self._inner = inner
        self._calls = calls

    def delete_document_points(self, document_id: str) -> int:
        self._calls.append("vectors")
        return self._inner.delete_document_points(document_id)


class RecordingProfileDeleter:
    """Same, for the PostgreSQL side. Everything else forwards, so the store
    under test is still the one the promote wrote to."""

    def __init__(self, inner, calls: list[str]) -> None:
        self._inner = inner
        self._calls = calls

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def delete_document_and_relations(self, document_id: str):
        self._calls.append("profile")
        return self._inner.delete_document_and_relations(document_id)


class RefusingVectorDeleter:
    """The cleanup's own first step fails — Qdrant is still down."""

    def delete_document_points(self, document_id: str) -> int:
        raise QdrantIsDown("still down, cannot delete either")


def _promote(entry, *, store, buffer, writer, vector_deleter, profile_deleter=None):
    return promote_approved_ingestion(
        entry,
        profile_store=store,
        profile_deleter=profile_deleter if profile_deleter is not None else store,
        buffer=buffer,
        vector_writer=writer,
        vector_deleter=vector_deleter,
        embedding_model=FakeBgeM3(),
        relation_scope=make_scope(),
        relation_document_source=store,
        saturation_epsilon=SATURATION_EPSILON,
        saturation_rounds=SATURATION_ROUNDS,
        scan_pair_budget=SCAN_PAIR_BUDGET,
        scan_time_budget=SCAN_TIME_BUDGET,
    )


def test_an_upsert_that_fails_after_some_points_landed_leaves_none_behind(
    tmp_path, profile_store
) -> None:
    """The partial-write case — the one a delete by "the ids I just sent"
    would get wrong, because those ids are not the ids that landed."""
    store = profile_store
    buffer = InMemoryPreApprovalBuffer()
    vectors = InMemoryVectorStoreWriter()
    entry = buffer_a_document(tmp_path, buffer=buffer, fingerprint_index=store)
    assert len(entry.chunks) >= 2, "this case needs a document of several chunks"

    with pytest.raises(QdrantIsDown):
        _promote(
            entry,
            store=store,
            buffer=buffer,
            writer=HalfWritingVectorStoreWriter(vectors, applied=1),
            vector_deleter=vector_deleter_for(vectors),
        )

    assert vectors.count() == 0, "a partially applied write left points behind"
    assert store.get_document(DOCUMENT_ID) is None
    assert store.relations() == []


def test_a_retry_of_an_already_committed_document_is_never_rolled_back(
    tmp_path, profile_store
) -> None:
    """A document an earlier promote committed stays committed.

    Rolling back here would mean: Qdrant hiccups during a re-run, and a
    healthy, findable document is deleted from both stores as a side effect.
    """
    store = profile_store
    buffer = InMemoryPreApprovalBuffer()
    vectors = InMemoryVectorStoreWriter()
    entry = buffer_a_document(tmp_path, buffer=buffer, fingerprint_index=store)

    # First promote: succeeds. The document is now committed and findable.
    _promote(
        entry,
        store=store,
        buffer=buffer,
        writer=vectors,
        vector_deleter=vector_deleter_for(vectors),
    )
    points_after_success = vectors.count()
    assert store.get_document(DOCUMENT_ID) is not None
    assert points_after_success > 0

    # Second promote of the same entry, with Qdrant down.
    with pytest.raises(QdrantIsDown):
        _promote(
            entry,
            store=store,
            buffer=buffer,
            writer=HalfWritingVectorStoreWriter(vectors, applied=0),
            vector_deleter=vector_deleter_for(vectors),
        )

    assert store.get_document(DOCUMENT_ID) is not None, (
        "a retry rolled back a document an EARLIER promote had committed — "
        "that is data loss, not cleanup"
    )
    assert vectors.count() == points_after_success


def test_the_cleanup_deletes_vectors_before_the_profile_row(tmp_path, profile_store) -> None:
    """S6 order, backwards is forbidden: a profile deleted while its points
    survive is the dangling pointer of điều cấm #17."""
    store = profile_store
    buffer = InMemoryPreApprovalBuffer()
    vectors = InMemoryVectorStoreWriter()
    entry = buffer_a_document(tmp_path, buffer=buffer, fingerprint_index=store)
    calls: list[str] = []

    with pytest.raises(QdrantIsDown):
        _promote(
            entry,
            store=store,
            buffer=buffer,
            writer=HalfWritingVectorStoreWriter(vectors, applied=1),
            vector_deleter=RecordingVectorDeleter(vector_deleter_for(vectors), calls),
            profile_deleter=RecordingProfileDeleter(store, calls),
        )

    assert calls == ["vectors", "profile"]


def test_a_cleanup_whose_vector_delete_fails_leaves_the_profile_alone(
    tmp_path, profile_store
) -> None:
    """Between "a document nothing can find" and "chunks that lead nowhere",
    the cleanup stops at the first — and says so in the log."""
    store = profile_store
    buffer = InMemoryPreApprovalBuffer()
    vectors = InMemoryVectorStoreWriter()
    entry = buffer_a_document(tmp_path, buffer=buffer, fingerprint_index=store)

    with pytest.raises(QdrantIsDown):
        _promote(
            entry,
            store=store,
            buffer=buffer,
            writer=HalfWritingVectorStoreWriter(vectors, applied=1),
            vector_deleter=RefusingVectorDeleter(),
        )

    assert store.get_document(DOCUMENT_ID) is not None, (
        "the profile was deleted while its points were still in the vector "
        "store — điều cấm #17, the dangling pointer S6 exists to prevent"
    )


def test_the_original_failure_is_what_comes_out_of_a_failed_cleanup(
    tmp_path, profile_store
) -> None:
    """The cleanup never replaces the story. `RefusingVectorDeleter` raises
    its own `QdrantIsDown`, but what the caller sees must be the exception the
    WRITE raised — the one that says what actually went wrong."""
    store = profile_store
    buffer = InMemoryPreApprovalBuffer()
    vectors = InMemoryVectorStoreWriter()
    entry = buffer_a_document(tmp_path, buffer=buffer, fingerprint_index=store)

    with pytest.raises(QdrantIsDown) as raised:
        _promote(
            entry,
            store=store,
            buffer=buffer,
            writer=HalfWritingVectorStoreWriter(vectors, applied=1),
            vector_deleter=RefusingVectorDeleter(),
        )

    assert "request body too large" in str(raised.value)


def test_the_cleanup_writes_no_deletion_log_line(tmp_path, profile_store) -> None:
    """⛔ The promote has no `deletion_log` port, and must not grow one.

    A line there would say a person ordered this deletion (06 Mục 5.6 —
    *"ai, khi nào, tài liệu nào, lý do"*), and would leave an open entry
    `space_deletion.delete_space` later adopts as unfinished work.
    """
    log = InMemoryDeletionLog()
    store = profile_store
    buffer = InMemoryPreApprovalBuffer()
    vectors = InMemoryVectorStoreWriter()
    entry = buffer_a_document(tmp_path, buffer=buffer, fingerprint_index=store)

    with pytest.raises(QdrantIsDown):
        _promote(
            entry,
            store=store,
            buffer=buffer,
            writer=HalfWritingVectorStoreWriter(vectors, applied=1),
            vector_deleter=vector_deleter_for(vectors),
        )

    assert log.entries() == []
    parameters = inspect.signature(promote_approved_ingestion).parameters
    assert not [name for name in parameters if "log" in name.lower()], (
        "promote_approved_ingestion grew a log port — the cleanup of a failed "
        "write is not a permanent deletion (06 Mục 5.6)"
    )
