"""Nền chung cho test T1.1 — chèn `packages/` vào sys.path để import `schema.*`.

Cùng cách `tests/t0_3_reader/test_reader.py` chèn `packages/` để import
`ingestion.*`: `packages/` không có `__init__.py` ở gốc, mỗi package con
(`schema`, `ingestion`, `retrieval`) là điểm vào riêng.
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))
