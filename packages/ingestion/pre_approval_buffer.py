"""T2.7, part 1/2 — the pre-approval working area: a buffer that is NOT a
shared store (06 Mục 5.2 GĐ1, 08 T2.7, 09 Mục 4.2).

In a private (`riêng`) Space the stage chain runs GĐ2, GĐ3 and GĐ5 and then
**stops before GĐ6 and GĐ7**; the result waits for a Manager. 06 Mục 5.2
GĐ1: *"Kết quả nằm trong vùng làm việc riêng của Ingestion, chưa ghi vào ba
kho dùng chung. Manager duyệt xong mới chạy nốt GĐ6, GĐ7 và ghi ra."* This
module is that working area's contract; `pre_approval_runner.py` is the
chain that fills it.

--------------------------------------------------------------------------
Why a separate TABLE, and why that is the whole mechanism
--------------------------------------------------------------------------

08 T2.7 states the trap in one line: *"Với hai kho vật lý (T0.1),
PostgreSQL CŨNG LÀ KHO DÙNG CHUNG. Ghi hồ sơ tài liệu vào đó rồi chỉ hoãn
nạp vector là đã vi phạm bất biến."* That is CLAUDE.md điều cấm #20 — reusing
the official `document` table and marking the row "chờ duyệt" is the tempting
version and the forbidden one, because it makes pre-approval depend on a
FILTER running correctly instead of on structure, and it grows the third hard
filter NT4 forbids.

Storage plan LOCKED 22/9/2026: a dedicated pair of tables inside the
PostgreSQL that already exists. No third piece of infrastructure — v1 has
exactly TWO physical stores, Qdrant + PostgreSQL (07 line 63, CLAUDE.md Mục
5), so a Redis or an object store for "just the buffer" would break a CHỐT
decision to solve a problem two tables already solve.

⭐ **The chunk table has no `embedding` column, deliberately.** GĐ6 has not
run for anything in here, and a table with nowhere to put a vector cannot be
half-promoted by a caller who forgets. Same reasoning the design applies to
itself: *"tiền kiểm được chặn BẰNG CẤU TRÚC chứ không bằng một bộ lọc phải
chạy đúng"* (06 Mục 5.2 GĐ1).

--------------------------------------------------------------------------
Why the buffer holds a real `Document`, not a parallel dataclass
--------------------------------------------------------------------------

A `BufferedDocument` mirroring sixteen field names would re-declare them
outside `packages/schema/`, which CLAUDE.md Mục 6 forbids in as many words:
*"Tên trường định nghĩa đúng một lần trong `packages/schema/`; không service
nào tự khai báo lại"* — that is the `doc_profile_code`/`profile_code` bug the
rule exists to stop, and two spellings of one field silently return nothing.

So an entry carries a `schema.document.Document` and `schema.chunk.Chunk`
values. What keeps them out of the shared stores is WHERE THEY ARE WRITTEN —
these two tables — not what Python type they happen to have. The invariant is
structural, exactly as 06 Mục 5.2 GĐ1 argues it must be.

The official-lifecycle fields of `Document` (`removed_as_wrong`,
`superseded`, `relations_scan_state` and their trace columns) have no column
here on purpose: none of them means anything for a document that is not yet
in the shared store, and GĐ7 — which is what would set a scan state — has not
run.

--------------------------------------------------------------------------
Why a Protocol instead of a psycopg call
--------------------------------------------------------------------------

Same shape as `FingerprintIndex` (T2.1) and `SpaceScanScope` /
`SpaceDocumentSource` (T2.6): this module names the reads and writes the
pre-approval path needs, exports the DDL that backs them, and leaves the real
connection to the assembling layer. `InMemoryPreApprovalBuffer` below enforces
every constraint the DDL enforces, so the T2.7 acceptance test runs without a
live PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from schema.chunk import Chunk
from schema.document import Document

__all__ = [
    "BufferedIngestion",
    "ChunkDocumentMismatchError",
    "DuplicatePreApprovalEntryError",
    "EmbeddedChunkInPreApprovalBufferError",
    "InMemoryPreApprovalBuffer",
    "PRE_APPROVAL_CHUNK_TABLE",
    "PRE_APPROVAL_CHUNK_TABLE_DDL",
    "PRE_APPROVAL_DOCUMENT_TABLE",
    "PRE_APPROVAL_DOCUMENT_TABLE_DDL",
    "PreApprovalBuffer",
    "PreApprovalBufferError",
]


# --------------------------------------------------------------------------- #
# Tables — names and DDL exported as constants so real code and tests share one
# spelling (same rule as `embedding_registry.py`: a test must never re-type the
# SQL it is checking).
# --------------------------------------------------------------------------- #

#: The document-to-be. NOT the official profile table — nothing in Retrieval
#: may ever read this, and nothing here is visible to any query path.
PRE_APPROVAL_DOCUMENT_TABLE = "ingestion_pre_approval_document"

#: The chunks already cut by GĐ3, waiting for GĐ6. No vector column: see the
#: module docstring.
PRE_APPROVAL_CHUNK_TABLE = "ingestion_pre_approval_chunk"

PRE_APPROVAL_DOCUMENT_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {PRE_APPROVAL_DOCUMENT_TABLE} (
    document_id           text        NOT NULL PRIMARY KEY,
    space_id              text        NOT NULL,
    tenant_id             text        NOT NULL,
    title                 text        NOT NULL,
    doc_number            text        NOT NULL,
    issued_date           date        NOT NULL,
    issued_date_source    text        NOT NULL,
    effective_date        date        NOT NULL,
    effective_date_source text        NOT NULL,
    ingested_at           timestamptz NOT NULL,
    source_format         text        NOT NULL,
    content_fingerprint   text        NOT NULL,
    extracted_text        text        NOT NULL,
    version_chain_id      text        NOT NULL,
    version_ordinal       integer     NOT NULL,
    version_declared_by   text,
    category_labels       text[]      NOT NULL,
    subject_entities      text[]      NOT NULL,
    buffered_at           timestamptz NOT NULL,
    UNIQUE (space_id, content_fingerprint)
)
"""

PRE_APPROVAL_CHUNK_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {PRE_APPROVAL_CHUNK_TABLE} (
    chunk_id        text    NOT NULL PRIMARY KEY,
    document_id     text    NOT NULL
        REFERENCES {PRE_APPROVAL_DOCUMENT_TABLE} (document_id) ON DELETE CASCADE,
    space_id        text    NOT NULL,
    tenant_id       text    NOT NULL,
    structure_path  text[]  NOT NULL,
    span_start      integer NOT NULL,
    span_end        integer NOT NULL,
    parent_chunk_id text,
    category_labels text[]  NOT NULL,
    chunk_ordinal   integer NOT NULL,
    UNIQUE (document_id, chunk_ordinal)
)
"""


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class PreApprovalBufferError(Exception):
    """Base for every rejection the buffer makes."""


class EmbeddedChunkInPreApprovalBufferError(PreApprovalBufferError):
    """A chunk arrived carrying a vector — GĐ6 ran on the pre-approval path.

    The chain must stop before GĐ6 (06 Mục 5.2 GĐ1), so a non-empty
    `Chunk.embedding` here means the stop was crossed. The real table has no
    column to hold it; this is the same refusal at the Python boundary, so the
    mistake surfaces in a test rather than at the first live INSERT.
    """


class DuplicatePreApprovalEntryError(PreApprovalBufferError):
    """A second entry for the same `(space_id, content_fingerprint)`.

    The storage-level UNIQUE of the same name is what 08's 21/9 update asks
    for — checking only in application code loses the race when two uploads
    of one file land together. Mirrored here so the in-memory buffer refuses
    what PostgreSQL would refuse.
    """


class ChunkDocumentMismatchError(PreApprovalBufferError):
    """A chunk in the entry does not belong to the entry's document.

    The FK does this in PostgreSQL; without the check here, an entry could be
    buffered whose chunks point at another document entirely.
    """


# --------------------------------------------------------------------------- #
# The buffered entry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True, kw_only=True)
class BufferedIngestion:
    """Everything GĐ1→GĐ2→GĐ3→GĐ5 produced for one document, held whole.

    This is what must survive an indefinite wait: 09 Mục 4.2 on T2.7 —
    *"phải giữ được trạng thái trung gian (cây cấu trúc, danh sách mẩu, nhãn)
    qua một khoảng thời gian không xác định"*.

    The structure TREE is kept in the form everything downstream actually
    consumes — `chunks`, each carrying `structure_path`, `parent_chunk_id` and
    its span. Serialising `reader.structure.Node` alongside would be a second
    copy of facts already here, and two copies of one thing drift (the
    reasoning of điều cấm #3, which keeps chunk text in exactly one place).
    Re-cutting from scratch after approval is not a use case: the chunks are
    already cut, and re-reading the file is what a chunking FIX would need
    anyway.

    `document.relations_scan_state` is untouched schema default here and means
    nothing yet — GĐ7 has not run, and there is no column for it.
    """

    document: Document
    buffered_at: datetime
    chunks: list[Chunk] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# The Protocol
# --------------------------------------------------------------------------- #


class PreApprovalBuffer(Protocol):
    """Reads and writes the pre-approval working area.

    ⭐ **`put` is the transaction boundary.** One call writes the document row
    and ALL of its chunk rows, or writes nothing. A half-written entry — a
    document whose chunk list is truncated — would be indistinguishable after
    the fact from a document that genuinely cut to that many chunks, and the
    Manager would approve a partial reading of the file. A real implementation
    must therefore wrap the whole call in one PostgreSQL transaction, not one
    per row.

    Nothing here is reachable from Retrieval. These rows are not a shared
    store: no query path reads them, and promoting an entry (running GĐ6 +
    GĐ7 and writing the official profile) is a separate step that does not
    exist yet — see the T2.7 report's escalation.
    """

    def put(self, entry: BufferedIngestion) -> None: ...

    def get(self, document_id: str) -> BufferedIngestion | None: ...

    def find_in_space_by_fingerprint(
        self, *, space_id: str, content_fingerprint: str
    ) -> BufferedIngestion | None: ...

    def list_in_space(self, space_id: str) -> list[BufferedIngestion]: ...

    def discard(self, document_id: str) -> bool: ...


# --------------------------------------------------------------------------- #
# In-memory implementation — tests and single-process runs, NOT the real store
# (same disclaimer as `InMemoryFingerprintIndex`).
# --------------------------------------------------------------------------- #


class InMemoryPreApprovalBuffer:
    """`PreApprovalBuffer` in a dict, enforcing every constraint the DDL does.

    The point of enforcing them here is that T2.7's acceptance test — a
    pre-approval document must appear in NO shared store — can run with no
    live PostgreSQL, and a violation shows up as a red test rather than as an
    integrity error on someone's first real INSERT.
    """

    def __init__(self) -> None:
        self._by_document_id: dict[str, BufferedIngestion] = {}

    def put(self, entry: BufferedIngestion) -> None:
        """Validate EVERYTHING before mutating anything — a rejected entry must
        leave the buffer exactly as it was, which is what the real single
        transaction gives for free and what a check-as-you-go loop here would
        quietly lose."""
        document_id = entry.document.document_id

        for chunk in entry.chunks:
            if chunk.embedding:
                raise EmbeddedChunkInPreApprovalBufferError(
                    f"chunk {chunk.chunk_id!r} of document {document_id!r} carries a "
                    f"{len(chunk.embedding)}-dimension embedding; the pre-approval chain "
                    f"stops before GĐ6 and table {PRE_APPROVAL_CHUNK_TABLE!r} has no "
                    f"column to hold a vector (06 Mục 5.2 GĐ1)"
                )
            if chunk.document_id != document_id:
                raise ChunkDocumentMismatchError(
                    f"chunk {chunk.chunk_id!r} belongs to document "
                    f"{chunk.document_id!r}, not to {document_id!r}"
                )

        clash = self.find_in_space_by_fingerprint(
            space_id=entry.document.space_id,
            content_fingerprint=entry.document.content_fingerprint,
        )
        if clash is not None and clash.document.document_id != document_id:
            raise DuplicatePreApprovalEntryError(
                f"document {clash.document.document_id!r} is already buffered for space "
                f"{entry.document.space_id!r} with the same content_fingerprint; "
                f"UNIQUE (space_id, content_fingerprint) on "
                f"{PRE_APPROVAL_DOCUMENT_TABLE!r} refuses the second one"
            )

        self._by_document_id[document_id] = entry

    def get(self, document_id: str) -> BufferedIngestion | None:
        return self._by_document_id.get(document_id)

    def find_in_space_by_fingerprint(
        self, *, space_id: str, content_fingerprint: str
    ) -> BufferedIngestion | None:
        for entry in self._by_document_id.values():
            if (
                entry.document.space_id == space_id
                and entry.document.content_fingerprint == content_fingerprint
            ):
                return entry
        return None

    def list_in_space(self, space_id: str) -> list[BufferedIngestion]:
        return [
            entry
            for entry in self._by_document_id.values()
            if entry.document.space_id == space_id
        ]

    def discard(self, document_id: str) -> bool:
        """Drop an entry — the Manager rejected it, or it was superseded.

        Returns whether anything was there, so calling it twice is not an
        error (the shape T2.8 will need for permanent deletion). The real
        implementation gets the chunk rows removed by `ON DELETE CASCADE`.
        """
        return self._by_document_id.pop(document_id, None) is not None
