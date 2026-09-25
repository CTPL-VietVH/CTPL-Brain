"""Ba nhóm cấu hình + con dấu trên kho — 07 Mục 3.1, 3.2, 3.3 (T1.2).

Ba nhóm, ba nơi, KHÔNG CHỒNG LẤN (07 Mục 3.3 bảng 1):

| Nhóm | File | Ai đọc | Lệch thì sao |
|---|---|---|---|
| Hợp đồng | `config/contract.yaml` | cả hai service | **hỏng ngầm** → so với con dấu trên kho, không khớp thì từ chối chạy |
| Ingestion | `config/ingestion.yaml` | chỉ Ingestion | không ảnh hưởng bên kia |
| Retrieval | `config/retrieval.yaml` | chỉ Retrieval | không ảnh hưởng bên kia |

⛔ HAI ĐIỀU TUYỆT ĐỐI trong file này (07 Mục 3.3 quy tắc 3, CLAUDE.md Mục 3 #2):

1. **Không có giá trị mặc định trong mã** — không `dict.get(key, default)`,
   không tham số mặc định trong hàm nạp, không hằng số giá trị khởi đầu nằm đâu
   đó "ngay trước chỗ dùng". Một mặc định trong mã là CÁI NHÀ THỨ HAI của tham
   số: file cấu hình thiếu khoá mà service vẫn chạy thì không ai biết giá trị
   đang sống là bao nhiêu.
2. **Thiếu khoá → TỪ CHỐI CHẠY**, và thông báo lỗi phải nêu ĐÚNG TÊN khoá thiếu
   cùng ĐƯỜNG DẪN file — đó là thứ duy nhất người trực đêm dùng được.

Vì sao các hàm nạp không có đường dẫn mặc định: chỗ đặt thư mục `config/` là
tham số TRIỂN KHAI của từng bản cài (R6), không phải hằng số của module dùng
chung. Ai gọi thì người đó nêu rõ đường dẫn — cùng lý do `.env.example` giữ
tham số kết nối hạ tầng ở ngoài ba nhóm này.

Phạm vi T1.2 dừng ở CƠ CHẾ THUẦN: `StoreStamp` dưới đây là con dấu đã được đọc
ra khỏi kho, không phải kết nối tới kho. CHỌN nhà thật cho `embedding_model`
(điểm dữ liệu dành riêng trong collection, hay bảng Postgres khoá theo tên
collection) và ĐỌC con dấu thật lúc service khởi động là việc của T1.3 —
tests/t0_1_stores/test_b_store_stamp.py đã chứng minh cả hai nhà đều chạy được
và cố ý chưa chọn.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

import yaml

__all__ = [
    "ConfigError",
    "ConfigFileNotFoundError",
    "MissingConfigKeyError",
    "UnknownConfigKeyError",
    "ConfigValueError",
    "StoreStampMismatchError",
    "DistanceMetric",
    "ContractConfig",
    "IngestionConfig",
    "RetrievalConfig",
    "StoreStamp",
    "CONTRACT_KEYS",
    "INGESTION_KEYS",
    "RETRIEVAL_KEYS",
    "load_contract_config",
    "load_ingestion_config",
    "load_retrieval_config",
    "assert_contract_matches_store_stamp",
]


# --------------------------------------------------------------------------- #
# Lỗi — mỗi loại một tên riêng, để nơi gọi bắt được đúng thứ nó muốn bắt
# --------------------------------------------------------------------------- #


class ConfigError(Exception):
    """Gốc cho mọi lỗi cấu hình. Mọi lỗi ở đây đều dẫn tới TỪ CHỐI CHẠY."""


class ConfigFileNotFoundError(ConfigError):
    """Không có file cấu hình. Không được coi là "rỗng rồi dùng mặc định"."""


class MissingConfigKeyError(ConfigError):
    """Thiếu khoá trong file cấu hình — 07 Mục 3.3 quy tắc 3."""


class UnknownConfigKeyError(ConfigError):
    """Có khoá lạ trong file cấu hình.

    Vì sao cũng phải nổ: gõ nhầm `document_caps` thì khoá thật biến mất và khoá
    lạ nằm im. Nếu chỉ kiểm khoá thiếu thì thông báo sẽ nói "thiếu
    `document_cap`" trong khi người ta nhìn thấy nó ngay trên màn hình — mất
    thêm nửa giờ. Nổ kèm tên khoá lạ là chỉ thẳng vào chỗ gõ sai.

    Đây cũng là chỗ bắt được một tham số bị đặt NHẦM NHÀ: `document_cap` lọt
    sang `ingestion.yaml` thì file kia thiếu khoá, file này thừa khoá — hai đầu
    cùng lên tiếng (07 Mục 3.3 quy tắc 2).
    """


class ConfigValueError(ConfigError):
    """Khoá có mặt nhưng giá trị sai kiểu hoặc ngoài miền hợp lệ."""


class StoreStampMismatchError(ConfigError):
    """Cấu hình hợp đồng lệch con dấu trên kho — 07 Mục 3.1 ràng buộc 2."""


# --------------------------------------------------------------------------- #
# Kiểu giá trị
# --------------------------------------------------------------------------- #


class DistanceMetric(str, Enum):
    """Thước đo khoảng cách trong kho vector — 07 Mục 3.1.

    ⚠️ Thước đo là THUỘC TÍNH CỦA MÔ HÌNH, không phải lựa chọn tự do: các dòng
    mô hình đang cân nhắc đều huấn luyện bằng hàm mất mát tương phản trên cosine
    và đều yêu cầu chuẩn hoá L2. Dùng `DOT` không chuẩn hoá hoặc `EUCLID` thì
    KHÔNG có lỗi nào báo, chỉ tụt chất lượng tìm kiếm âm thầm (07 Mục 3.1,
    nghiên cứu 14/9). Hai giá trị đó có mặt ở đây vì R5 — đổi mô hình bằng cấu
    hình, không phải sửa mã — chứ không phải vì chúng tương đương nhau.

    v1 CHỐT `COSINE` + vector chuẩn hoá L2 (S5). Không có khoá `l2_normalize`
    riêng: chuẩn hoá L2 là điều kiện đi kèm của cosine trong pipeline này, tách
    ra thành ô thứ hai là tạo thêm một ô phải khớp với ô thứ nhất.
    """

    COSINE = "cosine"
    DOT = "dot"
    EUCLID = "euclid"


@dataclass(frozen=True, slots=True, kw_only=True)
class ContractConfig:
    """Nhóm HỢP ĐỒNG — 07 Mục 3.1. Cả hai service đọc cùng ba giá trị này.

    `frozen=True`: đổi giá trị hợp đồng giữa lúc chạy là đúng thứ cơ chế con dấu
    sinh ra để chặn — service đã kiểm lúc khởi động rồi thì không ai được sửa
    sau lưng nó.
    """

    embedding_model: str
    embedding_dim: int
    distance_metric: DistanceMetric


@dataclass(frozen=True, slots=True, kw_only=True)
class IngestionConfig:
    """Nhóm INGESTION — 07 Mục 3.2. Chỉ Ingestion v2 đọc.

    `scan_time_budget` ĐƠN VỊ LÀ PHÚT (07 Mục 3.2 ghi "10 phút"). Tên khoá
    khớp đúng tên đã chốt trong tài liệu nguồn chân lý — đơn vị được nêu trong
    comment cạnh giá trị ở `config/ingestion.yaml`, không nhét vào tên khoá
    (PO chốt 18/9/2026, thay cho hậu tố `_minutes` trước đó).

    `saturation_epsilon` ĐƠN VỊ LÀ TỶ LỆ 0–1; giá trị chốt 1% ghi thành 0.01.

    `chunk_length_cap` — trần độ dài một mẩu, Điểm mở #4 (06 Mục 10), PO chốt
    5000 ký tự Unicode (21/9/2026). ĐƠN VỊ LÀ KÝ TỰ UNICODE, không phải byte
    (CLAUDE.md Mục 3 #4) — đơn vị nêu trong comment cạnh giá trị ở
    `config/ingestion.yaml`, không nhét vào tên khoá, cùng khuôn với
    `scan_time_budget`. Đây là tham số bắt buộc của `cat_thanh_mau()`
    (`packages/ingestion/chunking.py`) — module đó không hardcode giá trị.

    `max_upload_bytes` và `source_download_timeout_seconds` — hai trần của
    bước tải file theo tham chiếu (docs/10 §4.1, PO chốt 24/9/2026). ĐƠN VỊ
    lần lượt là BYTE và GIÂY, nêu trong comment cạnh giá trị. Chúng thuộc
    nhóm Ingestion vì chỉ đường nạp đọc tới: Retrieval không tải file nào.
    `max_upload_bytes` là con số duy nhất trong nhóm này được công bố ra
    ngoài — docs/10 §3.6 bắt `GET /v1/meta` nêu *"cỡ file tối đa"* để Backend
    biết trước, thay vì để một lần tải 100 MB kết thúc bằng `413`.

    `qdrant_upsert_batch_points` — how many points ONE `upsert` call may
    carry (VEC-1, after the 25/9/2026 incident: one upsert holding a whole
    document's chunks reached 40-43 MB and Qdrant's REST endpoint refused it).
    UNIT: NUMBER OF POINTS, not bytes — the dominant term in a point is the
    embedding, whose size is fixed by `embedding_dim`, so a point count IS a
    byte budget expressed in the only unit this side can count without
    re-implementing the client's serialiser. It belongs to the Ingestion group
    because only Ingestion writes points; Retrieval never upserts.
    """

    saturation_epsilon: float
    saturation_rounds: int
    scan_pair_budget: int
    scan_time_budget: float
    accepted_formats: tuple[str, ...]
    chunk_length_cap: int
    max_upload_bytes: int
    source_download_timeout_seconds: float
    qdrant_upsert_batch_points: int


@dataclass(frozen=True, slots=True, kw_only=True)
class RetrievalConfig:
    """Nhóm RETRIEVAL — 07 Mục 3.2. Chỉ Retrieval v2 đọc.

    ⚠️ `inheritance_decay` áp trên ĐIỂM ĐÃ CHUẨN HOÁ trên tập ứng viên, không
    phải điểm giống thô (07 Mục 3.2, CLAUDE.md Mục 3 #12).
    ⚠️ `relation_pull_threshold` chỉ áp cho liên kết `origin=machine_inferred`
    (07 Mục 2.3, CLAUDE.md Mục 3 #21).
    """

    inheritance_decay: float
    document_cap: int
    cap_warning_multiple: int
    relation_pull_threshold: float


@dataclass(frozen=True, slots=True, kw_only=True)
class StoreStamp:
    """Con dấu đã đóng trên MỘT kho cụ thể — 07 Mục 3.1 ràng buộc 2.

    Đây là con dấu ĐÃ ĐỌC RA khỏi kho, không phải kết nối tới kho: T1.2 chỉ xây
    phần quyết định (so khớp), phần đọc thật là T1.3. Tách như vậy để ca khó
    nhất — đổi mô hình mà giữ nguyên số chiều — test được mà không cần Qdrant
    hay PostgreSQL chạy.

    ⚠️ Cấu hình collection của Qdrant mang `embedding_dim` và `distance_metric`
    nhưng KHÔNG mang `embedding_model` (đã đo thật: T0.1 (b)). Nên dựng
    `StoreStamp` từ mình cấu hình collection là dựng một con dấu THIẾU đúng phần
    nguy hiểm nhất — `embedding_model` phải lấy từ nhà riêng của nó trên kho.
    """

    embedding_model: str
    embedding_dim: int
    distance_metric: DistanceMetric


# --------------------------------------------------------------------------- #
# Danh sách khoá bắt buộc — một nguồn duy nhất, dùng cho cả nạp lẫn test
# --------------------------------------------------------------------------- #

CONTRACT_KEYS: tuple[str, ...] = (
    "embedding_model",
    "embedding_dim",
    "distance_metric",
)

INGESTION_KEYS: tuple[str, ...] = (
    "saturation_epsilon",
    "saturation_rounds",
    "scan_pair_budget",
    "scan_time_budget",
    "accepted_formats",
    "chunk_length_cap",
    "max_upload_bytes",
    "source_download_timeout_seconds",
    "qdrant_upsert_batch_points",
)

RETRIEVAL_KEYS: tuple[str, ...] = (
    "inheritance_decay",
    "document_cap",
    "cap_warning_multiple",
    "relation_pull_threshold",
)


# --------------------------------------------------------------------------- #
# Đọc file và kiểm khoá
# --------------------------------------------------------------------------- #


def _read_yaml_mapping(path: Path) -> Mapping[str, Any]:
    """Đọc một file YAML thành ánh xạ. File vắng mặt hay rỗng đều là LỖI.

    Không có nhánh nào trả về ánh xạ rỗng rồi đi tiếp: "không đọc được cấu hình"
    và "cấu hình nói hãy dùng giá trị này" là hai chuyện khác nhau.
    """
    if not path.is_file():
        raise ConfigFileNotFoundError(
            f"Không tìm thấy file cấu hình: {path}. "
            "Service TỪ CHỐI CHẠY thay vì dùng giá trị mặc định trong mã "
            "(07 Mục 3.3 quy tắc 3)."
        )

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if raw is None:
        raise ConfigValueError(
            f"File cấu hình rỗng (không có khoá nào): {path}. "
            "Service TỪ CHỐI CHẠY (07 Mục 3.3 quy tắc 3)."
        )
    if not isinstance(raw, dict):
        raise ConfigValueError(
            f"File cấu hình {path} phải là một ánh xạ khoá–giá trị, "
            f"đọc ra kiểu {type(raw).__name__}."
        )
    return raw


def _check_keys(data: Mapping[str, Any], required: tuple[str, ...], path: Path) -> None:
    """Kiểm khoá thiếu và khoá lạ. Cả hai đều dẫn tới TỪ CHỐI CHẠY."""
    missing = [key for key in required if key not in data]
    if missing:
        raise MissingConfigKeyError(
            f"Thiếu khoá cấu hình trong {path}: "
            + ", ".join(f"`{key}`" for key in missing)
            + ". Service TỪ CHỐI CHẠY — không có giá trị mặc định trong mã "
            "(07 Mục 3.3 quy tắc 3, CLAUDE.md Mục 3 #2). "
            f"Khoá bắt buộc của file này: {', '.join(required)}."
        )

    unknown = [key for key in data if key not in required]
    if unknown:
        raise UnknownConfigKeyError(
            f"Khoá lạ trong {path}: "
            + ", ".join(f"`{key}`" for key in unknown)
            + ". Hoặc gõ sai tên, hoặc tham số đang nằm nhầm nhà — mỗi tham số "
            "có ĐÚNG MỘT nhà (07 Mục 3.3 quy tắc 2). "
            f"Khoá hợp lệ của file này: {', '.join(required)}."
        )


def _require(data: Mapping[str, Any], key: str, path: Path) -> Any:
    """Lấy giá trị của một khoá. KHÔNG dùng `dict.get(key, default)`.

    `_check_keys` đã chạy trước, nên tới đây khoá phải có mặt; nhánh raise dưới
    đây là lưới an toàn cho người sửa mã sau này, không phải nhánh mong đợi.
    """
    if key not in data:
        raise MissingConfigKeyError(f"Thiếu khoá cấu hình `{key}` trong {path}.")
    return data[key]


# --------------------------------------------------------------------------- #
# Ép kiểu — sai kiểu cũng phải NỔ, không âm thầm ép cho vừa
# --------------------------------------------------------------------------- #


def _as_str(value: Any, key: str, path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigValueError(
            f"`{key}` trong {path} phải là chuỗi không rỗng, "
            f"nhận được {value!r} (kiểu {type(value).__name__})."
        )
    return value


def _as_int(value: Any, key: str, path: Path) -> int:
    # `bool` là con của `int` trong Python — `true` trong YAML phải bị chặn,
    # không được lặng lẽ thành 1.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigValueError(
            f"`{key}` trong {path} phải là số nguyên, "
            f"nhận được {value!r} (kiểu {type(value).__name__}). "
            'Lưu ý: số viết trong dấu nháy ("6") là chuỗi, không phải số.'
        )
    return value


def _as_float(value: Any, key: str, path: Path) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigValueError(
            f"`{key}` trong {path} phải là số, "
            f"nhận được {value!r} (kiểu {type(value).__name__}). "
            'Lưu ý: số viết trong dấu nháy ("0.5") là chuỗi, không phải số.'
        )
    return float(value)


def _as_str_tuple(value: Any, key: str, path: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigValueError(
            f"`{key}` trong {path} phải là danh sách không rỗng, "
            f"nhận được {value!r} (kiểu {type(value).__name__})."
        )
    items = tuple(_as_str(item, key, path) for item in value)
    if len(set(items)) != len(items):
        raise ConfigValueError(f"`{key}` trong {path} có giá trị lặp: {items}.")
    return items


def _require_positive(value: float, key: str, path: Path) -> None:
    if value <= 0:
        raise ConfigValueError(f"`{key}` trong {path} phải lớn hơn 0, nhận được {value!r}.")


def _require_unit_interval(value: float, key: str, path: Path) -> None:
    """Miền hợp lệ của các tham số 07 Mục 3.2 ghi rõ là "thang 0–1".

    Đây là kiểm MIỀN HỢP LỆ, không phải giá trị mặc định: nó không cung cấp giá
    trị nào khi thiếu khoá, chỉ chặn một giá trị vô nghĩa (ghi 30 khi định ghi
    0.3) đi tiếp trong im lặng.
    """
    if not 0.0 <= value <= 1.0:
        raise ConfigValueError(
            f"`{key}` trong {path} phải nằm trong thang 0–1 (07 Mục 3.2), "
            f"nhận được {value!r}."
        )


# --------------------------------------------------------------------------- #
# Ba hàm nạp — KHÔNG hàm nào có tham số mặc định
# --------------------------------------------------------------------------- #


def load_contract_config(path: Path) -> ContractConfig:
    """Nạp nhóm HỢP ĐỒNG từ `path` (thường là `config/contract.yaml`).

    Nạp xong CHƯA đủ để khởi động: phải gọi tiếp
    `assert_contract_matches_store_stamp` với con dấu của kho đang đọc
    (07 Mục 3.1 ràng buộc 2).
    """
    data = _read_yaml_mapping(path)
    _check_keys(data, CONTRACT_KEYS, path)

    embedding_model = _as_str(_require(data, "embedding_model", path), "embedding_model", path)

    embedding_dim = _as_int(_require(data, "embedding_dim", path), "embedding_dim", path)
    _require_positive(embedding_dim, "embedding_dim", path)

    raw_metric = _as_str(_require(data, "distance_metric", path), "distance_metric", path)
    try:
        distance_metric = DistanceMetric(raw_metric)
    except ValueError as exc:
        valid = ", ".join(metric.value for metric in DistanceMetric)
        raise ConfigValueError(
            f"`distance_metric` trong {path} không hợp lệ: {raw_metric!r}. "
            f"Giá trị hiểu được: {valid}. "
            "Thước đo là thuộc tính của mô hình, không phải lựa chọn tự do "
            "(07 Mục 3.1)."
        ) from exc

    if distance_metric != DistanceMetric.COSINE:
        raise ConfigValueError(
            f"`distance_metric` trong {path} = {distance_metric.value!r}, nhưng "
            "docs/07 Mục 3.1: CHỐT cosine — v1 khoá cứng CHỈ chấp nhận `cosine`. "
            "`dot` và `euclid` vẫn còn trong enum `DistanceMetric` để R5 (đổi mô "
            "hình bằng cấu hình) còn chỗ đứng cho mô hình tương lai, nhưng dùng "
            "ngay bây giờ thì tụt chất lượng tìm kiếm ÂM THẦM, không lỗi nào báo "
            "(07 Mục 3.1). Đây là khoá cứng của v1 (PO chốt 18/9/2026), không "
            "phải giới hạn kỹ thuật của enum — sửa lại thành `cosine`."
        )

    return ContractConfig(
        embedding_model=embedding_model,
        embedding_dim=embedding_dim,
        distance_metric=distance_metric,
    )


def load_ingestion_config(path: Path) -> IngestionConfig:
    """Nạp nhóm INGESTION từ `path` (thường là `config/ingestion.yaml`)."""
    data = _read_yaml_mapping(path)
    _check_keys(data, INGESTION_KEYS, path)

    saturation_epsilon = _as_float(
        _require(data, "saturation_epsilon", path), "saturation_epsilon", path
    )
    _require_positive(saturation_epsilon, "saturation_epsilon", path)
    _require_unit_interval(saturation_epsilon, "saturation_epsilon", path)

    saturation_rounds = _as_int(
        _require(data, "saturation_rounds", path), "saturation_rounds", path
    )
    _require_positive(saturation_rounds, "saturation_rounds", path)

    scan_pair_budget = _as_int(
        _require(data, "scan_pair_budget", path), "scan_pair_budget", path
    )
    _require_positive(scan_pair_budget, "scan_pair_budget", path)

    scan_time_budget = _as_float(
        _require(data, "scan_time_budget", path), "scan_time_budget", path
    )
    _require_positive(scan_time_budget, "scan_time_budget", path)

    accepted_formats = _as_str_tuple(
        _require(data, "accepted_formats", path), "accepted_formats", path
    )

    chunk_length_cap = _as_int(
        _require(data, "chunk_length_cap", path), "chunk_length_cap", path
    )
    _require_positive(chunk_length_cap, "chunk_length_cap", path)

    max_upload_bytes = _as_int(
        _require(data, "max_upload_bytes", path), "max_upload_bytes", path
    )
    _require_positive(max_upload_bytes, "max_upload_bytes", path)

    source_download_timeout_seconds = _as_float(
        _require(data, "source_download_timeout_seconds", path),
        "source_download_timeout_seconds",
        path,
    )
    _require_positive(
        source_download_timeout_seconds, "source_download_timeout_seconds", path
    )

    qdrant_upsert_batch_points = _as_int(
        _require(data, "qdrant_upsert_batch_points", path),
        "qdrant_upsert_batch_points",
        path,
    )
    _require_positive(
        qdrant_upsert_batch_points, "qdrant_upsert_batch_points", path
    )

    return IngestionConfig(
        saturation_epsilon=saturation_epsilon,
        saturation_rounds=saturation_rounds,
        scan_pair_budget=scan_pair_budget,
        scan_time_budget=scan_time_budget,
        accepted_formats=accepted_formats,
        chunk_length_cap=chunk_length_cap,
        max_upload_bytes=max_upload_bytes,
        source_download_timeout_seconds=source_download_timeout_seconds,
        qdrant_upsert_batch_points=qdrant_upsert_batch_points,
    )


def load_retrieval_config(path: Path) -> RetrievalConfig:
    """Nạp nhóm RETRIEVAL từ `path` (thường là `config/retrieval.yaml`)."""
    data = _read_yaml_mapping(path)
    _check_keys(data, RETRIEVAL_KEYS, path)

    inheritance_decay = _as_float(
        _require(data, "inheritance_decay", path), "inheritance_decay", path
    )
    _require_unit_interval(inheritance_decay, "inheritance_decay", path)

    document_cap = _as_int(_require(data, "document_cap", path), "document_cap", path)
    _require_positive(document_cap, "document_cap", path)

    cap_warning_multiple = _as_int(
        _require(data, "cap_warning_multiple", path), "cap_warning_multiple", path
    )
    _require_positive(cap_warning_multiple, "cap_warning_multiple", path)

    relation_pull_threshold = _as_float(
        _require(data, "relation_pull_threshold", path), "relation_pull_threshold", path
    )
    _require_unit_interval(relation_pull_threshold, "relation_pull_threshold", path)

    return RetrievalConfig(
        inheritance_decay=inheritance_decay,
        document_cap=document_cap,
        cap_warning_multiple=cap_warning_multiple,
        relation_pull_threshold=relation_pull_threshold,
    )


# --------------------------------------------------------------------------- #
# So cấu hình hợp đồng với CON DẤU CỦA KHO — 07 Mục 3.1 ràng buộc 2
# --------------------------------------------------------------------------- #


def assert_contract_matches_store_stamp(
    config: ContractConfig,
    stamp: StoreStamp,
    *,
    store_name: str,
) -> None:
    """So cấu hình hợp đồng của MỘT service với CON DẤU CỦA KHO nó đang đọc.

    ⚠️ So với CON DẤU CỦA KHO, **không** so hai service với nhau. 07 Mục 3.1:
    "cách này bắt được cả trường hợp hai service khớp nhau nhưng **cả hai cùng
    lệch với kho** — tức là kho được tạo bằng mô hình cũ mà cả hai service đã
    đổi sang mô hình mới. So hai service với nhau thì trường hợp đó lọt."

    Hệ quả cho cách kiểm thử (08 T1.3): chạy MỘT MÌNH Retrieval với cấu hình
    lệch con dấu, không bật Ingestion — nó vẫn phải từ chối khởi động.

    Khớp cả ba trường → trả về `None`. Lệch bất kỳ trường nào → raise
    `StoreStampMismatchError`. **Không có chế độ cảnh báo rồi chạy tiếp**: một
    service chạy với cấu hình lệch chính là loại trừ im lặng ở tầng thấp nhất,
    cùng loại với việc cắt bớt ngầm khi tràn ngữ cảnh mà 06 Mục 6.5 đã cấm.

    Ca nguy hiểm nhất là lệch `embedding_model` khi `embedding_dim` KHỚP: phép
    so vector vẫn chạy, không lỗi nào báo, chỉ sai lệch âm thầm. Hàm này kiểm cả
    ba trường độc lập nên bắt được ca đó — miễn là `stamp` được dựng từ nhà
    riêng của `embedding_model` trên kho chứ không từ mình cấu hình collection.

    `store_name` bắt buộc nêu tên (không có giá trị mặc định): một bản cài có
    thể có nhiều kho — kho cũ còn phục vụ truy vấn trong lúc kho mới đang dựng
    (07 Mục 3.1) — nên thông báo lỗi không nói rõ KHO NÀO thì vô dụng.
    """
    mismatches: list[str] = []

    if config.embedding_model != stamp.embedding_model:
        mismatches.append(
            f"embedding_model: cấu hình={config.embedding_model!r} | "
            f"con dấu trên kho={stamp.embedding_model!r}"
        )
    if config.embedding_dim != stamp.embedding_dim:
        mismatches.append(
            f"embedding_dim: cấu hình={config.embedding_dim!r} | "
            f"con dấu trên kho={stamp.embedding_dim!r}"
        )
    if config.distance_metric != stamp.distance_metric:
        mismatches.append(
            f"distance_metric: cấu hình={config.distance_metric.value!r} | "
            f"con dấu trên kho={stamp.distance_metric.value!r}"
        )

    if not mismatches:
        return

    same_dim_other_model = (
        config.embedding_dim == stamp.embedding_dim
        and config.embedding_model != stamp.embedding_model
    )
    hint = (
        " ⚠️ SỐ CHIỀU KHỚP NHƯNG TÊN MÔ HÌNH KHÁC — đây là ca hỏng ngầm nặng "
        "nhất: phép so vector vẫn chạy, kết quả sai lệch âm thầm, không kho nào "
        "báo lỗi (07 Mục 3.1)."
        if same_dim_other_model
        else ""
    )

    raise StoreStampMismatchError(
        f"Cấu hình hợp đồng LỆCH con dấu của kho '{store_name}' → TỪ CHỐI CHẠY. "
        + "; ".join(mismatches)
        + "."
        + hint
        + " Không có chế độ cảnh báo rồi chạy tiếp (07 Mục 3.1 ràng buộc 2). "
        "Đổi mô hình biểu diễn ở v1 = dừng dịch vụ, nạp lại toàn kho bằng mô "
        "hình mới, đóng dấu lại, bật lại cùng lúc (07 Mục 3.1, 06 Mục 5.5)."
    )
