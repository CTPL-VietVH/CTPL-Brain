# T0.3 — Bộ đọc file và bộ chuẩn hoá phân cấp

# ⛔ T0.3 CHƯA NGHIỆM THU. ĐANG CHỜ PO GOM TẬP THỬ.

**Điều kiện xong** (`docs/08` Phần D, T0.3) — mỗi định dạng có một bộ đọc, mọi
bộ đọc trả ra **cùng một hình dạng cây**, và **đạt trên một tập thử có tên gọi**:

| Điều kiện | Trạng thái |
|---|---|
| Mỗi định dạng một bộ đọc, cùng một hình dạng cây | ✅ **đạt** — 15/15 ca thử |
| ≥ **20 văn bản hành chính VN thật** | ❌ **mới thử 4** |
| trong đó ≥ **5 văn bản soạn tay không Heading style** | ❌ **chưa có** (tập tự dựng có 1 bản, không tính) |
| trong đó ≥ **5 PDF** | ❌ **mới 2** |
| ≥ **90% dựng đúng hoàn toàn phân cấp** | ❌ **chưa đo được** — cần người đối chiếu với bản gốc |
| **Không ca nào rơi về cắt theo độ dài mà không báo** | ✅ **đạt** — chặn bằng cấu trúc, xem dưới |

**Không được tự nới điều kiện nghiệm thu để qua ải bằng tập thử nhỏ hơn.** Con
số 4 không thay được con số 20, và "có dựng ra cây" không thay được "dựng đúng
hoàn toàn" — thứ sau cần người đối chiếu.

## Đã dựng gì

```
packages/ingestion/reader/
  structure.py      hình dạng cây dùng chung — điểm cắm GĐ2
  vn_normalizer.py  bộ chuẩn hoá regex theo quy chuẩn hành chính VN  ← ĐƯỜNG CHÍNH
  readers.py        bốn bộ đọc: .txt .md .docx (python-docx) .pdf (Docling)
```

Bậc nhận diện: **Phần › Chương › Mục › Điều › Khoản › Điểm**, cộng hai đường cho
tài liệu không theo điều khoản.

> ⚠️ **Tên trường ở tầng đọc là tên CỤC BỘ, không phải hợp đồng dữ liệu.** Tầng
> này dùng `char_start` / `char_end` / `path`; `span_start`, `span_end`,
> `structure_path`, `parent_chunk_id` là tên của `packages/schema/` và được
> định nghĩa **đúng một lần** ở đó — việc đó là **T1.1, chưa làm**. Ánh xạ sang
> hợp đồng nằm ở T2.2 và chỉ được viết ở một chỗ.

## Bốn kết cục, và không có kết cục nào là "cắt theo độ dài"

`docs/06` Mục 5.2 và `docs/08` T0.3 cấm rõ việc **lặng lẽ rơi về cắt theo độ
dài**. Ở đây điều đó được chặn **bằng cấu trúc**: kiểu `Outcome` đơn giản là
**không có giá trị nào** mang nghĩa đó, và có ca thử canh chính điều ấy.

| Kết cục | Dựa trên | Chắc chắn |
|---|---|---|
| `DIEU_KHOAN` | số hiệu Chương/Điều/Khoản/Điểm | **sự kiện** |
| `TIEU_DE` | tiêu đề đánh số (`1.2.3`, `III.`) | **sự kiện** |
| `TIEU_DE_PHONG_DOAN` | tiêu đề chữ HOA **không** đánh số | ⚠️ **phán đoán** |
| `KHONG_DUNG_DUOC` | không có dấu hiệu nào | — từ chối, **không** cắt theo độ dài |

Giá trị thứ ba tách riêng có chủ ý, theo **NT2 ý 3**: số hiệu là sự kiện, còn
"dòng này viết HOA nên chắc là tiêu đề" là phán đoán — và phán đoán sai sinh ra
một **cây sai**, tức đơn vị đọc sai, trong im lặng. Tách thành một giá trị riêng
để chỗ phán đoán nhìn thấy được **ở tầng kiểu dữ liệu**, không chìm trong ghi chú.

## Kết quả trên tập TỰ DỰNG — 15/15 ca thử đạt

Tập tự dựng (`fixtures/`) chỉ phục vụ một việc: chứng minh **bốn bộ đọc trả ra
cùng một hình dạng cây**. Nó **không** chứng minh được việc dựng phân cấp có
đúng trên văn bản thật hay không.

- `.txt` / `.md` / `.docx` (2 bản) / `.pdf` → **cùng ra 2 Chương, 4 Điều, 3 Điểm**
- `.docx` **không gán Heading style** dựng phân cấp **y hệt** bản có style
- Vị trí đầu/cuối đếm đúng **ký tự Unicode** trên tiếng Việt có dấu
- Chuẩn hoá **NFC** trước khi đếm: chuỗi tổ hợp 6 ký tự → 4 ký tự, khớp bản dựng sẵn
- Văn bản không cấu trúc → `KHONG_DUNG_DUOC`, **không sinh khối con nào**
- `.xlsx` → từ chối kèm thông báo rõ; PDF không lớp chữ → từ chối **ồn ào**

## Kết quả trên VĂN BẢN THẬT — mới 4 file, **chưa đủ để nghiệm thu**

| File | Đuôi | Kết cục | Điều |
|---|---|---|---|
| Biểu mẫu Quyết định bổ nhiệm cán bộ | `.docx` | `điều khoản` | 4 |
| Biên bản nghiệm thu sản phẩm | `.docx` | `tiêu đề HOA` ⚠️ | 0 |
| Hướng dẫn triển khai (v3) | `.pdf` | `tiêu đề số` | 0 |
| Brand Overview | `.pdf` | `tiêu đề số` | 0 |

Cả 4 đều dựng ra cây. **Nhưng chưa ai đối chiếu cây đó với bản gốc**, nên chưa
nói được gì về tỷ lệ 90%.

## Hai phát hiện trong lúc dựng

### 1. `export_to_markdown()` của Docling PHÁ MẤT cấu trúc — đã đổi cách dùng

Lượt chạy đầu, PDF ra **0 Điểm** trong khi `.txt` cùng nội dung ra 3. Nguyên
nhân: tầng phân tích bố cục của Docling **gộp các dòng thành đoạn** —

```
Điều 1. Phạm vi điều chỉnh 1. Quy chế này quy định việc quản lý, sử dụng...
```

— "Điều 1." và Khoản "1." bị nối chung một dòng, còn "a)" / "b)" bị nuốt vào
đoạn trước. Với văn bản hành chính VN thì **ngắt dòng chính là tín hiệu cấu
trúc**, nên gộp dòng là làm mất đúng thứ cần nhất.

**Đã chữa bằng cách dùng đúng tầng, không phải bằng cách nới regex**: tầng
backend của Docling vẫn giữ ô chữ kèm toạ độ, nên bộ đọc dựng lại dòng theo toạ
độ `y`. Công nghệ đã chốt 14/9 **không đổi** — vẫn là Docling. Phụ thu: bỏ được
bước OCR không cần thiết, bộ thử chạy từ **130 s xuống 3 s**.

> 📌 **Cần PO biết.** `docs/08` T0.3 kỳ vọng Docling *"phân tích bố cục, xuất
> cây có phân cấp tiêu đề"*. Đo thật thì phần đáng giá của Docling với văn bản
> hành chính VN là **rút chữ kèm toạ độ**, còn phần suy ra phân cấp thì **gây
> hại**. Điều này không đòi đổi công nghệ, nhưng nó **khớp và mở rộng** cảnh
> báo ở B2 điểm 1: regex là đường chính — giờ đúng cho **cả PDF**, không riêng
> `.docx`.

### 2. Tiêu đề chữ HOA không đánh số — đã đi đường thoát (1)

Biên bản nghiệm thu thật ban đầu ra `KHONG_DUNG_DUOC`. Kiểm lại thì đó là **bỏ
sót thật**, không phải báo đúng: tài liệu có tiêu đề mục rõ ràng
(`CĂN CỨ NGHIỆM THU`, `THÔNG TIN CÁC BÊN`, `THỜI GIAN VÀ ĐỊA ĐIỂM`) nhưng viết
**HOA, không đánh số** — dạng rất phổ biến ở biên bản, tờ trình, báo cáo VN.

Đã xử theo đúng **đường thoát (1)** mà `docs/08` T0.3 xếp ưu tiên đầu: *đầu tư
thêm vào bộ chuẩn hoá regex*. Bộ nhận diện mới cố ý **dè dặt** (giới hạn độ dài,
loại quốc hiệu, đòi có nội dung thường theo sau) vì **dè dặt hơn là bắt trượt**:
bắt trượt thì rơi xuống `KHONG_DUNG_DUOC` — nhìn thấy được; bắt nhầm thì sinh
cây sai — im lặng.

**Chưa cần dùng tới đường thoát (2) hay (3).**

## Việc PO cần làm để T0.3 nghiệm thu được

1. **Gom tập thử có tên gọi**: ≥20 văn bản hành chính VN thật, trong đó ≥5 bản
   soạn tay không Heading style và ≥5 PDF.
2. **Đối chiếu tay** cây dựng ra với bản gốc trên từng văn bản — chỉ người mới
   phán được "dựng đúng **hoàn toàn**".
3. Nếu tỷ lệ dưới 90%, đi tiếp đường thoát (2) rồi (3) theo đúng thứ tự.

## Chạy lại

```bash
.venv/bin/python -m pytest tests/t0_3_reader/ -q          # bộ thử
.venv/bin/python tests/t0_3_reader/fixtures/dung_tap_thu.py   # dựng lại tập tự dựng
.venv/bin/python tools/infra/thu_bo_doc.py <thư mục>      # khảo sát một tập văn bản
```
