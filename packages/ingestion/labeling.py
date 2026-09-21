"""GĐ5 — Gán nhãn phân loại và trích ngày ký (T2.4, PHẦN 1/2).

`06` Mục 5.2 GĐ5 (dòng 254-256): *"Gán nhãn phân loại và trích ngày. **Máy
gợi ý, người đưa tài liệu vào xác nhận.** ... Bước này cũng trích ngày ký và
ngày có hiệu lực từ chính văn bản rồi đưa ra cho người xác nhận ... Trích
được thì ngày mang nguồn máy trích; người sửa lại thì thành người xác nhận;
không trích được và không ai điền thì rơi về mặc định ngày nạp và trục thời
gian không tin nó."*

⚠️ **PHẦN 2/2 (ngày CÓ HIỆU LỰC / `effective_date`, `trich_ngay_hieu_luc`)
nay ĐÃ CÓ trong module này** (T2.4-implement-effective-date) — ban đầu tách
sang work-order riêng vì chờ kết quả nghiên cứu song song
(`T2.4-research-effective-date-patterns` + `T2.4-validate-...-vs-corpus`).
`07` Phụ lục A dòng 466: *"ngày ký có khuôn mẫu chuẩn hoá ở đầu văn bản,
trích bằng khuôn mẫu là đủ. Ngày hiệu lực thì khó hơn — nằm ở điều khoản thi
hành cuối văn bản, và phải tránh nhầm với ngày của văn bản bị thay thế được
nhắc trong cùng câu."* — hai độ khó khác hẳn nhau, hai khuôn khác nhau, dùng
lại `trich_ngay_ky` khi cần (không viết lại logic trích ngày ký).

**Module này chỉ TRẢ VỀ giá trị gợi ý — không ghi/persist vào `Document`,
không tự đánh dấu đã xác nhận.** Đúng câu "máy gợi ý, người xác nhận":
quyết định ghi vào `labels_confirmed_by`/`labels_confirmed_at` hay sửa
`issued_date_source` thành `CONFIRMED` là việc của luồng khác (người đưa
tài liệu vào xác nhận), ngoài phạm vi T2.4.

`06` Mục 6.4 — ba giá trị nguồn của một ngày: *máy trích từ chính văn bản /
người xác nhận / mặc định ngày nạp*, ánh xạ đúng ba giá trị enum
`DateSource` đã có sẵn ở `packages/schema/document.py` (07 Mục 2.1):
`EXTRACTED` / `CONFIRMED` / `DEFAULT_INGESTION_DATE`. **Trục thời gian chỉ
tin hai nguồn đầu** — không trích được thì để `issued_date=None`, TUYỆT ĐỐI
không suy diễn một ngày "trông hợp lý" (06 Mục 6.4 cấm rõ).

⚠️ **`category_labels` — KHÔNG có taxonomy cố định nào được chốt trong
`docs/`.** `07` dòng 91 chỉ ghi *"danh sách nhãn, Ingestion gợi ý (GĐ5)"*,
không kèm danh sách đóng nào. Danh sách từ khoá LOẠI VĂN BẢN dưới đây
(`_TU_KHOA_LOAI_VAN_BAN`) là **GIẢ ĐỊNH TẠM của T2.4, không phải đặc tả đã
chốt** — xem báo cáo T2.4 phần Escalations. Nó chỉ nhận diện THỂ LOẠI hành
chính (Quyết định / Nghị định / Thông tư / ...) qua từ khoá xuất hiện ở đầu
văn bản — cố ý KHÔNG suy luận chủ đề/lĩnh vực (tài chính, nhân sự, ...) vì
việc đó cần một taxonomy đã chốt mà hiện chưa có.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from schema.document import DateSource

__all__ = [
    "GoiYNgayKy",
    "GoiYNgayHieuLuc",
    "goi_y_nhan",
    "trich_ngay_ky",
    "trich_ngay_hieu_luc",
]


# ---------------------------------------------------------------------------
# Ngày ký — GĐ5 phần "dễ" (07 Phụ lục A dòng 466).
#
# Khuôn mẫu chuẩn hành chính VN: "<Địa danh>, ngày DD tháng MM năm YYYY",
# thường đứng MỘT MÌNH ở đầu văn bản (dưới quốc hiệu/tiêu ngữ, cạnh số hiệu)
# và lặp lại ở khối ký tên cuối văn bản — cả hai vị trí đều là NGÀY KÝ thật,
# nên lấy trận khớp ĐẦU TIÊN là đủ.
#
# ⚠️ Bẫy đã biết và cách né: một câu dẫn chiếu văn bản khác cũng chứa cụm
# "ngày D tháng M năm Y" (vd "Căn cứ Quyết định số 115/QĐ-TCT ngày 12 tháng 3
# năm 2025") — nhưng KHÔNG có dấu PHẨY ngay trước "ngày" và KHÔNG đứng đầu
# dòng, vì nó luôn đi kèm số hiệu văn bản ngay trước đó. Bắt buộc một trong
# hai: đứng ĐẦU DÒNG, hoặc có DẤU PHẨY ngay trước — để phân biệt dòng ngày
# ký (đứng riêng) khỏi câu dẫn chiếu (nằm giữa câu dài hơn).
#
# ⚠️ GIỚI HẠN CÒN LẠI (chưa xử lý, chấp nhận vì đây chỉ là GỢI Ý cho người
# xác nhận): một câu dẫn chiếu CŨNG có dấu phẩy trước "ngày" (kiểu "Nghị định
# số 15/2020/NĐ-CP, ngày 03 tháng 02 năm 2020 của Chính phủ") vẫn có thể bị
# nhận nhầm. Người xác nhận sẽ thấy và sửa — đúng cơ chế "máy gợi ý, người
# xác nhận" mà 06 Mục 5.2 GĐ5 mô tả.
_MAU_NGAY_KY = re.compile(
    r"(?:^[ \t]*|,[ \t]*)[Nn]gày[ \t]+(\d{1,2})[ \t]+tháng[ \t]+(\d{1,2})[ \t]+năm[ \t]+(\d{4})\b",
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GoiYNgayKy:
    """Kết quả gợi ý ngày ký — CHƯA ghi vào `Document`, chỉ để người xác nhận.

    `issued_date=None` kèm `issued_date_source=DEFAULT_INGESTION_DATE` nghĩa
    là "chưa ai biết ngày thật" (06 Mục 6.4) — bên gọi (luồng GĐ1/T2.1) chịu
    trách nhiệm điền `Document.issued_date` bằng ngày nạp thật của nó, module
    này không tự bịa một ngày.
    """

    issued_date: date | None
    issued_date_source: DateSource


def trich_ngay_ky(extracted_text: str) -> GoiYNgayKy:
    """Trích ngày ký từ văn bản đã đọc ra — GĐ5 phần ngày (06 Mục 5.2, 6.4).

    Trích được → `EXTRACTED` kèm ngày. Không trích được, hoặc trích được một
    chuỗi số không phải ngày thật (vd "31 tháng 4") → `DEFAULT_INGESTION_DATE`
    kèm `issued_date=None` — KHÔNG đoán một ngày khác thay thế.
    """
    for so_ngay, so_thang, so_nam in _MAU_NGAY_KY.findall(extracted_text):
        try:
            ngay = date(int(so_nam), int(so_thang), int(so_ngay))
        except ValueError:
            continue
        return GoiYNgayKy(issued_date=ngay, issued_date_source=DateSource.EXTRACTED)

    return GoiYNgayKy(issued_date=None, issued_date_source=DateSource.DEFAULT_INGESTION_DATE)


# ---------------------------------------------------------------------------
# Nhãn phân loại — GIẢ ĐỊNH TẠM, không phải taxonomy đã chốt (xem docstring
# đầu file). Chỉ nhận diện THỂ LOẠI hành chính, không suy luận chủ đề/lĩnh
# vực.
# ---------------------------------------------------------------------------
_TU_KHOA_LOAI_VAN_BAN = (
    "NGHỊ QUYẾT",
    "NGHỊ ĐỊNH",
    "QUYẾT ĐỊNH",
    "CHỈ THỊ",
    "THÔNG TƯ",
    "THÔNG BÁO",
    "CÔNG VĂN",
    "TỜ TRÌNH",
    "BIÊN BẢN",
    "BÁO CÁO",
    "KẾ HOẠCH",
    "QUY CHẾ",
    "QUY TRÌNH",
    "QUY ĐỊNH",
    "HỢP ĐỒNG",
)

# Chỉ quét phần ĐẦU văn bản — quy chuẩn trình bày hành chính VN luôn nêu thể
# loại ở dòng tiêu đề gần đầu (dưới quốc hiệu/tiêu ngữ hoặc số hiệu). Quét cả
# văn bản sẽ bắt nhầm các từ khoá này khi chúng xuất hiện lại trong một câu
# dẫn chiếu ở thân bài (vd "... theo Quyết định số 12/QĐ-... ").
_DO_DAI_QUET_DAU_VAN_BAN = 300


def goi_y_nhan(extracted_text: str) -> list[str]:
    """Gợi ý `category_labels` — GĐ5 phần nhãn (06 Mục 5.2, NT4: tín hiệu MỀM).

    Trả về danh sách RỖNG nếu không nhận diện được từ khoá nào — không suy
    diễn, không mặc định một nhãn "chung chung" nào để lấp chỗ trống.
    """
    dau_van_ban = extracted_text[:_DO_DAI_QUET_DAU_VAN_BAN].upper()
    return [tu_khoa for tu_khoa in _TU_KHOA_LOAI_VAN_BAN if tu_khoa in dau_van_ban]


# ---------------------------------------------------------------------------
# Ngày CÓ HIỆU LỰC — GĐ5 phần "khó" (07 Phụ lục A dòng 466), T2.4 bước 2/2.
#
# Khuôn theo `T2.4-research-effective-date-patterns`, đối chiếu tay + sửa lỗi
# trên 21 văn bản thật (`T2.4-validate-effective-date-patterns-vs-corpus`,
# số liệu đã sửa 21/9/2026 — xem TASKS.md mục Done).
#
# ⭐ Phân biệt CÂU TUYÊN BỐ hiệu lực khỏi CÂU MƯỢN "ngày văn bản có hiệu lực"
# LÀM MỐC cho một nghĩa vụ khác, bằng THỨ TỰ TỪ — không cần một danh sách từ
# khoá bẫy riêng để loại câu mượn mốc:
#
#   * Tuyên bố THẬT:  "<văn bản> CÓ HIỆU LỰC (thi hành) ... (kể) TỪ NGÀY ..."
#     — "có hiệu lực" đứng TRƯỚC "từ ngày".
#   * Câu mượn mốc:    "... KỂ TỪ NGÀY <văn bản> CÓ HIỆU LỰC (thi hành) ..."
#     — thứ tự NGƯỢC LẠI. Ví dụ thật (47_2021_nd-cp_470561.docx): *"Trong
#     thời hạn 01 năm kể từ ngày Nghị định này có hiệu lực thi hành và 06
#     tháng trước kỳ..."* — đây KHÔNG phải câu tuyên bố hiệu lực, chỉ dùng nó
#     làm mốc đếm thời hạn cho việc khác. Bắt "có hiệu lực" phải đứng NGAY
#     TRƯỚC "từ ngày" (chỉ chen được tối đa "thi hành"/"áp dụng"/"sau N
#     ngày"/dấu phẩy ở giữa) loại thẳng câu mượn mốc vì thứ tự từ của nó
#     không khớp được mẫu.
#
# ⭐ Bẫy "ngày đi ngay sau số hiệu văn bản BỊ THAY THẾ" cũng tự động bị né mà
# không cần danh sách từ khoá "thay thế"/"bãi bỏ" riêng: cụm bắt được luôn
# bắt đầu NGAY SAU "từ ngày", còn ngày của văn bản bị thay thế nằm Ở XA HƠN
# trong cùng câu. Ví dụ thật (2021_291 + 292_06-2021-NĐ-CP.pdf, Điều 54):
# *"Nghị định này có hiệu lực từ ngày ký ban hành và thay thế Nghị định số
# 46/2015/NĐ-CP ngày 12 tháng 5 năm 2015..."* — cụm bắt được là "ngày ký ban
# hành..." (phân loại là NGÀY KÝ ngay từ tiền tố "ngày ký"); "12 tháng 5 năm
# 2015" nằm sau đó trong cùng câu nhưng KHÔNG BAO GIỜ được xét tới vì việc
# phân loại chỉ đọc TIỀN TỐ của cụm bắt được (`_MAU_NGAY_KY_TAI_MUC_TIEU`
# v.v.), không quét toàn bộ cụm tìm ngày.
#
# ⭐ Bẫy thứ ba, phát hiện lúc chạy tập thử 21 văn bản thật (không có trong
# báo cáo nghiên cứu ban đầu — T2.4-implement-effective-date tự tìm ra):
# CHỦ THỂ của "có hiệu lực" phải là CHÍNH văn bản đang đọc, không phải một
# quyết định/hợp đồng/nghị quyết KHÁC được nhắc TRONG nội dung văn bản. Ví dụ
# sai nếu không chặn — `Bộ-luật-45-2019-QH14.docx`: *"Hợp đồng lao động có
# hiệu lực kể từ ngày hai bên giao kết..."* (Điều 23, nói về hợp đồng lao
# động, KHÔNG phải chính Bộ luật) xuất hiện TRƯỚC "Điều 220. Hiệu lực thi
# hành" — lấy trận khớp đầu tiên mà không lọc chủ thể sẽ chụp nhầm câu này.
# Bắt buộc "có hiệu lực" phải đứng ngay sau CỤM TỰ THAM CHIẾU "<Loại văn bản>
# này" (Nghị định này / Luật này / Bộ luật này / Thông tư này / Quyết định
# này / Chỉ thị này / Nghị quyết này / Pháp lệnh này / Quy chế này) — đúng
# cách văn bản hành chính VN luôn tự xưng khi tuyên bố hiệu lực của CHÍNH nó.
_MAU_CHU_THE_TU_THAM_CHIEU = (
    r"(?:Nghị\s+định|Nghị\s+quyết|Bộ\s+luật|Luật|"
    r"Thông\s+tư(?:\s+liên\s+tịch)?|Quyết\s+định|Chỉ\s+thị|Pháp\s+lệnh|Quy\s+chế)"
    r"\s+này"
)

_MAU_KICH_HOAT_HIEU_LUC = re.compile(
    _MAU_CHU_THE_TU_THAM_CHIEU
    + r"\s+có hiệu lực(?:\s+thi hành)?(?:\s+áp dụng)?"
    + r"(?:\s+sau\s+(\d+)\s*ngày)?"
    + r"\s*,?\s*(?:kể\s+)?từ\s+(ngày[^\n]{0,80})",
    re.IGNORECASE,
)

_MAU_NGAY_KY_TAI_MUC_TIEU = re.compile(r"^ngày\s+ký\b", re.IGNORECASE)
_MAU_CONG_BAO_TAI_MUC_TIEU = re.compile(r"^ngày\s+đăng\s+công\s+báo\b", re.IGNORECASE)
_MAU_NGAY_CU_THE_TAI_MUC_TIEU = re.compile(
    r"^ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})\b", re.IGNORECASE
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GoiYNgayHieuLuc:
    """Kết quả gợi ý ngày có hiệu lực — cùng khuôn `GoiYNgayKy`, CHƯA ghi vào
    `Document`, không tự đánh dấu đã xác nhận.

    `effective_date=None` kèm `DEFAULT_INGESTION_DATE` nghĩa là "chưa ai biết
    ngày thật" (06 Mục 6.4) — bao gồm cả trường hợp văn bản quy định hiệu lực
    theo một SỰ KIỆN module này không trích được từ `extracted_text` (ví dụ
    "sau N ngày kể từ ngày ĐĂNG CÔNG BÁO" — không có ngày đăng Công báo trong
    văn bản, TUYỆT ĐỐI không suy diễn bằng ngày ký thay thế).
    """

    effective_date: date | None
    effective_date_source: DateSource


def trich_ngay_hieu_luc(extracted_text: str) -> GoiYNgayHieuLuc:
    """Trích ngày có hiệu lực — GĐ5 phần "khó" (06 Mục 5.2, 6.4), T2.4 bước 2/2.

    Chỉ xét TRẬN KHỚP ĐẦU TIÊN của cụm kích hoạt trong văn bản — đây chính là
    cách lấy đúng "mốc của khoản/điều CHÍNH": văn bản luôn nêu quy tắc chung
    trước (Khoản 1) rồi mới tới ngoại lệ (Khoản 2 "trừ quy định tại khoản
    2..."). CỐ Ý KHÔNG dò tiếp trận khớp sau khi trận đầu không resolve
    được — dò tiếp có thể vô tình lấy một mốc NGOẠI LỆ (Khoản 2, chỉ áp dụng
    cho một phần nhỏ) làm mốc hiệu lực chung, sai còn nặng hơn cả việc trả về
    "không biết".

    "Kể từ ngày ký" / "từ ngày ký" → `effective_date = issued_date` (gọi
    `trich_ngay_ky`, không suy luận lại). "Sau N ngày kể từ ngày ký" →
    `issued_date + N ngày` nếu `issued_date` trích được, ngược lại KHÔNG
    resolve. "... kể từ ngày đăng Công báo" (có hay không kèm "sau N ngày")
    → KHÔNG resolve — văn bản không tự chứa ngày đăng Công báo của chính nó.
    """
    match = _MAU_KICH_HOAT_HIEU_LUC.search(extracted_text)
    if match is None:
        return GoiYNgayHieuLuc(
            effective_date=None, effective_date_source=DateSource.DEFAULT_INGESTION_DATE
        )

    so_ngay_tre, muc_tieu = match.group(1), match.group(2)
    so_ngay_tre = int(so_ngay_tre) if so_ngay_tre is not None else None

    if _MAU_NGAY_KY_TAI_MUC_TIEU.match(muc_tieu):
        goi_y_ngay_ky = trich_ngay_ky(extracted_text)
        if goi_y_ngay_ky.issued_date is None:
            return GoiYNgayHieuLuc(
                effective_date=None, effective_date_source=DateSource.DEFAULT_INGESTION_DATE
            )
        hieu_luc = (
            goi_y_ngay_ky.issued_date + timedelta(days=so_ngay_tre)
            if so_ngay_tre is not None
            else goi_y_ngay_ky.issued_date
        )
        return GoiYNgayHieuLuc(effective_date=hieu_luc, effective_date_source=DateSource.EXTRACTED)

    if _MAU_CONG_BAO_TAI_MUC_TIEU.match(muc_tieu):
        return GoiYNgayHieuLuc(
            effective_date=None, effective_date_source=DateSource.DEFAULT_INGESTION_DATE
        )

    khop_ngay_cu_the = _MAU_NGAY_CU_THE_TAI_MUC_TIEU.match(muc_tieu)
    if khop_ngay_cu_the:
        so_ngay, so_thang, so_nam = khop_ngay_cu_the.groups()
        try:
            hieu_luc = date(int(so_nam), int(so_thang), int(so_ngay))
        except ValueError:
            return GoiYNgayHieuLuc(
                effective_date=None, effective_date_source=DateSource.DEFAULT_INGESTION_DATE
            )
        return GoiYNgayHieuLuc(effective_date=hieu_luc, effective_date_source=DateSource.EXTRACTED)

    # Cụm kích hoạt khớp nhưng mục tiêu không rơi vào ba hình dạng đã biết
    # (vd hiệu lực theo một sự kiện lạ) — KHÔNG đoán, trả về chưa biết.
    return GoiYNgayHieuLuc(
        effective_date=None, effective_date_source=DateSource.DEFAULT_INGESTION_DATE
    )
