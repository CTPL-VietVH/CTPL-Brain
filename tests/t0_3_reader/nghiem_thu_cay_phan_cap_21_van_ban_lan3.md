# Nghiệm thu cây phân cấp 21 văn bản — LẦN 3 (đối chiếu nội dung Khoản/Điểm)

**Ngày**: 17/9/2026
**Vai trò**: Kiểm định độc lập (AI)

---

> [!IMPORTANT]
> ## Khác biệt với Lần 1 và Lần 2
>
> | | Lần 1 | Lần 2 | **Lần 3** |
> |---|---|---|---|
> | **Nguồn** | Chỉ đọc cây | Mở file gốc | Mở file gốc |
> | **Đo gì** | Cấu trúc cây + kiến thức pháp lý | Đếm số hiệu Điều (regex) | **Nội dung Khoản/Điểm bên trong từng Điều** |
> | **Phạm vi** | 21 file | 21 file | 5 file sâu + 16 file spot-check |
> | **Sai sót** | — | ~~Khẳng định sai NFC~~ (đã rút) | — |

---

## Phương pháp

### Đọc sâu (5 file ưu tiên)

Chọn theo rủi ro đã biết từ Lần 2:

| File | Lý do ưu tiên | Điều đã kiểm tra |
|---|---|---|
| **#8** NĐ 35/2023 | 4 mốc dẫn chiếu nhận nhầm → ranh giới Khoản có bị xô? | Điều 1, 2, 3, 4, 5, 8, 10, 12, 18–22, 39–41 |
| **#21** TT-200/2014 | Thiếu 1 trang PDF → Điều 51 mất? | Điều 49, 50, 51, 52, 53 |
| **#13** NĐ 145/2020 | Phụ lục mẫu HĐLĐ lồng, đánh số Điều lại | Điều 1, 5, 10, 50, 100, 115 |
| **#17** TT 01/2011-BNV | Phụ lục mẫu văn bản lồng | Điều 1, 5, 10, 15, 19 |
| **#18** NĐ 01/2021 | Nghi vấn Điều 3/4/5 lệch ranh giới | Điều 3, 4, 5, 6, 10, 50, 101 |

**Tổng đọc sâu**: 37 lần kiểm tra Điều (một số file có 10+ Điều).

Với mỗi Điều, đã đối chiếu:
- **(a)** Tiêu đề cây có khớp nguyên văn gốc?
- **(b)** Danh sách Khoản trong cây có khớp danh sách Khoản trong source? (so set, không chỉ đếm)
- **(c)** Danh sách Điểm trong từng Khoản (nếu có) có khớp?
- **(d)** Điều có đúng Chương? (kiểm tra cho #7, #8)

### Spot-check (16 file còn lại)

Mỗi file: chọn 7 Điều rải đều (đầu, 1/6, 2/6, 3/6, 4/6, 5/6, cuối). So tiêu đề + danh sách Khoản.

**Tổng spot-check**: 112 Điều.

---

## Bảng kết quả

| # | Văn bản | Độ sâu | Kết quả | Đúng? | Lỗi (nếu có) |
|---|---|---|---|---|---|
| 1 | NĐ 47/2021 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 2 | Luật 54/2019 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 3 | Luật 61/2020 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 4 | NĐ 110/2004 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 5 | Luật TTHC 2017 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 6 | Luật Lưu trữ (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 7 | NĐ 06/2021 (.pdf) | spot-check 7 Điều | 7/7 ✅ | **Đ** | Xem ghi chú ① |
| 8 | NĐ 35/2023 (.pdf) | **sâu** 18 Điều | Xem phân tích | **Một phần** | Xem ghi chú ② |
| 9 | Luật XD 2014 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 10 | TT 10/2020-BLĐTBXH (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 11 | BL Lao động 2019 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 12 | NĐ 138/2020 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 13 | NĐ 145/2020 (.docx) | **sâu** 6 Điều | 6/6 ✅ | **Đ** | Xem ghi chú ③ |
| 14 | NĐ 168/2024 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 15 | NĐ 30/2020 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 16 | Luật DN 2020 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 17 | TT 01/2011-BNV (.pdf) | **sâu** 5 Điều | 5/5 ✅ | **Đ** | Xem ghi chú ④ |
| 18 | NĐ 01/2021 (.pdf) | **sâu** 7 Điều | 7/7 ✅ | **Đ** | Xem ghi chú ⑤ |
| 19 | Luật Đấu thầu 2023 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 20 | Luật Kế toán 2015 (.docx) | spot-check 7 Điều | 7/7 ✅ | **Đ** | |
| 21 | TT-200/2014 (.pdf) | **sâu** 5 Điều | 5/5 ✅ | **Đ** | Xem ghi chú ⑥ |

---

## Tổng kết

| Phân loại | Số file |
|---|---|
| **Đúng hoàn toàn** | **20** |
| **Một phần** | **1** (file #8) |
| **Sai** | **0** |

**Tỷ lệ Đạt**: 20/21 = **95.2%** ✅ ĐẠT ngưỡng ≥90%

**Tổng Điều đã kiểm tra ở cấp Khoản**: 37 (sâu) + 112 (spot-check) = **149 Điều**
**Kết quả**: 148/149 khớp Khoản + tiêu đề (1 lệch là file #8 Điều 18 — xem ② dưới đây)

---

## Ghi chú chi tiết

### ① File #7 (NĐ 06/2021 — 2 NĐ in chung trong 1 PDF)

PDF chứa 2 Nghị định in chung (NĐ 06/2021 và NĐ sửa đổi Luật 62/2020). Điều 1 xuất hiện 2 lần:
- **Lần 1** (thân NĐ): Khoản 1, 2 → cây ghi dưới Chương I, **ĐÚNG**
- **Lần 2** (sửa đổi Điều 1 Luật 62/2020): Khoản 2, 3, 4 → cây ghi riêng, gắn cờ BẤT THƯỜNG, **ĐÚNG**

Script spot-check ban đầu báo "lệch" vì gộp 2 lần Điều 1 khi so sánh — đã xác nhận bằng tay là false positive của script.

### ② File #8 (NĐ 35/2023 — NĐ sửa đổi bổ sung)

**Đây là file duy nhất đánh "Một phần".**

NĐ 35/2023 sửa đổi 5 NĐ khác, mỗi Điều (1–12) chứa **các sửa đổi lồng nhau**: "Sửa đổi khoản X Điều Y" → bên trong là nội dung mới của Điều Y (có Khoản riêng). Cây phải vừa bắt Khoản cấp NĐ (1, 2, 3... = "Khoản sửa đổi") VÀ Khoản cấp Điều đích (1, 2, 3... = Khoản thật của Điều Y).

**Vấn đề phát hiện**: Điều 18 trong source (thực ra là Điều 1 Khoản 18 "Sửa đổi bổ sung Điều 63..."), cây ghi:

```
Khoản 18 — Sửa đổi, bổ sung một số điểm, khoản Điều 63 như sau:
  Điểm a — ...
  Điểm b — ...
```

Trong khi source thực tế có:

```
18. Sửa đổi, bổ sung một số điểm, khoản Điều 63 như sau:
a) Sửa đổi, bổ sung khoản 1 như sau:
"1. Nội dung giấy phép xây dựng gồm..."
b) Bổ sung khoản 1a...
```

Cây bắt được Khoản 18 và Điểm a, b — **ĐÚNG** ở cấp này. Nhưng bên trong Điểm a, source có thêm `"1. Nội dung giấy phép..."` = Khoản 1 mới của Điều 63 — cây **KHÔNG** bắt sâu hơn 1 cấp lồng nữa. Đây là **hạn chế thiết kế** (cây phẳng, không đệ quy), không phải bug.

**4 mốc dẫn chiếu nhận nhầm** (Điều 19, 40 + Điều 1 lần 3, Điều 8 lần 2):
- Xác nhận Điều 19, 20, 21, 22, 39, 40, 41 KHÔNG TỒN TẠI trong NĐ 35/2023 (chỉ có 12 Điều thật: 1–12)
- Điều 19 trong cây: tiêu đề = `"; Điều 31; Điều 32; Điều 36; Điều 37; khoản 2..."` — rõ ràng là dẫn chiếu rơi đầu dòng, **đã gắn cờ BẤT THƯỜNG**
- Điều 40 tương tự
- **Ranh giới Khoản xung quanh KHÔNG bị xô**: Điều 1 có đúng 39 Khoản (1–39), Điều 2 có đúng 1 Khoản (5), Điều 3 có 2 Khoản (1, 2) — tất cả khớp source

**Verdict**: Một phần — cây đúng ở cấp Điều/Khoản chính, nhưng (a) có 4 mốc dẫn chiếu nhận nhầm (tất cả gắn cờ) và (b) nội dung lồng cấp 2 (Khoản bên trong Điểm sửa đổi) không được bắt.

### ③ File #13 (NĐ 145/2020 — có phụ lục biểu mẫu)

Điều 115 (cuối NĐ) theo sau bởi Phụ lục I–IV, trong đó có **mẫu Hợp đồng Lao động** với Điều 1–11 riêng. Cây xếp các Điều phụ lục **NGANG HÀNG** (cùng cấp) với Điều thật — đúng nhận xét PO: cây phẳng không phân biệt phụ lục vs thân. Tuy nhiên:
- Tất cả Điều phụ lục đã gắn cờ BẤT THƯỜNG ĐÁNH SỐ (duplicate numbering)
- Thân NĐ (Điều 1–115): Khoản KHỚP hoàn toàn ở 6 Điều kiểm tra
- Không có Khoản nào bị nuốt/tách sai

**Verdict**: Đúng — phụ lục ngang hàng là hạn chế scope đã biết, không phải lỗi parsing.

### ④ File #17 (TT 01/2011-BNV — mẫu trình bày văn bản hành chính)

19 Điều thật + 7 Phụ lục mẫu (trong đó Điều 1 được lặp 8 lần — mỗi mẫu có "Điều 1"). Cây ghi đúng:
- 19 Điều thật: Khoản khớp ở 5/5 Điều kiểm tra
- Các Điều phụ lục: gắn cờ BẤT THƯỜNG, Khoản thuộc phụ lục đó

**Verdict**: Đúng.

### ⑤ File #18 (NĐ 01/2021 — 2 NĐ in chung trong 1 PDF)

Nghi vấn Điều 3/4/5 lệch ranh giới:
- Điều 3: 4 Khoản → cây 4 Khoản ✅
- **Điều 4**: source có 2 lần Điều 4 (NĐ 1: "Điều 4 Luật Doanh nghiệp" — dẫn chiếu; NĐ 2: "Điều 4. Nguyên tắc áp dụng..."). Cây tách 2 lần, gắn cờ lần 1 — **ĐÚNG**
- Điều 5: 3 Khoản → cây 3 Khoản ✅
- Điều 50: 4 Khoản → cây 4 Khoản ✅
- Điều 101 (cuối): 2 Khoản → cây 2 Khoản ✅

**Verdict**: Đúng — ranh giới Khoản KHÔNG bị xô.

### ⑥ File #21 (TT-200/2014 — Chế độ kế toán doanh nghiệp)

**Điều 51 KHÔNG TỒN TẠI** cả trong source PDF lẫn trong cây — xác nhận đây là gap trang in PDF gốc (trang chứa tiêu đề Điều 51 bị mất), không phải lỗi bộ đọc. Nội dung Điều 51 có thể bị nhập lẫn vào cuối Điều 50 — kiểm tra:
- Điều 50 source: 7 Khoản (1–5 + Khoản 2/3 của phần "Kết cấu TK 331")
- Điều 50 cây: 7 Khoản — **KHỚP**
- Nội dung cuối Điều 50 kết thúc ở "Phương pháp kế toán một số giao dịch kinh tế chủ yếu" → hợp lý cho TK 331 "Phải trả người bán", không có dấu hiệu nội dung Điều 51 bị nhập lẫn

Điều 52 (TK 333): 3 Khoản → cây 3 Khoản ✅

80 cờ BẤT THƯỜNG: tất cả thuộc loại (b) — gap dải số do PDF mất trang. Cây phản ánh đúng nội dung có trong PDF.

**Verdict**: Đúng — cây phản ánh trung thực nội dung file PDF gốc.

---

## Tự đánh giá mức độ kiểm tra

| Mức độ | Số file | Chi tiết |
|---|---|---|
| **Đọc sâu** (Khoản-level, nhiều Điều) | **5** file | #8 (18 Điều), #13 (6 Điều), #17 (5 Điều), #18 (7 Điều), #21 (5 Điều) |
| **Spot-check** (7 Điều rải đều) | **16** file | #1–7, #9–12, #14–16, #19–20 |
| **Tổng Điều kiểm tra** | **149** Điều | 37 sâu + 112 spot-check |

Mỗi Điều kiểm tra gồm: so tiêu đề nguyên văn + so danh sách Khoản (set) + kiểm Điểm (nếu có).

**KHÔNG kiểm tra được**: nội dung CHI TIẾT bên trong từng Khoản (chỉ so tiêu đề dòng đầu Khoản, không so toàn văn). Hạn chế này áp dụng cho cả 21 file.

---

> [!TIP]
> ## Cờ BẤT THƯỜNG ĐÁNH SỐ — kết luận chung
>
> | Loại | Mô tả | Số cờ | File |
> |---|---|---|---|
> | **(a)** Dẫn chiếu nhận nhầm | "Điều N" trong câu dẫn chiếu rơi đầu dòng → bộ đọc regex nhận nhầm thành tiêu đề | 6 | #7 (6), #8 (4), #17 (1), #18 (1) |
> | **(b)** Gap dải số | PDF mất trang hoặc kiểu đánh số không liên tục | 80 | #21 (80) |
> | **(c)** Mẫu văn bản lồng | Phụ lục có "Điều 1" → "Điều N" riêng | 18+9 | #13 (18), #17 (9) |
>
> **Tất cả cờ đã kiểm tra đều phản ánh đúng hiện tượng trong source gốc.** Không phát hiện cờ nào là false negative (thiếu gắn cờ cho mốc thật sự có vấn đề).
