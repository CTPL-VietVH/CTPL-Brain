"""Nền chung cho test T2.4 — chèn `packages/` vào sys.path để import
`ingestion.*` và `schema.*`, cùng cách `tests/t2_3_chunking/conftest.py` đã làm.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import date

import pytest

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

# ---------------------------------------------------------------------------
# Tập thử 21 văn bản THẬT cho `trich_ngay_hieu_luc` — data/test-corpus-vn-admin/
# (docs/09 hàng T2.4: nghiệm thu ≥90%). Đường dẫn TƯƠNG ĐỐI so với thư mục đó.
#
# GIÁ TRỊ ĐÃ SỬA LỖI của Cowork (21/9/2026) — KHÔNG dùng số liệu gốc trong
# báo cáo T2.4-validate-effective-date-patterns-vs-corpus (2 văn bản dài/OCR
# nhiều nhất bị đọc tay sai lúc đối chiếu thủ công, xem TASKS.md mục Done):
#   * "ky"            → effective_date PHẢI bằng issued_date thật trích được
#   * ("ky_plus", N)  → effective_date PHẢI bằng issued_date + N ngày
#   * None            → PHẢI trả về None (không resolve được — vd cần ngày
#                        đăng Công báo mà văn bản không tự chứa)
#   * một `date` cụ thể → effective_date PHẢI khớp CHÍNH XÁC ngày đó
# ---------------------------------------------------------------------------
CORPUS_ROOT = REPO_ROOT / "data" / "test-corpus-vn-admin"

GROUND_TRUTH_HIEU_LUC: list[tuple[str, object]] = [
    ("ban-giam-doc-quan-tri/47_2021_nd-cp_470561.docx", "ky"),
    ("ban-giam-doc-quan-tri/Luật-54-2019-QH14.docx", date(2021, 1, 1)),
    ("ban-giam-doc-quan-tri/Luật-61-2020-QH14.docx", date(2021, 1, 1)),
    ("hanh-chinh-tong-hop/110-2004-nd-cp.docx", None),
    ("hanh-chinh-tong-hop/15_2017_QH14_322220_1_1.docx", date(2018, 1, 1)),
    ("hanh-chinh-tong-hop/luat_luutru_01.docx", date(2012, 7, 1)),
    ("ky-thuat-van-hanh/2021_291 + 292_06-2021-NĐ-CP.pdf", "ky"),
    (
        "ky-thuat-van-hanh/2023_nghi-dinh-35_2023_nd-cp_sua-doi-bo-sung-qlnn-cua-bxd.pdf",
        "ky",
    ),
    ("ky-thuat-van-hanh/Luật-50-2014-QH13.docx", date(2015, 1, 1)),
    ("nhan-su/10_2020_TT-BLDTBXH_454406.docx", date(2021, 1, 1)),
    ("nhan-su/Bộ-luật-45-2019-QH14.docx", date(2021, 1, 1)),
    ("nhan-su/Nghị-định-138-2020-NĐ-CP.docx", date(2020, 12, 1)),
    (
        "nhan-su/nghi-dinh-145-2020-huong-dan-thi-hanh-dieu-kien-lao-dong-va-quan-he-lao-dong.docx",
        date(2021, 2, 1),
    ),
    ("phap-che-tuan-thu/168.2024.NĐ.CP.docx", date(2025, 1, 1)),
    ("phap-che-tuan-thu/30_2020_ND_CP.docx", "ky"),
    ("phap-che-tuan-thu/Luật Doanh nghiệp 2020 (1).docx", date(2021, 1, 1)),
    ("phap-che-tuan-thu/VanBanGoc_01_2011_TT-BNV.pdf", ("ky_plus", 45)),
    ("tai-chinh-ke-toan/2021_113 + 114_01-2021-NĐ-CP.pdf", date(2021, 1, 4)),
    ("tai-chinh-ke-toan/Luat Dau thau 2023.docx", date(2024, 1, 1)),
    ("tai-chinh-ke-toan/Luật-88-2015-QH13.docx", date(2017, 1, 1)),
    ("tai-chinh-ke-toan/tt-200-btc-22-12-2014.pdf", ("ky_plus", 45)),
]


@pytest.fixture(scope="session")
def corpus_extracted_texts() -> dict[str, str]:
    """Đọc trọn 21 file thật MỘT LẦN cho cả phiên test (Docling trên 5 PDF
    tốn vài chục giây) — trả về `{đường_dẫn_tương_đối: extracted_text}`.

    Đây là dữ liệu CỤC BỘ, không nằm trong git (`data/` bị `.gitignore`) —
    thiếu thì `pytest.fail` rõ ràng, không âm thầm bỏ qua ca nghiệm thu bắt
    buộc của T2.4 (docs/09 hàng T2.4 yêu cầu ≥90% trên đúng 21 văn bản này).
    """
    if not CORPUS_ROOT.is_dir():
        pytest.fail(
            f"Thiếu tập thử {CORPUS_ROOT} — 21 văn bản thật để nghiệm thu "
            "trich_ngay_hieu_luc() (docs/09 hàng T2.4 yêu cầu ≥90%, so với "
            "bảng GROUND_TRUTH_HIEU_LUC). Dữ liệu CỤC BỘ, không nằm trong git. "
            "Xem data/test-corpus-vn-admin/MANIFEST.md."
        )

    from ingestion.extraction import extract_file

    ket_qua: dict[str, str] = {}
    for duong_dan, _ in GROUND_TRUTH_HIEU_LUC:
        file_that = CORPUS_ROOT / duong_dan
        if not file_that.is_file():
            pytest.fail(f"Thiếu file trong tập thử: {file_that}")
        ket_qua[duong_dan] = extract_file(file_that).extracted_text
    return ket_qua
