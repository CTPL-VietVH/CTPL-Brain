"""T1.2 (b) — Cấu hình hợp đồng lệch CON DẤU TRÊN KHO thì TỪ CHỐI CHẠY.

07 Mục 3.1 ràng buộc 2: mỗi service so cấu hình của mình với **con dấu của kho
nó đang đọc**, KHÔNG so với service kia — "cách này bắt được cả trường hợp hai
service khớp nhau nhưng cả hai cùng lệch với kho".

Phạm vi ở đây là PHẦN QUYẾT ĐỊNH, thuần logic: `StoreStamp` dựng tay, không nối
Qdrant/PostgreSQL. Chọn nhà thật cho `embedding_model` trên kho và đọc con dấu
thật lúc khởi động là T1.3 (docs/08 dòng T1.3) — tests/t0_1_stores/
test_b_store_stamp.py đã chứng minh cả hai nhà đều chạy được và cố ý chưa chọn.

Hai tên mô hình dùng ở đây lấy đúng cặp T0.1 đã dùng, vì **cả hai đều 1024
chiều** — đó là cái bẫy làm nên "ca khó nhất".
"""

from __future__ import annotations

import pytest

from schema.config import (
    ContractConfig,
    DistanceMetric,
    StoreStamp,
    StoreStampMismatchError,
    assert_contract_matches_store_stamp,
)

MODEL_A = "BAAI/bge-m3"
MODEL_B = "intfloat/multilingual-e5-large"  # CŨNG 1024 chiều — đó là cái bẫy
DIM = 1024
OTHER_DIM = 768

STORE = "cbrain_chunks"


def _config(*, model=MODEL_A, dim=DIM, metric=DistanceMetric.COSINE) -> ContractConfig:
    return ContractConfig(embedding_model=model, embedding_dim=dim, distance_metric=metric)


def _stamp(*, model=MODEL_A, dim=DIM, metric=DistanceMetric.COSINE) -> StoreStamp:
    return StoreStamp(embedding_model=model, embedding_dim=dim, distance_metric=metric)


def test_matching_config_and_stamp_passes_silently():
    """Khớp cả ba trường → trả về None, không ngoại lệ, không cảnh báo."""
    assert assert_contract_matches_store_stamp(_config(), _stamp(), store_name=STORE) is None


def test_model_mismatch_refuses_to_start():
    with pytest.raises(StoreStampMismatchError) as excinfo:
        assert_contract_matches_store_stamp(_config(model=MODEL_B), _stamp(), store_name=STORE)

    message = str(excinfo.value)
    assert "embedding_model" in message
    assert MODEL_B in message and MODEL_A in message, "Phải nêu CẢ giá trị cấu hình và giá trị trên kho"
    assert STORE in message, "Phải nêu KHO NÀO — một bản cài có thể có nhiều kho"


def test_dim_mismatch_refuses_to_start():
    with pytest.raises(StoreStampMismatchError) as excinfo:
        assert_contract_matches_store_stamp(_config(dim=OTHER_DIM), _stamp(), store_name=STORE)

    message = str(excinfo.value)
    assert "embedding_dim" in message
    assert str(OTHER_DIM) in message and str(DIM) in message


def test_metric_mismatch_refuses_to_start():
    """Lệch thước đo: 07 Mục 3.1 — dot không chuẩn hoá hay euclid thì KHÔNG lỗi
    nào báo, chỉ tụt chất lượng tìm kiếm âm thầm. Nên nó phải bị bắt ở đây.
    """
    with pytest.raises(StoreStampMismatchError) as excinfo:
        assert_contract_matches_store_stamp(
            _config(metric=DistanceMetric.DOT), _stamp(), store_name=STORE
        )

    message = str(excinfo.value)
    assert "distance_metric" in message
    assert "dot" in message and "cosine" in message


def test_hardest_case_same_dim_different_model_refuses_to_start():
    """⭐ CA KHÓ NHẤT (docs/08 T1.3): đổi mô hình mà GIỮ NGUYÊN số chiều.

    Số chiều khớp, thước đo khớp — kho không báo lỗi, phép so vector vẫn chạy,
    kết quả sai lệch âm thầm. 07 Mục 3.1 gọi đây là "rủi ro nặng nhất trong
    nhóm". Con dấu mang tên mô hình là thứ duy nhất bắt được.
    """
    config = _config(model=MODEL_B, dim=DIM)
    stamp = _stamp(model=MODEL_A, dim=DIM)
    assert config.embedding_dim == stamp.embedding_dim, "Số chiều PHẢI khớp — đó là điều làm ca này nguy hiểm"

    with pytest.raises(StoreStampMismatchError) as excinfo:
        assert_contract_matches_store_stamp(config, stamp, store_name=STORE)

    message = str(excinfo.value)
    assert "embedding_model" in message
    assert "embedding_dim" not in message, "Số chiều khớp thì không được báo là lệch"
    assert "SỐ CHIỀU KHỚP" in message, "Ca nguy hiểm nhất phải được gọi tên trong thông báo"


def test_one_service_alone_still_refuses_against_the_store():
    """08 T1.3: chạy MỘT MÌNH Retrieval, không bật Ingestion — vẫn phải từ chối.

    Hàm so khớp không nhận tham số nào mô tả service kia; nó chỉ biết cấu hình
    của mình và con dấu của kho. Ca này khẳng định điều đó ở mức hợp đồng hàm:
    không có đường nào để một service "hỏi service kia cho chắc" rồi cùng nhau
    lệch với kho.
    """
    import inspect

    parameters = inspect.signature(assert_contract_matches_store_stamp).parameters
    assert list(parameters) == ["config", "stamp", "store_name"]

    retrieval_alone = _config(model=MODEL_B)
    with pytest.raises(StoreStampMismatchError):
        assert_contract_matches_store_stamp(retrieval_alone, _stamp(), store_name=STORE)


def test_no_warn_and_continue_mode_exists():
    """"Không có chế độ cảnh báo rồi chạy tiếp" (07 Mục 3.1) — kiểm bằng hành vi.

    Hàm chỉ có hai kết cục: trả `None` khi khớp, raise khi lệch. Không có cờ nào
    làm nó trở thành cảnh báo, và không có giá trị trả về nào để nơi gọi lỡ bỏ
    qua (một `return False` là đủ để ai đó quên `if`).
    """
    import inspect

    signature = inspect.signature(assert_contract_matches_store_stamp)
    assert signature.return_annotation in (None, "None"), (
        "Hàm phải trả None — trả bool là mở đường cho nơi gọi bỏ qua kết quả"
    )
    for name, parameter in signature.parameters.items():
        assert parameter.default is inspect.Parameter.empty, f"`{name}` không được có mặc định"
    assert "strict" not in signature.parameters and "warn_only" not in signature.parameters
