"""T2.8 (p) — docs/10 §1 T4: `purge_document_permanently` must verify the
document actually lives in `space_id`, checked against whichever evidence
survives the run.

`08` T2.8 "Cập nhật 23/9/2026" names the trap this file is built to catch: a
resumable delete is only really resumable if a WRONG `space_id` on the retry
is refused too, using the deletion_log line a previous, interrupted call
already left — not just the profile, which step 2 has by then removed.

Three branches, in the order `_check_object_in_space` checks them:

1. the profile is still present — the common case (test_a covers the happy
   path; this file adds the mismatch);
2. the profile is gone, but the deletion_log line a previous call wrote
   survives it;
3. neither exists — covered in `test_m` (rewritten alongside this file).
"""

from __future__ import annotations

import pytest

from fault_injection import InjectedCrash, crash_after
from ingestion.deletion import ObjectNotInSpace, purge_document_permanently


# --------------------------------------------------------------------------- #
# Branch 1 — profile still present
# --------------------------------------------------------------------------- #


def test_matching_space_id_against_the_profile_proceeds(world, deletion_kwargs):
    outcome = purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert outcome.profile_was_present is True
    assert "doc-doomed" not in world.document_ids()


def test_mismatched_space_id_against_the_profile_is_refused(world, deletion_kwargs):
    before = world.snapshot()
    log_count_before = len(world.log.entries())

    with pytest.raises(ObjectNotInSpace):
        purge_document_permanently("doc-doomed", **{**deletion_kwargs, "space_id": "space-it"})

    assert world.snapshot() == before, "a wrong space_id must not touch any store"
    assert len(world.log.entries()) == log_count_before, (
        "a refusal must leave no new deletion_log line (raised before record_started)"
    )


# --------------------------------------------------------------------------- #
# Branch 2 — profile gone, the deletion_log line from a previous, interrupted
# call is the only evidence left of which Space the document came from.
# --------------------------------------------------------------------------- #


def _cut_after_the_profile_is_removed(world, deletion_kwargs) -> None:
    """The exact BẪY state: step 0 has already written `space_id` to the log
    (while the profile still existed), step 2 has committed (profile gone),
    and the process died before step 3."""
    crashing = crash_after(world.profile_store, "delete_document_and_relations")
    with pytest.raises(InjectedCrash):
        purge_document_permanently("doc-doomed", **{**deletion_kwargs, "profile_store": crashing})
    crashing.assert_fired()

    assert "doc-doomed" not in world.document_ids(), "the transaction must have committed"
    assert world.log.entries()[0].space_id == "space-hr", "step 0 recorded it before the profile left"
    assert world.log.entries()[0].purge_completed_at is None


def test_resuming_with_the_correct_space_id_finishes_the_job(world, deletion_kwargs):
    _cut_after_the_profile_is_removed(world, deletion_kwargs)

    outcome = purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert outcome.purge_settled is True
    assert world.cleanup.calls == ["doc-doomed"]
    assert len(world.log.entries()) == 1
    assert world.log.entries()[0].purge_completed_at is not None


def test_resuming_with_the_wrong_space_id_is_refused_not_finished(world, deletion_kwargs):
    _cut_after_the_profile_is_removed(world, deletion_kwargs)
    before = world.snapshot()
    open_entry = world.log.entries()[0]

    with pytest.raises(ObjectNotInSpace):
        purge_document_permanently("doc-doomed", **{**deletion_kwargs, "space_id": "space-it"})

    assert world.snapshot() == before, "the retry must not touch any store further"
    assert world.cleanup.calls == [], "step 3 must not run on a rejected space_id"
    entries = world.log.entries()
    assert len(entries) == 1, "a refusal must not add a second log line"
    assert entries[0] == open_entry, "and must not alter the one already there"
    assert entries[0].purge_completed_at is None, (
        "a rejected retry must NOT be reported as an already-finished deletion"
    )
