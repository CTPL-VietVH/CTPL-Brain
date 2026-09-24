"""`POST /v1/ingestions` → `active` — the happy path of docs/10 §4.1/§4.2,
and the three properties that make it a happy path rather than a `202`.

1. the file is fetched inside the call, before `202`;
2. the pipeline reaches BOTH physical stores — the assertion reads the stores
   themselves, the way §10 insists (*"kiểm thẳng kho"*);
3. the answer to `GET /v1/ingestions/{id}` tells the truth about what GĐ7 did
   and did not do.

Nothing here loads BGE-M3: `conftest.FakeBgeM3` stands in, for the reason
`tests/t2_7_promote/conftest.py` gives — GĐ6's real behaviour belongs to
T2.5, and what these cases need is that GĐ6 ran.
"""

from __future__ import annotations

from conftest import KEEPER_SPACE, SAMPLE_DOCUMENT, TEST_TENANT_ID


def _publish(world, *, filename: str = "quyet-dinh.txt", content: str | None = None):
    return world.object_store.publish(
        content=(content or SAMPLE_DOCUMENT).encode("utf-8"),
        filename=filename,
        content_type="text/plain",
    )


def test_j_a_submission_is_accepted_with_202_and_a_processing_status(backend, world):
    """docs/10 §4.1 — *"`202` · `{ ingestion_id, status: "processing" }`"*."""
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    response = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    )

    assert response.status_code == 202
    assert set(response.json()) == {"ingestion_id", "status"}
    assert response.json()["status"] == "processing"
    assert response.json()["ingestion_id"]


def test_j_the_file_is_fetched_before_the_202_not_by_the_worker(backend, world):
    """§4.1: *"Tải trong lời gọi chứ không để cho bộ chạy nền, vì hàng đợi dài
    sẽ làm đường dẫn hết hạn."*

    Checked by looking at the staging area the instant the call returns and
    before the worker has run: the bytes are already there.
    """
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    submitted = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    )
    ingestion_id = submitted.json()["ingestion_id"]

    record = world.records.get(ingestion_id)
    assert record is not None, "the row must exist before the 202 is answered"
    assert record.staged_filename is not None
    assert world.staging.path_for(record.staged_filename).is_file(), (
        "the file had not been fetched when the call returned — a queued "
        "download would outlive the presigned link"
    )


def test_j_the_document_lands_in_both_stores_and_reads_back_active(backend, world):
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    ingestion_id = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    ).json()["ingestion_id"]
    world.run_background()

    # ⭐ Straight into the stores.
    documents = world.inner_store.documents()
    assert len(documents) == 1, "the shared profile store did not get the document"
    document = documents[0]
    assert document.space_id == KEEPER_SPACE
    assert document.tenant_id == TEST_TENANT_ID, (
        "tenant_id must come from the install (CBRAIN_TENANT_ID), never from the call"
    )
    assert "Điều 1" in document.extracted_text
    assert world.vector_writer.count() > 0, "Qdrant got no points — GĐ6 did not run"
    assert world.model.encode_calls > 0, "the embedding model was never called"

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()
    assert body["status"] == "active"
    assert body["document_id"] == document.document_id
    assert body["code"] is None
    assert body["existing_document_id"] is None


def test_j_the_staged_file_is_gone_once_the_text_has_been_read(backend, world):
    """docs/10 §4.1: *"Bản tạm bị xoá ngay sau khi đọc xong chữ"* — and §2:
    *"**Không lưu file gốc**, chỉ giữ `extracted_text`."*

    C.Brain is not a file store (06 §5.6). A staged copy that outlived the
    read would be one, quietly, on whichever disk the deployment picked.
    """
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    ingestion_id = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    ).json()["ingestion_id"]
    world.run_background()

    assert list(world.staging.directory.iterdir()) == [], (
        "a staged copy of the customer's file is still on disk"
    )
    assert world.records.get(ingestion_id).staged_filename is None, (
        "the row still names a file that is gone"
    )


def test_j_a_freshly_ingested_document_says_it_is_not_reconciled_yet(backend, world):
    """⭐ PO chốt 24/9 (K5), docs/10 §7.1.

    This install has no Backend space-topology client, so GĐ7 cannot widen
    its scope past the document's own Space. The honest answer is *"đang mở
    rộng"* — *"chưa đối chiếu xong"* — and it must reach Backend, because
    06 §5.1 makes that caveat part of every answer built on the document.

    ⛔ If this ever reads `stopped`, the scan concluded without consulting a
    Space tree: every future answer would silently claim reconciliation is
    complete. That is the exact failure `UnavailableSpaceScanScope` exists
    to prevent.
    """
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    ingestion_id = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    ).json()["ingestion_id"]
    world.run_background()

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()

    assert body["status"] == "active"
    assert body["relations_scan_state"] == "expanding"
    assert world.inner_store.documents()[0].relations_scan_state.value == "expanding"


def test_j_suggestions_come_back_with_no_invented_title(backend, world):
    """docs/10 §4.2: *"Khi bộ trích hai trường này chưa có, AI trả `null`,
    **không** lấy tên file giả làm tên văn bản."*

    The filename here is a plausible-looking one on purpose. A `title` of
    `"quyet-dinh-quan-ly-tai-lieu"` would look like a real suggestion on the
    confirmation screen, and a Manager would approve it without ever knowing
    a machine had read nothing.
    """
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world, filename="quyet-dinh-quan-ly-tai-lieu.txt")

    ingestion_id = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    ).json()["ingestion_id"]
    world.run_background()

    suggestions = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()[
        "suggestions"
    ]

    assert suggestions is not None
    assert suggestions["title"] is None, "a filename was passed off as a title"
    assert suggestions["doc_number"] is None
    assert "quyet-dinh" not in str(suggestions), (
        "the uploaded filename leaked into the suggestions"
    )
    # GĐ5 really ran: the dates carry a source, which is what 06 §6.4 wants
    # the reader told.
    assert suggestions["issued_date_source"] in {
        "extracted",
        "confirmed",
        "default_ingestion_date",
    }


def test_j_the_ingestion_id_is_not_the_document_id_on_a_refusal(backend, world):
    """docs/10 §4.2, chốt 24/9 — *"đối tượng nạp có thể kết thúc mà không sinh
    tài liệu"*.

    A refused submission still has an `ingestion_id` Backend can poll, and
    `document_id` stays `null` because no document exists. Collapsing the two
    identifiers would put a document id on this answer that names nothing.
    """
    backend.register_space(KEEPER_SPACE)
    stored = world.object_store.publish(
        content=b"whatever", filename="bang-luong.xlsx", content_type="application/x"
    )

    ingestion_id = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    ).json()["ingestion_id"]
    world.run_background()

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()

    assert body["ingestion_id"] == ingestion_id
    assert body["status"] == "rejected"
    assert body["document_id"] is None
    assert world.inner_store.documents() == []
