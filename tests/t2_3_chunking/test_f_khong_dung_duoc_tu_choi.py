"""T2.3 (bổ sung) — GĐ3 cắt THEO CẤU TRÚC (06 Mục 5.2 GĐ3); khi GĐ2 không
dựng được cấu trúc (`Outcome.KHONG_DUNG_DUOC`) thì không có ranh giới nào để
cắt theo. `cat_thanh_mau` phải TỪ CHỐI ồn ào, không lặng lẽ coi toàn văn là
một mẩu duy nhất — đúng tinh thần "hệ thống LÊN TIẾNG" (CLAUDE.md Mục 7) và
"im lặng hạ chuẩn" bị cấm (06 Mục 5.2).
"""

from __future__ import annotations

import pytest

from ingestion.chunking import KhongDungDuocCauTruc, cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU

VAN_BAN_KHONG_CAU_TRUC = (
    "Đây là một đoạn văn xuôi bình thường, không Chương không Điều, "
    "không tiêu đề đánh số, không tiêu đề viết hoa nào theo sau bởi nội dung."
)


def test_tu_thu_van_ban_khong_dung_duoc():
    kq = dung_cau_truc(VAN_BAN_KHONG_CAU_TRUC, source_format="txt")
    assert not kq.dung_duoc, "Phép thử tự hỏng: văn bản thử phải KHÔNG dựng được cấu trúc"


def test_khong_dung_duoc_thi_tu_choi_khong_cat_lang_le():
    read_result = dung_cau_truc(VAN_BAN_KHONG_CAU_TRUC, source_format="txt")
    with pytest.raises(KhongDungDuocCauTruc):
        cat_thanh_mau(
            read_result,
            document_id=DOC_ID,
            space_id=SPACE_ID,
            tenant_id=TENANT_ID,
            tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
        )
