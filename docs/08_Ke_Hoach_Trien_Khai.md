# 08 — Kế hoạch triển khai Ingestion v2 & Retrieval v2

| | |
|---|---|
| **Phiên bản** | v1.4 |
| **Ngày** | 23/9/2026 |
| **Lịch sử** | v1.4 — 23/9/2026, theo `10_Hop_Dong_API_Backend_AI_Services.md`: T2.10 đóng bằng tài liệu 10 (tám thao tác, không phải năm); T3.1 thu nhỏ — Backend tính phạm vi Space; T3.3 thêm điều kiện họ hàng qua bộ lọc quyền; T3.6 đổi đầu vào và thêm trạng thái hội thoại; T3.10 chuyển sang Backend; T4.2 thêm ba ca. Hồ sơ cá nhân hoá không có hạng mục nào ở phiên bản hiện tại. v1.3 — sau vòng đánh giá độc lập kế hoạch: thêm bốn hạng mục còn thiếu (T1.5 nạp lại kho, T2.10 bề mặt ghi cho Manager, T3.10 lịch sử hội thoại, T3.11 ràng buộc R1); siết tám điều kiện nghiệm thu; thêm sáu điều cấm vào Phần B (nay 25); thêm bảy ca thử vào T4.2. v1.2 — chốt ba quyết định công nghệ; T0.1–T0.3 đổi từ "chọn" sang "dựng và nghiệm thu"; T0.3 thêm ba đường thoát nếu phần chứng minh thất bại; T2.8 rút gọn thứ tự xoá theo hai kho vật lý. v1.1 — ghép kết quả gói nghiên cứu công nghệ `cmd_fd7fae9e` vào T0.1–T0.3, kèm ba chỗ nghiên cứu nói chưa đủ |
| **Đối tượng đọc** | Người hoặc agent lập trình sẽ viết hai service này |
| **Nguồn chân lý** | `06_Thiet_Ke_Pipeline_Ingestion_Retrieval_v2.md` v1.10 (thiết kế), `07_Hop_Dong_Du_Lieu_Schema_v2.md` v1.10 (hợp đồng dữ liệu) và `10_Hop_Dong_API_Backend_AI_Services.md` (hợp đồng với Backend C.Brain). Tài liệu này **không thay thế** hai tài liệu đó — nó chỉ sắp xếp việc và cảnh báo bẫy |

---

## A. Đọc gì trước khi gõ dòng đầu tiên

Hai tài liệu 06 và 07 là kết quả của sáu vòng phản biện độc lập trong ba ngày. **Gần như mọi chỗ trông có vẻ thừa hoặc rườm rà trong đó đều là kết quả của một lần hỏng đã được lường trước.** Đừng đơn giản hoá cái gì mà không đọc lý do kèm theo — lý do luôn được viết ngay cạnh quyết định.

Thứ tự đọc gợi ý, không cần đọc hết một lượt:

1. **06 Mục 0.1** — bối cảnh tối thiểu, sáu ràng buộc R1–R6, mô hình Space.
2. **06 Mục 2** — bốn nguyên tắc NT1–NT4. Đây là thứ mọi quyết định khác đều quy về.
3. **07 Mục 1** — ba quy tắc quyết định chỗ đứng của một trường.
4. **Phần B của tài liệu này** — hai mươi lăm cái bẫy. Đọc trước khi viết, không phải sau khi hỏng.
5. Mục cụ thể của việc đang làm, tra theo cột "Nguồn chân lý" trong Phần D.

**Việc đầu tiên nên làm là T0.4**: dựng `CLAUDE.md` trong repo mã nguồn, trỏ tới hai tài liệu trên và **chép nguyên Phần B vào đó**. Agent lập trình đọc `CLAUDE.md` ở mỗi phiên; bẫy nằm ngoài tầm với thì không có tác dụng.

---

## B. Hai mươi lăm điều KHÔNG được làm

Mỗi dòng dưới đây là một việc **trông hợp lý, gọn gàng hơn, và sai**. Cột giữa giải thích vì sao nó hấp dẫn — đó là phần quan trọng, vì thứ gì hấp dẫn thì sẽ có người làm.

| # | Không được | Vì sao nó hấp dẫn, và vì sao cấm |
|---|---|---|
| 1 | Gộp `removed_as_wrong` và `superseded` thành một trường `status` | Trông như hai giá trị của cùng một trạng thái. Gộp thì Manager đánh dấu một quyết định cũ là hết hiệu lực sẽ làm câu hỏi *"tháng 1/2024 ai là giám đốc"* không trả lời được nữa (06 Mục 6.3) |
| 2 | Đặt giá trị mặc định cho cấu hình ở trong mã | Cho service chạy được khi thiếu khoá. Nhưng mặc định trong mã là **cái nhà thứ hai** của tham số — thiếu khoá mà vẫn chạy nghĩa là không ai biết giá trị đang sống là bao nhiêu (07 Mục 3.3) |
| 3 | Chép văn bản của mẩu vào cạnh mẩu | Đỡ phải cắt theo vị trí ở mỗi lượt trả lời. Nhưng khi ấy có hai bản chữ và chúng sẽ lệch nhau (07 Mục 2.1) |
| 4 | Đếm vị trí đầu/cuối theo **byte** | Ngôn ngữ nào cũng có sẵn hàm đếm byte. Tiếng Việt có dấu, một ký tự nhiều byte — lệch cách đếm thì đoạn cắt sai, **không lỗi nào báo**, chỉ là dẫn nguồn sai chỗ (07 Mục 2.2) |
| 5 | Đưa cả lịch sử hội thoại vào lời nhắc rồi dặn mô hình *"đừng dùng làm nguồn"* | Là cách hiển nhiên nhất để mô hình hiểu câu hỏi tiếp nối. Nhưng mô hình đã đọc thì nó dùng được, và không ai biết nó có dùng hay không. Phải **tách hai bước** (06 Mục 9.4) |
| 6 | Dặn mô hình *"chỉ dùng tài liệu người này được phép đọc"* | Ngắn hơn viết bộ lọc. Nhưng một ràng buộc nằm trong lời nhắc không thể được bảo vệ bằng chính lời nhắc. Lọc **ngay lúc lấy dữ liệu** (06 Mục 8.4, R4) |
| 7 | Lọc cứng theo nhãn phân loại | Trông như cách thu hẹp tìm kiếm rẻ nhất. Nhãn gán nhầm thì tài liệu **biến mất im lặng** — người dùng thấy một câu trả lời gọn gàng có dẫn nguồn, không dấu hiệu nào cho thấy đang thiếu (NT4) |
| 8 | Cắt bớt ngữ cảnh ở tầng dưới khi tràn | Là hành vi mặc định của gần như mọi thư viện. Đây là loại trừ im lặng nằm dưới cả tầm nhìn của thiết kế. Tràn thì **báo lỗi và ghi nhật ký** (06 Mục 6.5) |
| 9 | Đưa danh sách người, nhóm hay dấu hiệu quyền vào dữ liệu đã nạp | Tra nhanh hơn nhiều so với tính lại mỗi lần. Đây đúng là con bug đã có thật trong hệ đang chạy: người vừa được cấp quyền qua được bộ lọc tươi nhưng trượt bộ lọc đóng băng, im lặng không ra kết quả (NT3, 07 Mục 5) |
| 10 | Chép trạng thái duyệt của liên kết xuống cạnh mẩu | Đỡ một nhịp hỏi kho quan hệ. Nhưng mỗi lần Manager duyệt một liên kết là phải nạp lại toàn bộ mẩu của hai tài liệu (06 Mục 6.4) |
| 11 | Thêm cờ `is_latest_version` | Rất tiện khi lọc. Cờ đó cũ đi ngay khi có bản mới nạp vào. Suy ra từ chuỗi phiên bản (07 Mục 2.1) |
| 12 | Nhân hệ số thừa hưởng lên **điểm giống thô** | Là cách đọc thẳng của công thức. Điểm thô dồn cục trong dải hẹp; nhân vào thì con của hạng nhất tụt dưới cả chục tài liệu không liên quan. Phải **chuẩn hoá trên tập ứng viên trước** (06 Mục 6.2) |
| 13 | Cắt theo ý nghĩa vượt qua ranh giới điều/khoản | Cho ra các mẩu đều đặn hơn, đẹp hơn. Nhưng người ta **sửa đổi văn bản theo điều khoản** — mẩu không trùng ranh giới cấu trúc thì không có khối cha để làm đơn vị đọc (06 Mục 5.2 GĐ3) |
| 14 | Nạp tài liệu chờ duyệt vào kho rồi lọc lúc truy vấn | Duyệt xong là thấy ngay, không độ trễ. Nhưng khi ấy tiền kiểm được chặn bằng một bộ lọc phải chạy đúng, thay vì bằng cấu trúc; và nó sinh ra bộ lọc cứng thứ ba (06 Mục 5.2 GĐ1) |
| 15 | Lưu nguyên văn câu trả lời vào nhật ký điều tra | Tái hiện sự cố dễ hơn hẳn. Nhưng nhật ký là kho **không xoá được** — nội dung tài liệu nằm ở đó thì cả người dùng lẫn thao tác xoá vĩnh viễn đều không với tới (06 Mục 9.2) |
| 16 | Thêm trường `is_certain` riêng cho liên kết | Đọc mã dễ hiểu hơn. Hai ô phải khớp nhau thì sẽ có ngày lệch nhau. Suy ra từ `origin` (07 Mục 2.3) |
| 17 | Xoá hồ sơ tài liệu trước, xoá vector sau | Là thứ tự tự nhiên vì hồ sơ nghe như "gốc". Cổng chặn của hệ này là **kho vector** — xoá hồ sơ trước thì mẩu vẫn tìm được nhưng không đọc được gì (07 Mục 6, S6) |
| 18 | Cho khối Đo lường đọc nhật ký điều tra | Dữ liệu đã sẵn ở đó. Nhật ký chỉ Admin đọc khi có việc; cho Đo lường đọc thì nó thành công cụ theo dõi nhân viên (06 Mục 9.6) |
| 19 | Để một Điều trúng ba Khoản chiếm ba suất trong trần | Là kết quả tự nhiên nếu không khử trùng. Hai mẩu cùng một cha thì cha chỉ lấy **một** lần (07 Mục 2.2) |
| 20 | Lưu tài liệu **chờ duyệt** chung bảng với tài liệu chính thức, chỉ hoãn nạp vector | Tái dùng bảng có sẵn thay vì dựng vùng đệm — rất cám dỗ. Nhưng với hai kho vật lý thì **PostgreSQL cũng là kho dùng chung**: hồ sơ nằm đó là đã vi phạm bất biến *mọi thứ trong kho dùng chung đều đã dùng được* (06 Mục 5.2 GĐ1) |
| 21 | Áp ngưỡng tin cậy lên liên kết do **người gắn** hoặc do đọc **dẫn chiếu tường minh** | Gộp chung một điều kiện lọc thì câu truy vấn ngắn hơn. Ngưỡng sinh ra để lọc **phán đoán của máy**, không phải để xét lại quyết định của người (07 Mục 2.3) |
| 22 | Dùng **một** số phiên bản schema thay vì hai | Quản hai cấp phiên bản rườm rà hơn thật. Nhưng một số thì mỗi lần thêm một trường là một lần dừng cả hai service, và người ta sẽ nhanh chóng ngừng tăng số (07 Mục 3.3) |
| 23 | Nêu **tên Space** trong cảnh báo "tài liệu này có thể đã lỗi thời" | Trông như giúp Manager dễ đối chiếu. Nhưng **việc không nêu chính LÀ cơ chế** — nêu tên là biến nó thành một ngoại lệ của 06 Mục 9.5 và phải quyết lại từ đầu |
| 24 | Xoá trắng lịch sử hội thoại khi quyền của người dùng thay đổi | Là cách "giải quyết" vấn đề quyền nhanh nhất. Nhưng 06 Mục 9.4 chốt lịch sử **giữ nguyên kể cả khi quyền đổi** — giữ lại bản ghi của điều đã được nói với mình không phải một lần tiết lộ mới |
| 25 | Bỏ bước chia nhỏ tiếp một khối cấu trúc **quá dài** | Cắt theo cấu trúc rồi là xong, đơn giản hơn. Nhưng một Điều ba trang thành một mẩu thì việc so khớp loãng hẳn — cấu trúc quyết định **ranh giới**, không có nghĩa là cấm chia nhỏ bên trong (06 Mục 5.2 GĐ3) |

---

## B2. Ba quyết định công nghệ — CHỐT 14/9/2026

Dựa trên gói nghiên cứu `cmd_fd7fae9e`. Tiêu chí đánh giá gốc vẫn nằm ở T0.1–T0.3 để sau này còn kiểm lại được nếu hoàn cảnh đổi.

| | Đã chốt | Độ chắc chắn |
|---|---|---|
| Bộ đọc file | **Docling** cho PDF (rút chữ kèm toạ độ, **không** dùng phần suy ra phân cấp — xem T0.3), **python-docx** cho .docx, parser markdown cho .md, regex cho .txt — cộng **một bộ chuẩn hoá cây cấu trúc chung** theo quy chuẩn hành chính Việt Nam | cao |
| Mô hình biểu diễn | **BGE-M3** — 1024 chiều, ngữ cảnh 8192 token, ~2.5GB, chạy được trên GPU 8GB hoặc CPU | cao |
| Kho dữ liệu | **Qdrant + PostgreSQL**, **không cần kho đồ thị riêng** | cao |

### Ba chỗ nghiên cứu nói chưa đủ — phải xử lý khi triển khai

**1. `python-docx` chỉ đọc được phân cấp nếu tài liệu THẬT SỰ dùng Heading style.** Văn bản hành chính Việt Nam soạn tay rất thường in đậm và đánh số bằng tay, không gán style. Nghĩa là **bộ chuẩn hoá regex không phải phương án dự phòng — nhiều khả năng nó là đường chính cho cả .docx**, và Heading style chỉ là đường tắt khi may mắn có. Kế hoạch thử ở T0.3 phải lấy mẫu văn bản soạn tay thật, không chỉ lấy văn bản mẫu đẹp.

**2. Con dấu trên kho vector thiếu đúng phần nguy hiểm nhất.** Cấu hình collection của Qdrant mang **số chiều** và **thước đo**, nhưng **không mang tên mô hình**. Mà lệch tên mô hình khi cùng số chiều mới là thứ hỏng ngầm không báo lỗi (07 Mục 3.1). Vậy `embedding_model` phải có nhà riêng — một điểm dữ liệu dành riêng trong chính collection, hoặc một bảng trong PostgreSQL khoá theo tên collection. **Chọn cách nào cũng được, nhưng phải chọn, và ghi vào T1.3.**

**3. Hai kho thay vì ba làm cho việc xoá vĩnh viễn DỄ HƠN, không khó hơn.** Thiết kế nói "ba kho" ở mức **logic**; về vật lý gộp còn hai thì kho quan hệ và hồ sơ tài liệu nằm chung một cơ sở dữ liệu, nên hai bước xoá đó **thành một giao dịch nguyên khối**. Ranh giới duy nhất còn thiếu giao dịch chung là giữa Qdrant và PostgreSQL. Thứ tự ở S6 vẫn giữ nguyên và rút gọn còn: **kho vector → (quan hệ + hồ sơ, một giao dịch) → dọn nền.**

*Ghi chú thêm về BGE-M3*: nó hỗ trợ cả dense, sparse và colbert. **v1 chỉ dùng dense.** Bật thêm dạng khác là đổi cấu hình mô hình, kéo theo nạp lại toàn kho (06 Mục 5.5).

*Ghi chú về độ tin cậy*: lập luận "ba kho riêng là anti-pattern ở quy mô này" tôi đồng ý, nhưng nguồn được dẫn không nói điều đó. Nó đứng vững nhờ lý lẽ vận hành, không nhờ trích dẫn.

---

## C. Thứ tự và phụ thuộc

```
Nhóm 0 (quyết định + nền)
   └─> Nhóm 1 (module schema dùng chung)   ← chặn cả hai service
          ├─> Nhóm 2 (Ingestion v2)
          └─> Nhóm 3 (Retrieval v2)         ← cần dữ liệu từ Nhóm 2 để thử thật
                 └─> Nhóm 4 (điểm cắm + bộ kiểm chứng)
```

Hai service **độc lập với nhau** ở mức mã nguồn — chúng chỉ gặp nhau qua module Nhóm 1 và qua **hai kho vật lý** (ba kho logic — xem T0.1). Làm song song được, miễn là Nhóm 1 xong trước.

Trong Nhóm 2, chuỗi GĐ có thứ tự tự nhiên. Trong Nhóm 3, T3.1 và T3.2 phải xong trước phần còn lại.

---

## D. Danh sách công việc

### Nhóm 0 — Quyết định và dựng nền

**T0.1 — Dựng hai kho: Qdrant + PostgreSQL.** ✅ Đã chốt 14/9. Thiết kế cố tình **không chốt công nghệ lưu trữ** (07 Mục 0), chỉ chốt yêu cầu — năm yêu cầu dưới đây giữ lại làm thước đo nghiệm thu, và làm căn cứ nếu sau này phải chọn lại:
- (a) Lọc loại trừ theo danh sách định danh truyền vào mỗi truy vấn (vài chục tới vài trăm), kết hợp lọc theo trường phạm vi Space.
- (b) Đóng dấu siêu dữ liệu lên chính kho vector lúc tạo, để service kiểm lúc khởi động.
- (c) Đọc một đoạn văn bản **theo vị trí ký tự** từ một trường văn bản dài, không lấy cả trường về rồi cắt.
- (d) Đọc quan hệ giữa tài liệu **tại thời điểm truy vấn**, độ trễ thấp, đồ thị vài nghìn nút.
- (e) Chạy trọn trong hạ tầng khách hàng, mỗi khách hàng một bản cài đặt (R2, R6).

**Phân vai**: Qdrant lo vector và lọc loại trừ. PostgreSQL lo hồ sơ tài liệu, cắt đoạn văn bản theo vị trí (`SUBSTRING ... FROM ... FOR ...`), và **cả lớp quan hệ** bằng truy vấn đệ quy — đồ thị vài nghìn nút không đáng một kho chuyên dụng.

> **Ba kho trong tài liệu 06 và 07 là ba kho LOGIC.** Về vật lý chỉ có hai. Mọi câu "kho đồ thị" trong hai tài liệu đó đọc là *lớp quan hệ trong PostgreSQL*.

*Xong khi*: hai kho chạy được, và có bằng chứng cho từng yêu cầu (a)–(e) — riêng (a) phải thử với danh sách loại trừ cỡ vài trăm định danh, (c) phải thử với một tài liệu dài.

**T0.2 — Dựng mô hình biểu diễn BGE-M3.** ✅ Đã chốt 14/9. Ràng buộc gốc giữ lại làm thước đo: chạy nội bộ (R2), tiếng Việt là chính, thước đo **cosine với vector chuẩn hoá L2** (07 Mục 3.1), và **độ dài ngữ cảnh phải chứa được một Khoản dài** — vì đơn vị đem so khớp là mẩu, không phải câu.
**BGE-M3** — 1024 chiều, ngữ cảnh **8192 token**, ~2.5GB. Điểm quyết định không phải điểm số mà là **độ dài ngữ cảnh**: multilingual-e5 chỉ 512 token và bkai-vietnamese-bi-encoder chỉ 256 — quá ngắn, vì đơn vị đem so khớp là một Khoản chứ không phải một câu. gte-Qwen2-1.5B điểm cao hơn nhưng đòi VRAM 8GB, nặng cho mô hình mỗi khách hàng một bản cài đặt.

**v1 chỉ dùng dạng biểu diễn dense.** BGE-M3 còn có sparse và colbert — bật thêm là đổi cấu hình mô hình, kéo theo nạp lại toàn kho (06 Mục 5.5).

*Xong khi*: mô hình chạy được trên phần cứng đích, đo được độ trễ một lượt biểu diễn; và tên mô hình, số chiều, thước đo đã nằm trong nhóm cấu hình hợp đồng ở T1.2.

**T0.3 — Dựng bộ đọc file và CHỨNG MINH nó ra phân cấp.** ✅ Thư viện đã chốt 14/9; phần chứng minh đã XONG 17/9/2026 — đối chiếu tay đạt 95.2% (20/21) trên 149 Điều kiểm tra, xem `tests/t0_3_reader/README.md` và `tests/t0_3_reader/nghiem_thu_cay_phan_cap_21_van_ban_lan3.md`. PDF có lớp chữ, `.docx`, `.txt`, `.md`. **Yêu cầu sống còn: bộ đọc phải trả ra văn bản KÈM PHÂN CẤP** (Chương › Điều › Khoản › Điểm, hoặc chuỗi tiêu đề lồng nhau), không phải một khối chữ phẳng.
**Docling** cho PDF (**rút chữ kèm toạ độ** — xem cảnh báo dưới), **python-docx** cho .docx, parser markdown cho .md, regex cho .txt — cộng **một bộ chuẩn hoá cây cấu trúc chung** nhận diện Chương / Điều / Khoản / Điểm theo quy chuẩn hành chính Việt Nam.

⚠️ **Đừng tin Heading style của .docx.** Văn bản soạn tay ở Việt Nam thường in đậm và đánh số bằng tay chứ không gán style — bộ chuẩn hoá regex nhiều khả năng là **đường chính**, không phải dự phòng.

> ### ⚠️ Sửa 15/9/2026 sau khi dựng và đo thật — mở rộng cảnh báo trên sang cả PDF
>
> Bản trước của mục này ghi Docling *"phân tích bố cục, xuất cây có phân cấp tiêu đề"* và ngầm coi đó là nguồn phân cấp cho PDF. **Đo thật thì phần đó gây hại, không giúp ích:**
>
> **1. Tầng phân tích bố cục GỘP DÒNG thành đoạn.** `export_to_markdown()` nối *"Điều 1. Phạm vi điều chỉnh"* với Khoản *"1. …"* thành một dòng, và nuốt *"a)"*, *"b)"* vào đoạn trước. Với văn bản hành chính Việt Nam thì **ngắt dòng CHÍNH LÀ tín hiệu cấu trúc**, nên gộp dòng là làm mất đúng thứ cần nhất. Đo được: cùng một nội dung, bản `.txt` ra 3 Điểm còn bản PDF ra **0**.
>
> **2. Phần đáng giá của Docling là RÚT CHỮ KÈM TOẠ ĐỘ**, ở tầng backend — nơi vẫn giữ từng ô chữ với vị trí. Bộ đọc dựng lại dòng theo toạ độ `y` rồi giao cho bộ chuẩn hoá regex. **Công nghệ chốt 14/9 không đổi** — vẫn là Docling, chỉ dùng đúng tầng. Phụ thu: bỏ được bước OCR không cần thiết, bộ thử chạy từ 130 s xuống ~3 s.
>
> **3. Chèn dấu cách phải theo KHE HỞ NGANG, không được nối mù.** PDF văn bản pháp luật VN thường tách ký tự **có dấu** thành ô chữ **riêng** (font khác cho phần dấu). Đo trên `01/2011/TT-BNV`: ô `'CÔNG BÁO/S'` hết ở `x=266.72`, ô `'ố'` bắt đầu ở `x=266.73`. Nối bằng dấu cách vô điều kiện cho ra `"B Ộ  N Ộ I V Ụ"`, `"Ngh ị đị nh"` — khi ấy chuỗi `"Điều"` **không bao giờ khớp**, cả tài liệu tụt xuống "không có điều khoản" với 0 Điều **mà vẫn dựng ra được một cái cây**, nên không có gì báo lỗi. Đây là kiểu hỏng im lặng, và nó đã xảy ra thật với **4/5 PDF** trong tập thử trước khi được bắt.
>
> **Kết luận cho người lập trình**: cảnh báo *"bộ chuẩn hoá regex là đường chính, không phải dự phòng"* ở trên **áp cho cả PDF**, không riêng `.docx`. Không thư viện nào trong chuỗi này được tin để suy ra phân cấp — chúng chỉ được tin để **rút chữ**.

*Xong khi*: mỗi định dạng có một bộ đọc, mọi bộ đọc trả ra **cùng một hình dạng cây** (điểm cắm GĐ2), và **đạt trên một tập thử có tên gọi**:
- Ít nhất **20 văn bản hành chính Việt Nam thật**, trong đó ít nhất **5 văn bản soạn tay không dùng Heading style** và ít nhất 5 PDF.
- **Từ 90% trở lên dựng đúng hoàn toàn phân cấp.**
- **Không một ca nào rơi về cắt theo độ dài mà không báo** — điều kiện này quan trọng hơn con số 90%, vì nó là kiểu hỏng chứ không phải mức chất lượng.

> ⚠️ **Việc này CÓ THỂ THẤT BẠI, và phải biết trước sẽ làm gì.** Nếu thử trên văn bản thật mà phân cấp không dựng được đủ tin cậy, thì **không được lặng lẽ rơi về cắt theo độ dài** — đó đúng là kiểu hỏng 06 Mục 5.2 cảnh báo. Ba đường thoát, theo thứ tự ưu tiên: (1) đầu tư thêm vào bộ chuẩn hoá regex, vì văn bản hành chính Việt Nam có quy chuẩn đánh số khá chặt; (2) thu hẹp phạm vi v1 xuống những định dạng dựng được cấu trúc, và từ chối phần còn lại như đang từ chối ảnh quét; (3) quay lại bàn với PO, vì khi đó đơn vị ĐỌC ở S2 mất nền và cả Mục 6.1 phải xem lại. **Đường bị cấm là im lặng hạ chuẩn.**
> ⚠️ Đây là hạng mục rủi ro nhất Nhóm 0. 06 Mục 5.2 đã cảnh báo: bộ đọc không dựng được cấu trúc thì tài liệu **lặng lẽ rơi về cắt theo độ dài** trong khi mọi thứ khác tưởng vẫn bình thường. Cảnh báo đó viết cho OCR tương lai, nhưng áp y nguyên cho PDF hôm nay.

**T0.4 — Dựng repo và `CLAUDE.md`.** Trỏ tới 06 và 07, chép nguyên **Phần B** vào, ghi rõ ba nhóm cấu hình và nơi ở của chúng.
*Xong khi*: mở một phiên lập trình mới, agent đọc `CLAUDE.md` là biết được nguồn chân lý ở đâu và hai mươi lăm điều cấm là gì.

### Nhóm 1 — Module schema dùng chung

**T1.1 — Bốn thực thể có kiểu.** `document`, `chunk`, `relation`, `pending_version_claim` — theo đúng bảng trường ở 07 Mục 2. Cả hai service import từ đây, **không bên nào tự khai báo lại tên trường**.
*Xong khi*: đổi tên một trường ở module thì cả hai service không biên dịch được, thay vì lặng lẽ tìm nhầm tên. Đây chính là con bug `doc_profile_code`/`profile_code` mà module này sinh ra để chặn.

**T1.2 — Ba nhóm cấu hình.** Hợp đồng / Ingestion / Retrieval, theo 07 Mục 3.3. Kèm **hai số phiên bản** của chính module (phá vỡ tương thích → từ chối chạy; bổ sung tương thích → ghi nhật ký, vẫn chạy).
*Xong khi*: có một test **chạy service với file cấu hình thiếu LẦN LƯỢT TỪNG KHOÁ**, và mỗi lần đều khẳng định service không khởi động được, báo rõ thiếu khoá nào.
> Nói "không được đặt mặc định trong mã" là chưa đủ — nó vẫn có thể nằm ngay trước chỗ dùng. Test theo từng khoá là cách duy nhất bắt được.
> Tám giá trị khởi đầu đã chốt ở 07 Mục 3.2. **Chép luôn cột "dấu hiệu đặt sai" vào file cấu hình dưới dạng ghi chú cạnh từng giá trị** — vì v1 không có dòng số liệu nào, đó là chỗ duy nhất tri thức này sống được ở nơi người ta dùng tới.

**T1.3 — Con dấu trên kho vector.** Đóng tên mô hình, số chiều, thước đo lên kho lúc tạo. Mỗi service khởi động so cấu hình của mình với **con dấu của kho nó đang đọc**, không so với service kia.
⚠️ **Cấu hình collection của Qdrant mang số chiều và thước đo nhưng KHÔNG mang tên mô hình** — mà lệch tên mô hình khi cùng số chiều mới là thứ hỏng ngầm. `embedding_model` phải có nhà riêng: một điểm dữ liệu dành riêng trong chính collection, hoặc một bảng trong PostgreSQL khoá theo tên collection. Chọn cách nào cũng được, nhưng phải chọn tường minh.

*Xong khi*: đổi mô hình trong cấu hình mà chưa nạp lại kho thì service từ chối khởi động — kiểm cả trường hợp **đổi mô hình mà giữ nguyên số chiều**, vì đó là ca khó nhất.
> ⚠️ Test phải khẳng định service so với **con dấu trên kho**, không phải so với service kia. Cách bắt: chạy **một mình** Retrieval với cấu hình lệch con dấu, không bật Ingestion — nó vẫn phải từ chối khởi động. So hai service với nhau thì ca này lọt.

**T1.4 — Bộ test cho những gì KHÔNG được tồn tại.** Test rằng payload cạnh mẩu không chứa: danh sách quyền, loại Space, tên văn bản, ngày, trạng thái duyệt liên kết, cờ bản mới nhất. Test rằng vị trí đầu/cuối đếm theo ký tự Unicode chứ không phải byte (dùng chuỗi tiếng Việt có dấu làm ca thử).
*Xong khi*: thêm một trường bị cấm vào payload thì test đỏ.

**T1.5 — Công cụ nạp lại toàn kho.** 07 Mục 3.1 chốt đổi mô hình ở v1 = dừng dịch vụ, nạp lại toàn kho, bật lại. Nhưng chưa hạng mục nào **dựng cái công cụ đó**, và nó sẽ cần đúng vào lần đầu ai đó đổi mô hình.
Đầu vào là `extracted_text` đã có trong hồ sơ — **không đọc lại file gốc**. Chạy lại được từ giữa chừng nếu đứt.
*Xong khi*: đổi `embedding_model` trong cấu hình, chạy công cụ, đóng dấu lại kho, hai service khởi động được. Cùng công cụ này dùng lại khi **đổi cách cắt** (06 Mục 5.5).

**Cập nhật 19/9 (PO):** phát hiện T1.5 cần `extracted_text` đã ghi trong hồ sơ Postgres — nhưng hồ sơ đó do T2.2 (Nhóm 2) tạo ra, chưa tồn tại ở thời điểm này. Quyết định: HOÃN T1.5 tới khi T2.2 xong; gate Nhóm 1→Nhóm 2 chỉ còn yêu cầu T1.1–T1.4 (đóng băng tên trường), không còn yêu cầu T1.5.

### Nhóm 2 — Ingestion v2

**T2.1 — GĐ1 nhận và xác thực.** Vân tay nội dung; trùng khít cùng Space thì báo và không nạp lại; trùng khít khác Space thì hợp lệ và im lặng; người upload khai "đây là bản mới của X"; nếu không khai thì tạo `pending_version_claim` và nhắc **cả người upload lẫn Manager**. *Nguồn*: 06 Mục 5.7.
*Xong khi*: nạp cùng một file hai lần vào một Space chỉ ra một tài liệu; vào hai Space ra hai tài liệu, không cảnh báo.

**Cập nhật 19/9 (PO, theo N9):** `content_fingerprint` do GĐ2 (T2.2) tính sau khi đọc chữ ra (06 Mục 5.7, 07 Mục 2.1) — quyết định trùng/không-trùng của T2.1 phải đợi GĐ2 tính xong `content_fingerprint` rồi mới chốt, KHÔNG dùng hash file thô riêng (tránh bịa khái niệm mới ngoài hợp đồng).

**Cập nhật 19/9 (PO, theo N9):** nhánh "người upload không khai thì máy tự phân tích đề xuất" thuộc T2.4 (GĐ5), không phải T2.1 (06 Mục 5.7). T2.1 chỉ xử lý khai báo tường minh của người dùng; `pending_version_claim` chỉ được tạo sau khi T2.4 phân tích xong và đề xuất.

**Cập nhật 21/9 (PO, từ audit #7 — không cần sửa):** tra vân tay trùng khít ở T2.1 không lọc theo `tenant_id`. Chấp nhận được: R6 (mỗi khách hàng một bản cài đặt độc lập) đã cách ly dữ liệu ở tầng hạ tầng, nên không cần thêm điều kiện đó ở câu truy vấn tầng ứng dụng. Ghi lại như một giới hạn thiết kế đã biết, để không bị audit sau này phát hiện lặp lại và tưởng là bỏ sót.

**T2.2 — GĐ2 đọc file.** Bốn định dạng, từ chối phần còn lại kèm thông báo rõ. Sinh `extracted_text` — **nguồn chân lý duy nhất của chữ nghĩa**. Đây là **điểm cắm**: mọi bước sau chỉ nhận văn bản, cấu trúc, vị trí; **không bước nào được rẽ nhánh theo định dạng gốc**. *Nguồn*: 06 Mục 5.2, 07 Mục 2.1.

**Cập nhật 21/9 (PO, từ escalation T2.1-E2):** `version_ordinal` phải DUY NHẤT trong một `version_chain_id` — không chỉ suy từ bản khai +1 (có race condition khi 2 người cùng khai "bản mới của v1" đồng thời). Bắt buộc ép bằng unique constraint (`version_chain_id`, `version_ordinal`) ở tầng lưu trữ, không chỉ kiểm tra ở tầng ứng dụng.

**T2.3 — GĐ3 cắt thành mẩu.** **Cấu trúc quyết định ranh giới; ý nghĩa chỉ được chia nhỏ tiếp một khối cấu trúc quá dài.** Ba điều cấm: không gộp hai khối cấu trúc, không cắt ngang ranh giới điều/khoản, khối đủ ngắn thì là một mẩu. Sinh `structure_path` (**danh sách các đoạn**, không phải chuỗi nối), `parent_chunk_id`, `span_start`, `span_end`. *Nguồn*: 06 Mục 5.2 GĐ3, 07 Mục 2.2.
*Xong khi*: một Điều dài nhiều trang **được chia nhỏ tiếp** thành nhiều mẩu con, và cả nhóm mẩu con đó cùng trỏ về một `parent_chunk_id`. Cắt theo cấu trúc rồi dừng là chưa xong.

**T2.4 — GĐ5 gán nhãn và trích ngày.** Máy gợi ý, người đưa tài liệu vào xác nhận. Trích `issued_date` (ngày ký, ở đầu văn bản) và `effective_date` (ngày hiệu lực, ở điều khoản thi hành), mỗi ngày mang **nguồn**: máy trích / người xác nhận / mặc định ngày nạp. *Nguồn*: 06 Mục 5.2 GĐ5 và 6.4.
*Xong khi*: trên một tập thử có tên gọi gồm văn bản thật, **ngày ký trích đúng ở từ 90% trở lên** — không chỉ là "chạy không lỗi". Và: không trích được ngày hiệu lực thì trường đó mang nguồn *mặc định ngày nạp* và **không** giả vờ là ngày thật.
> Điều kiện tỷ lệ là bắt buộc, vì một hàm trích **luôn thất bại** cũng thoả được vế thứ hai mà không làm gì cả.

**T2.5 — GĐ6 tạo vector.** Dùng cấu hình nhóm hợp đồng, không đọc biến môi trường riêng.

**T2.6 — GĐ7 phát hiện quan hệ.** Bốn loại quan hệ có phân loại; điểm tin cậy; `origin` ba giá trị; chiều **`from` tác động lên `to`**. Nguồn đề nghị gồm cả dẫn chiếu tường minh **và** dấu hiệu *cùng đối tượng + cùng loại văn bản + ngày ban hành sau*. Tiêu chí dừng: **bão hoà VÀ trần chi phí, phải thoả đồng thời**. *Nguồn*: 06 Mục 5.3, 07 Mục 2.3 và 3.2.

**T2.7 — Tiền kiểm ở Space riêng.** Chạy GĐ2, GĐ3, GĐ5 rồi **dừng trước GĐ6 và GĐ7**; giữ trong vùng làm việc riêng của Ingestion. Manager duyệt xong mới chạy nốt và ghi ra ba kho. *Nguồn*: 06 Mục 5.2 GĐ1.
*Xong khi*: tài liệu chưa duyệt trong Space riêng **không có mặt trong BẤT KỲ kho dùng chung nào** — kiểm bằng cách truy vấn thẳng vào cả Qdrant **và** PostgreSQL, không qua service.
> ⚠️ Với hai kho vật lý (T0.1), **PostgreSQL cũng là kho dùng chung.** Ghi hồ sơ tài liệu vào đó rồi chỉ hoãn nạp vector là đã vi phạm bất biến. Vùng làm việc của Ingestion phải tách khỏi bảng hồ sơ chính thức.

**Cập nhật 21/9 (PO, gộp T2.1-E2 + audit #2):** khi T2.2+/T2.7 thật sự xây bảng bền vững ở Postgres, cần ÍT NHẤT hai unique constraint tầng lưu trữ, không chỉ kiểm tra ở tầng ứng dụng: (1) `(version_chain_id, version_ordinal)` — từ escalation T2.1-E2, ngăn race condition khi hai người cùng khai "bản mới của v1"; (2) `(space_id, content_fingerprint)` — từ audit #2, khớp hành vi "trùng khít cùng Space thì báo và không nạp lại" ở T2.1. Cả hai chưa có task chủ; gán khi thật sự đụng tầng lưu trữ bền vững, không phải lúc này.

**T2.8 — Xoá vĩnh viễn.** Với hai kho vật lý (T0.1), thứ tự rút gọn thành: **kho vector → (lớp quan hệ + hồ sơ tài liệu, MỘT giao dịch) → dọn nền**. Ranh giới duy nhất còn thiếu giao dịch chung là giữa Qdrant và PostgreSQL, nên chỉ chỗ đó cần làm lại được mà không hỏng thêm. Nhật ký giữ việc đã xoá, không giữ nội dung. *Nguồn*: 06 Mục 5.6, 07 Mục 6 (S6).
*Xong khi*: (1) cắt tiến trình **ở từng bước một** rồi chạy lại đều hoàn tất được, không để lại mẩu trỏ tới hồ sơ đã mất; (2) **chạy lệnh xoá hai lần liên tiếp** trên cùng một tài liệu không gây lỗi và không đổi kết quả.

**T2.9 — Hàng việc chăm sóc tri thức.** Ba loại mục: đề nghị quan hệ chờ duyệt, đề nghị bản mới chờ xác nhận, và *"tài liệu này có thể đã lỗi thời"* khi có bản mới ở nơi khác trùng vân tay. Mục thứ ba **không được nêu Space nào, không nêu ai, không nêu ở đâu** — đó chính là cơ chế, không phải chi tiết. *Nguồn*: 06 Mục 5.4 và 5.7.

**Cập nhật 21/9 (PO, từ escalation T2.1-E4):** hai cơ chế ở 06 Mục 5.7 (báo Manager các Space giữ bản trùng; bản mới thừa hưởng nhãn/quan hệ) chưa có task rõ chủ — cần gán trước khi triển khai.

**T2.10 — Bề mặt ghi cho các thao tác của Manager.** Thiết kế nói Manager *đánh dấu gỡ vì sai*, *đánh dấu hết hiệu lực*, *duyệt hoặc từ chối liên kết*, *xác nhận đề nghị bản mới*, *xoá vĩnh viễn* — nhưng chưa hạng mục nào định nghĩa **các thao tác đó đi vào hệ thống bằng đường nào**. T3.1 có bộ lọc đọc cờ gỡ, T2.9 có hàng việc hiển thị; đường **ghi** thì chưa ai phụ trách.
*Xong khi*: mỗi thao tác trên có một đường ghi xác định, và **đã chốt nó thuộc service nào** — Ingestion hay Backend. Ranh giới này nằm ngoài phạm vi hai tài liệu 06 và 07 (07 Mục 0 loại trừ hợp đồng với Backend), nên phải quyết tường minh chứ không mặc định.
> Không quyết thì mỗi thao tác sẽ mọc ra ở chỗ nào tiện nhất lúc đó, và cờ gỡ — một trong **hai bộ lọc cứng** — không có chủ.

**Cập nhật 23/9/2026 (PO) — ĐÓNG bằng `10_Hop_Dong_API_Backend_AI_Services.md`.** Mọi thao tác đi vào AI Services qua API do **Backend C.Brain** gọi (giao diện do đội khác làm, ngoài phạm vi repo này). Backend quyết ai được làm; AI tự kiểm đối tượng có thật nằm ở Space được nêu không (`10` Mục 1, T4). Danh sách đúng là **tám** thao tác, không phải năm — thiếu *duyệt/từ chối tài liệu ở Space riêng*, *xác nhận/sửa nhãn và ngày*, *Manager tự gắn liên kết* (`10` Mục 4.3, 4.4, 5.3). Phần việc phía AI là **tầng API** theo tài liệu 10 — chưa được ước lượng ở `09`.

### Nhóm 3 — Retrieval v2

**T3.1 — Phạm vi quyền và hai bộ lọc cứng.** Duyệt cây Space **tươi tại thời điểm hỏi** (người + nhóm + kế thừa một chiều xuống, cắt tại nhánh riêng). Danh sách tài liệu **gỡ vì sai** cũng tính tươi rồi truyền vào như danh sách loại trừ. **Chỉ hai bộ lọc cứng này, không có cái thứ ba.** *Nguồn*: 06 Mục 6.2 bước 1, NT4, 07 Mục 6 (S7).

**Cập nhật 23/9/2026 (PO, `10` Mục 1 và 3.3):** việc duyệt cây Space chuyển sang **Backend C.Brain** — Backend gửi `readable_space_ids` đã tính trọn ở **từng lượt hỏi**. Retrieval **không** tra cây Space, chỉ áp danh sách đó làm bộ lọc cứng **ngay trong lời gọi tìm** (lọc trong lúc tìm, không lọc sau khi đã lấy top-k). Danh sách tài liệu gỡ vì sai vẫn do Retrieval tự tính từ hồ sơ tài liệu.
*Xong khi*: thiếu `readable_space_ids` → từ chối với lỗi, **không** chạy tìm không điều kiện; danh sách rỗng → từ chối theo R1 mà không gọi mô hình.

**T3.2 — Tìm ở cấp mẩu** trong phạm vi đó.

**T3.3 — Kéo họ hàng.** Hỏi kho quan hệ **tại thời điểm truy vấn**, chỉ hỏi cho tài liệu đã lọt hạng đầu. Bốn loại quan hệ xử lý khác nhau: sửa đổi đi hết chuỗi cả hai chiều; phụ lục kéo; dẫn chiếu **chỉ một bước**; cùng chủ đề **không kéo**. Xếp hạng bằng **thừa hưởng điểm trên điểm đã chuẩn hoá**, hệ số 0.5 mỗi mắt xích. *Nguồn*: 06 Mục 6.2, 6.4.
*Xong khi*: ngưỡng `relation_pull_threshold` **chỉ áp cho liên kết có `origin` là máy suy luận**. Liên kết do người gắn và liên kết đọc từ dẫn chiếu tường minh luôn được kéo, bất kể điểm. Có test riêng cho điều này — gộp chung một điều kiện lọc là cách cài đặt ngắn hơn và sai.

**Cập nhật 23/9/2026:** tài liệu kéo theo họ hàng đọc từ lớp quan hệ trong PostgreSQL, **không đi qua bộ lọc của Qdrant** — nên truy vấn quan hệ phải tự áp lại **cùng** `readable_space_ids` và **cùng** danh sách gỡ vì sai. Liên kết có thể nối sang Space người hỏi không đọc được, vì GĐ7 quét dọc cây kế thừa.
*Xong khi* (bổ sung): thành viên chỉ có ở Space con kế thừa hỏi → không ra tài liệu của Space cha, kể cả khi tài liệu đó là họ hàng của một kết quả.

**T3.4 — Trần và cảnh báo.** Trần 6 tài liệu; chạm trần thì trả lời bình thường và **nói rõ đã giới hạn**; cảnh báo chỉ hiện khi số ứng viên vượt trần từ 3 lần trở lên. Tràn ngữ cảnh thì **báo lỗi và ghi nhật ký**, tuyệt đối không cắt ngầm. *Nguồn*: 06 Mục 6.5.

**T3.5 — Dựng đơn vị đọc.** Theo `parent_chunk_id` lên khối cha, cắt `extracted_text` theo vị trí của khối cha. Mẩu không có cha thì đơn vị đọc là chính nó. **Hai mẩu cùng cha thì cha chỉ lấy một lần.** *Nguồn*: 07 Mục 2.2.

**T3.6 — Tách bước hiểu câu hỏi khỏi bước trả lời.** Lịch sử hội thoại **chỉ** đi vào bước một — bước biến *"còn điều khoản thứ hai thì sao"* thành một câu hỏi đứng một mình. Bước sinh câu trả lời **chỉ nhận câu hỏi đã đứng một mình cộng tài liệu vừa lấy lại**, không nhận lịch sử. *Nguồn*: 06 Mục 9.4.
*Xong khi*: hỏi tiếp nối rồi thu hồi quyền giữa chừng — lượt sau không được trả lời bằng nội dung của lượt trước.

**Cập nhật 23/9/2026 (PO, 06 Mục 9.4 v1.10):** lịch sử không còn đọc từ kho của Retrieval. Đầu vào của bước một là **K lượt gần nhất** (câu hỏi + phần chữ câu trả lời) và **trạng thái hội thoại** do Backend gửi kèm lời gọi; đầu ra thêm **trạng thái hội thoại mới** để Backend lưu. Trạng thái là **biểu mẫu** — tài liệu đang nói tới (chỉ `document_id`), chủ đề, đối tượng, mạch câu hỏi — dựng chỉ từ câu hỏi của người dùng và định danh/tên tài liệu được dẫn nguồn, **không đọc phần chữ câu trả lời**. Các `document_id` trong trạng thái được lấy lại và cho qua cùng bộ lọc quyền như kết quả tìm mới. K là khoá cấu hình (nhóm Retrieval) — thiếu khoá thì từ chối chạy, như mọi tham số khác.
*Xong khi* (bổ sung): (1) trạng thái hội thoại không có trường nào chứa được con số hay trích đoạn — kiểm bằng schema, không bằng đọc đầu ra; (2) tài liệu trong trạng thái mà người hỏi vừa mất quyền → không vào ngữ cảnh lượt sau, không được nhắc tới, nhật ký có ghi việc loại.

**T3.7 — Agent chuyên miền.** Agent **không gắn Space**, không ảnh hưởng việc tìm. Mọi ràng buộc bất khả xâm phạm phải là **bước** bao quanh mô hình, không phải câu trong lời nhắc. Bộ kiểm lúc tạo agent. *Nguồn*: 06 Mục 8.

**T3.8 — Cảnh báo trong câu trả lời.** Năm loại, đều là dữ kiện đưa vào chứ không phải lời dặn mô hình: tài liệu mâu thuẫn nhau; quan hệ chưa đối chiếu xong; tài liệu **đã có bản mới hơn**; hai tài liệu trùng vân tay khác ngày; và **ngày không đáng tin** (nguồn là *mặc định ngày nạp*). *Nguồn*: 06 Mục 5.4, 5.7, 6.3, 6.4.

**T3.9 — Nhật ký điều tra.** Ai hỏi, lúc nào, phạm vi quyền tại thời điểm đó, con trỏ tới các mẩu đã vào ngữ cảnh, tài liệu bị loại kèm lý do trong hai lý do cứng, agent nào được dùng. **Không nguyên văn câu hỏi, không nguyên văn câu trả lời.** Chỉ Admin đọc. *Nguồn*: 06 Mục 9.2.

**T3.10 — Lịch sử hội thoại. ⛔ CHUYỂN SANG BACKEND C.BRAIN — chốt 23/9/2026.** Backend lưu nguyên văn câu hỏi, câu trả lời và trạng thái hội thoại; giữ nguyên kể cả khi quyền đổi; chỉ chính người đó đọc; người dùng xoá được (06 Mục 9.1, 9.4 v1.10). AI Services **không** lưu kho này và không có API đọc/xoá lịch sử. Phần việc còn ở phía AI đã gộp vào T3.6. *Nguồn*: 06 Mục 9.4; `10` Mục 6.1–6.2.
> Bản v1.3 tạo hạng mục này vì T3.6 giả định kho tồn tại. Giờ T3.6 nhận thẳng dữ liệu qua lời gọi — không còn phụ thuộc.

**T3.11 — R1: không có nguồn thì không trả lời.** ⚠️ **Làm cùng lúc với T3.2, không để cuối.** 06 Mục 8.4 chốt cách thực thi: không tìm được tài liệu nào thì **không gọi mô hình**, trả lời từ chối luôn. Đây là ràng buộc đầu tiên trong sáu ràng buộc bất khả xâm phạm, và nó phải là một **bước** chứ không phải một câu dặn.
*Xong khi*: hỏi một câu không có tài liệu nào trong phạm vi quyền trả lời được → hệ thống từ chối, và **mô hình sinh không được gọi lần nào** (kiểm bằng cách đếm lượt gọi, không kiểm bằng đọc câu trả lời).

### Nhóm 4 — Điểm cắm và kiểm chứng

**T4.1 — Điểm cắm đo lường.** Chừa chỗ cho một dòng sự kiện ẩn danh, tách khỏi cả ba kho ở 06 Mục 9.1. **v1 chưa phát sự kiện nào.** Khối Đo lường **không được đọc nhật ký điều tra**. *Nguồn*: 06 Mục 9.6.

**T4.2 — Bộ kiểm chứng cho các hỏng im lặng.** Đây là hạng mục dễ bị bỏ nhất và đáng giá nhất, vì toàn bộ thiết kế được dựng để chống một loại lỗi: **sai mà không ai biết**. Mỗi ca thử phải dựng đúng tình huống rồi khẳng định hệ thống **lên tiếng**:

| Ca thử | Phải xảy ra |
|---|---|
| Người vừa được cấp quyền hỏi ngay | Ra kết quả của Space mới, không im lặng rỗng |
| Người vừa bị thu hồi quyền hỏi ngay | Không ra tài liệu đó nữa |
| Tài liệu có bản mới hơn được dùng để trả lời | Câu trả lời nói rõ có bản mới |
| Số ứng viên vượt trần từ 3 lần | Câu trả lời nói rõ đã giới hạn |
| Số ứng viên vượt trần chút ít | **Không** hiện cảnh báo |
| Ngữ cảnh tràn | Báo lỗi, không cắt ngầm |
| Tài liệu chưa duyệt ở Space riêng | Không có trong kho vector |
| Ngày hiệu lực mang nguồn *mặc định ngày nạp* | Câu trả lời không đọc ra ngày đó như ngày thật |
| Quan hệ chưa quét xong | Câu trả lời nói rõ chưa đối chiếu xong |
| Cấu hình lệch con dấu trên kho | Service không khởi động |
| Thiếu một khoá cấu hình | Service không khởi động |
| Chuỗi tiếng Việt có dấu, cắt theo vị trí | Đoạn cắt ra đúng ký tự, không lệch |
| Không tài liệu nào trong quyền trả lời được | Từ chối, và **mô hình sinh không được gọi lần nào** |
| Quyền người dùng đổi sau khi đã hỏi vài lượt | Lịch sử hội thoại **vẫn còn nguyên** — *từ 23/9 là ca nghiệm thu của Backend (T3.10 chuyển sang Backend)* |
| Liên kết do người gắn, điểm tin cậy để trống | Vẫn được kéo vào ngữ cảnh |
| Một Điều dài nhiều trang | Bị chia nhỏ tiếp, các mẩu con cùng một `parent_chunk_id` |
| Chạy lệnh xoá vĩnh viễn hai lần liên tiếp | Không lỗi, kết quả không đổi |
| Cảnh báo tài liệu lỗi thời xuyên Space | **Không chứa tên Space nào** |
| Lời gọi hỏi thiếu `readable_space_ids` | Từ chối với lỗi, **không** tìm không điều kiện |
| Tài liệu trong trạng thái hội thoại, người hỏi vừa mất quyền | Không vào ngữ cảnh lượt sau, không được nhắc tới |
| Thành viên chỉ có ở Space con kế thừa; tài liệu Space cha là họ hàng của kết quả | Không được kéo vào ngữ cảnh |

---

## E. Ba việc song song, không thuộc đường găng

1. **Ước lượng công sức lại từ đầu.** Con số 14.5–15.0 MD cũ chỉ tính thiết kế cơ bản. ⚠️ Đây là **chỗ duy nhất trong cả chuỗi việc mà đọc mã nguồn hệ đang chạy là hợp lệ** — quy tắc "cấm lấy code cũ làm chuẩn" bảo vệ *phán đoán thiết kế*, không áp cho việc ước lượng khối lượng.
   > **Cập nhật 18/9/2026 (quyết định thay PO, theo uỷ quyền của Viet cùng ngày):** Đã có đề xuất đầy đủ tại `docs/09_Uoc_Luong_Cong_Suc_v2.md`. Dùng con số **ĐỀ XUẤT 85.5 MD** (dải 74–103) làm mốc lập kế hoạch từ nay. Nguồn đối chiếu hệ cũ dùng để soát quy mô (09 Mục 2) không ghi đường dẫn cụ thể — theo đúng yêu cầu bảo mật đã nêu trong chính tài liệu 09 — và chỉ dùng để **soát lại**, không dùng để **suy ra** số liệu, nên chấp nhận trạng thái này để không chặn tiến độ. Viet (PO) có thể yêu cầu ghi lại đường dẫn cụ thể bất kỳ lúc nào nếu thấy cần.
2. **Cập nhật bốn tài liệu ở 06 Mục 11.** Nợ từ 5/9.
> ⚠️ Riêng `research/R11_Phan_Quyen.md` có một việc **không phải dọn tài liệu mà là một tính năng thật**: cảnh báo hai chiều cho Manager khi thao tác với cờ kế thừa — bật thì báo ai sẽ đọc được, **tắt thì báo bao nhiêu người sẽ mất quyền đọc bao nhiêu tài liệu**. Nó ở đây vì việc thực thi thuộc tầng phân quyền chứ không thuộc hai service này, **không phải vì nó ít quan trọng**. Chiều tắt là chiều gây hỏng im lặng (06 Mục 7.3). Cần một người có tên phụ trách, nếu không nó sẽ rơi giữa hai kế hoạch. *(Cập nhật 23/9/2026: hiển thị cảnh báo thuộc Backend/giao diện; phần AI Services phải cung cấp là **số tài liệu theo Space** — `10` Mục 6.5.)*
3. **Chạy phép đo tỷ lệ dẫn chiếu tường minh** ngay khi có kho tài liệu thật. Ngoài giá trị vốn có, nó là điều kiện để bật cảnh báo đang treo ở 06 Mục 6.2.
