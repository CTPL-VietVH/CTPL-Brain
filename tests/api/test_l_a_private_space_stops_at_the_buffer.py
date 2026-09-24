"""The Space-riêng path, and the duplicate that can arrive on either path —
docs/10 §4.1, §4.2; 06 §5.2 GĐ1; 08 T2.7.

Two things are being held apart here, and CLAUDE.md điều cấm #14 and #20 are
the reasons:

* a document awaiting approval must be in **no shared store at all**, not in
  one with a flag on it. The check is structural — read both stores;
* `duplicate` is **one status on the wire** whichever store the twin sits in
  (docs/10 §4.2, chốt 24/9). Backend gets one thing to handle; AI keeps the
  distinction in its own log.
"""

from __future__ import annotations

from conftest import KEEPER_SPACE, SAMPLE_DOCUMENT


def _publish(world, *, filename: str = "quyet-dinh.txt"):
    return world.object_store.publish(
        content=SAMPLE_DOCUMENT.encode("utf-8"),
        filename=filename,
        content_type="text/plain",
    )


def _submit(backend, world, *, private: bool, filename: str = "quyet-dinh.txt") -> str:
    stored = _publish(world, filename=filename)
    return backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE, space_is_private=private
    ).json()["ingestion_id"]


def test_l_a_private_space_submission_waits_and_touches_no_shared_store(
    backend, world
):
    """docs/10 §4.1: *"`space_is_private = true` thì chạy GĐ2, GĐ3, GĐ5 rồi
    dừng ở vùng đệm (T2.7)"*, and §10: *"Tài liệu Space riêng chưa duyệt |
    Không có trong Qdrant lẫn PostgreSQL"*.

    ⭐ The assertion reads both physical stores. A `status` of
    `awaiting_approval` on top of a document that had quietly been written
    would pass an assertion about the answer and fail this one — and that is
    the exact failure CLAUDE.md điều cấm #20 describes.
    """
    backend.register_space(KEEPER_SPACE)

    ingestion_id = _submit(backend, world, private=True)
    world.run_background()

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()
    assert body["status"] == "awaiting_approval"
    assert body["document_id"] is None, (
        "an unapproved submission named a document in the shared store"
    )

    assert world.inner_store.documents() == [], "PostgreSQL holds an unapproved document"
    assert world.vector_writer.count() == 0, "Qdrant holds chunks of an unapproved document"
    assert world.buffered_ids() == {ingestion_id}, "the entry is not in the buffer"


def test_l_the_buffered_entry_carries_labels_and_dates_but_no_vector(backend, world):
    """GĐ5 ran, GĐ6 did not — 06 §5.2 GĐ1 stops the chain *"TRƯỚC GĐ6 và
    GĐ7"*.

    The Manager needs the labels to decide (that is why GĐ5 runs before the
    stop); the vectors are what would make the document findable, so they are
    what must not exist yet. The buffer's own table has no column for one
    (T2.7), which is the structural half of the same rule.
    """
    backend.register_space(KEEPER_SPACE)

    ingestion_id = _submit(backend, world, private=True)
    world.run_background()

    entry = world.buffer.get(ingestion_id)
    assert entry is not None
    assert entry.chunks, "GĐ3 did not run"
    assert all(chunk.embedding == [] for chunk in entry.chunks), (
        "a buffered chunk carries a vector — the chain ran past GĐ6"
    )
    assert world.model.encode_calls == 0, "the embedding model ran on the private path"

    # GĐ5's output is visible to the Manager through the status endpoint.
    suggestions = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()[
        "suggestions"
    ]
    assert suggestions is not None
    assert suggestions["issued_date"] is not None
    assert suggestions["title"] is None  # still nobody's suggestion (E3)


def test_l_a_duplicate_in_the_shared_store_reports_duplicate(backend, world):
    """06 §5.7 — *"Trùng khít, cùng Space | Báo trùng, không nạp lại — trỏ tới
    bản đã có"*. docs/10 §4.2 carries it as `duplicate` +
    `existing_document_id`."""
    backend.register_space(KEEPER_SPACE)

    first = _submit(backend, world, private=False)
    world.run_background()
    second = _submit(backend, world, private=False, filename="ban-sao.txt")
    world.run_background()

    first_body = backend.read_ingestion(first, space_id=KEEPER_SPACE).json()
    second_body = backend.read_ingestion(second, space_id=KEEPER_SPACE).json()

    assert first_body["status"] == "active"
    assert second_body["status"] == "duplicate"
    assert second_body["existing_document_id"] == first_body["document_id"]
    assert second_body["document_id"] is None, (
        "a duplicate must not name a document of its own — none was created"
    )
    assert len(world.inner_store.documents()) == 1, "the duplicate was ingested anyway"


def test_l_a_duplicate_waiting_in_the_buffer_reports_the_same_status(backend, world):
    """⭐ docs/10 §4.2, chốt 24/9: *"`duplicate` là một trạng thái duy nhất
    trên dây, dù bản trùng nằm ở kho dùng chung hay ở vùng đệm tiền kiểm; AI
    phân biệt hai trường hợp trong nhật ký nội bộ."*

    One status, because for the person who uploaded it the answer is the
    same: this file is already here. Two statuses would make Backend build
    two screens for one fact, and the second one would have to explain a
    storage detail of AI's.
    """
    backend.register_space(KEEPER_SPACE)

    first = _submit(backend, world, private=True)
    world.run_background()
    second = _submit(backend, world, private=True, filename="ban-sao.txt")
    world.run_background()

    second_body = backend.read_ingestion(second, space_id=KEEPER_SPACE).json()

    assert second_body["status"] == "duplicate", (
        "a twin in the pre-approval buffer produced a different wire status "
        "than a twin in the shared store"
    )
    assert second_body["existing_document_id"] == first
    assert world.buffered_ids() == {first}, "the duplicate was buffered as well"
    assert world.inner_store.documents() == []
