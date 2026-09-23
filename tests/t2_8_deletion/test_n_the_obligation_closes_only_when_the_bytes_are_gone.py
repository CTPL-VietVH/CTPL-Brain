"""T2.8 (n) — S6: *"xoá ở kho vector thường chỉ là xoá logic, dữ liệu chỉ
thật sự mất sau bước dọn nền"*, and therefore *"nghĩa vụ xoá dữ liệu cá nhân
chỉ được coi là hoàn thành khi bước dọn nền ĐÃ CHẠY XONG"*.

So an engine that has not finished reclaiming is not a failure — it is a "run
me again". What must not happen is the log calling the job done anyway.
"""

from __future__ import annotations

from ingestion.deletion import InMemoryBackgroundCleanup, purge_document_permanently


def test_an_unsettled_cleanup_leaves_the_log_line_open(world, deletion_kwargs):
    unsettled = InMemoryBackgroundCleanup(settles=False)

    outcome = purge_document_permanently(
        "doc-doomed", **{**deletion_kwargs, "background_cleanup": unsettled}
    )

    assert outcome.purge_settled is False
    assert world.log.entries()[0].purge_completed_at is None, (
        "the rows are gone but the bytes are not — the obligation is not discharged"
    )
    # The stores themselves are already clean; only the reclaim is pending.
    assert world.snapshot() == ({"chunk-neighbour-1"}, {"doc-neighbour", "doc-bystander"}, {"rel-elsewhere"})


def test_a_later_run_closes_it_once_the_engines_report_done(world, deletion_kwargs):
    unsettled = InMemoryBackgroundCleanup(settles=False)
    purge_document_permanently("doc-doomed", **{**deletion_kwargs, "background_cleanup": unsettled})

    outcome = purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert outcome.purge_settled is True
    assert world.log.entries()[0].purge_completed_at is not None
    assert len(world.log.entries()) == 1
