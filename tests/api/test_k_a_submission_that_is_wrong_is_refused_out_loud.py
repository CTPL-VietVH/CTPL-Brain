"""Every way `POST /v1/ingestions` says no — docs/10 §4.1, §4.2, §3.5.

The file is organised around WHERE the refusal happens, because that is the
part the contract fixes and the part that is easy to get wrong:

* **Inside the call** (Backend gets a code it can act on immediately):
  Space unknown or closing, a declared previous version that cannot be
  resolved, an unreachable link, bytes that do not match, a file over the
  ceiling.
* **On the row** (the failure is only knowable after reading the file):
  unsupported format, a document that cannot be structured, a duplicate.

⭐ The two lists are not interchangeable. §4.1 puts the Space check *"trước
khi tải byte nào"*, so a closing Space must never cost a download; and §4.1
puts duplicate detection after GĐ2 (*"vân tay tính sau khi đã đọc được
chữ"*), so a duplicate can never be a synchronous `409`. Each case below
asserts the boundary as well as the code.
"""

from __future__ import annotations

import hashlib

from api.errors import CODE_FIELD, ErrorCode
from conftest import DOOMED_SPACE, KEEPER_SPACE, SAMPLE_DOCUMENT
from fake_object_store import BLOCK_SIZE
from schema.ingestion_record import IngestionFailureCode


def _publish(world, *, filename: str = "quyet-dinh.txt", content: bytes | None = None):
    return world.object_store.publish(
        content=content if content is not None else SAMPLE_DOCUMENT.encode("utf-8"),
        filename=filename,
        content_type="text/plain",
    )


# --------------------------------------------------------------------------- #
# Refused inside the call
# --------------------------------------------------------------------------- #


def test_k_a_space_backend_never_announced_takes_no_document(backend, world):
    """docs/10 §4.1 — `404 SPACE_NOT_REGISTERED`, and §10 lists this case by
    name."""
    stored = _publish(world)

    response = backend.submit_ingestion(
        source=stored.source_block(), space_id="space-never-announced"
    )

    assert response.status_code == 404
    assert response.json()[CODE_FIELD] == ErrorCode.SPACE_NOT_REGISTERED
    assert stored.blocks_served == 0, (
        "the file was downloaded for a Space that does not exist — §4.1 puts the "
        "Space check before any byte is fetched"
    )
    assert world.records.records() == []


def test_k_a_space_being_deleted_takes_no_document(backend, world):
    """docs/10 §4.0 step 1 — *"Từ lúc này mọi lời gọi nộp tài liệu ... trả
    `409 SPACE_BEING_DELETED`"*, and "từ lúc này" means from the `202`, not
    from whenever the background job gets around to it.

    So the submission below happens AFTER the `DELETE` answered and BEFORE
    the worker has run a single step.
    """
    backend.register_space(DOOMED_SPACE)
    world.seed_document(document_id="doc-doomed-1", space_id=DOOMED_SPACE)
    stored = _publish(world)

    backend.delete_space(DOOMED_SPACE)
    response = backend.submit_ingestion(
        source=stored.source_block(), space_id=DOOMED_SPACE
    )

    assert response.status_code == 409
    assert response.json()[CODE_FIELD] == ErrorCode.SPACE_BEING_DELETED
    assert stored.blocks_served == 0
    assert world.records.records() == []


def test_k_an_expired_link_is_refused_and_nothing_is_created(backend, world):
    """docs/10 §3.5 `SOURCE_UNREACHABLE` (422), §4.1: *"Không tải được →
    `SOURCE_UNREACHABLE`, không tạo đối tượng nạp, không còn file tạm."*"""
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)
    world.object_store.expire(stored)

    response = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    )

    assert response.status_code == 422
    assert response.json()[CODE_FIELD] == ErrorCode.SOURCE_UNREACHABLE
    assert world.records.records() == [], "a refused fetch created an ingestion row"
    assert list(world.staging.directory.iterdir()) == [], "a partial file was left behind"


def test_k_the_refusal_never_repeats_the_presigned_link(backend, world):
    """⛔ docs/10 §4.1: *"AI **không lưu `url`** ở bất cứ đâu (nhật ký, bảng,
    thông báo lỗi)"*.

    A presigned URL is a temporary permission. Echoing it into an error body
    hands it to whatever reads that body — a log aggregator, a browser
    console, a support ticket — long after the call ended.
    """
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)
    world.object_store.expire(stored)

    response = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    )

    assert "signature" not in response.text
    assert stored.url not in response.text


def test_k_a_timeout_is_the_same_refusal_as_an_expired_link(backend, world):
    """docs/10 §3.5 folds *"hết hạn, bị từ chối, quá thời gian"* into one
    code: all three tell Backend the same thing — mint a new link and try
    again."""
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)
    world.object_store.time_out = True

    response = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    )

    assert response.status_code == 422
    assert response.json()[CODE_FIELD] == ErrorCode.SOURCE_UNREACHABLE
    assert list(world.staging.directory.iterdir()) == []


def test_k_a_file_that_does_not_match_its_digest_is_refused(backend, world):
    """docs/10 §3.5 `SOURCE_INTEGRITY_MISMATCH` (422).

    Backend describes the file; AI checks the description against the bytes.
    Ingesting a file that does not match would attach the wrong content to
    the submission — and `content_fingerprint`, the duplicate key of 06 §5.7,
    would be computed from bytes nobody described.
    """
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)
    wrong_digest = hashlib.sha256(b"a completely different file").hexdigest()

    response = backend.submit_ingestion(
        source=stored.source_block(sha256=wrong_digest), space_id=KEEPER_SPACE
    )

    assert response.status_code == 422
    assert response.json()[CODE_FIELD] == ErrorCode.SOURCE_INTEGRITY_MISMATCH
    assert world.records.records() == []
    assert list(world.staging.directory.iterdir()) == [], "the mismatched bytes were kept"


def test_k_a_file_that_does_not_match_its_declared_size_is_refused(backend, world):
    """The length is checked as well as the digest. A digest alone would
    pass a truncated transfer that happened to be re-hashed downstream; the
    two together describe one file and nothing else."""
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    response = backend.submit_ingestion(
        source=stored.source_block(size_bytes=len(stored.content) + 1),
        space_id=KEEPER_SPACE,
    )

    assert response.status_code == 422
    assert response.json()[CODE_FIELD] == ErrorCode.SOURCE_INTEGRITY_MISMATCH


def test_k_an_oversized_file_stops_mid_download(backend, world):
    """⭐ docs/10 §3.5: *"Ngừng tải ngay khi vượt, **không tải hết rồi mới
    kiểm**"* — `413 FILE_TOO_LARGE`.

    The assertion that matters is the second one. Refusing after reading the
    whole body is a refusal with the cost already paid: the bandwidth is
    spent and the disk is full, which is precisely what a ceiling is for.
    """
    backend.register_space(KEEPER_SPACE)
    ceiling = world.ingestion_config.max_upload_bytes
    oversized = b"x" * (ceiling + 5 * BLOCK_SIZE)
    stored = _publish(world, filename="qua-lon.txt", content=oversized)

    response = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    )

    assert response.status_code == 413
    assert response.json()[CODE_FIELD] == ErrorCode.FILE_TOO_LARGE
    assert stored.blocks_served < stored.block_count, (
        f"the whole body was read before refusing ({stored.blocks_served} of "
        f"{stored.block_count} blocks) — the ceiling must stop the transfer, "
        "not audit it afterwards"
    )
    assert world.records.records() == []
    assert list(world.staging.directory.iterdir()) == []


def test_k_a_declared_previous_version_that_is_not_there_is_refused_loudly(
    backend, world
):
    """⭐ PO chốt 24/9 (K11), docs/10 §4.1: *"`declared_previous_document_id`
    không tồn tại hoặc không nằm ở `space_id` này → từ chối
    `OBJECT_NOT_IN_SPACE`. **Không được** im lặng coi như tài liệu mới."*

    The silent branch is the dangerous one, and it is also the easy one to
    write: `decide_intake` treats `declared_previous_version=None` as "start
    a fresh chain", so forgetting to check here produces a `202`, a document,
    and two versions of one text that are never linked.
    """
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    response = backend.submit_ingestion(
        source=stored.source_block(),
        space_id=KEEPER_SPACE,
        declared_previous_document_id="doc-that-never-existed",
    )

    assert response.status_code == 404
    assert response.json()[CODE_FIELD] == ErrorCode.OBJECT_NOT_IN_SPACE
    assert world.records.records() == [], "a fresh version chain was started anyway"
    assert stored.blocks_served == 0, "the file was fetched before the claim was checked"


def test_k_a_declared_previous_version_in_another_space_is_refused(backend, world):
    """Same refusal, and the same reason AI checks it at all (T4): Backend
    says who is asking, AI says whether the object is where it was said to
    be. A version chain across Spaces would link two document sets with
    different readers."""
    backend.register_space(KEEPER_SPACE)
    backend.register_space(DOOMED_SPACE)
    world.seed_document(document_id="doc-elsewhere", space_id=DOOMED_SPACE)
    stored = _publish(world)

    response = backend.submit_ingestion(
        source=stored.source_block(),
        space_id=KEEPER_SPACE,
        declared_previous_document_id="doc-elsewhere",
    )

    assert response.status_code == 404
    assert response.json()[CODE_FIELD] == ErrorCode.OBJECT_NOT_IN_SPACE


# --------------------------------------------------------------------------- #
# Refused on the row — only knowable after the file has been read
# --------------------------------------------------------------------------- #


def test_k_an_unsupported_format_ends_as_a_rejected_row(backend, world):
    """docs/10 §4.2 — `rejected` + `code`, not an HTTP error.

    The format is only known once the pipeline looks at the file, which
    happens after `202`. So the refusal has to reach Backend through the
    status endpoint, and it does.
    """
    backend.register_space(KEEPER_SPACE)
    stored = world.object_store.publish(
        content=b"PK\x03\x04 not a document we read",
        filename="bang-luong.xlsx",
        content_type="application/vnd.ms-excel",
    )

    ingestion_id = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    ).json()["ingestion_id"]
    world.run_background()

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()

    assert body["status"] == "rejected"
    assert body["code"] == IngestionFailureCode.UNSUPPORTED_FORMAT.value
    assert world.inner_store.documents() == []
    assert world.vector_writer.count() == 0
    assert list(world.staging.directory.iterdir()) == [], (
        "a rejected file was left staged — §4.1 deletes it *kể cả khi từ chối "
        "giữa chừng*"
    )


def test_k_a_document_that_cannot_be_structured_ends_as_one_code(backend, world):
    """PO chốt 24/9 (E5): GĐ3's two refusals and GĐ6's one collapse into
    `DOCUMENT_NOT_STRUCTURABLE` (docs/10 §3.5).

    Here it is GĐ6's: the fake model's context ceiling is lowered under the
    chunk the document produces, which is the same shape as a real Điều that
    is too long for BGE-M3. `vectorization.sinh_vector` refuses rather than
    truncating — T0.2 measured that the library only WARNS and carries on
    with the truncated text, which is silent corruption.
    """
    backend.register_space(KEEPER_SPACE)
    world.model.max_seq_length = 2  # tokens; every chunk is over it
    stored = _publish(world)

    ingestion_id = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    ).json()["ingestion_id"]
    world.run_background()

    body = backend.read_ingestion(ingestion_id, space_id=KEEPER_SPACE).json()

    assert body["status"] == "rejected"
    assert body["code"] == IngestionFailureCode.DOCUMENT_NOT_STRUCTURABLE.value
    assert world.inner_store.documents() == [], (
        "a document that could not be vectorised still reached the profile store"
    )
    assert world.vector_writer.count() == 0


def test_k_reading_an_ingestion_of_another_space_is_a_404(backend, world):
    """docs/10 §1 T4 and §3.5 — `OBJECT_NOT_IN_SPACE`, *"Trả 404 chứ không trả
    403, để không tiết lộ đối tượng tồn tại"*.

    Backend asserts who is asking; AI checks for itself that the object is in
    the Space named. The answer for "in another Space" and for "does not
    exist" is deliberately identical.
    """
    backend.register_space(KEEPER_SPACE)
    backend.register_space(DOOMED_SPACE)
    stored = _publish(world)
    ingestion_id = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE
    ).json()["ingestion_id"]
    world.run_background()

    wrong_space = backend.read_ingestion(ingestion_id, space_id=DOOMED_SPACE)
    absent = backend.read_ingestion("ing-does-not-exist", space_id=KEEPER_SPACE)

    assert wrong_space.status_code == 404
    assert wrong_space.json()[CODE_FIELD] == ErrorCode.OBJECT_NOT_IN_SPACE
    assert absent.status_code == 404
    assert absent.json() == wrong_space.json(), (
        "the two answers differ, so the existence of the object leaks"
    )


def test_k_reading_an_ingestion_without_a_space_is_refused(backend, world):
    """docs/10 §3.3 — *"Thiếu trường thì trả `400 SCOPE_MISSING`"*, and the
    ⚠️ that forbids reading a missing scope as "no limit" (the old system's
    `workspace=""`)."""
    backend.register_space(KEEPER_SPACE)

    no_scope = backend.call("GET", "/v1/ingestions/ing-001")
    empty_scope = backend.call("GET", "/v1/ingestions/ing-001?space_id=")

    assert no_scope.status_code == 400
    assert no_scope.json()[CODE_FIELD] == ErrorCode.SCOPE_MISSING
    assert empty_scope.status_code == 400
    assert empty_scope.json()[CODE_FIELD] == ErrorCode.SCOPE_MISSING


def test_k_a_submission_without_an_idempotency_key_is_refused(backend, world):
    """docs/10 §3.4 — the header is mandatory on writes, and a submission is
    a write. Waving it through would let a retried upload be ingested twice.
    """
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    response = backend.call(
        "POST",
        "/v1/ingestions",
        json={
            "source": stored.source_block(),
            "space_id": KEEPER_SPACE,
            "space_is_private": False,
            "actor": {"user_id": "u1", "acting_as": "contributor"},
        },
        send_idempotency_key=False,  # the rule this case breaks
    )

    assert response.status_code == 400
    assert response.json()[CODE_FIELD] == ErrorCode.IDEMPOTENCY_KEY_MISSING
    assert world.records.records() == []
    assert stored.blocks_served == 0, "the file was fetched behind a 400"


def test_k_one_idempotency_key_submits_once(backend, world):
    """docs/10 §3.4 — *"Gửi lại cùng khoá thì nhận lại đúng kết quả lần đầu,
    không ghi thêm."*

    For a submission "không ghi thêm" is load-bearing in a way it is not for
    a deletion: a second row would download the file again, run the whole
    pipeline again, and produce a SECOND document from one upload — the
    duplicate check would not save it, because two rows in flight at once
    both see an empty store.
    """
    backend.register_space(KEEPER_SPACE)
    stored = _publish(world)

    first = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE, idempotency_key="key-up-1"
    )
    replay = backend.submit_ingestion(
        source=stored.source_block(), space_id=KEEPER_SPACE, idempotency_key="key-up-1"
    )
    world.run_background()

    assert first.status_code == 202
    assert replay.json() == first.json(), "the replay did not return the first answer"
    assert len(world.records.records()) == 1, "one upload produced two ingestion rows"
    assert len(world.inner_store.documents()) == 1, "one upload produced two documents"
