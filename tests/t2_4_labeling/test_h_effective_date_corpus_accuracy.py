"""T2.4 bước 2/2 — Tập thử tự động BẮT BUỘC: `trich_ngay_hieu_luc` đối chiếu
với 21 văn bản hành chính VN THẬT tại `data/test-corpus-vn-admin/` (docs/09
hàng T2.4: nghiệm thu ≥90%).

Bảng đối chiếu `GROUND_TRUTH_HIEU_LUC` (ở `conftest.py`) là SỐ LIỆU ĐÃ SỬA
LỖI của Cowork (21/9/2026) — KHÔNG dùng số liệu gốc trong báo cáo
`T2.4-validate-effective-date-patterns-vs-corpus` (2/21 văn bản dài/OCR
nhiều nhất bị đọc tay sai lúc đối chiếu thủ công).
"""

from __future__ import annotations

from datetime import timedelta

from ingestion.labeling import trich_ngay_hieu_luc, trich_ngay_ky

from .conftest import GROUND_TRUTH_HIEU_LUC


def _ky_vong_thanh_ngay(ky_vong: object, extracted_text: str):
    """Giải mã ký hiệu "ky"/("ky_plus", N)/None/`date` trong bảng đối chiếu
    thành ngày cụ thể cần so sánh — resolve `issued_date` thật của CHÍNH văn
    bản đó, không hard-code ngày ký tay (tránh một nguồn số liệu kỳ vọng sai
    lệch với chính `trich_ngay_ky` mà bước 1/2 đã kiểm riêng)."""
    if ky_vong is None:
        return None
    if ky_vong == "ky":
        return trich_ngay_ky(extracted_text).issued_date
    if isinstance(ky_vong, tuple) and ky_vong[0] == "ky_plus":
        ngay_ky = trich_ngay_ky(extracted_text).issued_date
        return ngay_ky + timedelta(days=ky_vong[1]) if ngay_ky else None
    return ky_vong


def test_do_chinh_xac_tren_21_van_ban_that_it_nhat_90_phan_tram(corpus_extracted_texts):
    sai: list[str] = []

    for duong_dan, ky_vong_ma_hoa in GROUND_TRUTH_HIEU_LUC:
        extracted_text = corpus_extracted_texts[duong_dan]
        ky_vong = _ky_vong_thanh_ngay(ky_vong_ma_hoa, extracted_text)
        thuc_te = trich_ngay_hieu_luc(extracted_text).effective_date

        if thuc_te != ky_vong:
            sai.append(f"{duong_dan}: kỳ vọng={ky_vong} thực tế={thuc_te}")

    tong = len(GROUND_TRUTH_HIEU_LUC)
    dung = tong - len(sai)
    ty_le = dung / tong

    assert ty_le >= 0.90, (
        f"Chỉ đạt {dung}/{tong} ({ty_le:.1%}), cần ≥90% (docs/09 hàng T2.4). "
        f"Sai lệch:\n" + "\n".join(sai)
    )


def test_ca_khong_resolve_duoc_van_tinh_la_dung_khi_tra_ve_none(corpus_extracted_texts):
    """Xác nhận rõ ca "không resolve được" (110-2004-nd-cp — cần ngày đăng
    Công báo, văn bản không tự chứa) trả về đúng `None`, không đoán bừa
    bằng một ngày nào khác (06 Mục 6.4)."""
    duong_dan = "hanh-chinh-tong-hop/110-2004-nd-cp.docx"
    ket_qua = trich_ngay_hieu_luc(corpus_extracted_texts[duong_dan])
    assert ket_qua.effective_date is None
