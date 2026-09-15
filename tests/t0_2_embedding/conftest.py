"""Nền chung cho bằng chứng T0.2.

Mô hình nằm trong `.runtime/models` (đã .gitignore) để một bản cài là một thư
mục tự chứa — đúng tinh thần R6.
"""

from __future__ import annotations

import os
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODEL_HOME = REPO_ROOT / ".runtime" / "models"

# Ba giá trị này là thứ T0.2 phải giao lại cho nhóm cấu hình HỢP ĐỒNG ở T1.2.
# Ghi ở đây dưới dạng hằng của phép thử, KHÔNG phải nhà chính thức của chúng —
# nhà chính thức là config/ và việc dựng nó là T1.2.
EXPECTED_MODEL_NAME = "BAAI/bge-m3"
EXPECTED_DIM = 1024
EXPECTED_METRIC = "cosine"
EXPECTED_MAX_TOKENS = 8192


@pytest.fixture(scope="session")
def model():
    """Nạp BGE-M3 từ đĩa cục bộ — R2: không gọi ra ngoài lúc chạy."""
    os.environ["HF_HOME"] = str(MODEL_HOME)
    os.environ["HF_HUB_OFFLINE"] = "1"  # nổ nếu còn cần mạng

    from sentence_transformers import SentenceTransformer

    if not MODEL_HOME.exists():
        pytest.fail(f"Chưa tải mô hình về {MODEL_HOME}. Xem tests/t0_2_embedding/README.md")

    # ⚠️ CỐ Ý KHÔNG đặt `max_seq_length`. Nếu ở đây ghi đè thành 8192 thì phép
    # thử chỉ chứng minh lệnh ghi đè của chính nó chạy được — trong khi thứ cần
    # canh là **giá trị mặc định** mà mọi chỗ gọi mô hình sẽ nhận. Để nguyên
    # mặc định thì hôm nào thư viện hoặc mô hình hạ nó xuống, ca thử đỏ ngay.
    return SentenceTransformer(EXPECTED_MODEL_NAME)
