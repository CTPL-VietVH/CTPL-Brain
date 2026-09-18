"""Nền chung cho test T1.2 — chèn `packages/` vào sys.path để import `schema.*`.

Cùng khuôn `tests/t1_1_schema/conftest.py`: `packages/` không có `__init__.py` ở
gốc, mỗi package con (`schema`, `ingestion`, `retrieval`) là điểm vào riêng.

Ba fixture đường dẫn dưới đây trỏ tới BA FILE CẤU HÌNH THẬT của repo. Test lấy
chính chúng làm điểm xuất phát rồi bỏ đi từng khoá — không chép giá trị vào
test, vì chép là tạo cái nhà thứ hai cho tham số, đúng thứ 07 Mục 3.3 quy tắc 2
cấm.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def config_dir() -> pathlib.Path:
    return REPO_ROOT / "config"


@pytest.fixture(scope="session")
def contract_path(config_dir: pathlib.Path) -> pathlib.Path:
    return config_dir / "contract.yaml"


@pytest.fixture(scope="session")
def ingestion_path(config_dir: pathlib.Path) -> pathlib.Path:
    return config_dir / "ingestion.yaml"


@pytest.fixture(scope="session")
def retrieval_path(config_dir: pathlib.Path) -> pathlib.Path:
    return config_dir / "retrieval.yaml"


@pytest.fixture(scope="session")
def env_example_path() -> pathlib.Path:
    return REPO_ROOT / ".env.example"
