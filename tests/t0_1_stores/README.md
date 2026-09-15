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
lệch**, không phải độ dài đoạn. Đo trên tài liệu 400.000 ký tự khó nén, đã khử
biến gây nhiễu (cả hai truy vấn cùng có tham số):

| | Khối lượng về | Độ trễ (trung vị) |
|---|---|---|
| Cắt trong kho | 400 ký tự (**0,1%**) | 3,25 ms |
| Lấy cả trường | 400.000 ký tự | 1,42 ms |

Đã thử cả `STORAGE EXTENDED` và `STORAGE EXTERNAL` — **không đổi** (2,16 vs 2,19 ms).

**Yêu cầu (c) vẫn ĐẠT**: đúng ký tự, và chỉ đoạn cần đọc đi qua dây. Nhưng lý lẽ
ở `docs/07` Mục 7 yêu cầu 2 — *"không lấy toàn văn về rồi mới cắt; với tài liệu
dài thì đó là lãng phí ở mọi lượt trả lời"* — chỉ đúng cho **băng thông và bộ
nhớ**, **không đúng cho độ trễ** khi kho nằm cùng máy với service.

> Đây là chỗ `CLAUDE.md` Mục 8 áp dụng: thấy số liệu ngược với lý lẽ trong thiết
> kế thì **báo PO, không tự đổi**. Thiết kế giữ nguyên. Ghi lại để PO quyết khi
> có hình dung về nơi đặt kho (cùng máy hay qua mạng).

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
