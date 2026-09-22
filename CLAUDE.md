# CLAUDE.md — C.Brain: Ingestion v2 & Retrieval v2

Repo này **xây lại từ đầu** hai service của C.Brain. Đọc file này ở **mỗi phiên**, trước khi gõ dòng đầu tiên.

Hai tài liệu nguồn chân lý là kết quả của **sáu vòng phản biện độc lập**. Gần như mọi chỗ trông có vẻ thừa hoặc rườm rà trong đó đều là kết quả của một lần hỏng đã được lường trước. **Đừng đơn giản hoá cái gì mà không đọc lý do kèm theo** — lý do luôn được viết ngay cạnh quyết định.

---

## 0. ⛔ Bốn điều tuyệt đối

**1. KHÔNG đọc, không import, không lấy mã nguồn hệ cũ làm chuẩn.**
Repo cũ đặt ở nơi khác và **cố ý không có mặt ở đây**. Hai service này viết lại từ đầu, cố tình không kế thừa cách làm cũ. Khi tài liệu nhắc tới "hệ thống hiện tại", đó luôn là dẫn chứng *một kiểu lỗi đã từng xảy ra thật*, **không phải chuẩn phải theo**. Ngoại lệ hợp lệ duy nhất là ước lượng khối lượng công việc — và việc đó không làm trong repo này.

**2. Nguồn chân lý là `docs/06` và `docs/07`.**
Không phải file này, không phải code đã viết, không phải phiên trước. File này là bản trích để luôn trong tầm tay; khi nó lệch với `docs/` thì **`docs/` đúng**.

**3. Không tự quyết điểm còn mở.**
`docs/06` Mục 10 liệt kê **bảy điểm còn mở**. Chạm phải một trong số đó thì **dừng và hỏi PO**, không chọn bừa một hướng rồi đi tiếp.

**4. Code chỉ dùng tiếng Anh — CHỐT 22/9/2026.**
Tên định danh (hàm, biến, tham số, lớp, exception...), comment, docstring, và thông điệp lỗi (exception message) đều viết bằng **tiếng Anh** — kể cả khi sửa/mở rộng code cũ đang mang tên tiếng Việt (ví dụ `cat_thanh_mau`, `tran_do_dai_mau`, `KhongDungDuocCauTruc`): đổi tên luôn trong lúc work-order chạm tới đúng hàm/lớp đó (boy-scout rule), không để dành riêng cho một đợt refactor tổng thể. Mục tiêu: giảm khối lượng việc phải làm khi repo chuyển hẳn sang tiếng Anh sau này.

**Ngoại lệ duy nhất**: trích dẫn nguyên văn từ `docs/06`/`docs/07`/`docs/08`/`docs/09` (các tài liệu nguồn chân lý này luôn viết bằng tiếng Việt) trong comment/docstring — giữ nguyên tiếng Việt, đặt trong ngoặc kép, kèm chỉ rõ Mục/dòng nguồn, để còn đối chiếu chính xác ký tự-với-ký tự với tài liệu gốc (dịch sang tiếng Anh ở đây có rủi ro dịch sai ý pháp lý/kỹ thuật).

**Không áp dụng cho dữ liệu**: quy tắc này chỉ nói về **mã nguồn**. Giá trị chuỗi là nội dung thật trích từ văn bản tiếng Việt đang được xử lý (`structure_path`, `category_labels`, `extracted_text`, và mọi dữ liệu tương tự) vẫn giữ nguyên tiếng Việt — đó là dữ liệu của khách hàng, không phải code, và văn bản khách hàng đưa vào hệ thống không đổi ngôn ngữ theo quy tắc đặt tên của repo.

---

## 1. Nguồn chân lý và thứ tự đọc

| File | Là gì |
|---|---|
| `docs/06_Thiet_Ke_Pipeline_Ingestion_Retrieval_v2.md` | Thiết kế — cơ chế nghiệp vụ và **lý do** đằng sau từng quyết định |
| `docs/07_Hop_Dong_Du_Lieu_Schema_v2.md` | Hợp đồng dữ liệu — tên trường, kiểu, nơi cư trú, ai được ghi |
| `docs/08_Ke_Hoach_Trien_Khai.md` | Kế hoạch — 32 hạng mục T0.1–T4.2 kèm điều kiện nghiệm thu |

Vào việc mới: `06 Mục 0.1` (bối cảnh + R1–R6) → `06 Mục 2` (NT1–NT4) → `07 Mục 1` (QT1–QT3) → **Mục 3 của file này** (25 điều cấm) → mục cụ thể, tra theo cột *Nguồn chân lý* ở `08 Phần D`.

---

## 2. Hệ thống này là gì

C.Brain là trợ lý hỏi–đáp trên kho tri thức nội bộ của doanh nghiệp: người dùng hỏi bằng ngôn ngữ tự nhiên, hệ thống tìm trong tài liệu công ty và trả lời **kèm dẫn nguồn**. Nó **không phải nơi lưu trữ file** như một ổ đĩa dùng chung.

**Space** là *phạm vi tri thức mà AI được phép dùng để trả lời*, không phải thư mục chứa file. Space thành cây; Space con có hai loại: **kế thừa** (quyền đọc chảy một chiều **xuống**) và **riêng** (mặc định khi tạo mới). Cờ kế thừa là **cờ sống**, kiểm lại mỗi lần tính quyền. v1 dùng ba vai trò: *Viewer*, *Contributor*, *Manager*. **Quyền mặc định của tài khoản mới là 0**; kênh cấp quyền duy nhất là được gắn vào Space.

### Sáu ràng buộc bất khả xâm phạm

| | |
|---|---|
| **R1** | Không có nguồn thì không trả lời |
| **R2** | Dữ liệu không rời ranh giới hạ tầng khi chưa qua lớp bảo vệ; mặc định chạy nội bộ |
| **R3** | Nhật ký phải tra cứu và xuất được |
| **R4** | Kiểm quyền tại nơi **lấy dữ liệu**, không phải nơi hiển thị |
| **R5** | Đổi mô hình bằng **cấu hình**, không phải sửa mã |
| **R6** | Mỗi khách hàng một bản cài đặt độc lập |

### Bốn nguyên tắc thiết kế

- **NT1 — Ranh giới "được biết" đi qua từng CÂU HỎI; ranh giới "hiểu gì" đi qua từng TÀI LIỆU.** Cái gì trả lời *"ai được biết"* thì tính lúc hỏi; cái gì trả lời *"tài liệu này nói gì"* thì làm lúc nạp, một lần. Đây là đường cắt giữa hai service, và là lý do **agent không gắn vào Space**.
- **NT2 — Sự kiện lọc trước; phán đoán đứng sau và chấp nhận bỏ sót; chỗ nào bỏ sót gây hại thì phải NHÌN THẤY ĐƯỢC.** Ý thứ ba là thứ ngăn nguyên tắc này thoái hoá: không có nó, "chấp nhận bỏ sót" trượt thành "bỏ sót mà không ai biết". Cắt theo trần *được phép* vì câu trả lời nói rõ đã giới hạn; lọc cứng theo nhãn *bị cấm* vì tài liệu biến mất không dấu vết.
  - Hệ quả 1: **ngày là sự kiện, "tài liệu này nói về thời điểm nào" là phán đoán** — hỏi về mốc quá khứ thì KHÔNG được cắt bỏ tài liệu có ngày sau mốc đó.
  - Hệ quả 2: **ngưỡng chỉ chặn việc THÊM thì luôn an toàn** — đặt sai chỉ làm thêm được ít hơn, không làm mất cái đã có.
- **NT3 — Không lưu thứ sẽ cũ đi.** Thành viên, nhóm, cấu trúc cây, loại Space đều đổi vì con người thao tác → **không được nằm trong dữ liệu đã nạp**, tính tươi mỗi lần truy vấn. Nguyên tắc này một mình giải quyết "quyền có hiệu lực tức thì" mà không cần bất kỳ tiến trình đồng bộ nào — không có bản sao nào để mà đồng bộ.
- **NT4 — Chỉ có HAI bộ lọc cứng: quyền đọc, và tài liệu bị gỡ vì sai.** Mọi thứ còn lại — nhãn, lĩnh vực, agent, ngày, "hết hiệu lực" — đều **mềm**, chỉ được xếp thứ tự.

### Ranh giới hai service

| | **Ingestion v2 sản xuất** | **Retrieval v2 sản xuất** |
|---|---|---|
| Trả lời | *Tài liệu này nói gì, cấu trúc ra sao?* (ở phiên bản sau, thêm: *chỗ nhạy cảm nằm đâu* — 06 Mục 5.2 GĐ4, **hoãn ở v1**) | *Người này được biết gì, và trong đó cái gì trả lời được câu hỏi?* |
| Đầu ra | Hiểu biết về nội dung — **bất biến theo người hỏi** | Phán quyết về quyền + câu trả lời có dẫn nguồn |
| Tuyệt đối không | Không quyết định ai đọc được gì; **không che thông tin theo người** | Không suy diễn thêm về nội dung ngoài cái đã hiểu lúc nạp |

Hai service **không chia sẻ quyết định nào** — chỉ chia sẻ một mô tả về nội dung.

### ⚠️ Phạm vi v1: KHÔNG che thông tin cá nhân

**v1 không triển khai cơ chế che PII nào.** Kiểm soát hoàn toàn dựa vào phân quyền Space. Tuyến phòng thủ thật không phải là che, mà là **chỗ đặt tài liệu** (`docs/06` Mục 7.1).

Hệ quả khi lập trình:
- **GĐ4 (quét chỗ nhạy cảm) HOÃN ở v1.** Nó vẫn xuất hiện trong `docs/06` Mục 5.2 — đã đánh dấu HOÃN. **Không xây.**
- Bảng PII 4 tier trong tài liệu phân quyền là **đặc tả cho phiên bản sau**, không phải việc của v1.
- `extracted_text` **bắt buộc phải giữ**: đó là thứ cho phép quét lại về sau mà không đọc lại file gốc và không tạo lại vector.

### Ba quy tắc quyết định chỗ đứng của một trường

- **QT1 — Không mang PHÁN QUYẾT về quyền; được ghi DẤU VẾT của hành động đã xảy ra.** Phép thử: *xoá trường này đi, hệ thống có còn quyết định đúng ai được đọc gì không?* Còn → dấu vết, giữ được. Không còn → phán quyết, phải rời khỏi dữ liệu dùng chung.
- **QT2 — Cạnh mẩu vector chỉ đặt thứ BẤT BIẾN dùng để CẮT KHÔNG GIAN TÌM.** Phép thử: *trường này đổi giá trị thì có phải nạp lại mẩu không?* Có → không được đặt cạnh mẩu.
- **QT3 — Chỉ HAI trường được xuất hiện trong mệnh đề loại trừ**: quyền đọc, và tài liệu bị gỡ vì sai. Mọi trường khác chỉ được dùng để **xếp thứ tự**.

---

## 3. ⛔ Hai mươi lăm điều KHÔNG được làm

Mỗi dòng là một việc **trông hợp lý, gọn gàng hơn, và sai**. Cột giữa giải thích *vì sao nó hấp dẫn* — đó là phần quan trọng, vì thứ gì hấp dẫn thì sẽ có người làm.

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

### Những trường BỊ CẤM có mặt

| Cấm | Vì sao |
|---|---|
| Mọi danh sách người, nhóm, hay dấu hiệu quyền đóng băng trong dữ liệu đã nạp | **NT3 + QT1.** Hệ thống hiện tại đóng băng danh sách quyền vào payload lúc nạp và không có cơ chế đồng bộ lại; người vừa được cấp quyền qua được bộ lọc tươi nhưng trượt bộ lọc đóng băng → im lặng không ra kết quả |
| Loại Space (kế thừa/riêng), cấu trúc cây Space, danh sách thành viên | **NT3** — đổi vì con người thao tác, phải tính tươi mỗi lần hỏi |
| `is_latest_version` hoặc bất kỳ cờ "mới nhất" nào | Cũ đi ngay khi có bản mới; suy ra từ chuỗi phiên bản |
| `approval_state` của liên kết, đặt cạnh mẩu | **06 Mục 6.4** — buộc phải nạp lại mẩu mỗi lần Manager duyệt |
| `title`, `doc_number`, `effective_date`, trạng thái tài liệu, đặt cạnh mẩu | **06 Mục 6.4** — thứ dùng để ĐỌC và DẪN NGUỒN thì lấy sau từ hồ sơ |
| Một trường trạng thái **gộp** "gỡ vì sai" với "hết hiệu lực" | **06 Mục 6.3** — làm mất khả năng trả lời câu hỏi về quá khứ |
| Mức nhạy cảm tối đa của tài liệu | **06 Mục 7.1** — v1 không triển khai cơ chế che nào; và nó là phán đoán nên **NT4** cấm dùng để loại trừ |
| Nguyên văn câu hỏi hoặc câu trả lời trong nhật ký | **06 Mục 9.2** — tạo bản sao nội dung ở kho không xoá được, ngoài tầm với của xoá vĩnh viễn 5.6 |

> **Agent chuyên miền không sinh ra trường nào trong dữ liệu dùng chung.** Ai đề xuất một trường gắn agent vào tài liệu hoặc vào mẩu — đó là dấu hiệu ranh giới hai service đã bị vi phạm.

---

## 4. Cấu hình

### Ba nhóm, ba nơi, không chồng lấn

> 📌 **Ba nhóm là thiết kế đã chốt** (`docs/07` Mục 3.3). **Tên file cụ thể dưới đây là quyết định triển khai của repo này**, chưa từng xuất hiện trong `docs/` — đổi được, miễn giữ đúng ba nhóm không chồng lấn.

| Nhóm | File | Gồm | Ai đọc | Lệch thì sao |
|---|---|---|---|---|
| **Hợp đồng** | `config/contract.yaml` | `embedding_model`, `embedding_dim`, `distance_metric` | cả hai service | **hỏng ngầm** → kiểm với con dấu trên kho, không khớp thì từ chối chạy |
| **Ingestion** | `config/ingestion.yaml` | `saturation_*`, `scan_*`, danh sách định dạng nhận | chỉ Ingestion | không ảnh hưởng bên kia |
| **Retrieval** | `config/retrieval.yaml` | `inheritance_decay`, `document_cap`, `cap_warning_multiple`, `relation_pull_threshold` | chỉ Retrieval | không ảnh hưởng bên kia |

### Năm quy tắc

1. **Mỗi tham số có ĐÚNG MỘT nhà.** Không tham số nào xuất hiện ở hai nhóm.
2. ⛔ **Thiếu khoá cấu hình thì TỪ CHỐI CHẠY — không có giá trị mặc định trong mã.** Một mặc định trong mã chính là cái nhà thứ hai của tham số.
3. **Dấu hiệu đặt sai phải nằm NGAY CẠNH giá trị trong file cấu hình**, dạng ghi chú. v1 không có dòng số liệu nào, nên đây là chỗ duy nhất tri thức đó sống được ở nơi người ta dùng tới.
4. **`docs/07` ghi lý do; file cấu hình có thẩm quyền lúc chạy.** Bảng 3.2 ghi *giá trị khởi đầu*, không phải trạng thái hiện hành.
5. ⛔ **Không con số cứng trong mã.** Đây là **R5** mở rộng từ mô hình sang mọi tham số điều chỉnh.

### Chín giá trị khởi đầu (chốt 14/9/2026 — chi tiết + dấu hiệu đặt sai: `docs/07` Mục 3.2)

| Tham số | Giá trị | Service |
|---|---|---|
| `inheritance_decay` | **0.5** — áp trên điểm **đã chuẩn hoá** trên tập ứng viên | Retrieval |
| `document_cap` | **6** | Retrieval |
| `cap_warning_multiple` | **3** (báo khi >18 ứng viên) | Retrieval |
| `relation_pull_threshold` | **0.3** thang 0–1 | Retrieval |
| `saturation_epsilon` | **1%** | Ingestion |
| `saturation_rounds` | **3** | Ingestion |
| `scan_pair_budget` | **500** cặp/tài liệu | Ingestion |
| `scan_time_budget` | **10** phút/tài liệu | Ingestion |
| `chunk_length_cap` | **5000** ký tự Unicode/mẩu (chốt 21/9/2026, Điểm mở #4) | Ingestion |

> Giả định nằm dưới cả bảng: **kho cỡ vài nghìn tài liệu**. Lớn hơn một bậc thì `cap_warning_multiple`, `scan_pair_budget`, `scan_time_budget` phải tính lại.

### Con dấu trên kho vector

Lúc tạo kho, đóng dấu **tên mô hình + số chiều + thước đo** lên chính kho đó. Mỗi service khởi động so cấu hình của mình với **con dấu của kho nó đang đọc** — KHÔNG so với service kia (so với nhau thì lọt trường hợp cả hai cùng lệch với kho).

⚠️ Cấu hình collection của Qdrant mang số chiều và thước đo **nhưng không mang tên mô hình** — mà lệch tên mô hình khi **cùng số chiều** mới là thứ hỏng ngầm. `embedding_model` phải có nhà riêng: một điểm dữ liệu dành riêng trong collection, hoặc một bảng Postgres khoá theo tên collection.

**Module schema mang HAI số phiên bản**: phá vỡ tương thích → **từ chối chạy**; bổ sung tương thích → **ghi nhật ký, vẫn chạy**.

---

## 5. Công nghệ đã chốt (14/9/2026)

| | |
|---|---|
| **Bộ đọc file** | **Docling** (PDF có lớp chữ) · **python-docx** (.docx) · parser markdown (.md) · regex (.txt) — cộng **một bộ chuẩn hoá cây cấu trúc chung** nhận diện Chương › Điều › Khoản › Điểm theo quy chuẩn hành chính VN |
| **Mô hình biểu diễn** | **BGE-M3** — 1024 chiều, ngữ cảnh 8192 token, ~2.5GB. **v1 chỉ dùng dense** |
| **Kho** | **Qdrant** (vector + lọc loại trừ) + **PostgreSQL** (hồ sơ tài liệu, cắt đoạn theo vị trí, **và cả lớp quan hệ**). Không kho đồ thị riêng |

> **"Ba kho" trong `docs/06` và `docs/07` là ba kho LOGIC. Vật lý chỉ có hai.** Mọi câu "kho đồ thị" đọc là *lớp quan hệ trong PostgreSQL*.

⚠️ **Đừng tin thư viện nào để suy ra phân cấp — chúng chỉ được tin để RÚT CHỮ.** Văn bản hành chính VN soạn tay thường in đậm và đánh số bằng tay, không gán style, nên **bộ chuẩn hoá regex là đường chính, không phải dự phòng**. Đo thật 15/9 đã mở rộng điều này **sang cả PDF**: tầng phân tích bố cục của Docling gộp dòng thành đoạn, làm mất chính tín hiệu cấu trúc; phần dùng được là **rút chữ kèm toạ độ** ở tầng backend. Chi tiết và ba cái bẫy cụ thể: `docs/08` T0.3.

⚠️ **`span_start`/`span_end` đếm theo KÝ TỰ UNICODE, không phải byte.**

⚠️ **Thước đo khoảng cách là thuộc tính của mô hình, không phải lựa chọn tự do**: cosine + chuẩn hoá L2. Đổi mô hình thì phải đổi cả thước đo theo mô hình.

---

## 6. Cấu trúc repo và thứ tự làm việc

> 📌 **Cấu trúc thư mục dưới đây là quyết định triển khai của repo này**, không trích từ `docs/`. Cái bắt buộc là *một* module schema dùng chung mà cả hai service import; cách xếp thư mục thì đổi được.

```
docs/                      nguồn chân lý (06, 07, 08)
config/                    ba nhóm cấu hình, ba file, không chồng lấn
packages/schema/           Nhóm 1 — module dùng chung, CHẶN cả hai service
packages/ingestion/        Nhóm 2
packages/retrieval/        Nhóm 3
tools/reindex/             T1.5 — nạp lại toàn kho
tests/
```

**Thứ tự bắt buộc**: Nhóm 0 (nền) → **Nhóm 1** → Nhóm 2 ∥ Nhóm 3 → Nhóm 4.
Hai service độc lập ở mức mã nguồn — chỉ gặp nhau qua module Nhóm 1 và qua hai kho. Làm song song được, **miễn là Nhóm 1 xong và tên trường đã đóng băng trước**.

**Quy ước đặt tên trường**: chữ thường, nối bằng gạch dưới, tiếng Anh. Tên trường định nghĩa **đúng một lần** trong `packages/schema/`; **không service nào tự khai báo lại**. Đây chính là con bug `doc_profile_code` / `profile_code` mà module này sinh ra để chặn: hai chuỗi ký tự ở hai file khác nhau, mọi truy vấn có bộ lọc đó trả về **0 kết quả, im lặng**.

---

## 7. Thế nào là "xong"

> *"Xong khi làm được X"* luôn lỏng hơn *"xong khi có test chứng minh **không** làm được cái ngược lại."*

Viết test theo hướng **khẳng định hệ thống LÊN TIẾNG**, không phải khẳng định nó chạy trôi:

- Thiếu lần lượt **từng khoá** cấu hình → service **không khởi động được**, báo rõ thiếu khoá nào.
- Chạy **một mình** Retrieval với cấu hình lệch con dấu, không bật Ingestion → vẫn **từ chối khởi động**. Kiểm cả ca khó nhất: **đổi mô hình mà giữ nguyên số chiều**.
- Đổi tên một trường trong `packages/schema/` → cả hai service **không biên dịch được**.
- Thêm một trường bị cấm vào payload cạnh mẩu → **test đỏ**.
- Vị trí đầu/cuối đếm theo ký tự Unicode → ca thử phải là **chuỗi tiếng Việt có dấu**.
- Cắt tiến trình **ở từng bước** của lệnh xoá vĩnh viễn, và **chạy lệnh xoá hai lần liên tiếp**.
- **R1**: không có nguồn thì **không gọi mô hình**. Nghiệm thu bằng **đếm lượt gọi mô hình**, không bằng đọc câu trả lời.

Điều kiện nghiệm thu đầy đủ của từng hạng mục: `docs/08` Phần D.

---

## 8. Khi bí

- Mâu thuẫn giữa file này và `docs/` → **`docs/` đúng**, và báo để sửa file này.
- Chạm điểm còn mở (`docs/06` Mục 10) → **dừng, hỏi PO**.
- Thấy một cách làm gọn hơn thiết kế → **đọc lý do viết ngay cạnh quyết định đó trước**. Nếu vẫn thấy nên đổi, báo PO; không tự đổi.
