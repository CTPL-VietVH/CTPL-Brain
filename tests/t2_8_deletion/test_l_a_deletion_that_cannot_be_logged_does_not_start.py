"""T2.8 (l) — 06 Mục 5.6 names four things the log must keep. Three of them
come from the caller, and a blank one is refused before any store is touched.

The log is not paperwork wrapped around the deletion — after step 3 it is the
only thing left. A deletion whose log line would say "somebody, for some
reason" has already lost what R3 exists to provide.
"""

from __future__ import annotations

import pytest

from ingestion.deletion import DeletionRequestIncomplete, purge_document_permanently


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("space_id", ""),
        ("space_id", "   "),
        ("deleted_by", ""),
        ("deleted_by", "   "),
        ("reason", ""),
        ("reason", "\t\n"),
    ],
)
def test_a_blank_required_field_is_refused(world, deletion_kwargs, field, value):
    before = world.snapshot()

    with pytest.raises(DeletionRequestIncomplete) as refusal:
        purge_document_permanently("doc-doomed", **{**deletion_kwargs, field: value})

    assert field in str(refusal.value)
    assert world.snapshot() == before, "the refusal must come before the first step"
    assert world.log.entries() == []


@pytest.mark.parametrize("document_id", ["", "  "])
def test_a_blank_document_id_is_refused_too(world, deletion_kwargs, document_id):
    before = world.snapshot()

    with pytest.raises(DeletionRequestIncomplete):
        purge_document_permanently(document_id, **deletion_kwargs)

    assert world.snapshot() == before
