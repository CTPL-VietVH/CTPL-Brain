"""T2.8 (m) — docs/10 §1 T4, branch 3 of `_check_object_in_space`: a document
id with no evidence at all — no profile, no deletion_log line — is not
"nothing to do". It is refused, the same as a Space mismatch.

A document this module has genuinely ever touched always leaves a
deletion_log line naming a Space (step 0 records it, from the profile, before
step 2 can remove that profile). So "no profile AND no log line" can only
mean the id never existed anywhere this module knows about; completing
silently here would let a caller pass ANY `space_id` for an id it invented
and have this command agree — exactly the hole T4 exists to close.

This replaces the previous version of this file, which asserted the opposite
(an unknown id was "not an error") — that was correct before T4 existed and
is the exact case T4 changes.
"""

from __future__ import annotations

import pytest

from ingestion.deletion import ObjectNotInSpace, purge_document_permanently


def test_an_unknown_document_id_is_refused_not_silently_completed(world, deletion_kwargs):
    before = world.snapshot()
    log_count_before = len(world.log.entries())

    with pytest.raises(ObjectNotInSpace):
        purge_document_permanently("doc-never-existed", **deletion_kwargs)

    assert world.snapshot() == before, "no store may be touched for an unknown document"
    assert world.cleanup.calls == [], "step 3 must not run"
    assert len(world.log.entries()) == log_count_before, "a refusal leaves no log line"


def test_a_profile_gone_with_no_matching_log_line_is_the_same_unknown_case(world, deletion_kwargs):
    """The state test (d)/(e)/(p) leave behind — profile gone after a real
    interrupted run — always comes WITH an open deletion_log line, because
    step 0 runs before step 2 removes the profile. Popping the profile
    directly, with no log line ever written, is not that state: it is
    indistinguishable from an id that never existed, and must be refused the
    same way, not treated as "the deletion continuing"."""
    world.inner_store._documents.pop("doc-doomed")
    before_points = world.point_ids()

    with pytest.raises(ObjectNotInSpace):
        purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert world.point_ids() == before_points, "the orphaned vectors must be left alone too"
    assert world.log.entries() == []
