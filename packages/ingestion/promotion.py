"""T2.7, the second half — promote an approved entry out of the pre-approval
buffer into the shared stores (08 dòng 206: *"Manager duyệt xong mới chạy nốt
và ghi ra ba kho"*; 06 Mục 5.2 GĐ1).

`pre_approval_runner.py` stops before GĐ6 and GĐ7 and parks everything in the
buffer. This module is what runs when a Manager approves: GĐ6, GĐ7, then the
first write this project makes into the official stores.

──────────────────────────────────────────────────────────────────────────
Write order — the MIRROR of the delete order, and why that is the safe one
──────────────────────────────────────────────────────────────────────────

S6 (07 Mục 6) locks deletion as: **kho vector → (quan hệ + hồ sơ, MỘT giao
dịch) → dọn nền**, and states the reason — *"đường đọc là tính phạm vi quyền
→ tìm trong kho vector → kéo họ hàng ở kho đồ thị → đọc hồ sơ ... Cổng chặn
nằm ở KHO VECTOR."* Deleting the vector first makes the document unfindable
immediately and never leaves a chunk pointing at a profile that is gone.

Writing therefore runs S6 backwards:

1. Recompute `version_ordinal` against the live chain (see below).
2. GĐ6 — `vectorization.sinh_vector`, no store touched.
3. GĐ7 — `relations_scan.scan_relations_for_new_document`, no store touched.
4. **PostgreSQL, ONE transaction**: profile + relations. 07 Mục 2 dòng 65 is
   what makes this possible — *"hai bước xoá quan hệ và hồ sơ nằm chung một
   cơ sở dữ liệu nên thành một giao dịch nguyên khối"* — and the same holds
   for writing them.
5. **Qdrant**: the vectors. The document becomes findable exactly here.
6. `buffer.discard(...)`.

The gate opens LAST, so a half-done write never leaves findable chunks whose
profile is missing — precisely the dangling pointer S6 was written to
prevent.

──────────────────────────────────────────────────────────────────────────
⚠️ Step 5 failing is NOT a harmless state — VEC-1, sự cố 25/9/2026
──────────────────────────────────────────────────────────────────────────

This docstring used to call a profile with no vectors *"invisible to every
query, and pointing at nothing that does not exist"*, i.e. harmless. **That
was wrong, and the 25/9/2026 incident is the proof.** It is invisible to
QUESTIONS, and it is poison to the NEXT UPLOAD of the same file:

* the fingerprint index reads the `document` table directly
  (`pg_document_stores.PgDocumentStore.find_by_fingerprint`), so
  `intake.decide_intake` finds the orphan and answers `duplicate`;
* Backend is then told the file is already here, naming a `document_id` that
  no question can ever reach — no error, no log, nothing to notice.

So step 5 is wrapped, and a failure of it **undoes the write this call
made**, in S6 order: the vectors (by `document_id` FILTER, which catches a
partially applied batch — see `vectorization.write_to_qdrant`), then profile
+ relations in ONE transaction. Then the ORIGINAL error is re-raised; the
cleanup is not allowed to replace the story of what actually went wrong.

Three rules the cleanup follows, each one load-bearing:

* **Only when THIS call created the profile.** A promote re-run over a
  document that was already committed (`already_committed is not None`) must
  never roll back: that document may be healthy and findable, and its
  vectors merely failed to be re-written. Deleting it would turn a retry into
  data loss.
* **Vectors first, PostgreSQL second — never the other way.** If the vector
  delete fails, the profile is LEFT ALONE on purpose: removing it while
  points survive is the dangling pointer of điều cấm #17 and S6.
* **No `deletion_log` line.** 06 Mục 5.6's log answers *"ai, khi nào, tài
  liệu nào, lý do"* for a permanent deletion a PERSON ordered. This is the
  system undoing its own half-finished write of a document no user ever saw;
  inventing a `deleted_by` for it would put fiction in the one record that
  has to stay literal, and would leave an open line that
  `space_deletion.delete_space` would later adopt as unfinished work.
  The visible trace lives where the rest of this job's story lives: the
  `ingestion_record` row (`failed`) plus this module's log.

What is still NOT handled here, by decision: a process that dies mid-cleanup
leaves an orphan nothing has swept yet. Finishing those at startup is VEC-2 —
`IngestionPipeline.sweep_promotion_orphans`.

⚠️ **VEC-2 asks one thing of every caller of this function**: record the
`document_id` this promote is about to write, durably, BEFORE calling it —
`ingestion_record.promoting_document_id`, which `IngestionPipeline._ingest`
writes for the ordinary path. The pointer cannot be created here, because the
crash it exists to survive can happen inside this function; and it cannot be
derived afterwards, because `ingestion_id` and `document_id` are deliberately
two different identifiers (docs/10 §4.2, PO chốt 25/9/2026). A caller that
skips it gets a promote that still behaves correctly — and an orphan that no
sweep will ever find.

⚠️ The Qdrant↔PostgreSQL boundary has no shared transaction — 07 Mục 2 calls
it *"ranh giới duy nhất còn thiếu giao dịch chung"*. The answer is the same
one S6 gives for deletion: **every step must be re-runnable without doing
further damage.** `promote_approved_ingestion` is therefore idempotent end to
end, and `discard` comes last so a crash anywhere leaves the entry in the
buffer for the retry to pick up.

──────────────────────────────────────────────────────────────────────────
`version_ordinal` is RECOMPUTED here, never carried over
──────────────────────────────────────────────────────────────────────────

The ordinal assigned when the entry entered the buffer was provisional: an
approval can sit for an unbounded time, and the chain can grow meanwhile.
Reusing the buffered value would let two pending uploads both promote as
ordinal 2 — T2.1-E2's race condition walking back in through the approval
door. So the ordinal is recomputed against the chain as it stands AT PROMOTE
TIME, and `document_version_chain_ordinal_unique` (schema/store_schema.py)
catches the residual race at the storage layer, where 08 dòng 210 insists it
must be caught.

Re-running a promote that already committed keeps the ordinal already
written — recomputing max+1 a second time would hand the same document a new
ordinal on every retry.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

# The two delete-side ports the compensating cleanup needs. Imported from
# `deletion.py`, never re-declared here: a second Protocol describing the same
# two calls is the `doc_profile_code`/`profile_code` bug in Protocol form
# (CLAUDE.md Mục 6). `deletion.py` imports nothing from this module, so the
# dependency stays one-way.
from ingestion.deletion import DeletableProfileStore, VectorStoreDeleter
from ingestion.pre_approval_buffer import BufferedIngestion, PreApprovalBuffer
from ingestion.relations_scan import (
    SpaceDocumentSource,
    SpaceScanScope,
    scan_relations_for_new_document,
)
from ingestion.vectorization import BgeM3Like, sinh_vector, write_to_qdrant
from schema.chunk import Chunk
from schema.document import Document
from schema.relation import ApprovalState, Relation
from schema.store_schema import (
    DOCUMENT_ACTIVE_FINGERPRINT_INDEX,
    DOCUMENT_VERSION_CHAIN_ORDINAL_CONSTRAINT,
    RELATION_FROM_DOCUMENT_FK,
    RELATION_PAIR_TYPE_CONSTRAINT,
)

__all__ = [
    "DuplicateActiveFingerprintError",
    "InMemorySharedProfileStore",
    "InMemoryVectorStoreWriter",
    "PromotionResult",
    "QdrantVectorStoreWriter",
    "SharedProfileStore",
    "SharedStoreError",
    "UnknownRelationEndpointError",
    "VectorStoreWriter",
    "VersionChainOrdinalConflictError",
    "promote_approved_ingestion",
]

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Errors — each one mirrors a constraint in `schema/store_schema.py`, so the
# in-memory store refuses exactly what PostgreSQL would refuse.
# --------------------------------------------------------------------------- #


class SharedStoreError(Exception):
    """Base for every refusal from the official profile store."""


class VersionChainOrdinalConflictError(SharedStoreError):
    """`(version_chain_id, version_ordinal)` is already taken.

    The storage-level half of T2.1-E2: two writers both computed the same
    next ordinal and one of them has to lose. Recomputing at promote time
    narrows the window; this constraint closes it.
    """


class DuplicateActiveFingerprintError(SharedStoreError):
    """An ACTIVE document with this `(space_id, content_fingerprint)` exists.

    Active is the operative word — a `removed_as_wrong` twin does not block a
    re-upload, matching `intake.decide_intake` and the partial unique index
    that backs it.
    """


class UnknownRelationEndpointError(SharedStoreError):
    """A relation points at a document that is not in the store — the foreign
    key named by `RELATION_FROM_DOCUMENT_FK` / `RELATION_TO_DOCUMENT_FK`,
    refused here too so it surfaces without a live PostgreSQL."""


# --------------------------------------------------------------------------- #
# Protocols
# --------------------------------------------------------------------------- #


class SharedProfileStore(Protocol):
    """The official PostgreSQL side: `document` + `relation`.

    ⭐ **`write_document_and_relations` is the transaction boundary.** One call
    writes the profile and every relation, or writes nothing. This is the
    atomic unit 07 Mục 2 dòng 65 makes available by putting both tables in one
    database, and the write order INSIDE it is fixed — the document row first,
    because each relation row carries a foreign key to it.

    Both writes are UPSERTs: a promote that crashed after this step and is
    retried must converge, not duplicate.
    """

    def get_document(self, document_id: str) -> Document | None: ...

    def max_version_ordinal_in_chain(self, version_chain_id: str) -> int | None: ...

    def write_document_and_relations(
        self, *, document: Document, relations: list[Relation]
    ) -> None: ...


class VectorStoreWriter(Protocol):
    """The Qdrant side, narrowed to the one call this module makes.

    Narrowed on purpose: `vectorization.write_to_qdrant` needs a live
    `QdrantClient` AND a live PostgreSQL connection (it verifies the store
    stamp before writing a single point — T1.3). `QdrantVectorStoreWriter`
    below is the real adapter that supplies both; the Protocol is what lets
    the promote path be tested without either.
    """

    def write(self, chunks: list[Chunk]) -> None: ...


class QdrantVectorStoreWriter:
    """The real `VectorStoreWriter` — delegates to `write_to_qdrant`, which
    stays the single entry point for the stamp check (06 dòng 258, 07 Mục
    3.1 ràng buộc 2). Nothing about that check is re-implemented here.

    `upsert_batch_points` has no default: it is `qdrant_upsert_batch_points`
    from `config/ingestion.yaml`, handed down by the composition root like
    every other live number (CLAUDE.md Mục 4 quy tắc 2). Held here rather
    than passed through `VectorStoreWriter.write` because it describes the
    STORE this adapter talks to, not the document being written — the promote
    path must not have to know about the transport's limits.
    """

    def __init__(
        self,
        *,
        qdrant_client: object,
        collection_name: str,
        contract_config: object,
        pg_connection: object,
        upsert_batch_points: int,
    ) -> None:
        self._qdrant_client = qdrant_client
        self._collection_name = collection_name
        self._contract_config = contract_config
        self._pg_connection = pg_connection
        self._upsert_batch_points = upsert_batch_points

    def write(self, chunks: list[Chunk]) -> None:
        write_to_qdrant(
            chunks,
            qdrant_client=self._qdrant_client,  # type: ignore[arg-type]
            collection_name=self._collection_name,
            contract_config=self._contract_config,  # type: ignore[arg-type]
            pg_connection=self._pg_connection,  # type: ignore[arg-type]
            upsert_batch_points=self._upsert_batch_points,
        )


# --------------------------------------------------------------------------- #
# Result
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True, kw_only=True)
class PromotionResult:
    """What a completed promote produced.

    `document` carries the RECOMPUTED `version_ordinal` and the
    `relations_scan_state` GĐ7 recommended — the buffered entry's values for
    both are superseded, not reused.

    `relations` are `PENDING` machine proposals, as both T2.6 detectors
    produce them: 06 Mục 5.3 keeps Manager approval in the loop, and an
    unapproved relation is still pulled into context, just with weaker wording.
    """

    document: Document
    chunks: list[Chunk]
    relations: list[Relation]
    version_ordinal_was_recomputed: bool


# --------------------------------------------------------------------------- #
# The promote
# --------------------------------------------------------------------------- #


def promote_approved_ingestion(
    entry: BufferedIngestion,
    *,
    profile_store: SharedProfileStore,
    profile_deleter: DeletableProfileStore,
    buffer: PreApprovalBuffer,
    vector_writer: VectorStoreWriter,
    vector_deleter: VectorStoreDeleter,
    embedding_model: BgeM3Like,
    relation_scope: SpaceScanScope,
    relation_document_source: SpaceDocumentSource,
    saturation_epsilon: float,
    saturation_rounds: int,
    scan_pair_budget: int,
    scan_time_budget: float,
    clock: Callable[[], float] = time.monotonic,
) -> PromotionResult:
    """Run GĐ6 and GĐ7 for an approved entry and write it to the shared stores.

    None of the four scan parameters has a default — they belong to
    `config/ingestion.yaml` and the caller passes the live values down
    (CLAUDE.md Mục 4 quy tắc 2). `scan_time_budget` is IN MINUTES, the unit
    that config key carries.

    `profile_deleter` and `vector_deleter` are the SAME two stores as
    `profile_store` and `vector_writer` — in a deployment `PgDocumentStore` is
    literally both halves of the first pair. Four parameters because they are
    four different sets of promises, the same reason `IngestionPipeline`
    keeps `profile_store` and `fingerprint_index` apart. They are required,
    not optional: a promote wired without them would look like it worked and
    would quietly go back to leaving orphans behind.

    This function does not record WHO approved: `Document` has no approval
    field, by design — S1 makes everything in the shared store already usable,
    so "approved" is not a state a profile can be in. The approval trace
    belongs to the Manager write surface (T2.10), which does not exist yet.

    Idempotent: re-running after a crash converges on the same state rather
    than duplicating anything. See the module docstring for the order and why
    `discard` comes last.
    """
    buffered_document = entry.document

    # ---- 1. Version ordinal, recomputed against the live chain ----------
    already_committed = profile_store.get_document(buffered_document.document_id)
    if already_committed is not None:
        # A retry. Keep the ordinal that was actually written — recomputing
        # max+1 again would move the document one slot further on every run.
        version_ordinal = already_committed.version_ordinal
        recomputed = False
    else:
        current_max = profile_store.max_version_ordinal_in_chain(
            buffered_document.version_chain_id
        )
        version_ordinal = 1 if current_max is None else current_max + 1
        recomputed = version_ordinal != buffered_document.version_ordinal

    document = dataclasses.replace(buffered_document, version_ordinal=version_ordinal)

    # ---- 2. GĐ6 — vectors. No store touched. ----------------------------
    vectorized_chunks = sinh_vector(
        entry.chunks,
        full_text=document.extracted_text,
        model=embedding_model,
    )

    # ---- 3. GĐ7 — relations. No store touched. --------------------------
    scan = scan_relations_for_new_document(
        document,
        scope=relation_scope,
        document_source=relation_document_source,
        saturation_epsilon=saturation_epsilon,
        saturation_rounds=saturation_rounds,
        scan_pair_budget=scan_pair_budget,
        scan_time_budget=scan_time_budget,
        clock=clock,
    )
    document = dataclasses.replace(
        document, relations_scan_state=scan.recommended_scan_state
    )

    # ---- 4. PostgreSQL — profile + relations, ONE transaction ------------
    profile_store.write_document_and_relations(document=document, relations=scan.relations)

    # ---- 5. Qdrant — the gate opens here --------------------------------
    try:
        vector_writer.write(vectorized_chunks)
    except Exception as vector_write_error:
        if already_committed is None:
            # This call is the one that created the profile in step 4, so this
            # call is the one that has to take it back. See the module
            # docstring for why a retry over an already-committed document is
            # NOT rolled back.
            _undo_the_write_this_call_made(
                document_id=document.document_id,
                profile_deleter=profile_deleter,
                vector_deleter=vector_deleter,
                cause=vector_write_error,
            )
        else:
            logger.warning(
                "Vector write failed for document %s, which an EARLIER promote had "
                "already committed. Leaving both stores alone: that document may be "
                "healthy and findable, and rolling it back here would turn a retry "
                "into data loss. Cause: %r",
                document.document_id,
                vector_write_error,
            )
        raise

    # ---- 6. Release the working area ------------------------------------
    buffer.discard(document.document_id)

    return PromotionResult(
        document=document,
        chunks=vectorized_chunks,
        relations=scan.relations,
        version_ordinal_was_recomputed=recomputed,
    )


def _undo_the_write_this_call_made(
    *,
    document_id: str,
    profile_deleter: DeletableProfileStore,
    vector_deleter: VectorStoreDeleter,
    cause: BaseException,
) -> None:
    """Take back step 4 and whatever of step 5 landed — in S6 order.

    Never raises: the caller re-raises the ORIGINAL failure, which is the one
    that explains what happened. A cleanup error that replaced it would hide
    the cause behind its own symptom.

    ⭐ **Vectors first, and the profile is left alone if that fails.** S6
    (07 Mục 6) puts the gate at the vector store; a profile deleted while its
    points survive is the dangling pointer of điều cấm #17 — findable chunks
    whose profile is gone. Between "a document nothing can find" and "chunks
    that lead nowhere", the first is the one the design already tolerates for
    the length of a retry, so that is the state this function stops in.

    ⛔ Writes NOTHING to `deletion_log`. See the module docstring: that log
    belongs to a permanent deletion a person ordered (06 Mục 5.6), not to the
    system undoing its own half-finished write.
    """
    logger.warning(
        "Vector write failed for document %s after PostgreSQL had committed. "
        "Undoing this promote — vector store first, then profile + relations "
        "(S6 order). Cause: %r",
        document_id,
        cause,
    )

    try:
        # By FILTER on document_id, inside `VectorStoreDeleter` — not by the
        # ids just sent. A batch that applied partially leaves points this
        # call never confirmed, and only a filter catches those.
        points_deleted = vector_deleter.delete_document_points(document_id)
    except Exception:
        logger.exception(
            "⚠️ CLEANUP INCOMPLETE for document %s: the vector store refused to "
            "delete its points, so the PostgreSQL profile is deliberately LEFT IN "
            "PLACE (deleting it now would leave findable chunks pointing at nothing "
            "— điều cấm #17). The document is an orphan in BOTH stores until it is "
            "swept. Original failure that started this: %r",
            document_id,
            cause,
        )
        return

    try:
        counts = profile_deleter.delete_document_and_relations(document_id)
    except Exception:
        logger.exception(
            "⚠️ CLEANUP INCOMPLETE for document %s: its vectors are gone (%d points) "
            "but PostgreSQL still holds the profile. Nothing can find the document, "
            "and re-uploading the same file will be refused as a duplicate until "
            "this row is swept. Original failure that started this: %r",
            document_id,
            points_deleted,
            cause,
        )
        return

    logger.warning(
        "Promote of document %s undone: %d vector point(s), %d profile row(s) and "
        "%d relation(s) removed. Both stores are back to not knowing this document, "
        "so the same file can be submitted again.",
        document_id,
        points_deleted,
        counts.profile_rows_deleted,
        counts.relations_deleted,
    )


# --------------------------------------------------------------------------- #
# In-memory implementations — tests and single-process runs, NOT the real
# stores (same disclaimer as `InMemoryFingerprintIndex`).
# --------------------------------------------------------------------------- #


class InMemorySharedProfileStore:
    """`SharedProfileStore` in dicts, enforcing every constraint the DDL does.

    Also satisfies `intake.FingerprintIndex` (`find_by_fingerprint`,
    `register`) and `relations_scan.SpaceDocumentSource` (`documents_in`) —
    not a convenience: in a real deployment those three readers ARE the same
    `document` table, and modelling them as three objects in tests would hide
    the fact that a promote makes a document visible to all three at once.
    """

    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self._relations: dict[str, Relation] = {}

    # -- SharedProfileStore --------------------------------------------- #

    def get_document(self, document_id: str) -> Document | None:
        return self._documents.get(document_id)

    def max_version_ordinal_in_chain(self, version_chain_id: str) -> int | None:
        ordinals = [
            document.version_ordinal
            for document in self._documents.values()
            if document.version_chain_id == version_chain_id
        ]
        return max(ordinals) if ordinals else None

    def write_document_and_relations(
        self, *, document: Document, relations: list[Relation]
    ) -> None:
        """Validate everything, then apply everything — the in-memory stand-in
        for one PostgreSQL transaction. A refusal must leave the store
        untouched, which a check-as-you-write loop would quietly lose."""
        self._check_version_chain(document)
        self._check_active_fingerprint(document)

        known_ids = set(self._documents) | {document.document_id}
        for relation in relations:
            for endpoint in (relation.from_document_id, relation.to_document_id):
                if endpoint not in known_ids:
                    raise UnknownRelationEndpointError(
                        f"relation {relation.relation_id!r} points at document "
                        f"{endpoint!r}, which is not in the store "
                        f"({RELATION_FROM_DOCUMENT_FK} / {RELATION_PAIR_TYPE_CONSTRAINT} "
                        f"are declared in schema/store_schema.py)"
                    )

        # Apply. UPSERT semantics on both tables so a retried promote
        # converges instead of duplicating.
        self._documents[document.document_id] = document
        for relation in relations:
            key = self._relation_key(relation)
            existing_id = next(
                (
                    stored_id
                    for stored_id, stored in self._relations.items()
                    if self._relation_key(stored) == key
                ),
                None,
            )
            # `relation_pair_type_unique`: one (from, to, type) keeps one row,
            # so re-running a scan that regenerates `relation_id` does not pile
            # up duplicates of the same link.
            if existing_id is not None:
                existing = self._relations[existing_id]
                # ⭐ A Manager's decision is NEVER overwritten by a machine
                # re-scan. Replacing the row wholesale would turn an APPROVED or
                # REJECTED link back into PENDING with no error and no trace —
                # a rerun of GĐ7 quietly resurrecting a link a human already
                # rejected. 07 Mục 2.3 gives `approval_state` to the Manager,
                # and 06 Mục 5.4 makes acting on it the "vòng lặp chăm sóc tri
                # thức"; a machine pass may propose, never un-decide.
                if existing.approval_state is not ApprovalState.PENDING:
                    continue
                del self._relations[existing_id]
            self._relations[relation.relation_id] = relation

    @staticmethod
    def _relation_key(relation: Relation) -> tuple[str, str, object]:
        return (relation.from_document_id, relation.to_document_id, relation.relation_type)

    def _check_version_chain(self, document: Document) -> None:
        for stored in self._documents.values():
            if stored.document_id == document.document_id:
                continue
            if (
                stored.version_chain_id == document.version_chain_id
                and stored.version_ordinal == document.version_ordinal
            ):
                raise VersionChainOrdinalConflictError(
                    f"document {stored.document_id!r} already holds ordinal "
                    f"{document.version_ordinal} of chain "
                    f"{document.version_chain_id!r} — "
                    f"{DOCUMENT_VERSION_CHAIN_ORDINAL_CONSTRAINT} refuses the second one"
                )

    def _check_active_fingerprint(self, document: Document) -> None:
        if document.removed_as_wrong:
            return  # outside the partial index's WHERE clause
        for stored in self._documents.values():
            if stored.document_id == document.document_id or stored.removed_as_wrong:
                continue
            if (
                stored.space_id == document.space_id
                and stored.content_fingerprint == document.content_fingerprint
            ):
                raise DuplicateActiveFingerprintError(
                    f"active document {stored.document_id!r} already holds this "
                    f"content_fingerprint in space {document.space_id!r} — "
                    f"{DOCUMENT_ACTIVE_FINGERPRINT_INDEX} refuses the second one"
                )

    # -- FingerprintIndex (T2.1) ---------------------------------------- #

    def find_by_fingerprint(self, content_fingerprint: str) -> list[Document]:
        return [
            document
            for document in self._documents.values()
            if document.content_fingerprint == content_fingerprint
        ]

    def register(self, document: Document) -> None:
        self.write_document_and_relations(document=document, relations=[])

    # -- SpaceDocumentSource (T2.6) ------------------------------------- #

    def documents_in(self, space_ids: frozenset[str]) -> list[Document]:
        return [
            document
            for document in self._documents.values()
            if document.space_id in space_ids
        ]

    # -- Inspection ------------------------------------------------------ #

    def relations(self) -> list[Relation]:
        return list(self._relations.values())

    def documents(self) -> list[Document]:
        return list(self._documents.values())


class InMemoryVectorStoreWriter:
    """`VectorStoreWriter` in a dict — the Qdrant stand-in.

    Refuses a chunk with no vector for the same reason `write_to_qdrant` does
    (`ChunkChuaCoVector`): writing an empty vector is worse than not writing.
    """

    def __init__(self) -> None:
        self.points: dict[str, Chunk] = {}

    def write(self, chunks: list[Chunk]) -> None:
        missing = [chunk.chunk_id for chunk in chunks if not chunk.embedding]
        if missing:
            raise AssertionError(
                f"{len(missing)} chunks still carry embedding=[] — GĐ6 did not run "
                f"over them: {missing}"
            )
        for chunk in chunks:
            self.points[chunk.chunk_id] = chunk

    def count(self) -> int:
        return len(self.points)
