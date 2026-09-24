"""T2.8 (q) — the exact scenario PO named as the reason T4 exists (docs/10
§1 T4): *"tránh xoá nhầm bản trùng ở Space khác"*.

Two documents can share a `content_fingerprint` when they live in different
Spaces — the active-fingerprint uniqueness in `store_schema.py` is scoped to
`(space_id, content_fingerprint)`, not to the fingerprint alone. Deleting one
of the pair, by its own `document_id` plus its own `space_id`, must never
reach the other in either store, and must not gỡ any relation that does not
name the deleted document directly.
"""

from __future__ import annotations

from ingestion.deletion import purge_document_permanently
from t2_8_deletion.conftest import make_chunk, make_document, make_relation

FINGERPRINT = "fingerprint-shared-across-two-spaces"


def test_deleting_the_duplicate_in_space_a_leaves_the_one_in_space_b_whole(world, deletion_kwargs):
    doc_a = make_document(
        document_id="doc-fp-a", space_id="space-fp-a", content_fingerprint=FINGERPRINT
    )
    doc_b = make_document(
        document_id="doc-fp-b", space_id="space-fp-b", content_fingerprint=FINGERPRINT
    )

    world.profile_store.write_document_and_relations(document=doc_a, relations=[])
    world.profile_store.write_document_and_relations(
        document=doc_b,
        relations=[
            make_relation(
                relation_id="rel-a-to-b", from_document_id="doc-fp-a", to_document_id="doc-fp-b"
            ),
            make_relation(
                relation_id="rel-b-unrelated",
                from_document_id="doc-fp-b",
                to_document_id="doc-neighbour",
            ),
        ],
    )
    world.vector_writer.write(
        [
            make_chunk(chunk_id="chunk-fp-a-1", document=doc_a, span=(0, 28)),
            make_chunk(chunk_id="chunk-fp-b-1", document=doc_b, span=(0, 28)),
        ]
    )

    outcome = purge_document_permanently(
        "doc-fp-a", **{**deletion_kwargs, "space_id": "space-fp-a"}
    )

    assert outcome.profile_was_present is True

    # B, the duplicate in the OTHER Space, survives intact in both stores.
    assert world.profile_store.get_document("doc-fp-b") == doc_b
    assert "chunk-fp-b-1" in world.point_ids()
    assert "rel-b-unrelated" in world.relation_ids()

    # Only the link naming A directly is gone; B's own, unrelated link stays.
    assert "rel-a-to-b" not in world.relation_ids()

    # A itself, and only A, is gone.
    assert "doc-fp-a" not in world.document_ids()
    assert "chunk-fp-a-1" not in world.point_ids()
