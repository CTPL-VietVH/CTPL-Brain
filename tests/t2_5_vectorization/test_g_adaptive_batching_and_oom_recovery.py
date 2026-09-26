"""T2.5 (g) — VEC-3: adaptive batching in `sinh_vector()`.

Uses a FAKE model, not the real BGE-M3: this file's subject is the batching /
sort / halve-and-retry ARITHMETIC, which does not need 2.5GB of real weights
to exercise — the real model's shape (1024-dim, L2-normalised, 8192-token
ceiling) is already covered by `test_a` and `test_b` in this directory.

The fake model's `encode` is fully deterministic and content-addressed
(`_vector_for`), so a wrong chunk↔vector pairing after sorting/splitting shows
up as a wrong VALUE, not just a missing one — the exact silent mis-pairing
VEC-3 exists to rule out.
"""

from __future__ import annotations

import uuid

import numpy as np
import pytest
from schema.chunk import Chunk

from ingestion.vectorization import EmbeddingOutOfMemory, sinh_vector

from .conftest import DOC_ID, SPACE_ID, TENANT_ID


class _FakeTokenizer:
    def encode(self, text: str) -> list[str]:
        return text.split()


class _FakeBgeM3:
    """`BgeM3Like` stand-in whose `encode` is deterministic and can be told
    to run out of memory above some batch size — `oom_above_batch_size=0`
    means EVERY batch, including one of a single chunk, runs out."""

    def __init__(
        self, *, max_seq_length: int = 10_000, oom_above_batch_size: int | None = None
    ) -> None:
        self.tokenizer = _FakeTokenizer()
        self.max_seq_length = max_seq_length
        self._oom_above_batch_size = oom_above_batch_size
        self.encode_calls: list[list[str]] = []

    def encode(self, sentences, *, normalize_embeddings, batch_size):
        self.encode_calls.append(list(sentences))
        if self._oom_above_batch_size is not None and len(sentences) > self._oom_above_batch_size:
            raise RuntimeError("MPS backend out of memory (allocated 4.00 GiB)")
        return np.array([_vector_for(text) for text in sentences])


def _vector_for(text: str) -> list[float]:
    """Deterministic and distinct per DISTINCT text content — a wrong pairing
    after sorting/splitting produces a wrong NUMBER, not just a stale one."""
    return [float(len(text)), float(sum(ord(char) for char in text) % 100_003)]


def _make_chunks_and_text(word_counts: list[int]) -> tuple[str, list[Chunk]]:
    """One chunk per entry in `word_counts`. Chunk i's text is `toki` repeated
    `word_counts[i]` times, so `_FakeTokenizer` reports exactly that many
    tokens for it and every chunk's text is distinct from every other's."""
    parts = [" ".join([f"tok{i}"] * count) for i, count in enumerate(word_counts)]
    full_text = "\n".join(parts)

    chunks: list[Chunk] = []
    cursor = 0
    for index, part in enumerate(parts):
        start = cursor
        end = start + len(part)
        chunks.append(
            Chunk(
                chunk_id=f"chunk-{index}-{uuid.uuid4().hex[:6]}",
                document_id=DOC_ID,
                space_id=SPACE_ID,
                tenant_id=TENANT_ID,
                structure_path=["Điều 1"],
                span_start=start,
                span_end=end,
                structure_block_start=start,
                structure_block_end=end,
                embedding=[],
            )
        )
        cursor = end + 1  # the "\n" joiner
    return full_text, chunks


# --------------------------------------------------------------------------- #
# (a) mapping is correct BY INDEX after sorting, not by leftover order
# --------------------------------------------------------------------------- #


def test_g_a_each_chunk_gets_its_own_vector_after_reordering():
    word_counts = [3, 50, 1, 20, 8]  # deliberately not already sorted
    full_text, chunks = _make_chunks_and_text(word_counts)
    model = _FakeBgeM3()

    result = sinh_vector(chunks, full_text=full_text, model=model, embedding_batch_size=2)

    assert len(result) == len(chunks)
    for original, produced in zip(chunks, result):
        own_text = full_text[original.span_start : original.span_end]
        assert produced.embedding == _vector_for(own_text), (
            f"chunk {original.chunk_id!r} received a vector that is not the "
            f"vector of its OWN text — a mapping bug hiding behind the sort"
        )


# --------------------------------------------------------------------------- #
# (b) the heaviest batch runs first
# --------------------------------------------------------------------------- #


def test_g_b_the_first_batch_is_the_heaviest():
    word_counts = [5, 1, 9, 3, 7, 2]
    full_text, chunks = _make_chunks_and_text(word_counts)
    model = _FakeBgeM3()

    sinh_vector(chunks, full_text=full_text, model=model, embedding_batch_size=2)

    texts = [full_text[chunk.span_start : chunk.span_end] for chunk in chunks]
    heaviest_two = sorted(range(len(word_counts)), key=lambda i: word_counts[i], reverse=True)[:2]
    expected_first_batch = {texts[i] for i in heaviest_two}

    assert set(model.encode_calls[0]) == expected_first_batch, (
        "the first call into the model was not the two chunks with the most "
        "tokens — an OOM on a real document would surface on the LAST batch "
        "instead of the first"
    )


# --------------------------------------------------------------------------- #
# (c) OOM above a size self-heals by halving, same result as no OOM at all
# --------------------------------------------------------------------------- #


def test_g_c_oom_above_a_size_halves_and_converges_to_the_same_result():
    word_counts = [4, 9, 1, 6, 3, 8, 2, 5]
    full_text, chunks = _make_chunks_and_text(word_counts)

    baseline_model = _FakeBgeM3()
    baseline = sinh_vector(
        chunks, full_text=full_text, model=baseline_model, embedding_batch_size=8
    )

    oom_model = _FakeBgeM3(oom_above_batch_size=3)
    recovered = sinh_vector(chunks, full_text=full_text, model=oom_model, embedding_batch_size=8)

    assert [chunk.embedding for chunk in recovered] == [chunk.embedding for chunk in baseline]
    assert any(len(call) > 3 for call in oom_model.encode_calls), (
        "test fixture is broken: the full-size batch never actually ran into "
        "the fake OOM, so this proves nothing about the recovery path"
    )
    assert any(len(call) <= 3 for call in oom_model.encode_calls), (
        "no batch ever got small enough to succeed — halving never converged"
    )


# --------------------------------------------------------------------------- #
# (d) OOM even at a batch of one raises the dedicated exception
# --------------------------------------------------------------------------- #


def test_g_d_oom_even_at_batch_of_one_raises_embedding_out_of_memory():
    word_counts = [3, 5]
    full_text, chunks = _make_chunks_and_text(word_counts)
    model = _FakeBgeM3(oom_above_batch_size=0)  # every batch OOMs, including size 1

    with pytest.raises(EmbeddingOutOfMemory):
        sinh_vector(chunks, full_text=full_text, model=model, embedding_batch_size=8)


# --------------------------------------------------------------------------- #
# (e) a non-OOM error is never swallowed by the retry branch
# --------------------------------------------------------------------------- #


def test_g_e_a_non_oom_runtime_error_is_not_swallowed():
    word_counts = [3, 5]
    full_text, chunks = _make_chunks_and_text(word_counts)

    class _BrokenModel(_FakeBgeM3):
        def encode(self, sentences, *, normalize_embeddings, batch_size):
            raise RuntimeError("tokenizer produced malformed input")

    with pytest.raises(RuntimeError, match="malformed input"):
        sinh_vector(chunks, full_text=full_text, model=_BrokenModel(), embedding_batch_size=8)


# --------------------------------------------------------------------------- #
# (f) batches are sized by embedding_batch_size, not by a constant
# --------------------------------------------------------------------------- #


def test_g_f_batches_are_sized_by_embedding_batch_size():
    word_counts = list(range(1, 11))  # 10 chunks, all distinct token counts
    full_text, chunks = _make_chunks_and_text(word_counts)
    model = _FakeBgeM3()

    sinh_vector(chunks, full_text=full_text, model=model, embedding_batch_size=3)

    assert [len(call) for call in model.encode_calls] == [3, 3, 3, 1]
