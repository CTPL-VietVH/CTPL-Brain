"""T2.8 (b) — S6 (07 Mục 6), shortened by 08 dòng 212 for two physical
stores: **kho vector → (quan hệ + hồ sơ, MỘT giao dịch) → dọn nền.**

The order is not a preference. S6: *"Cổng chặn nằm ở KHO VECTOR"* — reverse
it and the chunks stay findable while the profile that gives them their text
is already gone (điều cấm #17).
"""

from __future__ import annotations

from fault_injection import CallRecorder
from ingestion.deletion import purge_document_permanently


def test_vector_store_first_then_the_one_transaction_then_cleanup(world, deletion_kwargs):
    order: list[str] = []
    deletion_kwargs["vector_store"] = CallRecorder(
        world.vector_store, label="vector", sink=order
    )
    deletion_kwargs["profile_store"] = CallRecorder(
        world.profile_store, label="postgres", sink=order
    )
    deletion_kwargs["background_cleanup"] = CallRecorder(
        world.cleanup, label="cleanup", sink=order
    )
    deletion_kwargs["deletion_log"] = CallRecorder(world.log, label="log", sink=order)

    purge_document_permanently("doc-doomed", **deletion_kwargs)

    durable_steps = [
        call
        for call in order
        if call
        in {
            "vector.delete_document_points",
            "postgres.delete_document_and_relations",
            "cleanup.purge",
        }
    ]
    assert durable_steps == [
        "vector.delete_document_points",
        "postgres.delete_document_and_relations",
        "cleanup.purge",
    ]


def test_the_log_line_is_opened_before_the_first_step_and_closed_after_the_last(
    world, deletion_kwargs
):
    """Step 0 runs first because `space_id`/`tenant_id` stop existing at step
    2, and because a deletion cut halfway has to be visible to somebody
    (NT2: *"chỗ nào bỏ sót gây hại thì phải NHÌN THẤY ĐƯỢC"*)."""
    order: list[str] = []
    deletion_kwargs["vector_store"] = CallRecorder(
        world.vector_store, label="vector", sink=order
    )
    deletion_kwargs["background_cleanup"] = CallRecorder(
        world.cleanup, label="cleanup", sink=order
    )
    deletion_kwargs["deletion_log"] = CallRecorder(world.log, label="log", sink=order)

    purge_document_permanently("doc-doomed", **deletion_kwargs)

    assert order.index("log.record_started") < order.index("vector.delete_document_points")
    assert order.index("cleanup.purge") < order.index("log.mark_purged")


def test_the_log_line_names_the_space_the_document_used_to_be_in(world, deletion_kwargs):
    purge_document_permanently("doc-doomed", **deletion_kwargs)

    entry = world.log.entries()[0]
    assert entry.space_id == "space-hr"
    assert entry.tenant_id == "tenant-1"
