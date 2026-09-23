"""T2.8 (g) — the transaction claim, stated as something a test can refute.

08 dòng 212 says relations and profile go in **MỘT giao dịch**, which 07 Mục
2 dòng 65 makes possible: *"hai bước xoá quan hệ và hồ sơ nằm chung một cơ sở
dữ liệu nên thành một giao dịch nguyên khối"*.

The observable form of that claim: **no way of cutting this process leaves
relations gone while the profile is still there, or the profile gone while
its relations are still there.** So the test enumerates every cut point in
the run — both sides of every durable step — and checks the invariant at each
one. A future refactor that splits the delete into two calls fails here
without anyone having to remember to add a case for it.
"""

from __future__ import annotations

import pytest

from fault_injection import InjectedCrash, crash_after, crash_before
from ingestion.deletion import purge_document_permanently

PORTS = ("vector_store", "profile_store", "background_cleanup", "deletion_log")
METHODS = {
    "vector_store": ("delete_document_points",),
    "profile_store": ("get_document", "delete_document_and_relations"),
    "background_cleanup": ("purge",),
    "deletion_log": ("get", "record_started", "mark_purged"),
}
CUTS = [
    (port, method, side)
    for port in PORTS
    for method in METHODS[port]
    for side in (crash_before, crash_after)
]


@pytest.mark.parametrize(
    ("port", "method", "side"),
    CUTS,
    ids=[f"{side.__name__}-{port}.{method}" for port, method, side in CUTS],
)
def test_relations_and_profile_are_never_observed_apart(world, deletion_kwargs, port, method, side):
    crashing = side(deletion_kwargs[port], method)
    kwargs = {**deletion_kwargs, port: crashing}

    try:
        purge_document_permanently("doc-doomed", **kwargs)
    except InjectedCrash:
        pass
    crashing.assert_fired()

    profile_gone = "doc-doomed" not in world.document_ids()
    relations_gone = not ({"rel-in", "rel-out"} & world.relation_ids())
    assert profile_gone == relations_gone, (
        "found a cut point where the profile and its relations disagree — "
        "the one transaction of 08 dòng 212 is not one transaction"
    )


@pytest.mark.parametrize(
    ("port", "method", "side"),
    CUTS,
    ids=[f"{side.__name__}-{port}.{method}" for port, method, side in CUTS],
)
def test_every_cut_point_converges_on_the_re_run(world, deletion_kwargs, port, method, side):
    """The other half of acceptance (a): whatever the cut, running the command
    again reaches the same final state. No manual cleanup, no special case."""
    crashing = side(deletion_kwargs[port], method)
    try:
        purge_document_permanently("doc-doomed", **{**deletion_kwargs, port: crashing})
    except InjectedCrash:
        pass
    crashing.assert_fired()

    purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert world.snapshot() == ({"chunk-neighbour-1"}, {"doc-neighbour", "doc-bystander"}, {"rel-elsewhere"})
    assert len(world.log.entries()) == 1
    assert world.log.entries()[0].purge_completed_at is not None
