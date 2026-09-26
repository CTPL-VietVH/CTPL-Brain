"""The background half of `POST /v1/ingestions` — one job, start to terminal
state (docs/10 §4.1, §4.2).

`POST` fetches the file, writes a `QUEUED` row and answers `202`. This module
is what happens after: GĐ2 on the staged file, then the shared head
(`pre_approval_runner.prepare_ingestion` — GĐ1, GĐ5, GĐ3), then ONE of two
destinations, and finally a terminal row Backend can read through `GET
/v1/ingestions/{id}`.

──────────────────────────────────────────────────────────────────────────
Both destinations, one write path
──────────────────────────────────────────────────────────────────────────

    prepare_ingestion(...)
        │
        ├── requires_pre_approval ──►  buffer.put(entry)        → awaiting_approval
        │                                  … Manager approves later:
        │                                  promote_approved_ingestion(entry)
        │
        └── otherwise ─────────────►  promote_approved_ingestion(entry) → active

`promote_approved_ingestion` is the ONLY function in this repo that writes a
document into the shared stores, and both branches reach it — the ordinary
one now, the pre-approval one after a Manager acts. PO chốt 24/9/2026, and
`tests/api/` asserts it by watching the call rather than by trusting this
comment.

The last step of a promote is `buffer.discard(document_id)`. On the ordinary
path there is nothing in the buffer, so it returns `False`. That is not a
failure and is not special-cased: `discard` is documented as *"calling it
twice is not an error"*, and a branch here to avoid it would be a second
place where the two paths differ.

──────────────────────────────────────────────────────────────────────────
The staged file dies with GĐ2 — and what that costs
──────────────────────────────────────────────────────────────────────────

docs/10 §4.1: *"Bản tạm bị xoá ngay sau khi đọc xong chữ, kể cả khi từ chối
giữa chừng."* So the delete is in a `finally` around GĐ2 alone, not around
the whole job, and the row's `staged_filename` is cleared in the same breath.

⚠️ The consequence is deliberate and is NOT hidden: a process killed AFTER
GĐ2 but before the job reached a terminal state leaves a row that will be
requeued (see `IngestionRecordStore.recover_orphans`) with no file to read.
That job cannot be re-run — the presigned URL it came from is short-lived by
design and AI never stored it. It therefore ends `failed` with a message that
says exactly this, and Backend can submit again. The alternative — keeping
customer document bytes on disk until the whole pipeline finishes, so a rare
crash could be resumed — is the one docs/10 §2 rules out (*"Không lưu file
gốc"*), and it would hold the file through GĐ6, the slowest stage.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from ingestion.chunking import KhoiVuotTranKhongTheChia, KhongDungDuocCauTruc
from ingestion.deletion import DeletableProfileStore, VectorStoreDeleter
from ingestion.extraction import DinhDangKhongNhan, ExtractionResult, KhongDocDuocLopChu, extract_file
from ingestion.intake import BanMoiKhacSpace, FingerprintIndex, VanTayNoiDungRong
from ingestion.ingestion_record_store import IngestionRecordStore
from ingestion.labeling import extract_document_number, extract_title
from ingestion.pre_approval_buffer import PreApprovalBuffer
from ingestion.pre_approval_runner import PreApprovalRequest, prepare_ingestion
from ingestion.promotion import (
    SharedProfileStore,
    VectorStoreWriter,
    promote_approved_ingestion,
)
from ingestion.relations_scan import SpaceDocumentSource, SpaceScanScope
from ingestion.space_registry import (
    SpaceNotAcceptingDocuments,
    SpaceNotRegistered,
    SpaceRegistry,
)
from ingestion.staging import StagingArea
from ingestion.vectorization import BgeM3Like, ChunkVuotTranNguCanh, EmbeddingOutOfMemory
from schema.document import Document
from schema.ingestion_record import (
    IngestionFailureCode,
    IngestionRecord,
    IngestionStatus,
)

__all__ = ["IngestionPipeline", "StagedFileMissing"]

logger = logging.getLogger(__name__)


class StagedFileMissing(Exception):
    """The row points at a staged file that is not on disk.

    Raised, not swallowed: the two ways to get here are a job requeued after
    a crash that had already consumed its file (see the module docstring) and
    a staging directory somebody emptied by hand. Both are worth a `failed`
    row that names the file, and neither may be read as "an empty document".
    """


#: GĐ2 refusals → `UNSUPPORTED_FORMAT` (docs/10 §3.5: *"Không thuộc 4 định
#: dạng v1, **hoặc PDF chỉ có ảnh quét**"* — the spec itself puts both behind
#: one code).
_UNSUPPORTED_FORMAT_ERRORS = (DinhDangKhongNhan, KhongDocDuocLopChu)

#: The three refusals PO chốt 24/9/2026 (escalation E5) to be ONE code,
#: `DOCUMENT_NOT_STRUCTURABLE`: GĐ3 could not cut the document, GĐ3 hit a
#: block it may not split further, GĐ6 found a chunk over the model's context
#: ceiling. One code because they are one fact for Backend — the file was
#: readable and could still not be turned into searchable chunks — and
#: because none of the three is fixed by Backend sending something different.
#: `InternalBlockHasNoOwnText` is deliberately NOT in this tuple. It is a
#: tripwire for a tree shape nobody has produced yet (chunking.py docstring:
#: "never fires" on the 36-document corpus, smallest own-text region found is
#: 10 characters) — an unforeseen system bug, not a document the pipeline
#: knows how to refuse. Falling through to the generic handler below turns it
#: into `INTERNAL_ERROR` so a developer sees it, instead of quietly reporting
#: `DOCUMENT_NOT_STRUCTURABLE` to Backend for something no format change on
#: their side could ever fix.
_NOT_STRUCTURABLE_ERRORS = (
    KhongDungDuocCauTruc,
    KhoiVuotTranKhongTheChia,
    ChunkVuotTranNguCanh,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class IngestionPipeline:
    """Everything one ingestion job needs, assembled once by the composition
    root.

    Every store is a Protocol from this package, so the whole pipeline runs
    against the in-memory pair in tests and against live PostgreSQL + Qdrant
    in a deployment, unchanged. ⛔ Nothing here is constructed by this class:
    a stand-in built inside would be a deployment quietly serving out of a
    dict (the rule `api/app.py` states for itself).

    The six numbers are read from `config/ingestion.yaml` by the composition
    root and passed down — none has a default here (CLAUDE.md Mục 4 quy tắc
    2). `scan_time_budget` is IN MINUTES, the unit that config key carries.
    """

    records: IngestionRecordStore
    staging: StagingArea
    space_registry: SpaceRegistry
    #: In a deployment `profile_store` and `fingerprint_index` are ONE object
    #: — both are the `document` table. Two fields because they are two
    #: different sets of promises, the same reason `IngestionServices` keeps
    #: `document_source` and `profile_store` apart.
    profile_store: SharedProfileStore
    fingerprint_index: FingerprintIndex
    buffer: PreApprovalBuffer
    vector_writer: VectorStoreWriter
    #: ⭐ The SAME two stores again, in their delete-side roles — VEC-1. A
    #: promote whose Qdrant write fails has to take its own PostgreSQL write
    #: back (`promotion.py`'s module docstring says why that is not optional),
    #: and it cannot do that through the write-side ports above. In a
    #: deployment `profile_deleter is profile_store`, exactly as
    #: `fingerprint_index is profile_store` already is.
    profile_deleter: DeletableProfileStore
    vector_deleter: VectorStoreDeleter
    embedding_model: BgeM3Like
    embedding_batch_size: int
    relation_scope: SpaceScanScope
    relation_document_source: SpaceDocumentSource
    chunk_length_cap: int
    saturation_epsilon: float
    saturation_rounds: int
    scan_pair_budget: int
    scan_time_budget: float
    clock: Callable[[], datetime]
    monotonic: Callable[[], float] = time.monotonic

    # -- startup ---------------------------------------------------------- #

    def recover(self) -> list[IngestionRecord]:
        """What a process does FIRST, before serving anything.

        Three sweeps, in this order and not another:

        1. every `RUNNING` row back to `QUEUED` — PO chốt 24/9/2026, and
           `IngestionRecordStore` explains why no timeout is involved and
           what it costs (one replica only);
        2. delete every staged file no unfinished row still names;
        3. VEC-2 — finish the cleanup of promotes that died half-written
           (`sweep_promotion_orphans`).

        The first two orders matter: sweeping files first would delete the
        inputs of the jobs step 1 is about to revive, because a `RUNNING` row
        is not yet in `unfinished()`'s answer… and in fact it is — but
        relying on that would make the sweep depend on a detail of the other
        step. Doing the requeue first makes the `keep` list correct by
        construction.

        Step 3 comes LAST for a different reason: step 1 has just moved every
        `RUNNING` row to `QUEUED`, so by the time the orphan sweep runs, no
        row it could look at is one a live job is holding. It is also the
        only step that may touch the shared stores, and running it after the
        cheap local work means a store that is down cannot stop the rest.
        """
        recovered = self.records.recover_orphans(now=self.clock())
        if recovered:
            logger.warning(
                "Requeued %d ingestion job(s) left RUNNING by a previous process: "
                "%s. This is only correct while exactly ONE worker runs.",
                len(recovered),
                [record.ingestion_id for record in recovered],
            )
        keep = {
            record.staged_filename
            for record in self.records.unfinished()
            if record.staged_filename is not None
        }
        removed = self.staging.collect_garbage(keep=keep)
        if removed:
            logger.warning(
                "Deleted %d orphaned staged file(s): %s", len(removed), removed
            )
        self.sweep_promotion_orphans()
        return recovered

    def sweep_promotion_orphans(self) -> list[str]:
        """VEC-2 — delete the profiles that a half-finished promote left in
        PostgreSQL, so the same file can be uploaded again.

        Returns the `document_id`s actually cleaned, for the caller's log and
        for tests. An empty list is the normal answer.

        ──────────────────────────────────────────────────────────────────
        The state this exists for
        ──────────────────────────────────────────────────────────────────

        `promote_approved_ingestion` writes PostgreSQL (step 4) and then
        Qdrant (step 5), and already undoes step 4 itself when step 5 fails
        (VEC-1). Two things that undo cannot cover:

        * the undo's OWN first step fails — Qdrant is down, so the points
          cannot be deleted, and `promotion.py` then deliberately leaves the
          profile in place rather than create the dangling pointer of điều
          cấm #17;
        * the process dies between step 4 and step 5, so no undo runs at all.
          That row comes back as `RUNNING`, which this sweep deliberately
          will not touch; it reaches `FAILED` when the requeued job finds
          its staged file gone (`_read_out`), and the sweep at the NEXT
          start is the one that cleans it.

        Either way PostgreSQL holds a profile with no vectors. Nothing can
        find it — and `intake.decide_intake` answers `duplicate` for the next
        upload of the same bytes, because the fingerprint index reads that
        very table. The file becomes un-ingestable, silently. That is the
        whole reason this sweep exists.

        ──────────────────────────────────────────────────────────────────
        Three gates, and what each one prevents
        ──────────────────────────────────────────────────────────────────

        1. `promotion_orphan_candidates()` — terminal `FAILED` **and** a
           non-null `promoting_document_id` (see `PROMOTION_ORPHAN_STATUS`).
        2. the profile must still BE there. A row whose undo already worked
           is not work; probing first also means a second run of this sweep
           finds nothing to do even if step 3 below never ran.
        3. S6 order — vectors first, then profile + relations in one
           transaction. Reversing it would produce findable chunks pointing
           at a profile that is gone.

        ⛔ **No `deletion_log` line**, the same rule VEC-1 fixed for the
        inline undo: that log records a permanent deletion a PERSON ordered
        (06 Mục 5.6). This is the system finishing its own interrupted write
        of a document no user ever saw.

        ⚠️ **A failure here never stops startup.** The case is logged with
        the ids that identify it and the row keeps its pointer, so the next
        start tries again — which is also why the pointer is only cleared
        AFTER both deletes have returned.
        """
        swept: list[str] = []
        try:
            candidates = self.records.promotion_orphan_candidates()
        except Exception:
            logger.exception(
                "Could not read the promotion-orphan worklist; skipping the sweep. "
                "Any orphaned profile stays until the next start — it blocks "
                "re-uploading that one file, and nothing else."
            )
            return swept

        for record in candidates:
            document_id = record.promoting_document_id
            if document_id is None:  # pragma: no cover - the store filtered these
                continue
            try:
                if self.profile_store.get_document(document_id) is None:
                    # The undo already ran, or this job never got past step 4.
                    # Nothing to delete, so nothing to mark: leaving the
                    # pointer costs one indexed lookup at the next start and
                    # keeps the trace of which document the failed job made.
                    continue

                logger.warning(
                    "Ingestion %s failed after writing document %s to PostgreSQL but "
                    "before its vectors were complete. Finishing the cleanup now "
                    "(vector store first, then profile + relations).",
                    record.ingestion_id,
                    document_id,
                )
                points_deleted = self.vector_deleter.delete_document_points(document_id)
                counts = self.profile_deleter.delete_document_and_relations(document_id)
            except Exception:
                logger.exception(
                    "⚠️ Promotion-orphan sweep FAILED for ingestion %s / document %s. "
                    "The row keeps its promoting_document_id, so the next startup "
                    "tries again; until then, re-uploading that one file is refused "
                    "as a duplicate.",
                    record.ingestion_id,
                    document_id,
                )
                continue

            try:
                self.records.update(
                    dataclasses.replace(
                        record, promoting_document_id=None, updated_at=self.clock()
                    )
                )
            except Exception:
                # Both stores are already clean; only the marker survived.
                # Not an error worth failing over — the next sweep finds no
                # profile and does nothing.
                logger.exception(
                    "Cleaned document %s but could not clear promoting_document_id on "
                    "ingestion %s. Harmless: the next sweep sees no profile and stops.",
                    document_id,
                    record.ingestion_id,
                )

            logger.warning(
                "Promotion orphan cleaned: ingestion %s / document %s — %d vector "
                "point(s), %d profile row(s), %d relation(s) removed. That file can "
                "be submitted again.",
                record.ingestion_id,
                document_id,
                points_deleted,
                counts.profile_rows_deleted,
                counts.relations_deleted,
            )
            swept.append(document_id)

        return swept

    # -- the queue -------------------------------------------------------- #

    def run_next(self) -> IngestionRecord | None:
        """Claim one job and carry it to a terminal state. `None` if idle."""
        claimed = self.records.claim_next(now=self.clock())
        if claimed is None:
            return None
        return self._execute(claimed)

    def drain(self) -> int:
        """Run until the queue is empty. Returns how many jobs ran.

        This is the unit the background worker submits. It is also what a
        test calls directly, so every case below runs without a thread.
        """
        ran = 0
        while self.run_next() is not None:
            ran += 1
        return ran

    # -- one job ---------------------------------------------------------- #

    def _execute(self, record: IngestionRecord) -> IngestionRecord:
        """Never raises. A job that fails ends as a ROW, not an exception.

        The worker thread is shared (one worker, v1), so an exception escaping
        here would kill every later job as well. Every failure path below ends
        in a terminal row, which is the only thing Backend can see.
        """
        try:
            extraction = self._read_out(record)
        except _Terminal as terminal:
            return self._finish(record, **terminal.fields)
        except Exception:  # pragma: no cover - defensive, logged and reported
            logger.exception("Ingestion %s failed while reading the file", record.ingestion_id)
            return self._finish(
                record, status=IngestionStatus.FAILED, code=IngestionFailureCode.INTERNAL_ERROR
            )

        try:
            return self._ingest(record, extraction)
        except _Terminal as terminal:
            return self._finish(record, **terminal.fields)
        except Exception:
            logger.exception("Ingestion %s failed after the file was read", record.ingestion_id)
            return self._finish(
                record, status=IngestionStatus.FAILED, code=IngestionFailureCode.INTERNAL_ERROR
            )

    def _read_out(self, record: IngestionRecord) -> ExtractionResult:
        """GĐ2, and the death of the staged file (docs/10 §4.1)."""
        if record.staged_filename is None:
            raise _Terminal(
                status=IngestionStatus.FAILED,
                code=IngestionFailureCode.INTERNAL_ERROR,
                log=(
                    f"ingestion {record.ingestion_id!r} has no staged file to read. "
                    f"A job requeued after a crash that had already consumed its file "
                    f"cannot be re-run: the presigned URL it came from is short-lived "
                    f"and is never stored (docs/10 §4.1). Backend must submit again."
                ),
            )

        path = self.staging.path_for(record.staged_filename)
        try:
            if not path.is_file():
                raise StagedFileMissing(
                    f"staged file {path} for ingestion {record.ingestion_id!r} is gone"
                )
            return extract_file(path)
        except _UNSUPPORTED_FORMAT_ERRORS as exc:
            raise _Terminal(
                status=IngestionStatus.REJECTED,
                code=IngestionFailureCode.UNSUPPORTED_FORMAT,
                log=str(exc),
            ) from exc
        except StagedFileMissing as exc:
            raise _Terminal(
                status=IngestionStatus.FAILED,
                code=IngestionFailureCode.INTERNAL_ERROR,
                log=str(exc),
            ) from exc
        finally:
            # ⭐ Unconditional, and before anything downstream runs: *"Bản tạm
            # bị xoá ngay sau khi đọc xong chữ, kể cả khi từ chối giữa chừng"*
            # (docs/10 §4.1). The row is updated in the same breath so a later
            # staging sweep can tell an in-use file from a leaked one.
            self.staging.discard(record.staged_filename)
            self.records.update(
                dataclasses.replace(
                    record, staged_filename=None, updated_at=self.clock()
                )
            )

    def _ingest(
        self, record: IngestionRecord, extraction: ExtractionResult
    ) -> IngestionRecord:
        """GĐ1 → GĐ5 → GĐ3, then one of the two destinations."""
        request = PreApprovalRequest(
            # ⭐ `path=None`: the staged file was deleted the moment GĐ2
            # finished, so there is nothing left to point at. GĐ2's result
            # travels as `extraction=` instead — see `prepare_ingestion`.
            path=None,
            # ⭐ `document_id = ingestion_id` is a DELIBERATE choice, not the
            # two identifiers collapsing into one (docs/10 §4.2 keeps them
            # apart, and `ingestion_record` stores both). The row's
            # `document_id` column stays NULL unless this job ends `active`,
            # so a rejected submission never names a document. Minting the
            # value here, from a value that is already unique, avoids a
            # second id generator on the job path.
            document_id=record.ingestion_id,
            space_id=record.space_id,
            tenant_id=record.tenant_id,
            # ⛔ NOT the uploaded filename (docs/10 §4.2: *"không lấy tên file
            # giả làm tên văn bản"*). GĐ5 (`ingestion.labeling`, task T2.4b)
            # suggests both from the front matter of `extracted_text`; a
            # human still confirms or corrects through §4.3. Neither
            # extractor guesses when it is not confident — it returns "",
            # exactly the same "nobody has suggested one yet" value the
            # columns held before T2.4b (07 Mục 2.1: NOT NULL, so "" rather
            # than `None`), and `_suggestions` in `api/ingestion_routes.py`
            # already projects "" to `null` either way.
            title=extract_title(extraction.extracted_text).title,
            doc_number=extract_document_number(extraction.extracted_text).doc_number,
            ingested_at=record.submitted_at,
            declared_previous_version=self._resolve_declared_previous(record),
        )

        try:
            prepared = prepare_ingestion(
                request,
                extraction=extraction,
                fingerprint_index=self.fingerprint_index,
                buffer=self.buffer,
                space_registry=self.space_registry,
                chunk_length_cap=self.chunk_length_cap,
            )
        except (SpaceNotRegistered, SpaceNotAcceptingDocuments) as exc:
            # The Space went away between the submission and this job. Not a
            # server failure: Backend asked for a Space that is on its way
            # out, and §4.0 step 1 says writes into it stop from that moment.
            raise _Terminal(
                status=IngestionStatus.REJECTED,
                code=IngestionFailureCode.OBJECT_NOT_IN_SPACE,
                log=str(exc),
            ) from exc
        except BanMoiKhacSpace as exc:
            raise _Terminal(
                status=IngestionStatus.REJECTED,
                code=IngestionFailureCode.NEW_VERSION_OTHER_SPACE,
                log=str(exc),
            ) from exc
        except VanTayNoiDungRong as exc:
            raise _Terminal(
                status=IngestionStatus.REJECTED,
                code=IngestionFailureCode.UNSUPPORTED_FORMAT,
                log=str(exc),
            ) from exc
        except _NOT_STRUCTURABLE_ERRORS as exc:
            raise _Terminal(
                status=IngestionStatus.REJECTED,
                code=IngestionFailureCode.DOCUMENT_NOT_STRUCTURABLE,
                log=str(exc),
            ) from exc

        if prepared.duplicate is not None:
            # docs/10 §4.2 — ONE `duplicate` status on the wire whether the
            # twin sits in the shared store or in the pre-approval buffer.
            # Which of the two it was stays here, in AI's own log.
            logger.info(
                "Ingestion %s is a duplicate of %s, found in %s",
                record.ingestion_id,
                prepared.duplicate.document_id,
                prepared.duplicate.found_in.value,
            )
            return self._finish(
                record,
                status=IngestionStatus.DUPLICATE,
                existing_document_id=prepared.duplicate.document_id,
            )

        entry = prepared.buffered
        if entry is None:  # pragma: no cover - prepare_ingestion's invariant
            raise AssertionError(
                "prepare_ingestion returned neither a prepared entry nor a duplicate"
            )

        if record.requires_pre_approval:
            # 06 Mục 5.2 GĐ1 — stop here. Nothing of this document is in any
            # shared store, and that is enforced by WHERE the rows are, not by
            # a filter (CLAUDE.md điều cấm #20).
            self.buffer.put(entry)
            return self._finish(record, status=IngestionStatus.AWAITING_APPROVAL)

        # ⭐ VEC-2 — the pointer goes down BEFORE the promote, and it is
        # committed by the time the next line runs (`IngestionRecordStore`
        # writes are not held open). From here until this job reaches a
        # terminal state, the row knows which document the promote is about to
        # create; if the process dies in the middle of the write, that pointer
        # is the only thing left connecting the failed job to the profile it
        # created, and `sweep_promotion_orphans` has nothing to work from
        # without it.
        #
        # `entry.document.document_id` and not the promote's return value, for
        # the same reason: a value read afterwards cannot survive a crash
        # before "afterwards". The promote never changes the id — it replaces
        # `version_ordinal` and `relations_scan_state` and nothing else — so
        # this is the same document_id step 4 writes.
        #
        # ⚠️ Re-read before writing, for the reason `_finish` states for
        # itself: `_read_out` cleared `staged_filename` in the STORE, and the
        # `record` this method was handed still carries it. Writing that copy
        # back resurrects the name of a file that was already deleted — which
        # is exactly what `tests/api/test_j` caught the first time this update
        # was written from the stale value.
        current = self.records.get(record.ingestion_id) or record
        self.records.update(
            dataclasses.replace(
                current,
                promoting_document_id=entry.document.document_id,
                updated_at=self.clock(),
            )
        )

        try:
            promoted = promote_approved_ingestion(
                entry,
                profile_store=self.profile_store,
                profile_deleter=self.profile_deleter,
                # The ordinary path holds nothing in the buffer, so the
                # `discard` at the end of the promote answers False. See the
                # module docstring: not special-cased on purpose.
                buffer=self.buffer,
                vector_writer=self.vector_writer,
                vector_deleter=self.vector_deleter,
                embedding_model=self.embedding_model,
                embedding_batch_size=self.embedding_batch_size,
                relation_scope=self.relation_scope,
                relation_document_source=self.relation_document_source,
                saturation_epsilon=self.saturation_epsilon,
                saturation_rounds=self.saturation_rounds,
                scan_pair_budget=self.scan_pair_budget,
                scan_time_budget=self.scan_time_budget,
                clock=self.monotonic,
            )
        except EmbeddingOutOfMemory as exc:
            # VEC-3 — a device-memory ceiling, not a document-structure
            # problem (DOCUMENT_NOT_STRUCTURABLE would misname the cause)
            # and not an unforeseen bug (INTERNAL_ERROR would too). FAILED,
            # not REJECTED: the submission itself was not wrong.
            raise _Terminal(
                status=IngestionStatus.FAILED,
                code=IngestionFailureCode.EMBEDDING_OUT_OF_MEMORY,
                log=str(exc),
            ) from exc
        except _NOT_STRUCTURABLE_ERRORS as exc:
            # GĐ6's context-ceiling refusal lands here — the same code as
            # GĐ3's, per PO's E5 decision.
            raise _Terminal(
                status=IngestionStatus.REJECTED,
                code=IngestionFailureCode.DOCUMENT_NOT_STRUCTURABLE,
                log=str(exc),
            ) from exc

        return self._finish(
            record,
            status=IngestionStatus.ACTIVE,
            document_id=promoted.document.document_id,
        )

    def _resolve_declared_previous(self, record: IngestionRecord) -> Document | None:
        """Look the declared *"bản mới của X"* up again, at job time.

        ⛔ A declaration that cannot be resolved is a REFUSAL, never silence.
        PO chốt 24/9/2026 (K11): *"TUYỆT ĐỐI KHÔNG được im lặng coi như tài
        liệu hoàn toàn mới khi khai báo mà không tra được."* Falling through
        to `declared_previous_version=None` would start a fresh version chain
        for a document the uploader said is version N+1 of something — and
        the answer would look like a success.

        The submission endpoint already checked this; it is checked again
        because the document may have been permanently deleted in between.
        """
        if record.declared_previous_document_id is None:
            return None
        previous = self.profile_store.get_document(record.declared_previous_document_id)
        if previous is None or previous.space_id != record.space_id:
            raise _Terminal(
                status=IngestionStatus.REJECTED,
                code=IngestionFailureCode.OBJECT_NOT_IN_SPACE,
                log=(
                    f"ingestion {record.ingestion_id!r} declares "
                    f"declared_previous_document_id="
                    f"{record.declared_previous_document_id!r}, which is not in space "
                    f"{record.space_id!r} any more. Refusing — a declaration that "
                    f"cannot be resolved is never treated as a brand-new document "
                    f"(docs/10 §4.1)."
                ),
            )
        return previous

    # -- writing the terminal row ----------------------------------------- #

    def _finish(
        self,
        record: IngestionRecord,
        *,
        status: IngestionStatus,
        code: IngestionFailureCode | None = None,
        document_id: str | None = None,
        existing_document_id: str | None = None,
        log: str | None = None,
    ) -> IngestionRecord:
        if log is not None:
            logger.warning("Ingestion %s → %s: %s", record.ingestion_id, status.value, log)

        # Re-read: `_read_out` already cleared `staged_filename`, and writing
        # the stale copy this method was handed would resurrect a file name
        # whose file is gone.
        current = self.records.get(record.ingestion_id) or record
        terminal = dataclasses.replace(
            current,
            status=status,
            code=code,
            document_id=document_id,
            existing_document_id=existing_document_id,
            updated_at=self.clock(),
        )
        self.records.update(terminal)
        return terminal


class _Terminal(Exception):
    """Internal control flow: *this job ends, in this state, for this reason.*

    A private exception rather than a return value because the decision is
    made deep inside three nested stages, and every one of them would
    otherwise have to thread it back out by hand — which is how one of them
    ends up forgetting and returning success instead.

    ⛔ Never escapes this module: `_execute` catches it and turns it into a
    row. Nothing outside may catch it, and nothing outside may raise it.
    """

    def __init__(self, **fields: object) -> None:
        super().__init__(fields.get("log") or fields.get("status"))
        self.fields = fields
