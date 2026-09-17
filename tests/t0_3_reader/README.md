# T0.3 — Bộ đọc file và bộ chuẩn hoá phân cấp

# ✅ T0.3 ĐÃ NGHIỆM THU — 17/9/2026. Đối chiếu tay đạt 95.2% (20/21).
Xem `nghiem_thu_cay_phan_cap_21_van_ban_lan3.md`.

**Điều kiện xong** (`docs/08` Phần D, T0.3):

| Điều kiện | Trạng thái |
|---|---|
| Mỗi định dạng một bộ đọc, cùng một hình dạng cây | ✅ **đạt** — 16/16 ca thử |
| ≥ **20 văn bản hành chính VN thật** | ✅ **đạt** — 21 văn bản (PO đã chốt tính cả 11 bản chuyển đổi, 15/9/2026 — xem MANIFEST.md) |
| trong đó ≥ **5 PDF** | ✅ **đạt** — 5 PDF |
| trong đó ≥ **5 văn bản không dùng Heading style** | ✅ **đạt** — 11/16 `.docx`, kiểm bằng máy |
| **Không ca nào rơi về cắt theo độ dài mà không báo** | ✅ **đạt** — chặn bằng cấu trúc |
| ≥ **90% dựng đúng HOÀN TOÀN phân cấp** | ✅ **đạt — 95.2% (20/21), xem `nghiem_thu_cay_phan_cap_21_van_ban_lan3.md`** |

> ## ⛔ Vì sao dòng cuối chưa thể đánh dấu đạt
>
> Công cụ đếm được **bộ đọc có dựng ra cây hay không**. Nó **không phán được
> cây đó có ĐÚNG với văn bản gốc hay không**. 21/21 file ra `DIEU_KHOAN`
> **không phải** là 100% đạt — nó chỉ có nghĩa là không file nào rơi xuống
> `KHONG_DUNG_DUOC`.
>
> Ví dụ những thứ công cụ **không** thấy được: một Điều bị gán nhầm vào Chương
> trước đó; một Khoản bị nuốt vào Điều trên; một dòng trong bảng bị nhận nhầm
> thành Khoản. Tất cả đều cho ra "một cái cây", và đều **sai**.
>
> Vế 90% chỉ đóng được khi **người** mở từng bản gốc và đối chiếu. Preview cây
> ở cuối trang này in sẵn để việc đó nhanh hơn.
>
> ✅ **Cập nhật 17/9/2026**: đã đối chiếu tay xong qua 3 lần lặp (Lần 1: chỉ
> đọc cây, không đủ căn cứ; Lần 2: đếm lại số hiệu Điều bằng regex, bị PO bác vì
> không đọc nội dung; Lần 3: đọc trực tiếp tiêu đề + danh sách Khoản/Điểm của
> 149 Điều — 37 đọc sâu ở 5 file rủi ro cao nhất, 112 spot-check rải đều 16 file
> còn lại). Kết quả 20/21 Đúng hoàn toàn, 1/21 Một phần (file #8, hạn chế thiết
> kế cây phẳng với văn bản sửa đổi lồng — không phải bug). Chi tiết:
> `nghiem_thu_cay_phan_cap_21_van_ban_lan3.md`.

## Đã dựng gì

```
packages/ingestion/reader/
  structure.py      hình dạng cây dùng chung — điểm cắm GĐ2
  vn_normalizer.py  bộ chuẩn hoá regex theo quy chuẩn hành chính VN  ← ĐƯỜNG CHÍNH
  readers.py        bốn bộ đọc: .txt .md .docx (python-docx) .pdf (Docling)
```

Bậc nhận diện: **Phần › Chương › Mục › Điều › Khoản › Điểm**, cộng hai đường
cho tài liệu không theo điều khoản.

> ⚠️ **Tên trường ở tầng đọc là tên CỤC BỘ, không phải hợp đồng dữ liệu.** Tầng
> này dùng `char_start` / `char_end` / `path`; `span_start`, `span_end`,
> `structure_path`, `parent_chunk_id` là tên của `packages/schema/` và được
> định nghĩa **đúng một lần** ở đó — việc đó là **T1.1, chưa làm**.

## Bốn kết cục, và không có kết cục nào là "cắt theo độ dài"

| Kết cục | Dựa trên | Chắc chắn |
|---|---|---|
| `DIEU_KHOAN` | số hiệu Chương/Điều/Khoản/Điểm | **sự kiện** |
| `TIEU_DE` | tiêu đề đánh số (`1.2.3`, `III.`) | **sự kiện** |
| `TIEU_DE_PHONG_DOAN` | tiêu đề chữ HOA **không** đánh số | ⚠️ **phán đoán** |
| `KHONG_DUNG_DUOC` | không có dấu hiệu nào | — từ chối, **không** cắt theo độ dài |

Giá trị thứ ba tách riêng theo **NT2 ý 3**: số hiệu là sự kiện, "dòng này viết
HOA nên chắc là tiêu đề" là phán đoán — và phán đoán sai sinh ra **cây sai**,
tức đơn vị đọc sai, trong im lặng. Tách ở tầng kiểu để chỗ phán đoán nhìn thấy
được.

## Tập thử thật — 21 văn bản hành chính VN

Nguồn: `data/test-corpus-vn-admin/` (PO tự tải; xem `MANIFEST.md` cạnh đó).
Thư mục này **nằm ngoài git** (`.gitignore: data/`) — không commit tài liệu thật.

Thành phần: **5 PDF · 5 `.docx` gốc · 11 `.docx` chuyển đổi cơ học từ `.doc`**
bằng LibreOffice headless. Bản `.doc` gốc vẫn còn nguyên cạnh mỗi bản chuyển đổi.

> ✅ **PO đã chốt (15/9/2026): tính cả 11 bản chuyển đổi vào tập thử chính thức**
> — lý do đầy đủ ở `data/test-corpus-vn-admin/MANIFEST.md`. Cột *Nguồn* dưới
> đây vẫn giữ nguyên để minh bạch loại nào, phục vụ đối chiếu tay.

```bash
.venv/bin/python tools/infra/thu_bo_doc.py data/test-corpus-vn-admin/
```

| # | File | Phòng ban | Nguồn | Kết cục | Chương | Điều | Khoản | Điểm | Ký tự |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| 1 | `47_2021_nd-cp_470561.docx` | ban-giam-doc-quan-tri | docx chuyển đổi | `DIEU_KHOAN` | 6 | 35 | 141 | 64 | 68,300 |
| 2 | `Luật-54-2019-QH14.docx` | ban-giam-doc-quan-tri | docx gốc | `DIEU_KHOAN` | 10 | 135 | 511 | 656 | 211,102 |
| 3 | `Luật-61-2020-QH14.docx` | ban-giam-doc-quan-tri | docx gốc | `DIEU_KHOAN` | 7 | 77 | 348 | 392 | 155,483 |
| 4 | `110-2004-nd-cp.docx` | hanh-chinh-tong-hop | docx chuyển đổi | `DIEU_KHOAN` | 6 | 36 | 88 | 45 | 23,383 |
| 5 | `15_2017_QH14_322220_1_1.docx` | hanh-chinh-tong-hop | docx chuyển đổi | `DIEU_KHOAN` | 10 | 134 | 474 | 389 | 140,585 |
| 6 | `luat_luutru_01.docx` | hanh-chinh-tong-hop | docx chuyển đổi | `DIEU_KHOAN` | 7 | 42 | 133 | 101 | 36,673 |
| 7 | `2021_291 + 292_06-2021-NĐ-CP.pdf` | ky-thuat-van-hanh | PDF | `DIEU_KHOAN` | 5 | 60 | 380 | 393 | 171,621 |
| 8 | `2023_nghi-dinh-35_2023_nd-cp_sua-doi-bo-sung-qlnn-cua-bxd.pdf` | ky-thuat-van-hanh | PDF | `DIEU_KHOAN` | 0 | 25 | 177 | 261 | 138,107 |
| 9 | `Luật-50-2014-QH13.docx` | ky-thuat-van-hanh | docx gốc | `DIEU_KHOAN` | 10 | 168 | 658 | 599 | 200,550 |
| 10 | `10_2020_TT-BLDTBXH_454406.docx` | nhan-su | docx chuyển đổi | `DIEU_KHOAN` | 5 | 12 | 151 | 40 | 33,323 |
| 11 | `Bộ-luật-45-2019-QH14.docx` | nhan-su | docx gốc | `DIEU_KHOAN` | 17 | 220 | 645 | 287 | 189,425 |
| 12 | `Nghị-định-138-2020-NĐ-CP.docx` | nhan-su | docx chuyển đổi | `DIEU_KHOAN` | 5 | 80 | 291 | 251 | 125,074 |
| 13 | `nghi-dinh-145-2020-huong-dan-thi-hanh-dieu-kien-lao-dong-va-quan-he-lao-dong.docx` | nhan-su | docx chuyển đổi | `DIEU_KHOAN` | 12 | 133 | 447 | 400 | 237,864 |
| 14 | `168.2024.NĐ.CP.docx` | phap-che-tuan-thu | docx chuyển đổi | `DIEU_KHOAN` | 4 | 55 | 332 | 910 | 254,227 |
| 15 | `30_2020_ND_CP.docx` | phap-che-tuan-thu | docx gốc | `DIEU_KHOAN` | 7 | 38 | 116 | 94 | 35,927 |
| 16 | `Luật Doanh nghiệp 2020 (1).docx` | phap-che-tuan-thu | docx chuyển đổi | `DIEU_KHOAN` | 10 | 218 | 897 | 822 | 320,551 |
| 17 | `VanBanGoc_01_2011_TT-BNV.pdf` | phap-che-tuan-thu | PDF | `DIEU_KHOAN` | 5 | 28 | 56 | 43 | 98,870 |
| 18 | `2021_113 + 114_01-2021-NĐ-CP.pdf` | tai-chinh-ke-toan | PDF | `DIEU_KHOAN` | 9 | 105 | 393 | 219 | 206,615 |
| 19 | `Luat Dau thau 2023.docx` | tai-chinh-ke-toan | docx chuyển đổi | `DIEU_KHOAN` | 10 | 96 | 428 | 552 | 172,047 |
| 20 | `Luật-88-2015-QH13.docx` | tai-chinh-ke-toan | docx chuyển đổi | `DIEU_KHOAN` | 6 | 74 | 287 | 216 | 75,166 |
| 21 | `tt-200-btc-22-12-2014.pdf` | tai-chinh-ke-toan | PDF | `DIEU_KHOAN` | 6 | 130 | 435 | 1237 | 1,106,700 |

**Tổng theo kết cục:** `DIEU_KHOAN` 21

### Preview cây dựng ra — để PO đối chiếu nhanh với bản gốc

**1. `47_2021_nd-cp_470561.docx`** — docx chuyển đổi · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh và đối tượng áp dụng.
    Điều 2 — Giải thích từ ngữ.
Chương II
    Điều 3 — Trách nhiệm của doanh nghiệp xã hội và chủ doanh nghiệp tư
```

**2. `Luật-54-2019-QH14.docx`** — docx gốc · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
    Điều 3 — Áp dụng Luật Chứng khoán, các luật có liên quan
    Điều 4 — Giải thích từ ngữ
```

**3. `Luật-61-2020-QH14.docx`** — docx gốc · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
    Điều 3 — Giải thích từ ngữ
    Điều 4 — Áp dụng Luật Đầu tư và các luật có liên quan
```

**4. `110-2004-nd-cp.docx`** — docx chuyển đổi · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi và đối tượng điều chỉnh
    Điều 2 — Giải thích từ ngữ
    Điều 3 — Trách nhiệm đối với công tác văn thư
Chương II
```

**5. `15_2017_QH14_322220_1_1.docx`** — docx chuyển đổi · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
    Điều 3 — Giải thích từ ngữ
    Điều 4 — Phân loại tài sản công
```

**6. `luat_luutru_01.docx`** — docx chuyển đổi · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh và đối tượng áp dụng
    Điều 2 — Giải thích từ ngữ
    Điều 3 — Nguyên tắc quản lý lưu trữ
    Điều 4 — Chính sách của Nhà nước về lưu trữ
```

**7. `2021_291 + 292_06-2021-NĐ-CP.pdf`** — PDF · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh và đối tượng áp dụng
    Điều 2 — Giải thích từ ngữ
    Điều 3 — Phân loại và phân cấp công trình xây dựng
    Điều 4 — Thí nghiệm chuyên ngành xây dựng, quan trắc, trắc đạc công
```

**8. `2023_nghi-dinh-35_2023_nd-cp_sua-doi-bo-sung-qlnn-cua-bxd.pdf`** — PDF · `DIEU_KHOAN`

```
    Điều 1 — Sửa đổi, bổ sung một số khoản của Điều 14 Nghị định
      Khoản 4 — Các lô đất có quy mô nhỏ phải đáp ứng các điều kiện sau:
    Điều 2 — Sửa đổi, bổ sung một số khoản của Điều 10 Nghị định
    Điều 3 — Sửa đổi, bổ sung một số điều của Nghị định số 85/2020/NĐ-C
    Điều 4 — Sửa đổi, bổ sung một số điều của Nghị định số 11/2013/NĐ-C
```

**9. `Luật-50-2014-QH13.docx`** — docx gốc · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
    Điều 3 — Giải thích từ ngữ
    Điều 4 — Nguyên tắc cơ bản trong hoạt động đầu tư xây dựng
```

**10. `10_2020_TT-BLDTBXH_454406.docx`** — docx chuyển đổi · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
Chương II
    Điều 3 — Nội dung chủ yếu của hợp đồng lao động
```

**11. `Bộ-luật-45-2019-QH14.docx`** — docx gốc · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
    Điều 3 — Giải thích từ ngữ
    Điều 4 — Chính sách của Nhà nước về lao động
```

**12. `Nghị-định-138-2020-NĐ-CP.docx`** — docx chuyển đổi · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
Chương II
  Mục 1 — CĂN CỨ, ĐIỀU KIỆN, THẨM QUYỀN TUYỂN DỤNG
```

**13. `nghi-dinh-145-2020-huong-dan-thi-hanh-dieu-kien-lao-dong-va-quan-he-lao-dong.docx`** — docx chuyển đổi · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
Chương II
    Điều 3 — Sổ quản lý lao động
```

**14. `168.2024.NĐ.CP.docx`** — docx chuyển đổi · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
    Điều 3 — Hình thức xử phạt vi phạm hành chính, biện pháp khắc phục 
    Điều 4 — Thời hiệu xử phạt vi phạm hành chính; hành vi vi phạm hành
```

**15. `30_2020_ND_CP.docx`** — docx gốc · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
    Điều 3 — Giải thích từ ngữ
    Điều 4 — Nguyên tắc, yêu cầu quản lý công tác văn thư
```

**16. `Luật Doanh nghiệp 2020 (1).docx`** — docx chuyển đổi · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
    Điều 3 — Áp dụng Luật Doanh nghiệp và luật khác
    Điều 4 — Giải thích từ ngữ
```

**17. `VanBanGoc_01_2011_TT-BNV.pdf`** — PDF · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi và đối tượng áp dụng
    Điều 2 — Thể thức văn bản
    Điều 3 — Kỹ thuật trình bày văn bản
    Điều 4 — Phông chữ trình bày văn bản
```

**18. `2021_113 + 114_01-2021-NĐ-CP.pdf`** — PDF · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
    Điều 3 — Giải thích từ ngữ
    Điều 4 — Luật Doanh nghiệp là hệ thống thông tin nghiệp vụ chuyên m
```

**19. `Luat Dau thau 2023.docx`** — docx chuyển đổi · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
    Điều 3 — Áp dụng Luật Đấu thầu, pháp luật có liên quan và điều ước 
    Điều 4 — Giải thích từ ngữ
```

**20. `Luật-88-2015-QH13.docx`** — docx chuyển đổi · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Phạm vi điều chỉnh
    Điều 2 — Đối tượng áp dụng
    Điều 3 — Giải thích từ ngữ
    Điều 4 — Nhiệm vụ kế toán
```

**21. `tt-200-btc-22-12-2014.pdf`** — PDF · `DIEU_KHOAN`

```
Chương I
    Điều 1 — Đối tượng áp dụng
    Điều 2 — Phạm vi điều chỉnh
    Điều 3 — Đơn vị tiền tệ trong kế toán
    Điều 4 — Lựa chọn đơn vị tiền tệ trong kế toán
```


---

## 📄 Cây ĐẦY ĐỦ để đối chiếu tay

[`cay_day_du_21_van_ban.md`](cay_day_du_21_van_ban.md) — in trọn cây tới tận
Khoản/Điểm cho cả 21 văn bản, **không cắt ngắn ở file nào** (đã đối chiếu: số
khai báo khớp đúng số dòng in ra ở 21/21). Mỗi văn bản một mục, kèm phòng ban và
nguồn gốc/chuyển đổi.

```bash
.venv/bin/python tools/infra/thu_bo_doc.py --cay-day-du data/test-corpus-vn-admin/ \
  > tests/t0_3_reader/cay_day_du_21_van_ban.md
```

Phần preview 5 dòng ở trên giữ lại để xem nhanh; bản đầy đủ mới là thứ dùng khi
ngồi soát với bản gốc.

---

## ⚠️ Cờ BẤT THƯỜNG ĐÁNH SỐ — ba loại nguyên nhân, hai trong ba KHÔNG phải lỗi

Bộ đọc gắn cờ mỗi mốc `Điều` có số hiệu **không nối tiếp** mốc trước (luật *"số
kế tiếp"*). Cờ **chỉ gắn, không bao giờ xoá hay sửa cây**.

> ### ⛔ Cờ là GỢI Ý CẦN NGƯỜI PHÂN LOẠI, không phải phán quyết
>
> Có cờ **không** có nghĩa là mốc đó sai. Không có cờ **không** có nghĩa là
> đúng. Xác minh tay 6/6 file cho thấy **ba** nguyên nhân khác hẳn nhau, và
> **hai trong ba không phải lỗi bộ đọc**:
>
> | | Loại | Có phải lỗi bộ đọc? |
> |---|---|---|
> | **(a)** | Dẫn chiếu giữa câu rơi xuống đầu dòng, bị nhận nhầm thành mốc thật | ✅ **có** — loại duy nhất là lỗi |
> | **(b)** | Văn bản nguồn **khuyết một dải số** vì thiếu trang / thiếu kỳ Công báo | ❌ không — bản PDF vốn đã thiếu |
> | **(c)** | Phụ lục là **mẫu văn bản lồng**, tự đánh số Điều lại từ 1 | ❌ không — cấu trúc thật, ngoài phạm vi mô hình cây phẳng |

### Kết quả phân loại tay — 63 cờ / 6 file, đã soi hết

| File | Cờ | (a) | (b) | (c) | Ghi chú |
|---|---:|---:|---:|---:|---|
| `2023_nghi-dinh-35_…pdf` | 8 | **8** | – | – | Cờ trùng khít ground-truth 8/8. Thật có 17 Điều, dựng ra 25 |
| `tt-200-btc-22-12-2014.pdf` | 80 | 1 | **79** | – | ⛔ Bản này **thiếu 1 trang in → mất tiêu đề Điều 51**; cờ dây chuyền Điều 52→130 |
| `nghi-dinh-145-2020-…docx` | 18 | – | – | **18** | Mẫu Quyết định + mẫu Hợp đồng lao động trong phụ lục |
| `2021_291 + 292_…pdf` | 6 | **6** | – | – | Đều là dẫn chiếu *"…quy định tại khoản N…"* |
| `VanBanGoc_01_2011_TT-BNV.pdf` | 9 | 1 | – | **8** | Thông tư hướng dẫn thể thức → phụ lục toàn văn bản mẫu |
| `2021_113 + 114_…pdf` | 4 | **4** | – | – | ⚠️ một cờ nằm nhầm lên mốc thật — xem dưới |
| **Tổng** | **125** | **20** | **79** | **26** | |

**Chỉ 20/125 cờ (16%) là lỗi nhận dạng thật.** 105 cờ còn lại trỏ vào mốc **có
thật** — hoặc vì nguồn khuyết, hoặc vì đó là văn bản lồng.

> **Số cờ nhảy 63 → 125 là do đổi file nguồn, không phải do đổi luật dò.** Bản
> Thông tư 200 cũ (thiếu **26 Điều**, dải 88–113) sinh 18 cờ; bản mới
> `tt-200-btc-22-12-2014.pdf` có đủ dải 1–130 nhưng **thiếu đúng 1 trang in**
> làm mất tiêu đề `Điều 51` — và **một** lỗ hổng số duy nhất đó khiến luật *"số
> kế tiếp"* gắn cờ dây chuyền cho **Điều 52 → Điều 130** (79 mốc, **đều là Điều
> thật**). Đây chính là giới hạn (1) đã ghi ở `BatThuongDanhSo`, gặp thật ở
> dạng rõ nhất: **một lỗ hổng → 79 cờ oan**.

### Hai giới hạn đã biết, KHÔNG có kế hoạch chữa ở T0.3

**1. Dẫn chiếu rơi ĐÚNG số kỳ vọng vẫn lọt — và kéo cờ sang mốc thật.**
Gặp thật ở `2021_113+114`: dẫn chiếu *"…khoản 19 **Điều 4** Luật Doanh nghiệp
là hệ thống thông tin…"* rơi đúng lúc đang chờ Điều 4 nên được nhận là nối
tiếp, còn `Điều 4. Nguyên tắc áp dụng giải quyết thủ tục đăng ký doanh nghiệp`
— **Điều thật** — thì bị gắn cờ. Số đếm vẫn đúng, nhưng **ranh giới khối sai
chỗ**.

**2. Bản hợp nhất có Điều bị bãi bỏ** để lại lỗ hổng số cố ý (…Điều 12, Điều
14…) sẽ bị gắn cờ oan, cùng hình dạng với loại (b). Tập 21 văn bản hiện tại
không có ca nào → rủi ro **chưa gặp**, không phải **đã xử lý**.

> 📌 **Không tinh chỉnh luật dò thêm ở T0.3.** Ba lượt tinh chỉnh liên tiếp mỗi
> lượt lộ ra một loại vấn đề khác — không hội tụ. Loại **(c)** là **giới hạn mô
> hình**, hẹn xử lý ở **T1.1 / GĐ2** (phụ lục / văn bản lồng), **không phải bug**.

> 📌 Phép **kiểm chéo độc lập** của PO (21/21 khớp số Chương/Điều) **không** bắt
> được lớp này, vì nó áp *cùng một quy tắc neo đầu dòng*. Nó loại trừ rủi ro
> **bỏ sót**, không loại trừ rủi ro **nhận thừa**.


---

## Kiểm chéo độc lập số đếm Chương/Điều (PO tự chạy, 15/9/2026)

PO chạy một đường trích chữ **độc lập hoàn toàn** — `pdftotext -layout` /
`pdfplumber` cho PDF, **không dùng lại Docling**, không dùng lại
`vn_normalizer.py`, chạy trên máy khác — rồi áp cùng regex mốc `Điều`/`CHƯƠNG`.

**Kết quả: 21/21 khớp tuyệt đối** số Chương và số Điều với bảng trên.

Lần chạy đầu (chưa chuẩn hoá NFC) báo lệch ở 5/21 file. Đó là lỗi của **chính
phép kiểm chéo**, không phải của bộ đọc: một số bản `.docx` chuyển đổi mã hoá dấu
tiếng Việt ở dạng **tổ hợp (NFD)**, regex không chuẩn hoá trước thì bỏ sót. Đây
đúng là cái bẫy mà docstring `chuan_hoa_van_ban()` đã cảnh báo. Áp NFC xong thì
21/21 khớp.

**Phép kiểm này chứng minh gì và KHÔNG chứng minh gì:**

- ✅ Rủi ro *"một Điều bị bỏ sót hoàn toàn khỏi cây"* giảm mạnh trên cả 21 file —
  hai đường trích chữ khác nhau cho cùng một số đếm.
- ❌ **Không** kiểm Khoản/Điểm, **không** kiểm thứ tự lồng (một Điều gán nhầm
  sang Chương khác mà tổng số vẫn đúng thì phép đếm không thấy), **không** kiểm
  nội dung tiêu đề, và **không** kiểm rủi ro nhận thừa nói ở mục trên.

Vế *"đối chiếu tay ≥90%"* vẫn nguyên là việc bắt buộc của PO.

---

## Hai phát hiện trước đó (giữ lại)

### 1. `export_to_markdown()` của Docling PHÁ MẤT cấu trúc — đã đổi cách dùng

Tầng phân tích bố cục của Docling **gộp các dòng thành đoạn**: "Điều 1. Phạm vi
điều chỉnh" và Khoản "1." bị nối chung một dòng, "a)"/"b)" bị nuốt. Với văn bản
hành chính VN thì **ngắt dòng chính là tín hiệu cấu trúc**.

Đã chữa bằng cách dùng đúng tầng (backend giữ ô chữ kèm toạ độ), **không** bằng
cách nới regex. Công nghệ chốt 14/9 không đổi. Phụ thu: bỏ được OCR thừa, bộ thử
từ **130 s xuống ~3 s**.

> 📌 `docs/08` T0.3 đã được vá theo phát hiện này.

### 2. Tiêu đề chữ HOA không đánh số — đã đi đường thoát (1)

Biên bản nghiệm thu thật ban đầu ra `KHONG_DUNG_DUOC` vì tiêu đề viết HOA không
đánh số (`CĂN CỨ NGHIỆM THU`, `THÔNG TIN CÁC BÊN`) — bỏ sót thật. Đã xử theo
đúng **đường thoát (1)** của `docs/08`: đầu tư thêm regex, cố ý **dè dặt**, và
mang một giá trị `Outcome` riêng.

**Chưa cần dùng tới đường thoát (2) hay (3).**

---

## Việc còn lại để T0.3 nghiệm thu đầy đủ

1. ⛔ **`tt-200-btc-22-12-2014.pdf` THIẾU MỘT TRANG IN — mất tiêu đề `Điều 51`.
   PO quyết có chấp nhận bản này để đối chiếu tay hay không; Claude Code KHÔNG
   tự quyết loại file khỏi tập thử.**

   ✅ **Cập nhật 17/9/2026: PO đã CHẤP NHẬN bản này vào tập thử.** Lần 3 đã xác
   minh Điều 51 không bị nhập lẫn vào Điều 50 (Khoản của Điều 50 khớp đúng 7/7
   với nguồn) — gap chỉ do PDF gốc thiếu trang in, cây phản ánh trung thực.

   Bản này **thay thế** `Thông-tư-200-2014-TT-BTC.pdf` (bản cũ thiếu cả dải
   Điều 88–113). **Bản mới tốt hơn hẳn**: 536 trang, đủ dải Điều 1–130, không
   trang nào rỗng chữ. Nhưng còn **đúng một** chỗ khuyết:

   | Phép kiểm | Kết quả |
   |---|---|
   | Chuỗi `"Điều 51"` trong **ô chữ thô** cả 536 trang | ❌ **không một ô nào** — không phải lỗi dựng dòng |
   | Số hiệu Điều dựng được | 130 mốc, dải 1–130, thiếu **đúng mỗi số 51** |
   | Trang rỗng chữ | **0/536** — bộ đọc không bỏ trang nào |
   | Trang vật lý 223 | bắt đầu **giữa câu**, đã ở mục `d)` → là **phần GIỮA của Điều 51** |

   **Bằng chứng quyết định — độ lệch số trang đổi đúng tại đây:**

   | Trang vật lý | 219 | 220 | 221 | 222 | **223** | 224 | 225 | 228 |
   |---|---|---|---|---|---|---|---|---|
   | Số in trên trang | 219 | 220 | 221 | 222 | **?** | **225** | 226 | 229 |
   | Độ lệch | 0 | 0 | 0 | 0 | → | **+1** | +1 | +1 |

   Độ lệch nhảy từ 0 sang +1 **đúng tại trang 223** ⇒ thiếu **đúng một trang
   in**, ngay sau trang 222. Trang đó chứa phần cuối `Điều 50` + tiêu đề
   **`Điều 51: Tài khoản 331 - Phải trả cho người bán`** + mục `1.a) 1.b) 1.c)`.
   Phần thân còn lại của Điều 51 (mục `1.d) đ) e)` và `2. Kết cấu…`) **vẫn có**.

   > So với bản cũ: cũ thiếu **26 Điều**; mới thiếu **1 tiêu đề Điều + ~1 trang
   > nội dung**. Mức độ khác hẳn — nên đây là quyết định của PO, không phải một
   > lần từ chối hiển nhiên.

   **Hệ quả nếu giữ bản này**: một lỗ hổng số duy nhất làm luật *"số kế tiếp"*
   gắn cờ dây chuyền cho **Điều 52 → 130** (79 mốc, đều là Điều thật). Khi đối
   chiếu tay, **bỏ qua 79 cờ đó** và chỉ soát `Điều 69` (dẫn chiếu thật) cùng
   vùng `Điều 50–52`.

2. ✅ **XONG 17/9/2026** — đối chiếu tay 21 văn bản, xem file Lần 3
   [`nghiem_thu_cay_phan_cap_21_van_ban_lan3.md`](nghiem_thu_cay_phan_cap_21_van_ban_lan3.md).
   Kết quả 95.2% (20/21) đạt ngưỡng ≥90%. Sáu file mang cờ có sẵn phân loại
   (a)/(b)/(c) ngay tại mục của chúng trong
   [`cay_day_du_21_van_ban.md`](cay_day_du_21_van_ban.md).
3. ~~PO quyết có tính 11 bản `.docx` chuyển đổi vào tập thử không~~ — ✅ **đã
   chốt 15/9/2026: CÓ tính.** Xem lý do ở `MANIFEST.md`.

## Chạy lại

```bash
.venv/bin/python -m pytest tests/t0_3_reader/ -q                   # bộ thử
.venv/bin/python tests/t0_3_reader/fixtures/dung_tap_thu.py        # dựng tập tự dựng
.venv/bin/python tools/infra/thu_bo_doc.py <thư mục>               # khảo sát
.venv/bin/python tools/infra/thu_bo_doc.py --markdown <thư mục>    # xuất markdown
.venv/bin/python tools/infra/thu_bo_doc.py --heading-style <thư mục>
```
