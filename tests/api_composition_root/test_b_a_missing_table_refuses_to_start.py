"""Item 3 of the work order: *"Lúc khởi động dịch vụ CHỈ KIỂM bảng đã có;
thiếu → từ chối khởi động, không tự tạo ngầm."*

Runs against the REAL, disposable PostgreSQL `pg` fixture builds (see
`conftest.py`) — a table dropped from a fake in-memory dict would prove
nothing about the actual `information_schema.tables` query
`_assert_tables_exist` runs.
"""

from __future__ import annotations

import pytest

from api.main import MissingTablesError, _REQUIRED_TABLES, _assert_tables_exist


@pytest.mark.parametrize("missing_table", _REQUIRED_TABLES)
def test_b_a_missing_table_is_named_in_the_refusal(pg, missing_table: str) -> None:
    pg.execute(f"DROP TABLE IF EXISTS {missing_table} CASCADE")

    with pytest.raises(MissingTablesError) as excinfo:
        _assert_tables_exist(pg)

    assert missing_table in str(excinfo.value), (
        f"The refusal must name the missing table. Got: {excinfo.value}"
    )


def test_b_a_complete_set_of_tables_passes(pg) -> None:
    """The control case — `pg` already created every required table."""
    _assert_tables_exist(pg)  # must not raise


def test_b_build_deployment_app_refuses_before_any_qdrant_call(
    pg, qdrant, deployment_env, config_dir, complete_environ, fake_model
) -> None:
    """The table check runs BEFORE the Qdrant stamp check — item 1's order
    ("mở PostgreSQL + Qdrant; kiểm con dấu kho vector... trước khi nhận lời
    gọi") only makes sense if a deployment with no tables at all fails fast
    on the store it can check first, rather than reaching into Qdrant with a
    collection that was never provisioned either.
    """
    from api.main import build_deployment_app

    pg.execute("DROP TABLE IF EXISTS document CASCADE")

    with pytest.raises(MissingTablesError):
        build_deployment_app(
            config_dir=config_dir,
            environ=complete_environ,
            deployment=deployment_env,
            pg_connection=pg,
            qdrant_client=qdrant,
            embedding_model=fake_model,
        )
