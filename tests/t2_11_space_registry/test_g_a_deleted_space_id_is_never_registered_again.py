"""T2.11 (g) — case 7: registering a `space_id` that has already been deleted
is refused.

docs/10 §4.0: *"`space_id` đã xoá thì **không được đăng ký lại** (`409
SPACE_BEING_DELETED`) — tránh tài liệu cũ trong nhật ký bị hiểu nhầm là thuộc
Space mới trùng mã."* 08 T2.11: *"`space_id` đã xoá không được đăng ký lại."*

The reason is in the deletion log. 06 Mục 5.6 keeps *"ai, khi nào, tài liệu
nào, lý do"* forever, and the line carries `space_id`. Hand that code to a new
Space and the old lines start describing the new Space's history — an audit
trail that is wrong without being empty, which is the worst kind.

The idempotent cases are here too, because "refuse a re-registration" and
"repeat a registration harmlessly" are the same method taking opposite
branches, and a fix to one is exactly what tends to break the other.
"""

from __future__ import annotations

import pytest

from ingestion.space_deletion import delete_space
from ingestion.space_registry import (
    InMemorySpaceRegistry,
    SpaceCannotBeRegisteredAgain,
    SpaceState,
)

from .conftest import DOOMED_SPACE


def test_registering_a_deleted_space_id_again_is_refused(
    world, space_deletion_kwargs
) -> None:
    delete_space(DOOMED_SPACE, **space_deletion_kwargs)
    assert world.registry.get(DOOMED_SPACE).state is SpaceState.DELETED

    with pytest.raises(SpaceCannotBeRegisteredAgain):
        world.registry.register(DOOMED_SPACE)

    assert world.registry.get(DOOMED_SPACE).state is SpaceState.DELETED, (
        "the refused registration must not have reopened anything"
    )


def test_registering_a_space_that_is_still_being_deleted_is_refused(
    world, space_deletion_kwargs
) -> None:
    """Not named explicitly in docs/10, and refused on the same grounds plus
    one: a re-registration mid-deletion would race the loop still emptying
    that Space, and documents accepted in that window would be walked past."""
    world.registry.advance_state(DOOMED_SPACE, to=SpaceState.BEING_DELETED)

    with pytest.raises(SpaceCannotBeRegisteredAgain):
        world.registry.register(DOOMED_SPACE)

    assert world.registry.get(DOOMED_SPACE).state is SpaceState.BEING_DELETED


def test_registering_a_space_that_is_in_use_is_idempotent() -> None:
    """docs/10 §4.0: *"Gọi lại cùng `space_id` đang dùng → trả kết quả như lần
    đầu (idempotent)."* Backend retrying a `POST /v1/spaces` after a timeout
    must not get an error — the Space is exactly as it asked for."""
    registry = InMemorySpaceRegistry()

    first = registry.register("space-new")
    second = registry.register("space-new")

    assert first == second
    assert second.state is SpaceState.IN_USE
    assert len(registry.registrations()) == 1, "no twin row"


def test_a_fresh_space_id_is_still_registrable_after_another_one_is_deleted(
    world, space_deletion_kwargs
) -> None:
    """The refusal is about reusing a CODE, not about the register becoming
    read-only once something has been deleted."""
    delete_space(DOOMED_SPACE, **space_deletion_kwargs)

    registration = world.registry.register("space-brand-new")

    assert registration.state is SpaceState.IN_USE
