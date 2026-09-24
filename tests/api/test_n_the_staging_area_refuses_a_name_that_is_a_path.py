"""`ingestion.staging` — the two rules that stop a staged FILE NAME from
becoming a path.

The name travels out of `ingestion_record.staged_filename`, i.e. out of a
database, and two callers turn it back into a path: the pipeline (to read
it) and the startup sweep (to DELETE it). A row carrying `../../something`
would make the second one delete a file outside the staging directory, at
startup, with a `WARNING` in the log saying it cleaned up nicely.

It is also where the uploader's own filename is handled, and that string is
whatever a person typed (docs/10 §4.1 — Backend passes it through).
"""

from __future__ import annotations

import pytest

from ingestion.staging import StagingArea, staged_filename_for


@pytest.mark.parametrize(
    "hostile",
    [
        "../escape.txt",
        "../../etc/passwd",
        "sub/dir.txt",
        "sub\\dir.txt",
        "..",
        ".",
        "",
    ],
)
def test_n_a_staged_name_that_is_not_a_plain_file_name_is_refused(tmp_path, hostile):
    staging = StagingArea(tmp_path / "staging")

    with pytest.raises(ValueError):
        staging.path_for(hostile)


def test_n_discard_of_a_hostile_name_is_refused_too(tmp_path):
    """⛔ `discard` must not be the soft door into the same problem.

    It is the forgiving one by design — *"safe to call twice"* — and a
    `return False` for anything it cannot resolve would be exactly the
    silent acceptance that lets a hostile name through the one call that
    deletes.
    """
    staging = StagingArea(tmp_path / "staging")
    outsider = tmp_path / "important.txt"
    outsider.write_text("nội dung của người khác", encoding="utf-8")

    with pytest.raises(ValueError):
        staging.discard("../important.txt")

    assert outsider.exists()


def test_n_discarding_nothing_is_not_an_error(tmp_path):
    """The two real callers are a `finally` block and a restart sweep, and
    both legitimately run over files that are already gone."""
    staging = StagingArea(tmp_path / "staging")

    assert staging.discard("never-existed.txt") is False
    assert staging.discard(None) is False


@pytest.mark.parametrize(
    "source_filename, expected_suffix",
    [
        ("quyet-dinh.PDF", ".pdf"),
        ("bao cao 2021.docx", ".docx"),
        ("../../etc/passwd", ""),
        ("no-extension", ""),
        ("weird.this-is-not-an-extension-at-all", ""),
        ("trailing.", ""),
    ],
)
def test_n_only_a_plausible_extension_survives_from_the_uploaded_name(
    source_filename, expected_suffix
):
    """The extension is carried over because `reader.readers.doc_file`
    dispatches on it — and NOTHING else from the uploader's filename is.

    An unrecognisable suffix becomes the empty string rather than an error:
    GĐ2 then refuses the file with `UNSUPPORTED_FORMAT`, which is the answer
    the contract already has for "we do not read this" (docs/10 §3.5).
    """
    name = staged_filename_for("ing-001", source_filename=source_filename)

    assert name == f"ing-001{expected_suffix}"
    assert "/" not in name and "\\" not in name


def test_n_the_staged_name_is_the_ingestion_id_not_the_uploaded_one():
    """⛔ docs/10 §4.2: *"không lấy tên file giả làm tên văn bản"*.

    The rule is about `title`, and this is the upstream half of it: the
    uploader's filename never becomes a stored artefact at all, so there is
    nothing lying around for a later screen to pick up by accident.
    """
    name = staged_filename_for("ing-042", source_filename="Quyết định số 15.txt")

    assert name == "ing-042.txt"
    assert "Quyết định" not in name
