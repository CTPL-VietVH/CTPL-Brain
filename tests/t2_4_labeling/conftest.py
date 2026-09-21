"""Nền chung cho test T2.4 — chèn `packages/` vào sys.path để import
`ingestion.*` và `schema.*`, cùng cách `tests/t2_3_chunking/conftest.py` đã làm.
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

# ---------------------------------------------------------------------------
# Văn bản thử có dateline chuẩn hành chính VN — "Địa danh, ngày D tháng M
# năm Y" đứng riêng một dòng ở đầu văn bản, dưới quốc hiệu/tiêu ngữ.
# ---------------------------------------------------------------------------
VAN_BAN_CO_DATELINE = """CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Hà Nội, ngày 15 tháng 9 năm 2026

QUYẾT ĐỊNH
Về việc ban hành Quy chế quản lý tài sản công

Điều 1. Phạm vi điều chỉnh
Quy chế này quy định việc quản lý, sử dụng tài sản công."""

# ---------------------------------------------------------------------------
# Văn bản KHÔNG có dateline nào — chỉ có một câu DẪN CHIẾU văn bản khác chứa
# cụm "ngày D tháng M năm Y" giữa câu, không có dấu phẩy ngay trước "ngày"
# và không đứng đầu dòng — đây CHÍNH LÀ bẫy false-positive đã lường trước.
# ---------------------------------------------------------------------------
VAN_BAN_CHI_CO_DAN_CHIEU = """QUY TRÌNH TIẾP NHẬN VÀ XỬ LÝ HỒ SƠ

1. Mục đích
Quy trình này mô tả các bước tiếp nhận hồ sơ từ khách hàng.

1.2 Tài liệu viện dẫn
Căn cứ Quyết định số 115/QĐ-TCT ngày 12 tháng 3 năm 2025."""

VAN_BAN_KHONG_CO_NGAY_NAO = (
    "Văn bản này hoàn toàn không có dòng ngày tháng nào theo bất kỳ khuôn mẫu nào."
)
