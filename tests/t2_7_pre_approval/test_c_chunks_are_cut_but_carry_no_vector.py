"""T2.7 (c) — GĐ3 ran and GĐ6 did not. The buffered chunks carry their full
structural identity (`structure_path`, `parent_chunk_id`, spans) and an EMPTY
`embedding`.

This is the pair of facts that makes the stopping point of 06 Mục 5.2 GĐ1
observable: cutting is done, vectorising is not.
"""

from __future__ import annotations

from ingestion.intake import InMemoryFingerprintIndex
from ingestion.pre_approval_runner import run_pre_approval_ingestion

from .conftest import CHUNK_LENGTH_CAP, make_request, registered_spaces, write_sample


def test_chunks_are_cut_but_carry_no_vector(tmp_path, buffer_factory) -> None:
    buffer = buffer_factory()
    request = make_request(write_sample(tmp_path))

    run_pre_approval_ingestion(
        request,
        fingerprint_index=InMemoryFingerprintIndex(),
        buffer=buffer,
        space_registry=registered_spaces(),
        chunk_length_cap=CHUNK_LENGTH_CAP,
    )

    chunks = buffer.get(request.document_id).chunks
    assert len(chunks) > 1

    for chunk in chunks:
        assert chunk.embedding == [], "GĐ6 must not have run on the pre-approval path"
        assert chunk.document_id == request.document_id
        assert chunk.span_end > chunk.span_start
        # The block really is inside the document, and really does contain the
        # span that was cut from it (07 Mục 2.2 v1.11).
        assert chunk.structure_block_start <= chunk.span_start
        assert chunk.span_end <= chunk.structure_block_end
        if chunk.structure_path:
            continue
        # An EMPTY `structure_path` is legal for exactly one thing: the block
        # before the first top-level structure block (or after the last) —
        # 07 Mục 2.2 v1.11, *"nó không nằm ở cấp nào của cây"*. It is not a
        # chunk that lost its path: such a block is a top-level unit by S2
        # rule 2, so it must have no parent either.
        assert chunk.parent_chunk_id is None, (
            "a chunk with no structure_path must be a leading/trailing block, "
            "and those have no parent (S2 quy tắc con 2)"
        )

    # Every chunk that sits INSIDE the tree keeps its full structural identity.
    trong_cay = [chunk for chunk in chunks if chunk.parent_chunk_id is not None]
    assert trong_cay, "the sample must produce at least one nested block"
    for chunk in trong_cay:
        assert chunk.structure_path, "the structure tree survives AS the chunks' paths"

    # The nesting really is preserved, not flattened: at least one chunk is a
    # child of another one in the same buffered entry.
    chunk_ids = {chunk.chunk_id for chunk in chunks}
    assert any(chunk.parent_chunk_id in chunk_ids for chunk in chunks)
    # ... and at least one top-level block has no parent (S2 rule 2).
    assert any(chunk.parent_chunk_id is None for chunk in chunks)
