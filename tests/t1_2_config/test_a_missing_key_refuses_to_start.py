"""T1.2 (a) — ⭐ "Xong khi" của chính hạng mục này (docs/08 T1.2):

    "có một test **chạy service với file cấu hình thiếu LẦN LƯỢT TỪNG KHOÁ**, và
    mỗi lần đều khẳng định service không khởi động được, báo rõ thiếu khoá nào."

Và ghi chú kèm theo, chính là lý do file này parametrize thay vì kiểm một khoá
đại diện:

    "Nói 'không được đặt mặc định trong mã' là chưa đủ — nó vẫn có thể nằm ngay
    trước chỗ dùng. Test theo từng khoá là cách duy nhất bắt được."

Điểm xuất phát của mỗi ca là BA FILE CẤU HÌNH THẬT trong `config/`: đọc file
thật, bỏ đi đúng một khoá, ghi ra thư mục tạm, rồi nạp. Nhờ vậy thêm một tham số
mới vào file thật là tự động có thêm một ca thử — không ai phải nhớ cập nhật
test.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest
import yaml

from schema import config as config_module
from schema.config import (
    ConfigFileNotFoundError,
    ConfigValueError,
    DistanceMetric,
    MissingConfigKeyError,
    UnknownConfigKeyError,
    load_contract_config,
    load_ingestion_config,
    load_retrieval_config,
)

#: Thư mục repo — tính lại ở đây (không dùng fixture) vì danh sách ca thử dưới
#: đây phải dựng xong TRƯỚC khi pytest chạy fixture nào.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: (tên nhóm, tên file, hàm nạp) — ba nhóm, ba nơi, không chồng lấn.
GROUPS = (
    ("contract", "contract.yaml", load_contract_config),
    ("ingestion", "ingestion.yaml", load_ingestion_config),
    ("retrieval", "retrieval.yaml", load_retrieval_config),
)

ALL_LOADERS = (load_contract_config, load_ingestion_config, load_retrieval_config)


def _real_mapping(filename: str) -> dict:
    """Đọc file cấu hình THẬT thành dict (không qua lớp nạp có kiểu)."""
    with (REPO_ROOT / "config" / filename).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


#: Mọi cặp (nhóm, khoá) — "lần lượt TỪNG khoá" của docs/08 T1.2.
#:
#: ⚠️ Danh sách ca thử lấy từ CHÍNH BA FILE CẤU HÌNH THẬT, **không** lấy từ
#: `CONTRACT_KEYS`/`INGESTION_KEYS`/`RETRIEVAL_KEYS` trong `schema.config`. Nếu
#: lấy từ đó thì ca thử và thứ bị thử cùng đọc một danh sách: ai gỡ một khoá
#: khỏi danh sách rồi đặt mặc định trong mã sẽ gỡ luôn ca thử của chính khoá đó,
#: và cả bộ test vẫn xanh. Lấy từ file thật thì hành vi đó làm test ĐỎ.
#: (`test_d_three_groups_do_not_overlap.py` khoá chặt chiều còn lại: tập khoá
#: trong file thật phải TRÙNG KHÍT tập khoá bắt buộc của module.)
EVERY_KEY = [
    pytest.param(group, filename, loader, key, id=f"{group}:{key}")
    for group, filename, loader in GROUPS
    for key in _real_mapping(filename)
]


def _write(tmp_path: pathlib.Path, filename: str, data) -> pathlib.Path:
    path = tmp_path / filename
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
    return path


@pytest.mark.parametrize("group, filename, loader, missing_key", EVERY_KEY)
def test_missing_each_key_refuses_to_start_and_names_the_key(
    tmp_path, group, filename, loader, missing_key
):
    """⭐ Thiếu LẦN LƯỢT TỪNG khoá → không nạp được, và báo ĐÚNG TÊN khoá thiếu.

    Nếu một ngày ai đó viết `data.get("document_cap", 6)` "cho tiện" thì đúng ca
    `retrieval:document_cap` ở đây chuyển xanh-sang-đỏ-ngược: nó sẽ KHÔNG raise
    nữa, và test đỏ. Đó là toàn bộ lý do tồn tại của file này.
    """
    data = _real_mapping(filename)
    assert missing_key in data, (
        f"File cấu hình thật {filename} đang thiếu `{missing_key}` — "
        "sửa file cấu hình, không sửa test."
    )
    del data[missing_key]
    path = _write(tmp_path, filename, data)

    with pytest.raises(MissingConfigKeyError) as excinfo:
        loader(path)

    message = str(excinfo.value)
    assert f"`{missing_key}`" in message, (
        f"Thông báo lỗi phải nêu ĐÚNG TÊN khoá thiếu. Nhận được: {message}"
    )
    assert str(path) in message, (
        f"Thông báo lỗi phải nêu file cấu hình liên quan. Nhận được: {message}"
    )


@pytest.mark.parametrize("group, filename, loader", GROUPS)
def test_empty_config_file_refuses_to_start(tmp_path, group, filename, loader):
    """File rỗng KHÔNG được đọc thành "không có khoá nào, dùng mặc định"."""
    path = tmp_path / filename
    path.write_text("", encoding="utf-8")

    with pytest.raises(ConfigValueError) as excinfo:
        loader(path)
    assert str(path) in str(excinfo.value)


@pytest.mark.parametrize("group, filename, loader", GROUPS)
def test_absent_config_file_refuses_to_start(tmp_path, group, filename, loader):
    """Không có file cấu hình cũng phải nổ — không im lặng chạy bằng mã."""
    path = tmp_path / filename

    with pytest.raises(ConfigFileNotFoundError) as excinfo:
        loader(path)
    assert str(path) in str(excinfo.value)


@pytest.mark.parametrize("group, filename, loader", GROUPS)
def test_typo_in_key_name_is_reported_as_unknown_key(tmp_path, group, filename, loader):
    """Gõ sai tên khoá: nổ CẢ hai đầu — thiếu khoá thật, và có khoá lạ.

    Đây cũng là lưới bắt một tham số bị đặt NHẦM NHÀ giữa ba nhóm
    (07 Mục 3.3 quy tắc 2).
    """
    data = _real_mapping(filename)
    real_key = next(iter(data))
    data[f"{real_key}_typo"] = data.pop(real_key)
    path = _write(tmp_path, filename, data)

    with pytest.raises((MissingConfigKeyError, UnknownConfigKeyError)) as excinfo:
        loader(path)
    message = str(excinfo.value)
    assert real_key in message


def test_old_scan_time_budget_minutes_key_is_no_longer_valid(tmp_path):
    """`scan_time_budget_minutes` là tên CŨ (PO chốt 18/9/2026: giữ đúng tên đã
    chốt trong 07 Mục 3.2/CLAUDE.md Mục 4 — `scan_time_budget`). Ai vẫn gõ tên
    cũ vào `config/ingestion.yaml` thì thiếu khoá THẬT `scan_time_budget`, và
    `_check_keys` kiểm MISSING trước UNKNOWN — nên phải thấy đúng
    `MissingConfigKeyError` nêu tên `scan_time_budget`, không phải một
    `UnknownConfigKeyError` nêu tên cũ.
    """
    data = _real_mapping("ingestion.yaml")
    assert "scan_time_budget" in data and "scan_time_budget_minutes" not in data, (
        "File cấu hình thật đổi tên khoá rồi mà ca này vẫn giả định tên cũ — "
        "kiểm lại config/ingestion.yaml trước khi kiểm test"
    )
    data["scan_time_budget_minutes"] = data.pop("scan_time_budget")
    path = _write(tmp_path, "ingestion.yaml", data)

    with pytest.raises(MissingConfigKeyError) as excinfo:
        load_ingestion_config(path)

    message = str(excinfo.value)
    assert "`scan_time_budget`" in message, (
        f"Thiếu khoá thật `scan_time_budget` phải được nêu tên. Nhận được: {message}"
    )


def test_no_loader_has_a_default_argument():
    """⛔ Không hàm nạp nào được có tham số mặc định (07 Mục 3.3 quy tắc 3).

    Một đường dẫn mặc định hay một giá trị mặc định nấp trong chữ ký hàm là cái
    nhà thứ hai của tham số, chỉ khác chỗ đứng.
    """
    for loader in ALL_LOADERS:
        signature = inspect.signature(loader)
        for name, parameter in signature.parameters.items():
            assert parameter.default is inspect.Parameter.empty, (
                f"{loader.__name__}({name}=...) có giá trị mặc định — "
                "vi phạm 07 Mục 3.3 quy tắc 3."
            )


def test_config_module_never_calls_dict_get():
    """Chặn ở mức CÂY CÚ PHÁP: `.get(` là lối vào quen thuộc của mặc định ngầm.

    Bắt cả `data.get("document_cap", 6)` lẫn `data.get("document_cap")` — cái
    thứ hai trả về `None` rồi hỏng ở đâu đó xa chỗ gây lỗi, còn tệ hơn.

    Quét bằng `ast` chứ không bằng tìm chuỗi, để chính lời cảnh báo trong
    docstring của module (nhắc tên `dict.get`) không tự làm test đỏ — một test
    cấm người ta VIẾT VỀ vấn đề là một test dạy người ta im lặng.
    """
    tree = ast.parse(inspect.getsource(config_module))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
    ]
    assert not offenders, (
        "packages/schema/config.py gọi `.get(` để đọc khoá cấu hình tại dòng "
        f"{offenders} — thiếu khoá phải nổ, không được có đường lùi."
    )


@pytest.mark.parametrize(
    "filename, loader, key, bad_value",
    [
        ("contract.yaml", load_contract_config, "embedding_dim", "1024"),
        ("retrieval.yaml", load_retrieval_config, "document_cap", True),
        ("retrieval.yaml", load_retrieval_config, "relation_pull_threshold", 30),
        ("ingestion.yaml", load_ingestion_config, "saturation_rounds", 0),
        ("contract.yaml", load_contract_config, "distance_metric", "cosinus"),
    ],
)
def test_wrong_typed_or_out_of_range_value_refuses_to_start(
    tmp_path, filename, loader, key, bad_value
):
    """Khoá có mặt nhưng giá trị vô nghĩa cũng phải nổ, nêu rõ khoá nào.

    `"1024"` (chuỗi) và `true` (bool, vốn là con của `int` trong Python) là hai
    ca trượt êm nhất; `30` cho một tham số thang 0–1 là ca gõ nhầm 0.3 thành 30.
    """
    data = _real_mapping(filename)
    data[key] = bad_value
    path = _write(tmp_path, filename, data)

    with pytest.raises(ConfigValueError) as excinfo:
        loader(path)
    assert key in str(excinfo.value)


@pytest.mark.parametrize("bad_metric", ["dot", "euclid"])
def test_distance_metric_locked_to_cosine_in_v1(tmp_path, bad_metric):
    """PO chốt 18/9/2026: v1 khoá cứng `distance_metric` CHỈ nhận `cosine`, dù
    enum `DistanceMetric` vẫn giữ `dot`/`euclid` cho R5 (đổi mô hình bằng cấu
    hình, không sửa mã). docs/07 Mục 3.1: "CHỐT: cosine" — dot/euclid tụt chất
    lượng tìm kiếm ÂM THẦM, không lỗi nào báo, nên phải chặn ngay ở loader,
    không đợi tới lúc so con dấu trên kho (đó là lớp phòng thủ KHÁC, ở T1.3).
    """
    data = _real_mapping("contract.yaml")
    data["distance_metric"] = bad_metric
    path = _write(tmp_path, "contract.yaml", data)

    with pytest.raises(ConfigValueError) as excinfo:
        load_contract_config(path)

    message = str(excinfo.value)
    assert bad_metric in message
    assert "cosine" in message
    assert "Mục 3.1" in message


def test_distance_metric_cosine_still_loads_normally(tmp_path):
    """Khoá cứng ở trên KHÔNG được đổi hành vi hiện tại: `cosine` (giá trị
    thật trong `config/contract.yaml`) vẫn phải nạp bình thường, không raise.
    """
    data = _real_mapping("contract.yaml")
    assert data["distance_metric"] == "cosine", (
        "File cấu hình thật không còn dùng cosine — kiểm lại config/contract.yaml "
        "trước khi kiểm test này"
    )
    path = _write(tmp_path, "contract.yaml", data)

    contract = load_contract_config(path)
    assert contract.distance_metric == DistanceMetric.COSINE
