"""T2.8 (k) — 06 Mục 5.6: the log keeps the event, *"**Không giữ nội dung**"*.

The reason this is worth a test of its own: the log is the one store nothing
can delete from. Content that lands there survives the very deletion that put
it there — 06 Mục 9.2 calls that *"đúng kiểu cửa sau mà 9.3 đã phải bịt một
lần"*, and CLAUDE.md lists "nguyên văn ... trong nhật ký" among the forbidden
fields.
"""

from __future__ import annotations

import dataclasses

from ingestion.deletion import DeletionLogEntry, purge_document_permanently

FORBIDDEN_FIELDS = {
    "title",
    "doc_number",
    "extracted_text",
    "content_fingerprint",
    "category_labels",
    "subject_entities",
    "chunks",
    "excerpt",
    "body",
}


def test_the_entry_has_no_field_that_could_carry_content():
    names = {field.name for field in dataclasses.fields(DeletionLogEntry)}
    assert names & FORBIDDEN_FIELDS == set(), (
        f"DeletionLogEntry grew a content-bearing field: {names & FORBIDDEN_FIELDS}"
    )
    # And the four 06 Mục 5.6 asks for are all there.
    assert {"document_id", "deleted_by", "reason", "requested_at"} <= names


def test_no_word_of_the_deleted_document_survives_in_the_log(world, deletion_kwargs):
    document = world.profile_store.get_document("doc-doomed")

    purge_document_permanently("doc-doomed", **deletion_kwargs)

    entry = world.log.entries()[0]
    written = " ".join(
        str(value) for value in dataclasses.asdict(entry).values() if value is not None
    )
    assert document.title not in written
    assert document.doc_number not in written
    for sentence in document.extracted_text.split("."):
        if sentence.strip():
            assert sentence.strip() not in written
