"""T2.7 promote (j) — a re-run of GĐ7 may not overwrite a Manager's decision on
a relation.

`relation_pair_type_unique` keeps one row per `(from, to, type)`, which is what
makes a retried promote converge instead of duplicating (test c). But "keep one
row" must not mean "keep the machine's row": a promote re-run after a Manager
had already REJECTED a proposed link would push it back to `PENDING` with no
error and no trace, and the link would reappear in the approval queue as if the
decision had never happened.

07 Mục 2.3 gives `approval_state` to the Manager, and 06 Mục 5.4 makes acting on
it the "vòng lặp chăm sóc tri thức". A machine pass proposes; it never
un-decides.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

from ingestion.promotion import InMemorySharedProfileStore
from schema.relation import ApprovalState, Relation, RelationOrigin, RelationType

from .conftest import make_stored_document


def _store_with_two_documents() -> InMemorySharedProfileStore:
    store = InMemorySharedProfileStore()
    for suffix in ("a", "b"):
        store.register(
            make_stored_document(
                document_id=f"doc-{suffix}",
                version_chain_id=f"chain-{suffix}",
                version_ordinal=1,
                content_fingerprint=f"fp-{suffix}",
            )
        )
    return store


def _proposal(relation_id: str) -> Relation:
    return Relation(
        relation_id=relation_id,
        from_document_id="doc-a",
        to_document_id="doc-b",
        relation_type=RelationType.AMENDS_OR_REPLACES,
        origin=RelationOrigin.MACHINE_INFERRED,
        approval_state=ApprovalState.PENDING,
        confidence=0.8,
    )


def test_a_rejected_relation_is_not_resurrected_by_a_rescan() -> None:
    store = _store_with_two_documents()
    document = store.get_document("doc-a")

    store.write_document_and_relations(document=document, relations=[_proposal("rel-1")])

    # The Manager rejects it.
    rejected = dataclasses.replace(
        store.relations()[0],
        approval_state=ApprovalState.REJECTED,
        approved_by="manager-1",
        approved_at=datetime(2026, 9, 22, 16, 0),
    )
    # Written directly: the Manager write surface that would normally do this
    # is T2.10, which does not exist yet (see the T2.7 report).
    store._relations[rejected.relation_id] = rejected

    # GĐ7 runs again and proposes the very same link, with a fresh relation_id.
    store.write_document_and_relations(document=document, relations=[_proposal("rel-2")])

    stored = store.relations()
    assert len(stored) == 1, "still one row per (from, to, type)"
    assert stored[0].approval_state is ApprovalState.REJECTED
    assert stored[0].approved_by == "manager-1"


def test_a_still_pending_relation_is_refreshed_by_a_rescan() -> None:
    """Nothing has been decided yet, so the newer proposal wins — that is what
    keeps a retried promote converging rather than piling up rows."""
    store = _store_with_two_documents()
    document = store.get_document("doc-a")

    store.write_document_and_relations(document=document, relations=[_proposal("rel-1")])
    store.write_document_and_relations(document=document, relations=[_proposal("rel-2")])

    stored = store.relations()
    assert len(stored) == 1
    assert stored[0].relation_id == "rel-2"
