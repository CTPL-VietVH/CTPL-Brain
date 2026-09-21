"""GĐ5 — Gán nhãn phân loại và trích ngày ký (T2.4, PHẦN 1/2).

`06` Mục 5.2 GĐ5 (dòng 254-256): *"Gán nhãn phân loại và trích ngày. **Máy
gợi ý, người đưa tài liệu vào xác nhận.** ... Bước này cũng trích ngày ký và
ngày có hiệu lực từ chính văn bản rồi đưa ra cho người xác nhận ... Trích
được thì ngày mang nguồn máy trích; người sửa lại thì thành người xác nhận;
không trích được và không ai điền thì rơi về mặc định ngày nạp và trục thời
gian không tin nó."*

⚠️ **PHẦN 2/2 (ngày CÓ HIỆU LỰC / `effective_date`) KHÔNG nằm trong module
này** — tách sang work-order riêng vì đang chờ kết quả nghiên cứu song song
(`T2.4-research-effective-date-patterns`). `07` Phụ lục A dòng 466 xác nhận
lý do tách: *"ngày ký có khuôn mẫu chuẩn hoá ở đầu văn bản, trích bằng khuôn
mẫu là đủ. Ngày hiệu lực thì khó hơn — nằm ở điều khoản thi hành cuối văn
bản, và phải tránh nhầm với ngày của văn bản bị thay thế được nhắc trong
cùng câu."* — hai độ khó khác hẳn nhau, không dùng chung một khuôn.

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
from datetime import date

from schema.document import DateSource

__all__ = ["GoiYNgayKy", "goi_y_nhan", "trich_ngay_ky"]


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
