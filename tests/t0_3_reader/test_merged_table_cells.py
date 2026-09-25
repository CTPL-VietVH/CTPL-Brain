"""READER-docx-o-gop, 25/9/2026 — `python-docx`'s `Row.cells` yields the same
`_Cell` once per grid column a horizontally-merged (`gridSpan`) cell spans
(documented library behavior, `docx/table.py` `Row.cells` docstring). Left
unhandled in `_doc_docx`, that duplicate was joined into the output line as
many times as the merge was wide — root cause of `47_2021_nd-cp_470561.docx`
failing GĐ3 (`CHUNK-47-2021-dieu-tra`): a `gridSpan=10` row turned 541/581
real characters into 5.431/5.831 characters in `extracted_text`.

These tests pin the fix (`_unique_row_cell_texts`, `packages/ingestion/reader/
readers.py`) on a table built at test time with `python-docx`, so the fixture
is exact and self-documenting rather than an opaque checked-in binary:

  * a horizontally-merged cell (3 grid columns) must not repeat its text,
  * a vertically-merged cell (`vMerge="continue"`, 2 rows) must keep its
    CURRENT behavior unchanged — this fix's scope is horizontal merges
    within one row only,
  * a plain row with no merge at all must come out byte-identical to what
    each cell's own text says.
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from ingestion.reader.readers import _doc_docx  # noqa: E402


def _build_mixed_merge_table(path: pathlib.Path) -> None:
    """One 4x4 table exercising all three cases in a single layout:

    Row 0: col 0 plain, cols 1-3 one cell merged HORIZONTALLY (gridSpan=3).
    Row 1: col 1 is the MASTER of a vertical merge that continues into row 2.
    Row 2: col 1 is the vMerge CONTINUATION cell of row 1's merge.
    Row 3: fully plain, no merge anywhere — the control row.
    """
    import docx

    document = docx.Document()
    table = document.add_table(rows=4, cols=4)

    table.cell(0, 0).text = "A0"
    horizontally_merged = table.cell(0, 1).merge(table.cell(0, 3))
    horizontally_merged.text = "HSPAN"

    table.cell(1, 0).text = "A1"
    vertically_merged = table.cell(1, 1).merge(table.cell(2, 1))
    vertically_merged.text = "VSPAN"
    table.cell(1, 2).text = "C1"
    table.cell(1, 3).text = "D1"

    table.cell(2, 0).text = "A2"
    table.cell(2, 2).text = "C2"
    table.cell(2, 3).text = "D2"

    table.cell(3, 0).text = "A3"
    table.cell(3, 1).text = "B3"
    table.cell(3, 2).text = "C3"
    table.cell(3, 3).text = "D3"

    document.save(path)


def test_horizontally_merged_cell_text_is_not_repeated(tmp_path):
    path = tmp_path / "mixed_merges.docx"
    _build_mixed_merge_table(path)

    lines = _doc_docx(path).split("\n")

    assert lines[0] == "A0 | HSPAN |  | ", (
        "the gridSpan=3 cell must contribute its text ONCE; the two extra "
        "grid columns it spans must come out as empty segments, not repeats "
        f"of 'HSPAN' — got {lines[0]!r}"
    )
    assert lines[0].count("HSPAN") == 1


def test_merged_row_keeps_the_same_column_count_as_an_unmerged_row(tmp_path):
    path = tmp_path / "mixed_merges.docx"
    _build_mixed_merge_table(path)

    lines = _doc_docx(path).split("\n")

    columns_merged_row = lines[0].split(" | ")
    columns_plain_row = lines[3].split(" | ")
    assert len(columns_merged_row) == len(columns_plain_row) == 4, (
        "blanking a repeated cell must not drop it from the row — column "
        "count (and therefore '|' alignment across rows of the same table) "
        "must stay the same whether or not a row has a merge"
    )


def test_vertically_merged_continuation_cell_behavior_is_unchanged(tmp_path):
    """Out of scope for this fix, pinned so it stays a deliberate choice.

    Row 1 (the vMerge master) and row 2 (the vMerge continuation) both carry
    "VSPAN" in the flat output — `python-docx` resolves the continuation
    cell to a `_tc` from row 1, a DIFFERENT row than row 2's own `_tc`
    objects, so `_unique_row_cell_texts`'s per-row `seen_tc_ids` never sees
    it twice and does not blank it. Fixing cross-row duplication from
    `vMerge` is explicitly future work, not this task.
    """
    path = tmp_path / "mixed_merges.docx"
    _build_mixed_merge_table(path)

    lines = _doc_docx(path).split("\n")

    assert lines[1] == "A1 | VSPAN | C1 | D1"
    assert lines[2] == "A2 | VSPAN | C2 | D2"


def test_plain_row_is_unaffected_by_the_fix(tmp_path):
    path = tmp_path / "mixed_merges.docx"
    _build_mixed_merge_table(path)

    lines = _doc_docx(path).split("\n")

    assert lines[3] == "A3 | B3 | C3 | D3"


# ---------------------------------------------------------------------------
# Regression on the real file named in CHUNK-47-2021-dieu-tra. Local data,
# `data/` is .gitignore'd (not source code) — same skip pattern as
# `tests/t2_3_chunking/test_o_leaf_split_by_single_line.py`.
# ---------------------------------------------------------------------------

CORPUS_FILE = (
    REPO_ROOT / "data" / "test-corpus-vn-admin" / "ban-giam-doc-quan-tri"
    / "47_2021_nd-cp_470561.docx"
)


def test_47_2021_ndcp_longest_line_is_now_under_the_chunk_cap():
    if not CORPUS_FILE.is_file():
        import pytest

        pytest.fail(
            f"Missing corpus file: {CORPUS_FILE}. Local data, not tracked in "
            "git — see data/test-corpus-vn-admin/MANIFEST.md."
        )

    lines = _doc_docx(CORPUS_FILE).split("\n")
    longest = max(len(line) for line in lines)

    # 5000 is `chunk_length_cap` (config/ingestion.yaml) — the two gridSpan=10
    # rows measured 5.431/5.831 chars before this fix (CHUNK-47-2021-dieu-tra)
    # and 787 chars after it, so any margin well under 5000 confirms the
    # duplication is gone, not just shrunk.
    assert longest < 5000, (
        f"longest line is {longest} chars — the gridSpan duplication that "
        "caused KhoiVuotTranKhongTheChia on this file appears to still be "
        "present"
    )
