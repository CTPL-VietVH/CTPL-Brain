"""T2.8 (f) — cut the process AFTER step 3, before the log line is closed.

Everything is deleted and the bytes are gone, but the log still claims the
deletion is in flight. The re-run must close it, and must not write a second
line while doing so.
"""

from __future__ import annotations

import pytest

from fault_injection import InjectedCrash, crash_after
from ingestion.deletion import purge_document_permanently


def test_the_re_run_closes_the_open_log_line_without_duplicating_it(world, deletion_kwargs):
    crashing = crash_after(world.cleanup, "purge")
    with pytest.raises(InjectedCrash):
        purge_document_permanently(
            "doc-doomed", **{**deletion_kwargs, "background_cleanup": crashing}
        )
    crashing.assert_fired()

    assert world.snapshot() == ({"chunk-neighbour-1"}, {"doc-neighbour", "doc-bystander"}, {"rel-elsewhere"})
    assert world.log.entries()[0].purge_completed_at is None

    outcome = purge_document_permanently("doc-doomed", **deletion_kwargs)

    entries = world.log.entries()
    assert len(entries) == 1
    assert entries[0].purge_completed_at is not None
    assert outcome.already_completed is False, (
        "the previous run never finished, so this one is the finishing run"
    )
