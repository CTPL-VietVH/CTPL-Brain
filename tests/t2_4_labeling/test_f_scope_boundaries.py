"""T2.4 (f) — ràng buộc phạm vi của work-order:

1. Module KHÔNG được đụng `effective_date`/`effective_date_source` — `GoiYNgayKy`
   không được có trường nào tên như vậy (phần đó tách sang work-order riêng,
   `T2.4-research-effective-date-patterns`).
2. Module chỉ TRẢ VỀ giá trị gợi ý — không tự ghi/persist vào `Document`, và
   không import `Document`/kho lưu trữ nào (module thuần hàm, không side
   effect).
"""

from __future__ import annotations

import dataclasses

from ingestion import labeling
from ingestion.labeling import GoiYNgayKy


def test_goi_y_ngay_ky_khong_co_truong_effective_date():
    ten_truong = {f.name for f in dataclasses.fields(GoiYNgayKy)}
    assert ten_truong == {"issued_date", "issued_date_source"}
    assert "effective_date" not in ten_truong
    assert "effective_date_source" not in ten_truong


def test_module_khong_import_document_hay_khoi_ghi():
    """Module chỉ SINH gợi ý — không có nghĩa vụ (và không có quyền) ghi
    thẳng vào `Document`, nên không cần import lớp đó vào namespace của
    mình (chỉ `DateSource` — kiểu enum thuần, không phải kho lưu trữ)."""
    assert not hasattr(labeling, "Document")
    assert hasattr(labeling, "DateSource")
