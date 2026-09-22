"""T2.3 bước 2/2 (j) — một Chunk LÁ vượt trần mà KHÔNG còn ranh giới an toàn
nào (đoạn/câu) để chia tiếp phải làm hệ thống LÊN TIẾNG (`KhoiVuotTranKhongTheChia`),
KHÔNG được lặng lẽ bịa cách cắt cứng theo số ký tự.

Ca thật trong work-order (PO, 21/9/2026): một bảng kế toán nhúng trong một
Khoản, hơn 55.000 ký tự, không dòng trống, và mọi dấu chấm chỉ là DẤU PHÂN
CÁCH HÀNG NGHÌN trong số liệu ("1.234.567,89") — không phải dấu kết câu thật.
Mô phỏng ở đây bằng văn bản NGẮN hơn nhưng cùng hình dạng: chỉ số liệu lặp
lại, không một dấu kết câu thật nào.
"""

from __future__ import annotations

import pytest

from ingestion.chunking import KhoiVuotTranKhongTheChia, cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU

# "1.234.567,89 " lặp lại: toàn dấu chấm phân cách hàng nghìn (luôn đứng
# ngay trước một CHỮ SỐ) — không có dấu kết câu thật nào (dấu . / ! / ?
# đứng trước chữ HOA hoặc cuối văn bản). Không dòng trống bên trong -> một
# ĐOẠN, và đoạn đó cũng không tách được xuống cấp câu.
_BANG_SO_LIEU = "1.234.567,89 " * 500

VAN_BAN_KHOAN_KHONG_CHIA_DUOC = f"""Điều 1. Phạm vi điều chỉnh
1. Số liệu chi tiết như sau: {_BANG_SO_LIEU}

Điều 2. Hiệu lực thi hành
Quy chế có hiệu lực kể từ ngày ký."""


def test_tu_thu_bang_so_lieu_vuot_tran_va_khong_co_ranh_gioi_an_toan():
    assert len(_BANG_SO_LIEU) > TRAN_DO_DAI_MAU_THU
    assert "\n\n" not in _BANG_SO_LIEU
    # Không dấu kết câu THẬT nào: mọi dấu chấm đều đứng ngay trước một chữ số.
    import re

    for m in re.finditer(r"[.!?…]", _BANG_SO_LIEU):
        j = m.end()
        while j < len(_BANG_SO_LIEU) and _BANG_SO_LIEU[j] in " \t":
            j += 1
        assert j >= len(_BANG_SO_LIEU) or _BANG_SO_LIEU[j].isdigit(), (
            "Phép thử tự hỏng: văn bản thử phải KHÔNG có dấu kết câu thật nào, "
            "để buộc phải rơi vào ca escalate"
        )


def test_khong_con_ranh_gioi_an_toan_thi_no_khoi_vuot_tran_khong_the_chia():
    read_result = dung_cau_truc(VAN_BAN_KHOAN_KHONG_CHIA_DUOC, source_format="txt")

    with pytest.raises(KhoiVuotTranKhongTheChia) as exc_info:
        cat_thanh_mau(
            read_result,
            document_id=DOC_ID,
            space_id=SPACE_ID,
            tenant_id=TENANT_ID,
            tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
        )

    thong_diep = str(exc_info.value)
    assert "Khoản 1" in thong_diep, (
        "Thông báo lỗi phải nêu structure_path của khối để người soát tìm "
        "đúng chỗ, không được chỉ nói chung chung"
    )
