"""The staging area — where a downloaded file lives between `POST
/v1/ingestions` and GĐ2, and nowhere else (docs/10 §4.1).

docs/10 §2 is blunt about what AI may keep: *"AI **tải về qua đường dẫn có
chữ ký BE cấp** (§4.1), chỉ để đọc chữ; xoá bản tạm ngay sau khi đọc xong
chữ. **Không lưu file gốc**, chỉ giữ `extracted_text`."* 06 §5.6 gives the
reason in one line — C.Brain is not a file store.

So this module is deliberately small and deliberately boring. It owns three
facts and no policy:

* the directory, which is INJECTED. There is no `tempfile.gettempdir()` call
  anywhere in this repo's ingestion path: where staged bytes land is a
  deployment decision (R6) — it needs to be on a disk with room for the
  largest accepted upload, and on a disk an operator is willing to have
  customer documents sit on for a few seconds. A library default would make
  that decision silently, in a different place on every machine;
* the one-to-one mapping between a staged file and an `ingestion_id`, so a
  leaked file can always be traced back to the row that should have removed
  it;
* deletion that is safe to call twice, because the callers are a `finally`
  block and a restart sweep, and both will sometimes run over a file that is
  already gone.

⛔ **No reading happens here.** GĐ2 (`extraction.extract_file`) opens the
path; this module only produces, deletes and enumerates paths. Keeping it
that way is what lets the whole staging policy be read in one screen.
"""

from __future__ import annotations

import pathlib
import re
from collections.abc import Iterable

__all__ = ["StagingArea", "staged_filename_for"]


#: A file extension we are willing to put on a staged file. Backend's
#: `source.filename` is UNTRUSTED input (docs/10 §4.1 — it is whatever the
#: person who uploaded typed), so only the suffix is used, and only if it
#: looks like a suffix. Anything else becomes the empty string, which GĐ2
#: then refuses with `DinhDangKhongNhan` → `UNSUPPORTED_FORMAT`.
#:
#: Why the extension is carried over at all: `reader.readers.doc_file`
#: dispatches on `path.suffix`. A staged file called `<ingestion_id>` with no
#: suffix would be refused no matter what Backend sent.
_SAFE_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,16}$")


def staged_filename_for(ingestion_id: str, *, source_filename: str) -> str:
    """The name a staged file gets: the `ingestion_id`, plus a safe suffix.

    The `ingestion_id` leads so that the mapping file → row is exact and
    needs no lookup table. ⛔ The uploader's own filename is NOT kept: it is
    a string a person typed, it can contain path separators, and none of the
    four v1 readers wants it. (It is also not a `title` — PO chốt 24/9,
    docs/10 §4.2: *"AI trả `null`, **không** lấy tên file giả làm tên văn
    bản"*.)
    """
    suffix = pathlib.PurePosixPath(source_filename).suffix
    if not _SAFE_SUFFIX.match(suffix):
        suffix = ""
    return f"{ingestion_id}{suffix.lower()}"


class StagingArea:
    """One directory, holding at most one file per unfinished ingestion."""

    def __init__(self, directory: pathlib.Path) -> None:
        """`directory` is required and is created if absent.

        Created rather than required-to-exist because the alternative is a
        deployment that starts, accepts a submission and only then discovers
        it has nowhere to put it — after the presigned URL has been used.
        """
        self._directory = pathlib.Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)

    @property
    def directory(self) -> pathlib.Path:
        return self._directory

    def path_for(self, staged_filename: str) -> pathlib.Path:
        """Where a staged file with this name lives.

        Refuses a name that is not a plain file name. `staged_filename` comes
        back out of the database, and a row carrying `../../etc/passwd` must
        not be turned into a path by this function — it would be a delete, in
        the sweep that runs at startup.
        """
        if not staged_filename or "/" in staged_filename or "\\" in staged_filename:
            raise ValueError(
                f"staged_filename={staged_filename!r} is not a plain file name; "
                f"the staging area holds flat names only"
            )
        if staged_filename in {".", ".."}:
            raise ValueError(f"staged_filename={staged_filename!r} is not a file name")
        return self._directory / staged_filename

    def discard(self, staged_filename: str | None) -> bool:
        """Delete a staged file. Returns whether anything was there.

        Safe to call twice, and safe to call with `None`: the two callers are
        a `finally` block and the startup sweep, and both legitimately run
        over files that are already gone. A refusal here would turn an
        already-successful cleanup into an error.
        """
        if staged_filename is None:
            return False
        path = self.path_for(staged_filename)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    def collect_garbage(self, *, keep: Iterable[str]) -> list[str]:
        """Delete every staged file NOT named in `keep`. Returns what went.

        Run at startup, with `keep` = the staged names of every ingestion row
        that is still unfinished. What it removes is the residue of a process
        that died between writing bytes and finishing the row — files no row
        will ever ask for again, holding customer document content on disk.

        ⚠️ `keep` must be computed from the store, never guessed. Passing an
        empty set on a live deployment would delete the queue's own inputs.
        """
        kept = set(keep)
        removed: list[str] = []
        for path in sorted(self._directory.iterdir()):
            if not path.is_file() or path.name in kept:
                continue
            try:
                path.unlink()
            except FileNotFoundError:  # pragma: no cover - raced with a discard
                continue
            removed.append(path.name)
        return removed
