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

A third section (`extract_subject_entities`, task T2.4-add-subject-entities)
now also lives in this module — the `subject_entities` suggestion locked at
`07` Section 2.1 line 93 + callout lines 127-135, 2026-09-22. Written in
English per CLAUDE.md Section 0 #4; see that section's own comment block
near the end of this file for the extraction method.

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
    "SubjectEntitySuggestion",
    "extract_subject_entities",
    "DocNumberSuggestion",
    "extract_document_number",
    "TitleSuggestion",
    "extract_title",
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


# ---------------------------------------------------------------------------
# Subject entities — schema decision at `docs/07` Section 2.1 line 93 +
# callout lines 127-135 (LOCKED 2026-09-22, task T2.4-add-subject-entities).
# Written in English per CLAUDE.md Section 0 #4 (LOCKED 2026-09-22): all new
# identifiers/comments/docstrings in this section are English; the
# surrounding Vietnamese functions above are untouched legacy code, not
# renamed here (boy-scout rule applies only where this work-order touches).
#
# Suggestion only — feeds the K3 relation-suggestion mechanism at GĐ7
# ("docs/06" Section 5.3, 6.2), NOT persisted to `Document` and NOT
# confirmed by this module. No `_confirmed_by`/`_at` pair on the schema
# field, unlike `category_labels`: this is an internal signal nobody
# reviews directly, and the relation it feeds already carries its own
# approval step (`relation.approval_state`) — see "docs/07" line 135.
#
# Three anchor positions, tried in PRIORITY ORDER — stop at the first anchor
# that produces a signal, matching the "V/v"/title/Điều 1 order agreed for
# this task:
#   (1) the "V/v" subject line near the top of the document — individual
#       acts (Quyết định/Công văn); the whole subject-line phrase IS the
#       entity (e.g. "V/v: Bổ nhiệm ông Nguyễn Văn A giữ chức vụ Giám đốc").
#   (2) UPPERCASE title — Luật/Nghị định/Thông tư/Nghị quyết/Pháp lệnh/Bộ
#       luật; find the document-type keyword at the START of a line within
#       the head-of-document window, then take the remainder of that same
#       line if non-empty (e.g. "LUẬT XÂY DỰNG" -> "XÂY DỰNG"), else the
#       next non-blank line (e.g. "NGHỊ ĐỊNH" followed on the next line by
#       "Quy định về tuyển dụng, sử dụng và quản lý công chức").
#   (3) fallback: Điều 1 "Phạm vi điều chỉnh"/"Phạm vi áp dụng" when (1) and
#       (2) found no signal — take the clause after "quy định về"/"quy định
#       việc" inside that article's text.
#
# Multi-valued: a document can name more than one subject, so every match
# found via the WINNING anchor is returned, not just the first. No anchor
# matches anywhere -> empty list, never guessed (project-wide "no silent
# inference" principle, same spirit as `goi_y_nhan`/`trich_ngay_ky` above).
# ---------------------------------------------------------------------------
_TITLE_KEYWORDS = ("BỘ LUẬT", "LUẬT", "NGHỊ ĐỊNH", "NGHỊ QUYẾT", "THÔNG TƯ", "PHÁP LỆNH")

# No anchor at line start: the real "V/v" line commonly follows a document
# number prefix on the same line (e.g. "Số: 15/QĐ-UBND V/v: Bổ nhiệm ..."),
# so anchoring at line start would miss it. Stops at a table-cell delimiter
# ("|", used by the docx table-cell join in `ingestion.reader`) or newline.
_SUBJECT_LINE_PATTERN = re.compile(r"[Vv]\s*/\s*[Vv][:.]?\s*(.+?)(?:\s*\||\n|$)")

_UPPERCASE_TITLE_PATTERN = re.compile(
    r"^(?:" + "|".join(re.escape(keyword) for keyword in _TITLE_KEYWORDS) + r")\b[ \t]*(.*)$",
    re.MULTILINE,
)

# Terminates at the next "Điều N." heading or a blank line — a plain "\n\n"
# terminator alone misses articles immediately followed by "Điều 2." on the
# very next line with no blank line in between (observed in real corpus
# files, e.g. Luật-50-2014-QH13.docx).
_SCOPE_ARTICLE_PATTERN = re.compile(
    r"Điều\s+1\.\s*Phạm\s+vi\s+(?:điều\s+chỉnh|áp\s+dụng)\s*\n?(.+?)(?:\n\s*Điều\s+\d|\n\n|\Z)",
    re.IGNORECASE | re.DOTALL,
)
# Alternation order matters: "về việc" must be tried before the shorter "về"
# alone, or the standalone "về" branch would win first and leave a stray
# leading "việc" in the captured clause.
_SCOPE_STATEMENT_PATTERN = re.compile(
    r"quy\s+định\s+(?:về\s+việc|về|việc)\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)


def _dedup_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _entities_from_subject_line(extracted_text: str) -> list[str]:
    head = extracted_text[:_DO_DAI_QUET_DAU_VAN_BAN]
    candidates = [
        match.group(1).strip(" .:") for match in _SUBJECT_LINE_PATTERN.finditer(head)
    ]
    return _dedup_preserve_order([candidate for candidate in candidates if candidate])


def _entities_from_uppercase_title(extracted_text: str) -> list[str]:
    head_lines = extracted_text[:_DO_DAI_QUET_DAU_VAN_BAN].split("\n")
    candidates: list[str] = []
    for index, line in enumerate(head_lines):
        match = _UPPERCASE_TITLE_PATTERN.match(line.strip())
        if match is None:
            continue
        remainder = match.group(1).strip(" .")
        if remainder:
            candidates.append(remainder)
            continue
        for next_line in head_lines[index + 1 :]:
            next_line = next_line.strip()
            if next_line:
                candidates.append(next_line.strip(" ."))
                break
    return _dedup_preserve_order(candidates)


def _entities_from_scope_article(extracted_text: str) -> list[str]:
    article_match = _SCOPE_ARTICLE_PATTERN.search(extracted_text)
    if article_match is None:
        return []
    statement_match = _SCOPE_STATEMENT_PATTERN.search(article_match.group(1))
    if statement_match is None:
        return []
    candidate = statement_match.group(1).strip(" .")
    return [candidate] if candidate else []


@dataclass(frozen=True, slots=True, kw_only=True)
class SubjectEntitySuggestion:
    """Suggested `Document.subject_entities` — NOT written to `Document`, no
    confirmation step recorded ("docs/07" line 135: internal signal feeding
    K3, "docs/06" Section 5.3).
    """

    subject_entities: list[str]


def extract_subject_entities(extracted_text: str) -> SubjectEntitySuggestion:
    """Suggest `Document.subject_entities` — GĐ5 ("docs/06" Section 5.2),
    schema decision at "docs/07" Section 2.1 line 93 + callout lines 127-135
    (LOCKED 2026-09-22).

    Tries the three anchors in priority order (see module comment above)
    and returns every entity found via the first anchor that produced a
    signal. No anchor matches anywhere -> empty list, never inferred.
    """
    for extractor in (
        _entities_from_subject_line,
        _entities_from_uppercase_title,
        _entities_from_scope_article,
    ):
        entities = extractor(extracted_text)
        if entities:
            return SubjectEntitySuggestion(subject_entities=entities)
    return SubjectEntitySuggestion(subject_entities=[])


# ---------------------------------------------------------------------------
# title / doc_number — task T2.4b (docs/10 §4.2: "AI gợi ý ... BE không gửi
# chúng khi nộp"; §4.3: người sửa qua PATCH). "docs/07" §2.1: nguồn của cả
# hai trường là Ingestion. Written in English per CLAUDE.md Section 0 #4.
#
# Both reuse the SAME front-matter window: real Vietnamese administrative
# documents put the letterhead (issuing body, "Số: ..."), the document-type
# line ("NGHỊ ĐỊNH" / "LUẬT" / ...) and the trích yếu (subject line) — in
# that order — before the first "Căn cứ ..." recital. `_front_matter_end`
# reuses the SAME anchor-2 pattern (`_UPPERCASE_TITLE_PATTERN`,
# `_TITLE_KEYWORDS`) that `_entities_from_uppercase_title` already uses, per
# the work-order instruction to not write a parallel detector.
#
# ⚠️ Neither anchor found -> window is UNBOUNDED-UNSAFE, so both extractors
# refuse rather than fall back to a fixed-length window: a body citation like
# "Căn cứ Nghị định số 48/2008/NĐ-CP ..." contains its own "số :" and would
# leak into doc_number if the window were not bounded by a real anchor.
# ---------------------------------------------------------------------------
_CAN_CU_LINE_PATTERN = re.compile(r"^[ \t]*Căn cứ\b", re.MULTILINE | re.IGNORECASE)


def _front_matter_end(extracted_text: str) -> int | None:
    """First of (document-type line, "Căn cứ" line) — `None` if neither is
    found anywhere in `extracted_text`."""
    starts = [
        match.start()
        for match in (
            _UPPERCASE_TITLE_PATTERN.search(extracted_text),
            _CAN_CU_LINE_PATTERN.search(extracted_text),
        )
        if match is not None
    ]
    return min(starts) if starts else None


# Catches "Số:", "Luật số:", "Bộ luật số:" in one pattern — "Luật\s*số"
# already matches the tail of "Bộ luật số:" too, so a third alternative is
# not needed for correctness, but is kept explicit for readability against
# the work-order's own wording. `re.IGNORECASE`: OCR'd PDFs lower-case the
# whole line sometimes (observed: "số: 200/2014/TT-BTC"). No anchor required
# before "Số" — a letterhead abbreviation commonly sits flush against it with
# no space (observed: "CHÍNH PHỦ––––Số: 110/2004/NĐ-CP").
_DOC_NUMBER_PATTERN = re.compile(
    r"(?:Bộ\s*luật\s*số|Luật\s*số|Số)\s*:\s*(\S+)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class DocNumberSuggestion:
    """Suggested `Document.doc_number` — NOT written to `Document` (same
    contract as every other GĐ5 suggestion in this module).

    `source_span` is a `(start, end)` character offset pair (Unicode
    code-point indices into `extracted_text`, per CLAUDE.md Mục 5 — never
    byte offsets) pointing at the matched number token, or `None` when
    `doc_number == ""`. This is NOT a schema field (07 §2.1 gives
    `doc_number` no companion span column) — it exists only for a caller
    that wants to show a reviewer WHERE the suggestion came from.
    """

    doc_number: str
    source_span: tuple[int, int] | None


def extract_document_number(extracted_text: str) -> DocNumberSuggestion:
    """Suggest `Document.doc_number` from the front matter — GĐ5 (task
    T2.4b), "docs/10" §4.2.

    `doc_number` is the join key `relations.py` uses for explicit-citation
    linking (`_normalized_document_number`), and DX1 treats that link as
    CERTAIN — so this function follows "THÀ TRỐNG CÒN HƠN SAI" (PO chốt):
    it returns `""` the moment it is not confident, rather than a number
    that merely looks plausible. In particular it NEVER reads past
    `_front_matter_end`, so a citation embedded in a "Căn cứ ... số ..."
    recital (this document CITING another one) can never be mistaken for
    this document's own number.
    """
    boundary = _front_matter_end(extracted_text)
    if boundary is None:
        return DocNumberSuggestion(doc_number="", source_span=None)

    match = _DOC_NUMBER_PATTERN.search(extracted_text, 0, boundary)
    if match is None:
        return DocNumberSuggestion(doc_number="", source_span=None)

    return DocNumberSuggestion(
        doc_number=match.group(1), source_span=(match.start(1), match.end(1))
    )


def _is_all_uppercase(text: str) -> bool:
    return any(character.isalpha() for character in text) and text == text.upper()


@dataclass(frozen=True, slots=True, kw_only=True)
class TitleSuggestion:
    """Suggested `Document.title` — NOT written to `Document` (same contract
    as every other GĐ5 suggestion in this module).

    `source_span` — same shape and same rationale as
    `DocNumberSuggestion.source_span` — covers the document-type line
    through the last trích yếu line consumed, or `None` when `title == ""`.
    """

    title: str
    source_span: tuple[int, int] | None


def extract_title(extracted_text: str) -> TitleSuggestion:
    """Suggest `Document.title` from the front matter — GĐ5 (task T2.4b),
    "docs/10" §4.2.

    `title` = document-type keyword + trích yếu (subject clause), WITHOUT
    the number ("docs/10" §4.2 keeps them as two separate suggestions).
    Reuses the anchor-2 pattern (`_UPPERCASE_TITLE_PATTERN`) that
    `_entities_from_uppercase_title` already uses to find the type line.

    The trích yếu may span more than one physical line in `extracted_text`
    — both a genuine multi-paragraph subject line AND a manual mid-sentence
    line-wrap look identical there (both are just "\\n": see
    `packages/ingestion/reader/readers.py::_doc_docx`, one paragraph per
    line). The two are told apart by CASE, not by newlines: a continuation
    of an unfinished clause starts lower-case ("...giao thông\\ntrong lĩnh
    vực...", real file `168.2024.NĐ.CP.docx`); a new, unrelated line — the
    issuing body repeated before the "Căn cứ" recitals ("CHÍNH PHỦ", real
    file `110-2004-nd-cp.docx`) — starts upper-case and must NOT be pulled
    in. The FIRST content line after the type keyword is always taken
    unconditionally (there is nothing yet to compare its case against);
    every line after that must start lower-case to be appended, and a
    blank line or a "Căn cứ" line always stops the scan.

    "IN HOA toàn bộ chuyển kiểu câu, đoạn đã viết thường/hoa lẫn thì giữ
    nguyên chữ" (T2.4b spec item 3): the type keyword is always rendered in
    sentence case (`"NGHỊ ĐỊNH" -> "Nghị định"`); the trích yếu is
    lower-cased ONLY when it is ALL CAPS end to end — a trích yếu that
    already mixes case (the normal way Vietnamese prose is written) is
    passed through byte-for-byte.

    No document-type line found anywhere -> `""`, never a guess built from
    a filename or from unrelated text (docs/10 §4.2 forbids the filename
    specifically).
    """
    match = _UPPERCASE_TITLE_PATTERN.search(extracted_text)
    if match is None:
        return TitleSuggestion(title="", source_span=None)

    matched_line = match.group(0)
    type_keyword = next(
        keyword for keyword in _TITLE_KEYWORDS if matched_line.startswith(keyword)
    )
    remainder = match.group(1).strip(" .")

    parts: list[str] = [remainder] if remainder else []
    span_end = match.end()
    text_length = len(extracted_text)
    # `match.end()` sits AT the matched line's own trailing "\n" ('$' in
    # MULTILINE mode matches before "\n" without consuming it) — step past
    # it once before scanning subsequent lines, or the first `find("\n",
    # cursor)` below would find that SAME newline and yield an empty line.
    cursor = match.end() + 1 if match.end() < text_length else match.end()
    while cursor < text_length:
        newline_index = extracted_text.find("\n", cursor)
        line_end = newline_index if newline_index != -1 else text_length
        line = extracted_text[cursor:line_end].strip()
        if not line:
            break
        if _CAN_CU_LINE_PATTERN.match(line):
            break
        if parts and not line[0].islower():
            break
        parts.append(line)
        span_end = line_end
        cursor = line_end + 1
        if newline_index == -1:
            break

    if not parts:
        return TitleSuggestion(title="", source_span=None)

    subject_clause = " ".join(parts)
    if _is_all_uppercase(subject_clause):
        subject_clause = subject_clause.lower()

    title = f"{type_keyword.capitalize()} {subject_clause}"
    return TitleSuggestion(title=title, source_span=(match.start(), span_end))
