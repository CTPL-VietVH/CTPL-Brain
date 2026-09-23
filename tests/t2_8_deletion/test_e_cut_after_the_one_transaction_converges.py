"""T2.8 (e) — cut the process AFTER step 2, before dọn nền.

Both stores are now clean, but S6 is explicit that the job is not finished:
*"nghĩa vụ xoá dữ liệu cá nhân chỉ được coi là hoàn thành khi bước dọn nền ĐÃ
CHẠY XONG, không phải khi người dùng bấm xoá."* The log line must therefore
still be open, and the re-run must close it.
"""

from __future__ import annotations

import pytest

from fault_injection import InjectedCrash, crash_after
from ingestion.deletion import purge_document_permanently


def test_the_log_stays_open_until_the_cleanup_has_run(world, deletion_kwargs):
    crashing = crash_after(world.profile_store, "delete_document_and_relations")
    with pytest.raises(InjectedCrash):
        purge_document_permanently("doc-doomed", **{**deletion_kwargs, "profile_store": crashing})
    crashing.assert_fired()

    assert world.snapshot() == ({"chunk-neighbour-1"}, {"doc-neighbour", "doc-bystander"}, {"rel-elsewhere"})
    assert world.cleanup.calls == [], "step 3 never ran"
    assert world.log.entries()[0].purge_completed_at is None

    outcome = purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert world.cleanup.calls == ["doc-doomed"]
    assert outcome.purge_settled is True
    assert world.log.entries()[0].purge_completed_at is not None
    assert len(world.log.entries()) == 1
    assert outcome.vector_points_deleted == 0
    assert outcome.relations_deleted == 0
    assert outcome.profile_rows_deleted == 0
