"""T2.8 (j) — 06 Mục 5.6 deletes *"các liên kết quan hệ của nó"*, and a link
belongs to both of its endpoints.

Keeping only the outbound half would leave `doc-neighbour --references-->
doc-doomed` pointing at a document that no longer exists — which the two
foreign keys in `schema/store_schema.py` (both `ON DELETE CASCADE`) refuse
outright once this runs against real PostgreSQL.
"""

from __future__ import annotations

from ingestion.deletion import purge_document_permanently


def test_outbound_and_inbound_links_both_disappear(world, deletion_kwargs):
    assert {"rel-in", "rel-out", "rel-elsewhere"} == world.relation_ids()

    purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert world.relation_ids() == {"rel-elsewhere"}


def test_no_surviving_link_points_at_a_deleted_document(world, deletion_kwargs):
    purge_document_permanently("doc-doomed", **deletion_kwargs)

    live_ids = world.document_ids()
    for relation in world.inner_store.relations():
        assert relation.from_document_id in live_ids
        assert relation.to_document_id in live_ids
