"""T2.5 (f) — VEC-1: `write_to_qdrant` splits the points into SEVERAL
`upsert` calls, and every one of them waits.

The incident (25/9/2026): 2 of 36 documents ended `failed`/`INTERNAL_ERROR`
because one `upsert` carried a whole document's chunks — a 40-43 MB body,
over Qdrant's 32 MB REST limit. At 1024 dimensions a point serialises to about
20 KB, so any document past ~1600 chunks does it. This is not an exotic size.

No live Qdrant here on purpose. The claim is about BATCHING, and a real store
would only slow the case down without proving more: what has to be observed is
the number of calls and the size of each one. The stamp check is replaced by a
counter (`test_e` is where it is proven against a real collection) — but the
replacement still RECORDS its calls, so deleting the check would turn this file
red rather than green.
"""

from __future__ import annotations

import uuid

import pytest
from schema.chunk import Chunk
from schema.config import ContractConfig, DistanceMetric

from ingestion import vectorization
from ingestion.vectorization import write_to_qdrant

from .conftest import DOC_ID, SPACE_ID, TENANT_ID

FAKE_DIM = 4
CONTRACT = ContractConfig(
    embedding_model="BAAI/bge-m3",
    embedding_dim=FAKE_DIM,
    distance_metric=DistanceMetric.COSINE,
)


class UpsertRecorder:
    """Stands in for `QdrantClient`, remembering only what it was asked to
    write."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def upsert(self, *, collection_name: str, points, wait=None):
        self.calls.append(
            {"collection_name": collection_name, "points": list(points), "wait": wait}
        )


@pytest.fixture
def stamp_check_calls(monkeypatch):
    """Replaces the store-stamp check with a counter — see the module
    docstring for why that does not weaken the case."""
    calls: list[str] = []

    def spy(*, config, qdrant_client, pg_connection, collection_name):
        calls.append(collection_name)

    monkeypatch.setattr(vectorization, "assert_collection_ready_for_contract", spy)
    return calls


def make_chunks(count: int) -> list[Chunk]:
    return [
        Chunk(
            chunk_id=str(uuid.uuid4()),
            document_id=DOC_ID,
            space_id=SPACE_ID,
            tenant_id=TENANT_ID,
            structure_path=["Điều 1"],
            span_start=index,
            span_end=index + 1,
            structure_block_start=index,
            structure_block_end=index + 1,
            embedding=[0.1, 0.2, 0.3, 0.4],
        )
        for index in range(count)
    ]


def write(chunks, *, client, upsert_batch_points: int) -> None:
    write_to_qdrant(
        chunks,
        qdrant_client=client,
        collection_name="cbrain_chunks_test",
        contract_config=CONTRACT,
        pg_connection=object(),
        upsert_batch_points=upsert_batch_points,
    )


def test_a_document_of_1500_chunks_is_written_in_batches_and_every_point_lands(
    stamp_check_calls,
) -> None:
    """The size that actually broke, at the batch size `config/ingestion.yaml`
    ships: six batches, no chunk dropped, no chunk sent twice. A dropped chunk
    is a missing passage of a document that nothing would report."""
    client = UpsertRecorder()
    chunks = make_chunks(1500)

    write(chunks, client=client, upsert_batch_points=256)

    sizes = [len(call["points"]) for call in client.calls]
    assert sizes == [256, 256, 256, 256, 256, 220]

    sent_ids = [point.id for call in client.calls for point in call["points"]]
    assert len(sent_ids) == len(set(sent_ids)) == 1500
    assert set(sent_ids) == {chunk.chunk_id for chunk in chunks}


def test_every_upsert_call_waits_for_the_batch_to_apply(stamp_check_calls) -> None:
    """`wait=True` is not a performance knob: without it a batch still in
    flight can land AFTER `promote_approved_ingestion`'s cleanup deleted this
    document's points, resurrecting exactly what was just removed."""
    client = UpsertRecorder()

    write(make_chunks(700), client=client, upsert_batch_points=256)

    assert [call["wait"] for call in client.calls] == [True, True, True]


def test_a_document_that_fits_is_still_one_upsert(stamp_check_calls) -> None:
    """Control: batching costs a small document no extra calls."""
    client = UpsertRecorder()

    write(make_chunks(10), client=client, upsert_batch_points=256)

    assert len(client.calls) == 1
    assert len(client.calls[0]["points"]) == 10


def test_the_batch_size_actually_comes_from_the_parameter(stamp_check_calls) -> None:
    """The batch size is a real parameter, not a constant hiding in the code:
    change the value and the batches change with it."""
    client = UpsertRecorder()

    write(make_chunks(10), client=client, upsert_batch_points=3)

    assert [len(call["points"]) for call in client.calls] == [3, 3, 3, 1]


def test_the_stamp_check_runs_once_per_call_not_once_per_batch(stamp_check_calls) -> None:
    """The stamp is a fact about the COLLECTION, not about a batch — checking
    it per batch would make a document's cost depend on how it was cut up."""
    client = UpsertRecorder()

    write(make_chunks(1000), client=client, upsert_batch_points=256)

    assert len(client.calls) == 4
    assert stamp_check_calls == ["cbrain_chunks_test"]


def test_a_batch_size_below_one_is_refused_before_anything_is_written(
    stamp_check_calls,
) -> None:
    """A batch size of 0 is a loop that never writes anything, so it must
    RAISE rather than quietly write nothing and report success. Refused ahead
    of the stamp check: a nonsensical parameter should not need a live store
    to be caught."""
    client = UpsertRecorder()

    with pytest.raises(ValueError) as raised:
        write(make_chunks(5), client=client, upsert_batch_points=0)

    assert "qdrant_upsert_batch_points" in str(raised.value)
    assert client.calls == []
    assert stamp_check_calls == []
