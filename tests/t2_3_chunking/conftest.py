"""Nền chung cho test T2.3 — chèn `packages/` vào sys.path để import
`ingestion.*` và `schema.*`, cùng cách các thư mục test khác đã làm
(`tests/t2_2_file_reading/conftest.py`, `tests/t1_4_negative_space/conftest.py`).
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

DOC_ID = "doc-t2-3-1"
SPACE_ID = "space-t2-3-1"
TENANT_ID = "tenant-t2-3-1"

# Trần độ dài mẩu (Điểm mở #4, 06 Mục 10) — PO chốt 5000 ký tự Unicode
# (21/9/2026). `cat_thanh_mau` không cho giá trị này một mặc định trong mã
# (CLAUDE.md Mục 4 quy tắc 2) nên MỌI lời gọi trong test đều phải truyền tay;
# hằng số này chỉ để khỏi lặp lại con số ở từng test file.
TRAN_DO_DAI_MAU_THU = 5000

# ---------------------------------------------------------------------------
# Văn bản thử — lồng 3 cấp: Chương › Điều › Khoản.
#
# Điều 2 CỐ Ý chỉ có một dòng nội dung, không Khoản con — dùng cho ca "khối
# đủ ngắn thì là một mẩu" (không liên quan phần chia nhỏ khối quá dài đã
# hoãn, đây chỉ là một Điều tự nhiên không có Khoản).
# ---------------------------------------------------------------------------
VAN_BAN_LONG_NHAU = """CHƯƠNG I
QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
1. Quy chế này áp dụng cho toàn thể cán bộ, nhân viên của công ty.
2. Mọi cá nhân phải chịu trách nhiệm trước pháp luật về hành vi của mình.

Điều 2. Giải thích từ ngữ
Các từ ngữ trong quy chế này được hiểu theo quy định của pháp luật hiện hành."""

# ---------------------------------------------------------------------------
# Văn bản thử — Điều nằm TRỰC TIẾP dưới gốc, không có Chương/Phần/Mục bao
# ngoài. Dùng cho ca "đơn vị cấu trúc cao nhất thì không có cha".
# ---------------------------------------------------------------------------
VAN_BAN_DIEU_TOP_LEVEL = """Điều 1. Phạm vi điều chỉnh
Quy chế này áp dụng cho toàn thể cán bộ, nhân viên của công ty.

Điều 2. Giải thích từ ngữ
Người đại diện là người được ủy quyền hợp pháp để thay mặt công ty giao dịch."""
