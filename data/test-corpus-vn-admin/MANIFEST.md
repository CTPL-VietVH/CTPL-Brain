# MANIFEST — Tập thử văn bản hành chính Việt Nam cho T0.3

## ✅ Trạng thái: 21 VĂN BẢN THẬT ĐÃ CÓ TRONG THƯ MỤC — chờ chạy `thu_bo_doc.py` + đối chiếu tay

PO đã tự tải 21/21 văn bản trong danh sách bằng trình duyệt của mình (đăng nhập/qua captcha
thật), đặt đúng vào 6 thư mục phòng ban. Đã kiểm dung lượng từng file — không có file rỗng/hỏng.

## Định dạng thật đang có

| Định dạng gốc tải về | Số lượng | Ghi chú |
|---|---|---|
| PDF | 5 | Đạt ≥5 PDF theo yêu cầu T0.3 |
| .docx (Word gốc) | 5 | `nhan-su/Bộ-luật-45-2019-QH14.docx`, `ban-giam-doc-quan-tri/Luật-54-2019-QH14.docx`, `ban-giam-doc-quan-tri/Luật-61-2020-QH14.docx`, `phap-che-tuan-thu/30_2020_ND_CP.docx`, `ky-thuat-van-hanh/Luật-50-2014-QH13.docx` |
| .doc (Word 97-2003, nhị phân) | 11 | ⚠️ Bộ đọc T0.3 hiện chỉ hỗ trợ .txt/.md/.docx/.pdf — KHÔNG đọc được .doc |

## ⚙️ Đã xử lý: chuyển đổi định dạng .doc → .docx (KHÔNG sửa nội dung)

11 file .doc đã được Cowork chuyển sang .docx bằng LibreOffice headless (`soffice --headless
--convert-to docx`) — đây là chuyển đổi CƠ HỌC giữ nguyên cấu trúc/định dạng gốc (không gõ lại,
không đọc-rồi-viết-lại nội dung), tương tự việc Docling đọc PDF cần qua một tầng xử lý định
dạng. **Bản .doc gốc vẫn giữ nguyên trong cùng thư mục** — không xoá, để đối chiếu nếu cần.

⚠️ Cần PO/Claude Code lưu ý: đây là bước xử lý duy nhất khác "tải nguyên vẹn" trong toàn bộ
tập thử — nếu thấy không ổn (lo ngại LibreOffice làm lệch cấu trúc dòng/đoạn khi convert),
báo lại, Cowork sẽ không tính các file này vào tập thử nữa, chỉ giữ 5 .docx gốc + 5 PDF (10/20,
chưa đủ — khi đó phải tìm nguồn .docx gốc khác).

## Tổng số file SẴN SÀNG cho `thu_bo_doc.py` (PDF + .docx, không tính .doc gốc)

| Phòng ban | Số file | Danh sách |
|---|---|---|
| Pháp chế – Tuân thủ | 4 | 30_2020_ND_CP.docx (gốc) · 168.2024.NĐ.CP.docx (chuyển đổi) · Luật Doanh nghiệp 2020 (1).docx (chuyển đổi) · VanBanGoc_01_2011_TT-BNV.pdf |
| Nhân sự | 4 | Bộ-luật-45-2019-QH14.docx (gốc) · 10_2020_TT-BLDTBXH_454406.docx (chuyển đổi) · Nghị-định-138-2020-NĐ-CP.docx (chuyển đổi) · nghi-dinh-145-2020-...docx (chuyển đổi) |
| Hành chính – Tổng hợp | 3 | 110-2004-nd-cp.docx (chuyển đổi) · 15_2017_QH14_322220_1_1.docx (chuyển đổi) · luat_luutru_01.docx (chuyển đổi) |
| Tài chính – Kế toán | 4 | tt-200-btc-22-12-2014.pdf · 2021_113+114_01-2021-NĐ-CP.pdf · Luật-88-2015-QH13.docx (chuyển đổi) · Luat Dau thau 2023.docx (chuyển đổi) |
| Kỹ thuật – Vận hành | 3 | 2021_291+292_06-2021-NĐ-CP.pdf · 2023_nghi-dinh-35...pdf · Luật-50-2014-QH13.docx (gốc) |
| Ban Giám đốc – Quản trị | 3 | 47_2021_nd-cp_470561.docx (chuyển đổi) · Luật-54-2019-QH14.docx (gốc) · Luật-61-2020-QH14.docx (gốc) |
| **Tổng** | **21** | 5 PDF + 5 docx gốc + 11 docx chuyển đổi |

## ✅ Kiểm Heading style — ĐÃ XONG BẰNG MÁY (15/9/2026)

Không cần người mở Word: đây là phép kiểm **khách quan**, đọc thẳng
`paragraph.style.name` bằng `python-docx`.

```bash
.venv/bin/python tools/infra/thu_bo_doc.py --heading-style data/test-corpus-vn-admin/
```

| File | Nguồn | Đoạn | Đoạn Heading | Dùng Heading style? |
|---|---|---:|---:|---|
| `47_2021_nd-cp_470561.docx` | chuyển đổi | 355 | 0 | ✅ KHÔNG |
| `Luật-54-2019-QH14.docx` | **gốc** | 1377 | 46 | ⚠️ có (`Heading #1`) |
| `Luật-61-2020-QH14.docx` | **gốc** | 900 | 2 | ⚠️ có |
| `110-2004-nd-cp.docx` | chuyển đổi | 224 | 0 | ✅ KHÔNG |
| `15_2017_QH14_322220_1_1.docx` | chuyển đổi | 1081 | 0 | ✅ KHÔNG |
| `luat_luutru_01.docx` | chuyển đổi | 329 | 0 | ✅ KHÔNG |
| `Luật-50-2014-QH13.docx` | **gốc** | 1512 | 27 | ⚠️ có (`Heading 2`) |
| `10_2020_TT-BLDTBXH_454406.docx` | chuyển đổi | 323 | 0 | ✅ KHÔNG |
| `Bộ-luật-45-2019-QH14.docx` | **gốc** | 1363 | 0 | ✅ KHÔNG (`Body Text`) |
| `Nghị-định-138-2020-NĐ-CP.docx` | chuyển đổi | 809 | 0 | ✅ KHÔNG |
| `nghi-dinh-145-2020-...docx` | chuyển đổi | 1546 | 63 | ⚠️ có (`Tiêu đề #4`) |
| `168.2024.NĐ.CP.docx` | chuyển đổi | 1363 | 0 | ✅ KHÔNG |
| `30_2020_ND_CP.docx` | **gốc** | 302 | 2 | ⚠️ có |
| `Luật Doanh nghiệp 2020 (1).docx` | chuyển đổi | 2009 | 0 | ✅ KHÔNG |
| `Luat Dau thau 2023.docx` | chuyển đổi | 1151 | 0 | ✅ KHÔNG |
| `Luật-88-2015-QH13.docx` | chuyển đổi | 608 | 0 | ✅ KHÔNG |

**Tổng: 11/16 file `.docx` KHÔNG dùng Heading style** (trên tổng 21 văn bản).
`docs/08` T0.3 đòi **≥5** — đang có **11**.

Tách theo nguồn: **1/5** bản `.docx` gốc và **10/11** bản chuyển đổi.

### Bằng chứng này KHÔNG vòng luẩn quẩn

Câu hỏi đúng phải đặt ra: *liệu chính LibreOffice có làm phẳng style khi
chuyển đổi không?* Nếu có thì 10 bản chuyển đổi "không Heading style" chẳng
chứng minh được gì về bản `.doc` gốc.

**Đã đối chứng:** bản chuyển đổi `nghi-dinh-145-2020-....docx` **vẫn giữ 63
đoạn `Tiêu đề #4`** sau khi convert. Tức LibreOffice **giữ được** Heading
style khi bản gốc có. Vậy 10 bản chuyển đổi không có Heading style là vì bản
`.doc` gốc vốn không có — đúng như MANIFEST dự đoán ở mục trên.

> ## ✅ PO CHỐT (15/9/2026): TÍNH cả 11 bản `.docx` chuyển đổi vào tập thử T0.3
>
> Lý do: (a) LibreOffice đã được đối chứng giữ nguyên Heading style khi bản
> gốc có (xem trên) — 10 bản không có Heading style phản ánh đúng bản `.doc`
> gốc, không phải do convert làm phẳng; (b) nội dung câu chữ không đổi qua
> bước convert, chỉ đổi định dạng lưu trữ; (c) ngay cả khi loại hết bản
> chuyển đổi, tập vẫn còn `Bộ-luật-45-2019-QH14.docx` (bản **gốc**) không
> dùng Heading style — loại bản chuyển đổi không tạo ra được một tập "thuần
> gốc" đạt chuẩn ≥5, nên không giải quyết được gì.
>
> Hệ quả: tập thử T0.3 chính thức là **21 văn bản** (5 PDF, 5 `.docx` gốc,
> 11 `.docx` chuyển đổi cơ học, bản `.doc` gốc giữ nguyên cạnh mỗi bản để đối
> chiếu khi cần). Cả hai điều kiện ≥20 văn bản và ≥5 không-Heading-style coi
> như **ĐÓNG**.

## ▶️ Còn thiếu để T0.3 nghiệm thu đầy đủ (docs/08)

1. ~~Chạy `thu_bo_doc.py`~~ — ✅ **xong 15/9/2026**, kết quả ở
   `tests/t0_3_reader/README.md` (21/21 file dựng được cây `DIEU_KHOAN`).
2. **Đối chiếu tay** — ✅ **XONG 17/9/2026**, đạt 95.2% (20/21), xem
   `tests/t0_3_reader/nghiem_thu_cay_phan_cap_21_van_ban_lan3.md`.
3. ~~Xác nhận Heading style~~ — ✅ **xong bằng máy**, xem mục trên.

## 🧹 Rác cần dọn trong thư mục này

LibreOffice để lại **11 file khoá** `.~lock.*.docx#` và **11 file tạm** `*.tmp`
(tổng ~1MB). Công cụ đã bỏ qua chúng, nhưng file khoá còn sót nghĩa là
LibreOffice không thoát sạch. Không xoá hộ vì đây là dữ liệu của PO.

## ✅ Kiểm chéo độc lập số đếm Chương/Điều (PO tự làm, 15/9/2026)

Trước khi đối chiếu tay, PO chạy một phép kiểm tra chéo bằng **công cụ khác
hoàn toàn**: `python-docx` (giữ nguyên) + `pdftotext -layout` / `pdfplumber`
cho PDF — **không dùng lại Docling** và không dùng lại `vn_normalizer.py` —
chạy trên máy khác (không phải máy chạy `thu_bo_doc.py`). Áp đúng regex mốc
`Điều`/`CHƯƠNG` của `vn_normalizer.py` (neo đầu dòng, có chuẩn hoá NFC).

**Kết quả: 21/21 văn bản khớp tuyệt đối** số Chương và số Điều với
`tests/t0_3_reader/README.md`.

> ⚠️ Lưu ý quan trọng về lần chạy đầu: bản kiểm tra chéo đầu tiên (không chuẩn
> hoá Unicode NFC) báo LỆCH ở 5/21 file. Hoá ra đó là lỗi của chính phép kiểm
> tra chéo, không phải lỗi bộ đọc — một số bản `.docx` chuyển đổi mã hoá dấu
> tiếng Việt ở dạng tổ hợp (NFD) thay vì dựng sẵn (NFC), và regex không chuẩn
> hoá trước thì bỏ sót. Đây **chính là cái bẫy** mà docstring của
> `chuan_hoa_van_ban()` trong `vn_normalizer.py` đã cảnh báo trước. Sau khi áp
> đúng bước chuẩn hoá NFC (giống hệt pipeline làm), cả 21/21 khớp.

**Phạm vi của phép kiểm này — không thay thế đối chiếu tay:**
- ✅ Xác nhận: số lượng tiêu đề Chương/Điều bộ đọc tìm thấy khớp với một
  đường trích chữ độc lập hoàn toàn — rủi ro "cả một Điều bị bỏ sót hoàn
  toàn khỏi cây" giảm mạnh trên cả 21 file.
- ❌ CHƯA kiểm: Khoản/Điểm (regex đánh số chung, dễ bắt nhầm bảng số liệu —
  không kiểm chéo dễ dàng), thứ tự lồng (một Điều có bị gán nhầm sang Chương
  *khác* dù tổng số Điều vẫn đúng thì phép đếm này không thấy), và nội dung/
  ngữ nghĩa tiêu đề có đúng bản gốc hay không.
- Vế "đối chiếu tay ≥90%" ở mục ▶️ bên trên **vẫn là việc bắt buộc của PO**,
  phép kiểm này chỉ giảm bớt phần rủi ro ở tầng đếm Chương/Điều, không thay
  thế.


## 🔄 16/9/2026 — PO thay file nguồn Thông tư 200

`Thông-tư-200-2014-TT-BTC.pdf` (bản Công báo đăng nhiều kỳ, **thiếu cả dải
Điều 88–113**) đã được gỡ, thay bằng **`tt-200-btc-22-12-2014.pdf`** (14,8MB,
536 trang).

**Bản mới tốt hơn hẳn**: đủ dải Điều 1–130, không trang nào rỗng chữ.

⛔ **Nhưng vẫn thiếu đúng MỘT trang in** — trang ngay sau trang 222, chứa phần
cuối `Điều 50` + tiêu đề **`Điều 51: Tài khoản 331 - Phải trả cho người bán`**
+ mục `1.a) 1.b) 1.c)`. Chuỗi `"Điều 51"` không xuất hiện trong bất kỳ ô chữ
thô nào của cả 536 trang. Phần thân còn lại của Điều 51 vẫn có.

Bằng chứng: độ lệch giữa số trang vật lý và số in trên trang nhảy từ 0 sang +1
đúng tại trang vật lý 223 (222→in 222; 224→in 225).

**PO quyết** có chấp nhận bản này để đối chiếu tay hay không. Chi tiết đầy đủ:
`tests/t0_3_reader/README.md` mục *Việc còn lại* và
`tests/t0_3_reader/cay_day_du_21_van_ban.md` mục 21.
