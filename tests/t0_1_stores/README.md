# T0.1 — Biên bản nghiệm thu hai kho

**Điều kiện xong** (`docs/08` Phần D, T0.1): *hai kho chạy được, và có bằng chứng
cho từng yêu cầu (a)–(e) — riêng (a) phải thử với danh sách loại trừ cỡ vài trăm
định danh, (c) phải thử với một tài liệu dài.*

Chạy lại toàn bộ: `.venv/bin/python -m pytest tests/t0_1_stores/ -s -q`

## Đã dựng

| | |
|---|---|
| **Qdrant** | 1.19.1, binary **ARM native** (`aarch64-apple-darwin`), cổng 6333, dữ liệu ở `.runtime/qdrant/storage` |
| **PostgreSQL** | 14.20, cơ sở dữ liệu `cbrain_dev`, mã hoá **UTF8** |
| **Bảng thăm dò** | schema riêng `t0_1_probe` — **không phải** hợp đồng dữ liệu; tên trường là việc của T1.1 |

> **Vì sao binary chứ không phải Docker.** Máy dev không có Docker, và **không tài
> liệu nào trong 06/07/08 chốt cơ chế đóng gói** — chỉ chốt yêu cầu (e). Binary
> native thoả (e) mà không đòi thêm một tầng hạ tầng nào trên máy khách.

## Kết quả từng yêu cầu

| | Yêu cầu | Kết quả | Số đo |
|---|---|---|---|
| **(a)** | Lọc loại trừ theo danh sách định danh + lọc phạm vi Space | ✅ ĐẠT | 400 tài liệu / 4.000 mẩu / 12 Space; loại trừ **300 định danh** + giới hạn 4 Space; **không ca nào lọt**; 9–45 ms |
| **(b)** | Đóng dấu siêu dữ liệu lên kho vector | ✅ ĐẠT | Qdrant tự mang `size`+`distance`; **không mang tên mô hình**; cả hai nhà ứng viên đều chạy được |
| **(c)** | Đọc đoạn theo **vị trí ký tự**, không lấy cả trường | ✅ ĐẠT | Tài liệu **200.306 ký tự / 268.426 byte**; Python slice == Postgres `SUBSTRING` ở **6 mốc**; **0,20%** khối lượng đi qua dây |
| **(d)** | Đọc quan hệ tại thời điểm truy vấn, đệ quy, vài nghìn nút | ✅ ĐẠT | 4.000 cạnh / 4.000 nút; chuỗi 12 mắt xích trong **3–9 ms**; có vòng vẫn dừng |
| **(e)** | Chạy trọn trong hạ tầng khách hàng, mỗi khách một bản cài | ✅ ĐẠT | Cả hai kho **chỉ localhost**; telemetry tắt; hai bản cài không thấy dữ liệu của nhau |

**19/19 ca thử đạt.**

## Ba điều phải đọc kèm, không được bỏ qua

### 1. (b) chứng minh năng lực, KHÔNG chọn nhà cho `embedding_model`

`docs/08` B2 điểm 2 và T1.3 nói *"chọn cách nào cũng được, **nhưng phải chọn**, và
ghi vào T1.3"*. T0.1 vì vậy chứng minh **cả hai** nhà ứng viên đều đọc/ghi được —
một điểm dữ liệu dành riêng trong collection, và một bảng Postgres khoá theo tên
collection — rồi **dừng lại**. Chọn là việc của T1.3.

Ca thử nặng ký nhất ở đây là **đổi mô hình mà giữ nguyên số chiều**: cấu hình
collection khớp hoàn hảo (1024 = 1024, cosine = cosine) nên service chỉ so số
chiều sẽ khởi động bình thường rồi tìm sai trong im lặng. Con dấu mang tên mô
hình là thứ duy nhất bắt được.

### 2. (c) — phát hiện ngược với lý lẽ trong `docs/07`

`SUBSTRING` theo vị trí **ký tự** trên văn bản đa byte **không nhảy thẳng tới vị
trí được**: PostgreSQL phải giải mã UTF-8 từ đầu, nên chi phí tỉ lệ với **độ
lệch**, không phải độ dài đoạn. Đã thử cả `STORAGE EXTENDED` và `STORAGE
EXTERNAL` — **không đổi**.

### Số liệu tuyệt đối trên bốn độ dài văn bản THẬT (15/9/2026)

```bash
.venv/bin/python tools/infra/do_substring.py
```

Văn bản cắt từ `Thông-tư-200-2014-TT-BTC.pdf` trong tập thử T0.3. PostgreSQL
cùng máy (loopback), trung vị trên 60 lượt, đoạn đọc 400 ký tự, đọc ở **giữa**
tài liệu (đọc ở đầu sẽ cho số đẹp giả tạo). Mỗi lượt đều `assert` hai cách cho
ra **đúng cùng một đoạn**.

| Độ dài văn bản | Ký tự | Byte | `SUBSTRING` | Lấy cả trường | Chênh | **Chênh tuyệt đối** |
|---|---:|---:|---:|---:|---:|---:|
| một Khoản ngắn | 60 | 75 | **0,100 ms** | 0,078 ms | 1,28× | **+0,02 ms** |
| gần trần ngữ cảnh | 25.000 | 32.634 | **0,300 ms** | 0,179 ms | 1,68× | **+0,12 ms** |
| một Điều dài | 108.508 | 136.936 | **1,271 ms** | 0,565 ms | 2,25× | **+0,71 ms** |
| cả tài liệu | 1.000.857 | 1.291.502 | **9,098 ms** | 6,759 ms | 1,35× | **+2,34 ms** |

**Điều quan trọng nhất nằm ở cột cuối, không phải cột "chênh".** Tỷ lệ 2,25×
nghe lớn, nhưng khoảng cách tuyệt đối là **0,71 ms**. Ở cỡ một đơn vị ĐỌC thật
(Khoản, hoặc một Điều nằm trong trần ngữ cảnh) khoảng cách là **0,02–0,12 ms**
— nhỏ hơn nhiều bậc so với một lượt biểu diễn vector (27 ms ở T0.2) hay một lượt
gọi mô hình sinh.

**Yêu cầu (c) vẫn ĐẠT**: đúng ký tự, và chỉ đoạn cần đọc đi qua dây. Nhưng lý lẽ
ở `docs/07` Mục 7 yêu cầu 2 — *"không lấy toàn văn về rồi mới cắt; với tài liệu
dài thì đó là lãng phí ở mọi lượt trả lời"* — cần đọc lại cho đúng:

- **Đúng cho băng thông và bộ nhớ**: chỉ **0,1%** khối lượng đi qua dây, và
  service không phải giữ cả triệu ký tự trong bộ nhớ ở mỗi lượt trả lời. Với
  trần 6 tài liệu mỗi lượt, đó là khác biệt thật.
- **Không đúng cho độ trễ** khi kho nằm **cùng máy**: `SUBSTRING` chậm hơn, tuy
  khoảng cách tuyệt đối nhỏ tới mức khó thấy (0,02–0,71 ms ở cỡ đơn vị đọc thật).
- **Chưa đo qua mạng.** Khi kho nằm máy khác, chi phí truyền 1,3 MB sẽ áp đảo
  0,71 ms CPU, và cán cân nhiều khả năng lật ngược. Phép đo này **không nói được
  gì** về trường hợp đó.

> Đây là chỗ `CLAUDE.md` Mục 8 áp dụng: thấy số liệu ngược với lý lẽ trong thiết
> kế thì **báo PO, không tự đổi**. **Thiết kế giữ nguyên.** Ghi lại để PO quyết
> khi có hình dung về nơi đặt kho. Nếu kho luôn nằm cùng máy với service thì lý
> lẽ "lãng phí" mỏng hơn tài liệu mô tả — nhưng ngay cả khi ấy, `SUBSTRING` vẫn
> là cách duy nhất giữ được bất biến *"không có hai bản chữ nào có thể lệch
> nhau"* ở `docs/07` Mục 2.1, và bất biến đó không phụ thuộc vào con số nào.

### 3. (e) bắt được một lỗi thật ngay trong kịch bản dựng kho

Lượt chạy đầu, ca `test_stores_listen_on_localhost_only` **ĐỎ**: Qdrant lắng nghe
`*:6333` — mở ra mọi giao diện mạng. Đó là **mặc định của Qdrant**, và nó vi phạm
R2 (*"mặc định chạy nội bộ"*).

Đã chữa bằng `QDRANT__SERVICE__HOST` ghim về loopback, khoá `CBRAIN_QDRANT_BIND_HOST`
trong `.env`. Nới khoá đó ra sẽ làm ca thử này đỏ — **cố ý**: mở kho ra mạng phải
là một hành động nhìn thấy được, không phải một dòng cấu hình lặng lẽ.

## Cái phép thử này KHÔNG khẳng định

- **Không** khẳng định không có đường ra Internet ở tầng mạng — đó là việc của
  tường lửa, không kiểm được ở T0.1.
- **Không** khẳng định mô hình sinh câu trả lời chạy nội bộ — R2 áp cho Retrieval,
  ngoài phạm vi hai kho.
