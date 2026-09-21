"""T2.5 (e) — `ghi_vao_qdrant` PHẢI thật sự gọi
`schema.embedding_registry.assert_collection_ready_for_contract` trước khi
ghi — không phải một lời gọi trang trí. Chứng minh bằng cách đưa vào một
`ContractConfig` LỆCH con dấu của kho và xác nhận bị từ chối, không có gì
được ghi.
"""

from __future__ import annotations

import dataclasses

import pytest
from schema.config import StoreStampMismatchError, load_contract_config

from ingestion.vectorization import ghi_vao_qdrant

from .conftest import CONTRACT_PATH


def test_contract_lech_dim_bi_tu_choi_khong_ghi_gi(qdrant, pg, stamped_collection):
    contract_that = load_contract_config(CONTRACT_PATH)
    contract_lech = dataclasses.replace(contract_that, embedding_dim=9999)

    with pytest.raises(StoreStampMismatchError):
        ghi_vao_qdrant(
            [],
            qdrant_client=qdrant,
            collection_name=stamped_collection,
            contract_config=contract_lech,
            pg_connection=pg,
        )


def test_contract_khop_that_thi_khong_bi_chan(qdrant, pg, stamped_collection):
    """Đối chứng: cấu hình ĐÚNG khớp con dấu thì bước kiểm không chặn gì
    (danh sách Chunk rỗng — chỉ kiểm cổng con dấu có mở đúng lúc không)."""
    contract_that = load_contract_config(CONTRACT_PATH)
    ghi_vao_qdrant(
        [],
        qdrant_client=qdrant,
        collection_name=stamped_collection,
        contract_config=contract_that,
        pg_connection=pg,
    )
