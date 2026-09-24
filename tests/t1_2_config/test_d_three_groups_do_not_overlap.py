"""T1.2 (d) — Ba nhóm cấu hình THẬT: mỗi tham số ĐÚNG MỘT NHÀ, và dấu hiệu đặt
sai phải NGAY CẠNH giá trị (07 Mục 3.3 quy tắc 2 và 4).

⚠️ File này CỐ Ý không khẳng định giá trị cụ thể của mười một tham số. 07 Mục 3.3
quy tắc 5: "Tài liệu này ghi lý do; file cấu hình là nơi có thẩm quyền lúc
chạy... Bảng 3.2 ghi giá trị khởi đầu và vì sao chọn nó, không phải trạng thái
hiện hành." Một test ghim `document_cap == 6` sẽ hoá đỏ đúng vào ngày người vận
hành làm đúng việc mà dấu hiệu đặt sai bảo họ làm (tăng lên 8) — tức là test
biến thành cái nhà thứ ba của tham số. Cái được ghim ở đây là thứ KHÔNG ĐƯỢC
đổi: mỗi tham số một nhà, và tri thức "khi nào biết mình đặt sai" phải sống
ngay cạnh giá trị.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from schema.config import (
    CONTRACT_KEYS,
    INGESTION_KEYS,
    RETRIEVAL_KEYS,
    DistanceMetric,
    load_contract_config,
    load_ingestion_config,
    load_retrieval_config,
)

#: Tham số trong bảng 07 Mục 3.2 → (file cấu hình, khoá trong file).
#: Từ PO chốt 18/9/2026, tên khoá trong file cấu hình khớp Y HỆT tên trong
#: 07 Mục 3.2 cho cả mười một tham số — đơn vị của `scan_time_budget` (phút),
#: `chunk_length_cap` (ký tự Unicode) và `max_upload_bytes` (byte) nằm ở
#: comment cạnh giá trị trong config/ingestion.yaml, không nằm trong tên khoá.
#: Ngoại lệ đã cân nhắc: `source_download_timeout_seconds` mang sẵn đơn vị
#: trong tên vì nó là tham số MỚI (24/9/2026) — 07 Mục 3.2 chốt luôn tên có
#: hậu tố, nên vẫn chỉ có một cách gọi, không phải hai.
ELEVEN_PARAMS = {
    "inheritance_decay": ("retrieval.yaml", "inheritance_decay"),
    "document_cap": ("retrieval.yaml", "document_cap"),
    "cap_warning_multiple": ("retrieval.yaml", "cap_warning_multiple"),
    "relation_pull_threshold": ("retrieval.yaml", "relation_pull_threshold"),
    "saturation_epsilon": ("ingestion.yaml", "saturation_epsilon"),
    "saturation_rounds": ("ingestion.yaml", "saturation_rounds"),
    "scan_pair_budget": ("ingestion.yaml", "scan_pair_budget"),
    "scan_time_budget": ("ingestion.yaml", "scan_time_budget"),
    "chunk_length_cap": ("ingestion.yaml", "chunk_length_cap"),
    "max_upload_bytes": ("ingestion.yaml", "max_upload_bytes"),
    "source_download_timeout_seconds": (
        "ingestion.yaml",
        "source_download_timeout_seconds",
    ),
}


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _flatten_comments(lines: list[str]) -> str:
    """Gộp các dòng ghi chú thành một chuỗi phẳng.

    Bỏ tiền tố `#` và gộp khoảng trắng để so được với nguyên văn trong docs/07
    mà không phụ thuộc chỗ xuống dòng của file cấu hình.
    """
    kept = [
        line.strip().lstrip("#").strip()
        for line in lines
        if line.strip().startswith("#")
    ]
    return _collapse(" ".join(kept))


def _comment_text(path: pathlib.Path) -> str:
    return _flatten_comments(path.read_text(encoding="utf-8").splitlines())


def _wrong_value_signals_from_docs(repo_root: pathlib.Path) -> dict[str, str]:
    """Rút cột "Dấu hiệu đặt sai" của bảng 07 Mục 3.2 ra khỏi chính docs/07.

    Đọc thẳng từ nguồn chân lý thay vì chép vào test: chép là tạo bản thứ hai và
    sẽ có ngày lệch — đúng bệnh mà cả module dùng chung lẫn quy tắc "một nhà"
    sinh ra để chữa.
    """
    doc = (repo_root / "docs" / "07_Hop_Dong_Du_Lieu_Schema_v2.md").read_text(encoding="utf-8")
    section = doc.split("### 3.2")[1].split("### 3.3")[0]

    signals: dict[str, str] = {}
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            continue
        name = re.match(r"`([a-z_]+)`", cells[0])
        if name is None:
            continue
        signals[name.group(1)] = _collapse(cells[3])
    return signals


def test_docs_07_still_lists_exactly_the_eleven_parameters(repo_root):
    """Lưới an toàn cho chính test dưới: nếu bảng 3.2 đổi hình dạng thì biết ngay."""
    signals = _wrong_value_signals_from_docs(repo_root)
    assert set(signals) == set(ELEVEN_PARAMS), (
        "Bảng 07 Mục 3.2 không còn đúng mười một tham số như test đang giả định: "
        f"{sorted(signals)}"
    )


@pytest.mark.parametrize("param", sorted(ELEVEN_PARAMS))
def test_wrong_value_signal_sits_next_to_the_value_verbatim(repo_root, config_dir, param):
    """⭐ 07 Mục 3.3 quy tắc 4 + 08 T1.2: chép NGUYÊN VĂN cột "dấu hiệu đặt sai"
    vào file cấu hình, cạnh từng giá trị.

    "vì v1 không có dòng số liệu nào, đó là chỗ duy nhất tri thức này sống được
    ở nơi người ta dùng tới" — nên xoá ghi chú đi phải làm test đỏ, y như xoá
    một trường bắt buộc.
    """
    filename, key = ELEVEN_PARAMS[param]
    path = config_dir / filename
    signal = _wrong_value_signals_from_docs(repo_root)[param]

    haystack = _comment_text(path)
    assert signal in haystack, (
        f"`{key}` trong {filename} thiếu NGUYÊN VĂN dấu hiệu đặt sai của "
        f"`{param}` (07 Mục 3.2):\n  {signal}"
    )

    lines = path.read_text(encoding="utf-8").splitlines()
    key_line = next(i for i, line in enumerate(lines) if line.startswith(f"{key}:"))
    block = _flatten_comments(lines[max(0, key_line - 20) : key_line])
    assert signal in block, (
        f"Dấu hiệu đặt sai của `{param}` có trong {filename} nhưng KHÔNG nằm ngay "
        f"trên `{key}:` — 07 Mục 3.3 quy tắc 4 đòi nó ở NGAY CẠNH giá trị"
    )


def test_three_groups_share_no_key(contract_path, ingestion_path, retrieval_path):
    """07 Mục 3.3 quy tắc 2: mỗi tham số có ĐÚNG MỘT nhà.

    "hai nơi cùng giữ một giá trị thì sẽ có ngày lệch nhau" — cùng một bệnh đã
    sinh ra module dùng chung.
    """
    groups = {
        "contract.yaml": set(yaml.safe_load(contract_path.read_text(encoding="utf-8"))),
        "ingestion.yaml": set(yaml.safe_load(ingestion_path.read_text(encoding="utf-8"))),
        "retrieval.yaml": set(yaml.safe_load(retrieval_path.read_text(encoding="utf-8"))),
    }

    names = sorted(groups)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            shared = groups[left] & groups[right]
            assert not shared, f"{left} và {right} cùng giữ khoá: {sorted(shared)}"

    assert groups["contract.yaml"] == set(CONTRACT_KEYS)
    assert groups["ingestion.yaml"] == set(INGESTION_KEYS)
    assert groups["retrieval.yaml"] == set(RETRIEVAL_KEYS)


def test_config_keys_do_not_collide_with_env_keys(env_example_path):
    """Tham số KẾT NỐI hạ tầng ở `.env` cũng phải không chồng lấn ba nhóm này.

    `.env.example` tự nói: "Quy tắc 'mỗi tham số đúng một nhà' vẫn giữ nguyên:
    không khoá nào ở đây trùng với bất kỳ khoá nào trong config/."
    """
    env_keys = {
        line.split("=", 1)[0].strip().lower()
        for line in env_example_path.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.strip().startswith("#")
    }
    config_keys = {key.lower() for key in CONTRACT_KEYS + INGESTION_KEYS + RETRIEVAL_KEYS}

    assert not (env_keys & config_keys), f"Khoá trùng nhà: {sorted(env_keys & config_keys)}"


def test_real_config_files_load_with_correct_types(contract_path, ingestion_path, retrieval_path):
    """Ba file thật trong repo nạp được và ra đúng kiểu — không khẳng định GIÁ TRỊ.

    Ngoại lệ duy nhất được ghim giá trị: `distance_metric` phải là một thành
    viên của `DistanceMetric`, vì thước đo sai là thứ 07 Mục 3.1 nói "không có
    lỗi nào báo".
    """
    contract = load_contract_config(contract_path)
    assert isinstance(contract.embedding_model, str) and contract.embedding_model
    assert isinstance(contract.embedding_dim, int) and contract.embedding_dim > 0
    assert isinstance(contract.distance_metric, DistanceMetric)

    ingestion = load_ingestion_config(ingestion_path)
    assert 0 < ingestion.saturation_epsilon <= 1
    assert ingestion.saturation_rounds >= 1
    assert ingestion.scan_pair_budget >= 1
    assert ingestion.scan_time_budget > 0
    assert ingestion.accepted_formats and all(
        isinstance(item, str) for item in ingestion.accepted_formats
    )
    assert ingestion.chunk_length_cap >= 1
    assert ingestion.max_upload_bytes >= 1
    assert ingestion.source_download_timeout_seconds > 0

    retrieval = load_retrieval_config(retrieval_path)
    assert 0 <= retrieval.inheritance_decay <= 1
    assert retrieval.document_cap >= 1
    assert retrieval.cap_warning_multiple >= 1
    assert 0 <= retrieval.relation_pull_threshold <= 1


def test_contract_config_carries_no_forbidden_extra_field():
    """Nhóm hợp đồng chỉ có ĐÚNG ba trường của 07 Mục 3.1.

    Thêm chẳng hạn `l2_normalize` vào đây là tạo ô thứ hai phải khớp với thước
    đo — cùng loại lỗi mà 07 Mục 2.3 đã cấm với `is_certain`.
    """
    assert set(CONTRACT_KEYS) == {"embedding_model", "embedding_dim", "distance_metric"}
