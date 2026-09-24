"""Fetching the file Backend points at — docs/10 §4.1, *"file đi bằng tham
chiếu"*, chốt 24/9/2026.

Backend does not send the bytes. It sends a **presigned, short-lived GET
URL** into the object store where the browser already put the file, together
with `sha256` and `size_bytes`. PO's reason, verbatim: *"FE đã lưu file lên
MinIO lúc người dùng tải lên, nên gửi nguyên file sẽ khiến file đi mạng hai
lần qua BE."*

──────────────────────────────────────────────────────────────────────────
Four rules this module exists to keep
──────────────────────────────────────────────────────────────────────────

1. **Plain HTTP GET, no object-store client.** §4.1: *"AI chỉ gọi HTTP GET,
   không dùng thư viện MinIO, không cầm tài khoản MinIO — BE vẫn là bên
   quyết ai đọc được gì (T2)."* A MinIO credential here would make AI a
   second place that decides what may be read.
2. **The size ceiling is enforced WHILE WRITING.** §3.5: *"Ngừng tải ngay
   khi vượt, không tải hết rồi mới kiểm."* `Content-Length` is a claim by
   the sender; a 2 GB body with `Content-Length: 10` fills the disk of a
   service that trusted it. The counter below is over bytes actually
   written.
3. **The digest is checked, and a mismatch is a refusal.** A file that does
   not match what Backend described is not "close enough": it is a different
   file, and ingesting it would attach the wrong bytes to the wrong
   submission.
4. ⛔ **The URL is never stored, logged or echoed.** §4.1: *"AI **không lưu
   `url`** ở bất cứ đâu (nhật ký, bảng, thông báo lỗi) — đường dẫn có chữ ký
   là một thứ quyền tạm thời."* Every exception message below therefore
   names the ingestion, never the link. `httpx` puts the URL in its own
   exception strings, which is why they are caught and replaced rather than
   chained with `from exc` into a handler that might format them.

Partial bytes are deleted on every failure path, so a refusal leaves nothing
behind for the staging sweep to find.
"""

from __future__ import annotations

import hashlib
import pathlib
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from ingestion.staging import StagingArea, staged_filename_for

__all__ = [
    "ClientFactory",
    "FetchedSource",
    "FileTooLarge",
    "SourceFetchError",
    "SourceIntegrityMismatch",
    "SourceUnreachable",
    "default_http_client",
    "fetch_source_to_staging",
]


class SourceFetchError(Exception):
    """Base for every refusal this module makes."""


class SourceUnreachable(SourceFetchError):
    """docs/10 §3.5 — *"Không tải được file từ đường dẫn BE gửi: hết hạn, bị
    từ chối, quá thời gian"* (`422`).

    One code for all three because from Backend's side they call for the
    same action: mint a fresh presigned URL and submit again. Telling them
    apart in the answer would also describe the object store's behaviour to
    whoever is on the other end of the API.
    """


class SourceIntegrityMismatch(SourceFetchError):
    """docs/10 §3.5 — the bytes do not match the `sha256`/`size_bytes`
    Backend declared (`422`)."""


class FileTooLarge(SourceFetchError):
    """docs/10 §3.5 — over `max_upload_bytes` (`413`), detected mid-download."""


@dataclass(frozen=True, slots=True, kw_only=True)
class FetchedSource:
    """What a successful fetch produced: a name in the staging area, and the
    size actually written.

    A NAME, not a path: the staging directory is the deployment's, and
    `ingestion_record.staged_filename` stores the name for the same reason
    (see that module).
    """

    staged_filename: str
    size_bytes: int


#: Injected so a test can drive a fake transport without a socket, and so a
#: deployment behind a proxy can supply its own client. Not a config value:
#: every number the client needs (the timeout) is passed per call.
ClientFactory = Callable[[float], httpx.Client]


def default_http_client(timeout_seconds: float) -> httpx.Client:
    return httpx.Client(timeout=timeout_seconds, follow_redirects=True)


def fetch_source_to_staging(
    *,
    url: str,
    sha256: str,
    size_bytes: int,
    source_filename: str,
    ingestion_id: str,
    staging: StagingArea,
    max_upload_bytes: int,
    timeout_seconds: float,
    client_factory: ClientFactory = default_http_client,
) -> FetchedSource:
    """Download one file into the staging area, or refuse and leave nothing.

    `max_upload_bytes` and `timeout_seconds` have no defaults: both are keys
    of `config/ingestion.yaml` (07 Mục 3.2) and the composition root passes
    the live values down (CLAUDE.md Mục 4 quy tắc 2).

    Raises:
        FileTooLarge: more than `max_upload_bytes` written. The download is
            abandoned at that byte, not after the body finishes.
        SourceIntegrityMismatch: the digest or the length disagrees with what
            Backend declared.
        SourceUnreachable: the link expired, was refused, timed out, or the
            transfer broke.
    """
    staged_filename = staged_filename_for(ingestion_id, source_filename=source_filename)
    path = staging.path_for(staged_filename)

    try:
        written, digest = _stream_to_file(
            url=url,
            path=path,
            max_upload_bytes=max_upload_bytes,
            timeout_seconds=timeout_seconds,
            client_factory=client_factory,
            ingestion_id=ingestion_id,
        )
    except SourceFetchError:
        staging.discard(staged_filename)
        raise

    if written != size_bytes or digest != sha256.lower():
        staging.discard(staged_filename)
        raise SourceIntegrityMismatch(
            f"ingestion {ingestion_id!r}: the fetched file does not match what "
            f"Backend declared — size {written} vs {size_bytes}, sha256 "
            f"{digest} vs {sha256.lower()}. Refusing rather than ingesting bytes "
            f"nobody described (docs/10 §4.1)."
        )

    return FetchedSource(staged_filename=staged_filename, size_bytes=written)


def _stream_to_file(
    *,
    url: str,
    path: pathlib.Path,
    max_upload_bytes: int,
    timeout_seconds: float,
    client_factory: ClientFactory,
    ingestion_id: str,
) -> tuple[int, str]:
    """Stream the body to `path`, counting and hashing as it goes.

    Returns `(bytes_written, sha256_hex)`. The hash is computed from the same
    bytes that were written — not from a second read of the file — so the two
    cannot disagree.
    """
    hasher = hashlib.sha256()
    written = 0

    try:
        with client_factory(timeout_seconds) as client:
            with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    raise SourceUnreachable(
                        f"ingestion {ingestion_id!r}: the object store answered "
                        f"{response.status_code} for the presigned link. Most often "
                        f"the link has expired (docs/10 §4.1)."
                    )
                with path.open("wb") as handle:
                    for block in response.iter_bytes():
                        written += len(block)
                        if written > max_upload_bytes:
                            # ⭐ Abandoned HERE, mid-body: the rest of the
                            # response is never read and never written.
                            raise FileTooLarge(
                                f"ingestion {ingestion_id!r}: the file exceeds the "
                                f"maximum upload size of {max_upload_bytes} bytes "
                                f"(config/ingestion.yaml `max_upload_bytes`, published "
                                f"by GET /v1/meta). Download stopped at {written} bytes."
                            )
                        handle.write(block)
                        hasher.update(block)
    except SourceFetchError:
        raise
    except httpx.HTTPError as exc:
        # ⛔ `exc` is NOT chained in and NOT formatted: httpx puts the URL in
        # its own message, and docs/10 §4.1 forbids the presigned link from
        # reaching a log or an error. The exception TYPE is enough to tell an
        # operator which class of failure it was.
        raise SourceUnreachable(
            f"ingestion {ingestion_id!r}: the presigned link could not be read "
            f"({type(exc).__name__}). Expired, refused, or timed out after "
            f"{timeout_seconds}s (config/ingestion.yaml "
            f"`source_download_timeout_seconds`)."
        ) from None
    except OSError as exc:
        raise SourceUnreachable(
            f"ingestion {ingestion_id!r}: the staged copy could not be written "
            f"({type(exc).__name__}). Check the staging directory."
        ) from None

    return written, hasher.hexdigest()
