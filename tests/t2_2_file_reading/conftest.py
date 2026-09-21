"""Nền chung cho test T2.2 — chèn `packages/` vào sys.path để import
`ingestion.*`, cùng cách `tests/t0_3_reader/test_reader.py` và
`tests/t2_1_intake/conftest.py` làm. Dùng lại fixture file thật của T0.3 thay
vì tạo bản sao — bốn định dạng đã có sẵn ở đó.
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

FIXTURES = REPO_ROOT / "tests" / "t0_3_reader" / "fixtures"
