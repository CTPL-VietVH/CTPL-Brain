"""T2.8 (o) — *"ai"* in 06 Mục 5.6 means the person who ordered the deletion,
not the last person to run the command.

`record_started` is insert-if-absent for this reason: an operator clearing a
crashed job is not the Manager who decided the document should go, and a log
that names the operator has quietly lost the fact R3 exists to preserve.
"""

from __future__ import annotations

import pytest

from fault_injection import InjectedCrash, crash_after
from ingestion.deletion import purge_document_permanently


def test_the_first_actor_and_reason_survive_the_retry(world, deletion_kwargs):
    crashing = crash_after(world.vector_store, "delete_document_points")
    with pytest.raises(InjectedCrash):
        purge_document_permanently("doc-doomed", **{**deletion_kwargs, "vector_store": crashing})
    crashing.assert_fired()

    purge_document_permanently(
        "doc-doomed",
        **{**deletion_kwargs, "deleted_by": "ops-duty", "reason": "dọn job treo"},
    )

    entries = world.log.entries()
    assert len(entries) == 1
    assert entries[0].deleted_by == "manager-lan"
    assert entries[0].reason.startswith("Người upload đưa nhầm")
