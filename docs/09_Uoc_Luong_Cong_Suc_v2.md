# 09 — Ước lượng công sức Ingestion v2 & Retrieval v2

> **⚠️ Cập nhật 23/9/2026 — các con số dưới đây CHƯA tính lại theo `10_Hop_Dong_API_Backend_AI_Services.md`.** Bốn thay đổi làm lệch ước lượng: (1) T3.10 (2.5 MD) chuyển sang Backend; (2) T2.10 chốt nghiêng về Backend nên phát sinh **tầng API phía AI Services** mà tài liệu này chưa tính — đúng cảnh báo ở dòng T2.10 bên dưới; (3) T3.6 thêm trạng thái hội thoại; (4) T4.2 thêm năm ca (18 → 23); T3.6/T3.8 thêm điều kiện nghiệm thu (23/9 tối). Cần ước lượng lại trước khi dùng tổng số cho lập kế hoạch.

> **⚠️ Ước lượng lại sơ bộ 23/9/2026 (Gemini 3.1 Pro, task `EST-09-uoc-luong-lai-theo-10`; Cowork cộng lại vì báo cáo gốc cộng sai):** các hạng mục chịu tác động của `10` v0.4 — cũ **24.5 MD** → mới **41.5–46.5 MD** (T3.10 0; T3.1 3.0; T2.9 3.5; T3.6 4.5; T3.8 4.0; T4.2 8.5; tầng HTTP 10.0–15.0 gồm khung dịch vụ 2.0–3.5 + endpoint nhập liệu 3.5–5.0 + chăm sóc tri thức 2.5–3.5 + hỏi–đáp/agent/nhật ký 2.0–3.0; `GET /v1/meta` 0.5; T2.11 3.0; gọi ngược BE lấy cây Space 1.5; dòng sự kiện 1.0; nghiệm thu chung BE+AI 2.0). **Tổng kế hoạch: 85.5 → ~102.5–107.5 MD**, ngang hoặc vượt mốc "thận trọng" cũ (~103). Dải phụ thuộc framework HTTP (chưa chốt) và việc có giả lập được Backend cho nghiệm thu chung hay không. **Chưa phải con số PO chốt.**

| | |
|---|---|
| **Phiên bản** | v1.0 |
| **Ngày** | 16/9/2026 |
| **Là gì** | Ước lượng công sức (MD) cho **từng hạng mục còn lại** trong `08_Ke_Hoach_Trien_Khai.md` Phần D, làm lại từ đầu trên thiết kế thật |
| **Vì sao có tài liệu này** | `06` Mục 12 việc 2 và `07` Mục 7 việc 2: *"Con số 14.5–15.0 MD trước đây chỉ tính thiết kế cơ bản, không còn đúng — phạm vi đã mở rộng nhiều lần kể từ đó."* Việc này nằm ở `08` Phần E, **không thuộc đường găng** |
| **Nguồn chân lý** | `06` v1.9 (cơ chế + lý do), `07` v1.8 (hợp đồng dữ liệu), `08` v1.3 Phần D (danh sách hạng mục + điều kiện nghiệm thu) |
| **Người quyết định** | Viet (PO) — tài liệu này là **đề xuất để PO chốt**, không phải cam kết |

---

## 0. Cách đọc con số

**1 MD = một ngày làm việc tập trung của một người đã đọc xong `06` và `07`.**
Thời gian đọc hai tài liệu nguồn (ước 1.0–1.5 MD một lần) **không** được cộng vào từng hạng mục.

**Mỗi con số ĐÃ bao gồm:**
- viết mã;
- viết test đủ để thoả **điều kiện nghiệm thu ghi ở `08` Phần D** — và ở repo này nghiệm thu được phát biểu theo hướng *"có test chứng minh hệ thống **không** làm được điều ngược lại"* (`08` Phần D, nhiều chỗ), nên phần test nặng gần bằng phần cài đặt;
- sửa sau review.

**Mỗi con số KHÔNG bao gồm:**
- thời gian **chờ PO quyết** (T2.10 có một quyết định phải chốt; bảy điểm còn mở ở `06` Mục 10 chạm phải thì dừng và hỏi — `CLAUDE.md` Mục 0.3);
- dựng hạ tầng, CI/CD, triển khai, vận hành;
- hợp đồng với Backend/Frontend — `07` Mục 0 loại trừ tường minh phần này;
- những thứ v1 **không xây**: GĐ4 quét chỗ nhạy cảm (hoãn — `06` 5.2), cơ chế che PII (`06` 7.1), OCR / ảnh quét (`06` 5.2), dòng sự kiện đo lường thật (`06` 9.6 — v1 chỉ chừa điểm cắm);
- việc 2 và việc 3 của `08` Phần E (cập nhật bốn tài liệu ở `06` Mục 11; chạy phép đo tỷ lệ dẫn chiếu tường minh).

**Giả định chung, đúng cho mọi dòng dưới đây:**

| | |
|---|---|
| G1 | **Nhóm 0 đã xong phần hạ tầng**: hai kho chạy được (T0.1 — 19/19 ca thử đạt), BGE-M3 chạy được (T0.2), `CLAUDE.md` đã dựng (T0.4). Chỉ T0.3 còn dư việc. |
| G2 | **Nhóm 1 xong và tên trường đóng băng trước khi mở Nhóm 2 và Nhóm 3** (`08` Phần C). Nếu vi phạm thứ tự này thì mọi con số ở Nhóm 2 và 3 đều sai. |
| G3 | Ước lượng tính theo **một người làm tuần tự**. Nhóm 2 ∥ Nhóm 3 chạy song song được thì rút **thời gian lịch**, không rút MD. |
| G4 | Kho cỡ **vài nghìn tài liệu** — đúng giả định nằm dưới bảng tám tham số ở `07` Mục 3.2. Lớn hơn một bậc thì T2.6 và T3.1 phải tính lại. |
| G5 | **Hai kho vật lý** (Qdrant + PostgreSQL), không kho đồ thị riêng — `08` Phần B2. Ba kho trong `06`/`07` là ba kho **logic**. |

---

## 1. ⛔ Kỷ luật phương pháp — lỗi ở Phụ lục `06` và cách tài liệu này tránh nó

`06` Phụ lục ghi lại một lỗi đã xảy ra thật ở **hai vòng phản biện đầu**:

> *"đề bài yêu cầu đối chiếu với **mã nguồn hiện tại**, trong khi đây là thiết kế xây lại từ đầu... Hậu quả là một số kết luận nghe rất chắc chắn nhưng thực chất dựa trên tham số của hệ cũ — ví dụ kết luận 'chi phí không bùng nổ' dựa trên một giá trị giới hạn đọc từ code cũ, trong khi thiết kế mới chưa chọn giá trị nào."*

Và bài học rút ra:

> *"mã nguồn hiện tại chỉ được dùng làm bằng chứng **'lỗi kiểu này đã từng xảy ra'** — không bao giờ được dùng làm chuẩn **'hệ thống phải hoạt động như vậy'**."*

**Vì sao lỗi đó nguy hiểm, nói lại cho rõ**: nó không tạo ra một kết luận *sai trông có vẻ sai*. Nó tạo ra một kết luận **sai trông rất chắc chắn**, vì nó có số thật đứng sau. Người đọc thấy con số, tin nó, và không nhận ra con số ấy đo một hệ thống **khác** với hệ thống đang được thiết kế. Đúng hình dạng hỏng im lặng mà cả `06` lẫn `07` dựng lên để chặn — chỉ khác là lần này nó xảy ra ở tầng *quy trình làm việc* chứ không ở tầng phần mềm.

**Ba luật tự áp cho tài liệu này:**

| | |
|---|---|
| **L1** | Mã nguồn hệ cũ chỉ được đọc để lấy **quy mô** — số dòng, số module, số ca thử. Không đọc để hiểu *cách nó làm*. |
| **L2** | Mọi chỗ hệ cũ làm **khác** `06`/`07` đều **bỏ qua không bình luận**. Không ghi "có thể nên xem lại", không ghi "hệ cũ làm thế này". Thiết kế đã chốt; tài liệu này chỉ đếm công. |
| **L3** | Hạng mục nào hệ cũ **không có thứ tương đương** thì ghi thẳng là **ước thuần từ đặc tả**, và đánh dấu độ chắc chắn thấp hơn — thay vì mượn tạm một con số gần đúng từ chỗ khác. |

> ⚠️ Có một chỗ L2 phải áp tay: hệ cũ **đóng băng danh sách quyền vào payload lúc nạp** — chính con bug mà `07` Mục 5 và `08` Phần B điều 9 ghi lại. Trong tài liệu này, sự kiện đó **chỉ** được đọc theo một nghĩa: *hạng mục T3.1 ở v2 không phải là một việc nhỏ như kích thước module tương ứng ở hệ cũ gợi ý, vì v2 tính tươi chứ không đóng băng*. Nó **không** được đọc theo bất kỳ nghĩa thiết kế nào.

---

## 2. Tham chiếu mã nguồn hệ cũ — chỉ tín hiệu quy mô

**`08` Phần E việc 1 cho phép đọc mã nguồn hệ đang chạy** — đây là chỗ duy nhất trong cả chuỗi việc mà việc đó hợp lệ, vì *"quy tắc 'cấm lấy code cũ làm chuẩn' bảo vệ phán đoán thiết kế, không áp cho việc ước lượng khối lượng"*.

> ⚠️ **`08` Phần E việc 1 KHÔNG ghi đường dẫn tới mã nguồn hệ cũ.** Nguồn đối chiếu do người lập ước lượng tự xác định, **PO cần xác nhận lại trước khi tin các dòng "tín hiệu hệ cũ"** trong tài liệu này. Nếu xác nhận là sai nguồn thì mọi con số vẫn đứng được — chúng được dựng bottom-up từ đặc tả, hệ cũ chỉ dùng để **soát lại**, không dùng để **suy ra**.

Đã đối chiếu quy mô với một hệ tương tự đã triển khai trước đó của cùng PO; chi tiết đường dẫn/tên file/số dòng không ghi lại theo yêu cầu bảo mật.

**Ba kết luận rút ra ở mức quy mô, và chỉ ở mức quy mô:**

1. **Hai service hệ cũ cộng lại ~26.400 dòng** (mã + test) cho một phạm vi **hẹp hơn** v2 — và một phần đáng kể số dòng đó là hạ tầng (Kafka, workspace, quan trắc) mà `07` Mục 0 loại ra khỏi phạm vi v2. Nghĩa là con số 26.400 **không** trừ thẳng ra được, nó chỉ nói *"khối lượng mã cho hai service kiểu này rơi vào hàng chục nghìn dòng, không phải vài nghìn"*.
2. **Bốn khối lớn của v2 không có thứ tương đương ở hệ cũ** — lớp quan hệ với quét bão hoà hai điều kiện (T2.6, T3.3), chuỗi phiên bản và `pending_version_claim` (T2.1), vùng đệm tiền kiểm tách khỏi kho dùng chung (T2.7), công cụ nạp lại toàn kho (T1.5). Bốn hạng mục này ước **thuần từ đặc tả** theo L3.
3. **Tỷ lệ test/mã ở hệ cũ khoảng 0.37** (7.100 / 19.300). v2 đặt chuẩn nghiệm thu cao hơn hẳn — `08` Phần D yêu cầu test cho *từng khoá cấu hình* (T1.2), test cho *những gì không được tồn tại* (T1.4), cắt tiến trình *ở từng bước* (T2.8), và 18 ca hỏng im lặng (T4.2). Tỷ lệ này ở v2 phải gần **1.0**. Đây là một trong những lý do lớn nhất làm con số phình so với 14.5–15.0 MD.

---

## 3. Trạng thái hiện tại — cái gì đã xong, cái gì còn lại

| Hạng mục | Trạng thái | Còn lại bao nhiêu |
|---|---|---|
| T0.1 Dựng hai kho | ✅ xong — 19/19 ca thử đạt, đã migrate ARM-native | 0 |
| T0.2 Dựng BGE-M3 | ✅ xong — có ca thử hợp đồng | 0 |
| T0.3 Bộ đọc + chứng minh phân cấp | 🟡 **gần xong** — đã dựng ~730 dòng (`readers.py`, `structure.py`, `vn_normalizer.py`), 5/6 điều kiện đạt | **còn vế 90%** |
| T0.4 Repo + `CLAUDE.md` | ✅ xong | 0 |
| T1.1 – T4.2 | ⛔ **chưa bắt đầu** — `packages/schema/` và `packages/retrieval/` còn rỗng | toàn bộ |

→ **Phạm vi tài liệu này: phần dư của T0.3, cộng trọn vẹn 28 hạng mục T1.1 – T4.2.**

---

## 4. Ước lượng theo nhóm

### 4.0 Nhóm 0 — phần dư

| Mã | Tên ngắn | **MD** | Giả định đứng sau con số | Điểm chưa chắc chắn | Tín hiệu hệ cũ |
|---|---|---|---|---|---|
| **T0.3-dư** | Đóng vế *"≥90% dựng đúng hoàn toàn phân cấp"* | **2.0** | PO đối chiếu tay 21 văn bản (công của PO, **không** tính vào đây); 2.0 MD là công **vá lỗi** bộ chuẩn hoá sau khi PO chỉ ra chỗ sai, cộng chạy lại bộ thử | ⚠️ **Rủi ro cao nhất Nhóm 0.** `08` T0.3 ghi rõ việc này **có thể thất bại** và có ba đường thoát. Rơi vào đường thoát 2 (thu hẹp định dạng) thì T2.2 rẻ đi; rơi vào đường thoát 3 (quay lại bàn với PO) thì **đơn vị ĐỌC ở S2 mất nền và cả `06` Mục 6.1 phải xem lại** — khi đó T2.3, T3.5 và toàn bộ con số này phải làm lại | — |

**Cộng Nhóm 0: 2.0 MD**

---

### 4.1 Nhóm 1 — Module schema dùng chung *(chặn cả hai service)*

| Mã | Tên ngắn | **MD** | Giả định đứng sau con số | Điểm chưa chắc chắn | Tín hiệu hệ cũ |
|---|---|---|---|---|---|
| **T1.1** | Bốn thực thể có kiểu | **2.5** | ~50 trường trên 4 thực thể (`07` Mục 2). Không chỉ khai kiểu mà còn **chặn bằng cấu trúc**: `removed_as_wrong` và `superseded` không gộp được thành `status`; không có `is_latest_version`; `structure_path` là **danh sách các đoạn**, không phải chuỗi nối; đánh dấu rõ trường nào được vào mệnh đề loại trừ (QT3). Nghiệm thu: đổi tên một trường → **cả hai service không biên dịch được** | Ngôn ngữ đích có ép được "không biên dịch được" đến đâu. Python thuần chỉ phát hiện lúc chạy — nếu muốn *ồn ào lúc build* thật thì phải thêm bước kiểm kiểu tĩnh vào CI, và bước đó **chưa có hạng mục nào phụ trách** | Có module tương ứng ở hệ cũ, nhưng ít trường hơn và **không** mang phần chặn bằng cấu trúc. Không dùng làm mốc |
| **T1.2** | Ba nhóm cấu hình + hai số phiên bản | **2.5** | ~15 khoá trên ba file không chồng lấn. Phần nặng **không** phải đọc YAML mà là: (a) một ca thử **cho từng khoá** thiếu, mỗi ca khẳng định service không khởi động và **báo rõ thiếu khoá nào**; (b) chứng minh **không có mặc định ẩn trong mã** — `08` T1.2 nói thẳng *"nói 'không được đặt mặc định trong mã' là chưa đủ, nó vẫn có thể nằm ngay trước chỗ dùng"*; (c) chép cột *dấu hiệu đặt sai* vào file cấu hình dạng ghi chú | Nếu thêm tham số trong lúc làm Nhóm 2/3 thì mỗi tham số mới kéo theo một ca thử mới — con số này trôi theo | Tín hiệu: bề mặt cấu hình của loại hệ thống này ở hệ cũ **lớn hơn nhiều so với cảm giác ban đầu**. Đây là lý do 2.5 MD chứ không phải 1.0 |
| **T1.3** | Con dấu trên kho vector | **2.0** | Chọn và cài **nhà riêng cho `embedding_model`** (`08` Phần B2 điều 2: Qdrant mang số chiều và thước đo **nhưng không mang tên mô hình**) — một điểm dữ liệu dành riêng trong collection, hoặc một bảng Postgres khoá theo tên collection. Cộng bước kiểm lúc khởi động ở **cả hai** service, so với **con dấu của kho**, không so với nhau | Ca khó nhất — **đổi mô hình mà giữ nguyên số chiều** — phải dựng được trong test mà không cần tải hai mô hình 2.5GB. Cần một lớp giả lập; chưa rõ nó có đủ thật để ca thử còn giá trị không | Hệ cũ **không có** khái niệm con dấu trên kho. Ước thuần từ đặc tả (L3) |
| **T1.4** | Bộ test cho những gì KHÔNG được tồn tại | **1.5** | Cần một cách **liệt kê được** mọi trường trong payload cạnh mẩu để đối chiếu với danh sách cấm (`07` Mục 5: danh sách quyền, loại Space, `title`, `doc_number`, `effective_date`, `approval_state`, cờ "mới nhất", mức nhạy cảm). Cộng ca thử vị trí đầu/cuối đếm theo **ký tự Unicode**, dữ liệu thử là **chuỗi tiếng Việt có dấu** | Bộ test này chỉ chặn được trường **đã biết tên**. Một trường cấm mang tên lạ vẫn lọt trừ khi test viết theo hướng *danh sách trắng* (chỉ 10 trường ở `07` Mục 2.2 được phép, còn lại đỏ). Nên viết theo hướng danh sách trắng — đã tính vào 1.5 MD | Ca thử cắt theo vị trí ký tự **đã có sẵn** ở `tests/t0_1_stores/test_c_substring_by_char.py`, dùng lại được |
| **T1.5** | Công cụ nạp lại toàn kho | **2.5** | Đầu vào là `extracted_text` đã có trong hồ sơ — **không đọc lại file gốc** (`08` T1.5). Phải **chạy lại được từ giữa chừng nếu đứt**, và phải **đóng dấu lại kho** sau khi xong. Cùng công cụ dùng lại khi đổi cách cắt (`06` 5.5) | Đổi **cách cắt** thì phải chạy lại cả GĐ3 chứ không chỉ GĐ6 — nghĩa là công cụ này phụ thuộc T2.3. Làm T1.5 trước T2.3 thì sẽ phải quay lại sửa; 2.5 MD giả định **làm sau T2.3**, tức là T1.5 ra khỏi đường găng của Nhóm 1 | Hệ cũ **không có** công cụ tương đương. Ước thuần từ đặc tả (L3) |

**Cộng Nhóm 1: 11.0 MD**

> Nhóm này nhỏ về số dòng nhưng **chặn mọi thứ phía sau** (`08` Phần C). Rút ngắn nó là cách chắc chắn nhất để làm hỏng Nhóm 2 và Nhóm 3 — con bug `doc_profile_code`/`profile_code` mà `07` Mục 0 mô tả chính là cái giá của việc bỏ qua nhóm này.

---

### 4.2 Nhóm 2 — Ingestion v2

| Mã | Tên ngắn | **MD** | Giả định đứng sau con số | Điểm chưa chắc chắn | Tín hiệu hệ cũ |
|---|---|---|---|---|---|
| **T2.1** | GĐ1 nhận và xác thực | **3.0** | Bốn việc riêng biệt trong một hạng mục: vân tay nội dung **có đánh chỉ mục** (`07` Mục 7 yêu cầu 1 — vân tay có **ba** người dùng); trùng khít cùng Space → báo, không nạp lại; trùng khít khác Space → hợp lệ và **im lặng** (báo là vi phạm `06` 9.5); người upload khai bản mới, không khai thì sinh `pending_version_claim` và nhắc **cả hai** người | Thuật toán vân tay và ngưỡng "gần giống" để rẽ sang đường bản mới chưa có đặc tả số. `07` 2.4 có trường `similarity` nhưng không có ngưỡng | — |
| **T2.2** | GĐ2 đọc file | **2.0** | **Đã có ~730 dòng từ T0.3** — bốn bộ đọc và bộ chuẩn hoá cây. Phần còn lại: biến nó thành **điểm cắm** thật (không bước nào sau đó rẽ nhánh theo `source_format` — S4), sinh `extracted_text` làm nguồn chân lý duy nhất của chữ nghĩa, từ chối định dạng ngoài danh sách kèm thông báo rõ | Bẫy toạ độ PDF (`08` T0.3 điều 3 — chèn dấu cách theo **khe hở ngang**) đã xử lý ở T0.3 nhưng chỉ trên 5 PDF. Gặp PDF lạ font thì có thể phải quay lại | Quy mô tương ứng ở hệ cũ gần bằng phần đã viết ở T0.3 (730 dòng) → phần dư quả thật nhỏ. **Đây là hạng mục mà tín hiệu hệ cũ trùng khớp tốt nhất với ước lượng** |
| **T2.3** | GĐ3 cắt thành mẩu | **4.0** | Cấu trúc quyết định ranh giới, ý nghĩa **chỉ** chia nhỏ tiếp khối quá dài (`06` 5.2 GĐ3 — ba điều cấm). Sinh `structure_path` dạng **danh sách**, `parent_chunk_id` đúng **một cấp** lên, `span_start`/`span_end` theo **ký tự Unicode**. Nghiệm thu: một Điều dài nhiều trang **bị chia nhỏ tiếp**, cả nhóm mẩu con cùng trỏ về một `parent_chunk_id` | ⚠️ **Chạm điểm mở #4 của `06` Mục 10** — *trần và sàn độ dài đơn vị cắt* chưa chốt. "Quá dài là bao nhiêu" chưa có số. Theo `CLAUDE.md` Mục 0.3 phải **dừng và hỏi PO**. 4.0 MD giả định PO trả lời trong lúc làm, không phải chờ | **Hệ cũ cắt theo độ dài** — một bài toán khác hẳn về độ khó. Theo L2 không suy gì thêm; chỉ giữ quy mô tương ứng ở hệ cũ như **sàn**, không phải trần |
| **T2.4** | GĐ5 gán nhãn và trích ngày | **4.0** | Hai loại ngày, mỗi ngày mang **nguồn** ba giá trị (`06` 6.4). Ngày ký có khuôn chuẩn nên trích dễ; **ngày hiệu lực khó hơn** — phải định vị điều khoản thi hành và **tránh nhầm với ngày của văn bản bị thay thế nhắc trong cùng câu** (`07` Phụ lục A). Nghiệm thu đòi **≥90% ngày ký trích đúng trên một tập thử có tên gọi** — nghĩa là phải **dựng tập thử và gán nhãn tay**, đã tính vào con số | Tập thử 21 văn bản của T0.3 dùng lại được cho ngày ký, nhưng **gán nhãn đúng/sai vẫn phải làm tay**. Nếu ≥90% không đạt ngay lượt đầu thì mỗi vòng tinh chỉnh khuôn mẫu thêm ~0.5 MD | Hệ cũ có phần tương ứng cho nhãn, nhưng **không** có phần ngày. Phần ngày ước thuần từ đặc tả (L3) |
| **T2.5** | GĐ6 tạo vector | **1.5** | BGE-M3 đã chạy được từ T0.2. Còn lại: gọi theo lô, **chuẩn hoá L2**, đọc cấu hình từ **nhóm hợp đồng** chứ không đọc biến môi trường riêng (`08` T2.5), ghi vào Qdrant | Độ dài mẩu biến thiên mạnh (`07` 2.2 — một Điều hai dòng tới ba trang). Gom lô theo số mẩu sẽ cho lô kích thước rất chênh; có thể phải gom theo token | — |
| **T2.6** | GĐ7 phát hiện quan hệ | **7.0** | **Hạng mục nặng nhất toàn kế hoạch.** Gồm: bốn loại quan hệ **có phân loại** (`06` 5.3 — không phân loại thì quy tắc kéo họ hàng ở 6.2 không chạy); điểm tin cậy liên tục; `origin` ba giá trị; quy ước chiều `from` **tác động lên** `to`; **hai** nguồn đề nghị — dẫn chiếu tường minh **và** dấu hiệu *cùng đối tượng + cùng loại văn bản + ngày ban hành sau*; phạm vi mở rộng dần từ Space chứa tài liệu; tiêu chí dừng **hai điều kiện phải thoả ĐỒNG THỜI** (S8: bão hoà **và** trần chi phí) | ⚠️ **Độ chắc chắn thấp nhất toàn tài liệu.** Ba lý do: (a) hệ cũ không có gì tương đương → không có mốc quy mô nào; (b) `06` Mục 10 ghi phép đo **tỷ lệ dẫn chiếu tường minh** là *"điểm chưa phân định quan trọng nhất"* và **hiện chưa đo được**; (c) dấu hiệu *"cùng đối tượng được nói tới"* đòi một bước rút thực thể từ văn bản mà **không tài liệu nào đặc tả**. Lệch ±3.0 MD là hoàn toàn có thể | Quy mô tương ứng ở hệ cũ **không dùng làm mốc**, vì hệ cũ không có lớp quan hệ theo nghĩa `06` 5.3. Ước thuần từ đặc tả (L3) |
| **T2.7** | Tiền kiểm ở Space riêng | **3.0** | Chạy GĐ2, GĐ3, GĐ5 rồi **dừng trước GĐ6 và GĐ7**, giữ trong **vùng làm việc riêng tách khỏi bảng hồ sơ chính thức** — `08` T2.7 cảnh báo: với hai kho vật lý thì **PostgreSQL cũng là kho dùng chung**, ghi hồ sơ vào đó rồi chỉ hoãn nạp vector là đã vi phạm bất biến. Nghiệm thu: truy vấn **thẳng** vào cả Qdrant và PostgreSQL, không qua service | Việc "chạy nốt sau khi duyệt" nghĩa là phải **giữ được trạng thái trung gian** (cây cấu trúc, danh sách mẩu, nhãn) qua một khoảng thời gian không xác định. Hình dạng lưu trữ cho vùng đệm này **chưa có bảng trường ở đâu cả** | Hệ cũ **không có** vùng đệm tiền kiểm. Ước thuần từ đặc tả (L3) |
| **T2.8** | Xoá vĩnh viễn | **3.5** | Thứ tự rút gọn theo hai kho vật lý: **kho vector → (quan hệ + hồ sơ, MỘT giao dịch) → dọn nền**. Phần đắt **không** phải thứ tự mà là hai điều kiện nghiệm thu: (1) **cắt tiến trình ở từng bước một** rồi chạy lại đều hoàn tất được — phải dựng cơ chế tiêm lỗi cho từng bước; (2) chạy lệnh xoá **hai lần liên tiếp** không gây lỗi, không đổi kết quả | Ranh giới Qdrant ↔ PostgreSQL **không có giao dịch chung**. Phải có sổ tiến độ để chạy lại được, và bản thân sổ đó cũng nằm ở một trong hai kho → vẫn còn một khe hở phải chọn cách sống chung. Chưa tài liệu nào chỉ định cách | Hệ cũ có phần tương ứng, nhưng không có nghiệm thu cắt-tiến-trình. Phần đó ước thuần từ đặc tả (L3) |
| **T2.9** | Hàng việc chăm sóc tri thức | **2.5** | Ba loại mục: quan hệ chờ duyệt, bản mới chờ xác nhận, và *"tài liệu này có thể đã lỗi thời"*. Loại thứ ba phải tra ngược **từ vân tay ra danh sách tài liệu** rồi đẩy vào hàng việc của Manager các Space giữ bản trùng — và **tuyệt đối không nêu Space nào, không nêu ai, không nêu ở đâu** (`06` 5.7 cơ chế 1; `08` Phần B điều 23) | Hàng việc là dữ liệu mà **Manager đọc qua giao diện** — ranh giới với Backend chưa rõ, cùng loại vấn đề mà T2.10 sinh ra để giải. Nếu T2.10 chốt hàng việc thuộc Backend thì phần này rút xuống ~1.5 MD | — |
| **T2.10** | Bề mặt ghi cho thao tác của Manager | **3.0** | Năm thao tác: đánh dấu gỡ vì sai, đánh dấu hết hiệu lực, duyệt/từ chối liên kết, xác nhận đề nghị bản mới, xoá vĩnh viễn. Nghiệm thu đòi **chốt tường minh mỗi thao tác thuộc service nào** — Ingestion hay Backend | ⚠️ **Đây là một QUYẾT ĐỊNH, không chỉ là mã.** `08` T2.10 ghi rõ ranh giới này **nằm ngoài phạm vi `06` và `07`** (`07` Mục 0 loại trừ hợp đồng với Backend), nên *"phải quyết tường minh chứ không mặc định"*. 3.0 MD giả định PO chốt nghiêng về **Ingestion**. Chốt nghiêng về Backend thì phần này còn ~1.0 MD nhưng **đẻ ra một hợp đồng API mới chưa ai ước lượng** | — |

**Cộng Nhóm 2: 33.5 MD**

---

### 4.3 Nhóm 3 — Retrieval v2

| Mã | Tên ngắn | **MD** | Giả định đứng sau con số | Điểm chưa chắc chắn | Tín hiệu hệ cũ |
|---|---|---|---|---|---|
| **T3.1** | Phạm vi quyền và hai bộ lọc cứng | **4.0** | Duyệt cây Space **tươi tại thời điểm hỏi**: người + nhóm (nhóm là **thực thể thật**, không phải tiện ích chọn nhiều người — `06` 0.1) + kế thừa **một chiều xuống** + **cắt tại nhánh riêng**, cờ kế thừa là **cờ sống** kiểm lại mỗi lần. Cộng danh sách *gỡ vì sai* cũng tính tươi, truyền vào làm danh sách loại trừ. Cộng đánh chỉ mục trường Space (`07` Mục 7 yêu cầu 3) | Độ trễ khi người hỏi **chỉ đọc được một phần rất nhỏ của kho** — `07` S7 ghi ghi chú vận hành: tỷ lệ điểm thoả bộ lọc thấp thì Qdrant có thể **tự chuyển sang quét toàn bộ**. Không sai kết quả, chỉ chậm — nhưng nếu chậm quá ngưỡng dùng được thì phát sinh việc chưa ước | Vì hệ cũ đóng băng quyền vào payload, quy mô tương ứng ở hệ cũ theo L1/L2 **KHÔNG phải mốc cho T3.1** — tính tươi là một bài toán khác hẳn về quy mô. Không rút ra gì về thiết kế |
| **T3.2** | Tìm ở cấp mẩu | **1.5** | Trong phạm vi do T3.1 trả về. Cosine trên vector chuẩn hoá L2 | Ít. Đây là phần chuẩn nhất của toàn hệ | nằm trong cùng một module lớn ở hệ cũ, gộp cả phần tương ứng T3.4, T3.5 |
| **T3.3** | Kéo họ hàng | **5.0** | Hỏi kho quan hệ **tại thời điểm truy vấn**, chỉ hỏi cho tài liệu đã lọt hạng đầu. Bốn loại xử lý **hoàn toàn khác nhau**: sửa đổi đi **hết chuỗi, cả hai chiều, mọi nhánh** (truy vấn đệ quy trong PostgreSQL); phụ lục kéo; dẫn chiếu **chỉ một bước**; cùng chủ đề **không kéo**. Xếp hạng bằng thừa hưởng điểm **trên điểm ĐÃ CHUẨN HOÁ trên tập ứng viên**, hệ số 0.5 mỗi mắt xích. Cộng một ca thử riêng: ngưỡng **chỉ** áp cho `origin` là máy suy luận | Hai chỗ dễ sai mà không có lỗi nào báo: (a) nhân hệ số lên **điểm thô** thay vì điểm chuẩn hoá — `06` 6.2 nói thẳng khi đó *"con của hạng nhất tụt dưới cả chục tài liệu không liên quan"*; (b) đi **ngược chiều** quy ước `from`/`to` — `07` 2.3 cảnh báo *"hai service vẫn biên dịch được nhưng một bên sẽ đi ngược chiều bên kia và không có lỗi nào báo"*. Cả hai đòi ca thử riêng, đã tính vào 5.0 | Hệ cũ không đi hết chuỗi sửa đổi. Ước thuần từ đặc tả (L3) |
| **T3.4** | Trần và cảnh báo | **2.0** | Trần 6 tài liệu; chạm trần thì trả lời bình thường và **nói rõ đã giới hạn**; cảnh báo **chỉ** hiện khi vượt trần từ 3 lần. Tràn ngữ cảnh → **báo lỗi và ghi nhật ký**, tuyệt đối không cắt ngầm | Chặn "cắt ngầm ở tầng dưới" đòi kiểm soát được cả thư viện gọi mô hình — `08` Phần B điều 8 ghi đó là **hành vi mặc định của gần như mọi thư viện**. Có thể phải tự đếm token trước khi gọi thay vì tin thư viện | nằm trong cùng module lớn nêu ở T3.2 |
| **T3.5** | Dựng đơn vị đọc | **2.0** | Theo `parent_chunk_id` lên **đúng một cấp**, cắt `extracted_text` theo vị trí của khối cha bằng `SUBSTRING ... FROM ... FOR ...` (**đọc theo đoạn**, không lấy cả trường về rồi cắt — `07` Mục 7 yêu cầu 2). Mẩu không có cha thì đơn vị đọc là chính nó. **Hai mẩu cùng cha thì cha chỉ lấy MỘT lần** | Ít. Bằng chứng khả thi đã có sẵn ở `tests/t0_1_stores/test_c_substring_by_char.py` | nằm trong cùng module lớn nêu ở T3.2 |
| **T3.6** | Tách bước hiểu câu hỏi khỏi bước trả lời | **3.0** | **Hai lượt gọi mô hình, tách rời.** Lịch sử hội thoại **chỉ** đi vào bước một — bước biến *"còn điều khoản thứ hai thì sao"* thành câu hỏi đứng một mình. Bước sinh câu trả lời **chỉ nhận câu hỏi đã đứng một mình + tài liệu vừa lấy lại**. Nghiệm thu: hỏi tiếp nối rồi **thu hồi quyền giữa chừng** — lượt sau không được trả lời bằng nội dung lượt trước | Chất lượng bước viết lại câu hỏi quyết định chất lượng cả vòng, và **không có tiêu chí đo nào trong `08`**. Làm kém thì hỏi tiếp nối hỏng mà không ai biết đó là do bước một | Hệ cũ có phần tương ứng, **nhưng đó là mở rộng truy vấn, chạm điểm mở #5 của `06` Mục 10, không thuộc v1**. Không dùng làm mốc, không ước lượng phần đó |
| **T3.7** | Agent chuyên miền | **4.5** | Hai tầng hướng dẫn; agent **không gắn Space**, không ảnh hưởng việc tìm. Dạng nhập tầng chuyên môn là **biểu mẫu có cấu trúc + một ô ghi chú nhỏ** (chặn bằng cấu trúc — `06` 8.5), cộng bộ kiểm soi **sáu loại câu** trên đúng ô ghi chú đó, cộng nhánh *"nghi ngờ thì cho tạo nhưng đánh dấu chờ duyệt, admin tự duyệt được nhưng bắt buộc ghi lý do"* | ⚠️ **`07` Mục 4 ghi rõ: định nghĩa agent chuyên miền CHƯA CÓ BẢNG TRƯỜNG ở bất kỳ đâu.** 4.5 MD đã gồm việc tự rút bảng trường đó, nhưng rút schema là một phép kiểm thiết kế (`07` Mục 6) — nó có thể lộ ra điểm mở mới và khi đó phải dừng hỏi PO | Hệ cũ có hệ thống agent với quy mô đáng kể nhưng **hình dạng khác hẳn**. Theo L2 không đối chiếu; chỉ ghi nhận quy mô cho thấy đây **không** phải hạng mục nhỏ |
| **T3.8** | Cảnh báo trong câu trả lời | **3.0** | Năm loại, **đều là dữ kiện đưa vào chứ không phải lời dặn mô hình** (`06` 8.4). Mỗi loại là một bước tính riêng: so ngày để thấy mâu thuẫn; đọc `relations_scan_state` để biết chưa đối chiếu xong; suy chuỗi phiên bản để biết có bản mới; so vân tay khác ngày; đọc `*_date_source` để biết ngày không đáng tin | Loại thứ ba — *"tài liệu đã có bản mới hơn"* — phải **suy ra** từ `version_chain_id` + `version_ordinal` vì `is_latest_version` bị cấm. Truy vấn suy ra này chạy cho mọi tài liệu trong trần, mỗi lượt hỏi | — |
| **T3.9** | Nhật ký điều tra | **3.0** | Ghi: ai hỏi, lúc nào, **phạm vi quyền tại thời điểm đó**, con trỏ tới các **mẩu** đã vào ngữ cảnh, tài liệu bị loại kèm lý do trong **hai** lý do cứng, agent nào. **Không nguyên văn câu hỏi, không nguyên văn câu trả lời.** Chỉ Admin đọc. Cộng phần **tra cứu và xuất được** (R3) | ⚠️ `07` Mục 4 ghi: nhật ký điều tra **chưa có bảng trường ở bất kỳ đâu**. Phải tự rút. Cộng: kho này **không xoá được** (`06` 9.1) → chọn sai cách lưu là một quyết định khó đảo ngược | Hệ cũ có phần tương ứng ở quy mô nhỏ. Tín hiệu: phần *ghi* rẻ; phần **tra cứu + xuất** (R3) mới là chỗ tốn công và hệ cũ không có |
| **T3.10** | Lịch sử hội thoại | **2.5** | Kho **riêng**, không phải nhật ký điều tra, không phải hồ sơ cá nhân hoá — ba kho có ba tính chất xoá khác nhau và **không được gộp** (`06` 9.1). Giữ **nguyên văn** câu hỏi và câu trả lời; **giữ nguyên kể cả khi quyền đã đổi**; **chỉ chính người đó đọc**; T3.6 đọc được từ đây | ⚠️ Cũng **chưa có bảng trường** (`07` Mục 4). Và `06` Mục 10 điểm mở **#15** — *dọn lịch sử hội thoại khi xoá tài liệu* — còn treo; `06` 5.6 ghi đó là giới hạn đã chấp nhận ở v1, nên **không ước lượng**, nhưng nó sẽ quay lại | — |
| **T3.11** | R1: không có nguồn thì không trả lời | **1.0** | Một **bước**, không phải một câu dặn. `08` T3.11 nhấn: **làm cùng lúc với T3.2, không để cuối**. Nghiệm thu bằng **đếm lượt gọi mô hình**, không bằng đọc câu trả lời — nên cần một lớp đếm bao quanh mô hình | Lớp đếm đó cũng là thứ T4.2 cần. Nếu T3.11 dựng nó tử tế thì T4.2 rẻ đi; con số 1.0 MD giả định dựng tử tế | — |

**Cộng Nhóm 3: 31.5 MD**

---

### 4.4 Nhóm 4 — Điểm cắm và kiểm chứng

| Mã | Tên ngắn | **MD** | Giả định đứng sau con số | Điểm chưa chắc chắn | Tín hiệu hệ cũ |
|---|---|---|---|---|---|
| **T4.1** | Điểm cắm đo lường | **1.0** | **v1 chưa phát sự kiện nào** (`06` 9.6) — chỉ chừa chỗ cho một dòng sự kiện ẩn danh, tách khỏi cả ba kho ở 9.1, và chặn bằng cấu trúc việc khối Đo lường đọc nhật ký điều tra | Rẻ **vì** v1 không phát gì. Nếu PO đổi ý và muốn phát sự kiện thật ở v1 thì đây thành một hạng mục hoàn toàn khác | — |
| **T4.2** | Bộ kiểm chứng cho các hỏng im lặng | **6.5** | **18 ca thử** ở `08` Phần D. Mỗi ca phải **dựng đúng tình huống** rồi khẳng định hệ thống **lên tiếng** — không phải khẳng định nó chạy trôi. Nhiều ca đòi dựng trạng thái xuyên cả hai service và cả hai kho: cấp quyền rồi hỏi ngay; thu hồi quyền rồi hỏi ngay; tài liệu chưa duyệt ở Space riêng; xoá vĩnh viễn chạy hai lần; quyền đổi mà lịch sử hội thoại còn nguyên. Con số giả định **dùng chung một bộ đồ gá dựng cảnh** cho phần lớn ca | ⚠️ **Hạng mục dễ bị cắt nhất và đáng giá nhất** — `08` nói thẳng điều đó. Nếu mỗi ca phải dựng cảnh riêng thay vì dùng chung đồ gá thì 6.5 MD thành ~10 MD. Đây cũng là chỗ dễ bị "xong 80%" rồi dừng, vì 18 ca thì ca nào cũng có vẻ giống ca trước | Tổng ca thử hệ cũ ~7.100 dòng cho **toàn bộ** hai service. Riêng T4.2 ở v2 đã là 18 ca đầu-cuối. Tín hiệu: **tỷ lệ test/mã ở v2 phải cao hơn hệ cũ đáng kể**, và 6.5 MD là con số dè dặt |

**Cộng Nhóm 4: 7.5 MD**

---

## 5. Tổng

| Nhóm | Số hạng mục còn lại | **MD** |
|---|---|---|
| Nhóm 0 — phần dư (T0.3) | 1 | **2.0** |
| Nhóm 1 — Module schema dùng chung | 5 | **11.0** |
| Nhóm 2 — Ingestion v2 | 10 | **33.5** |
| Nhóm 3 — Retrieval v2 | 11 | **31.5** |
| Nhóm 4 — Điểm cắm và kiểm chứng | 2 | **7.5** |
| **TỔNG** | **29** | **85.5 MD** |

**Dải, không phải một điểm:**

| | MD | Khi nào rơi vào đây |
|---|---|---|
| Lạc quan | **~74** | T0.3 qua ngay lượt PO đối chiếu đầu; T2.6 không phải làm lại phần rút thực thể; T2.10 chốt nhanh; T4.2 dùng chung được đồ gá dựng cảnh |
| **Đề xuất** | **85.5** | các giả định ghi ở Mục 0 và Mục 4 đúng |
| Thận trọng | **~103** | T2.6 lệch +3; ba hạng mục phải tự rút bảng trường (T3.7, T3.9, T3.10) lộ ra điểm mở mới phải hỏi PO; T4.2 phải dựng cảnh riêng cho từng ca |

> Con số này là **công lập trình**. Nó **không** phải thời gian lịch — Nhóm 2 và Nhóm 3 chạy song song được (`08` Phần C), nên lịch ngắn hơn MD nếu có hai người.

---

## 6. Vì sao lệch so với 14.5–15.0 MD

**85.5 / 14.75 ≈ 5.8 lần.**

`06` Mục 12 việc 2 đã nói trước lý do: *"Con số 14.5–15.0 MD trước đây chỉ tính **thiết kế cơ bản**, không còn đúng — phạm vi đã mở rộng nhiều lần kể từ đó."* Dưới đây là chỗ mở rộng, có dẫn chứng.

### 6.1 Bảy nguồn mở rộng, theo thứ tự đóng góp

| | Nguồn mở rộng | Dẫn chứng | Ảnh hưởng |
|---|---|---|---|
| **1** | **Chuẩn nghiệm thu đổi bản chất.** Từ *"xong khi làm được X"* sang *"xong khi có test chứng minh **không** làm được cái ngược lại"* | `08` T1.2 (test **từng khoá** cấu hình), T1.4 (test những gì **không được tồn tại**), T2.8 (**cắt tiến trình ở từng bước** + chạy xoá hai lần), T3.11 (nghiệm thu bằng **đếm lượt gọi mô hình**), T4.2 (**18 ca** hỏng im lặng) | **Lớn nhất.** Một ước lượng "thiết kế cơ bản" gần như chắc chắn không đếm phần này. Riêng nó đã cộng ~20 MD |
| **2** | **Vòng pre-mortem 14/9 thêm cơ chế thật, không chỉ thêm chữ.** Năm kịch bản K1–K5, bốn ở mức CAO | `06` Mục 12: **K2** → tách ngày ký khỏi ngày hiệu lực, **mỗi ngày mang nguồn** (T2.4 phình); **K3** → máy đề nghị quan hệ dựa trên *cùng đối tượng + cùng loại + ngày sau*, không chỉ dẫn chiếu tường minh (T2.6 phình mạnh); **K5** → hai cơ chế bù cho bản sao xuyên Space (T2.9 + T3.8) | ~8 MD |
| **3** | **`08` v1.3 thêm bốn hạng mục hoàn toàn mới** sau vòng đánh giá độc lập kế hoạch | `08` dòng lịch sử v1.3: **T1.5** nạp lại toàn kho, **T2.10** bề mặt ghi cho Manager, **T3.10** lịch sử hội thoại, **T3.11** ràng buộc R1. Ba trong bốn cái này trước đó **không ai phụ trách** — `08` T3.10 ghi thẳng *"Chưa có hạng mục nào phụ trách kho này trước hôm nay, trong khi T3.6 giả định nó tồn tại"* | **9.0 MD** — cộng thẳng, đo được chính xác |
| **4** | **Vòng bốn (cách ly, 11/9) phát hiện thiếu hẳn một đường** | `06` Phụ lục: *"(b) **thiếu hẳn đường xoá vĩnh viễn**, ba vòng trước không ai thấy — đã thành Mục 5.6"* → T2.8 | **3.5 MD** |
| **5** | **Lỗ hổng cả năm vòng đều bỏ sót: schema không có trường nào chứa văn bản** | `06` Phụ lục, đoạn cuối. Sinh ra `extracted_text` làm **nguồn chân lý duy nhất của chữ nghĩa**, kéo theo: đơn vị đọc phải **cắt theo vị trí** (T3.5), kho phải **đọc theo đoạn** (`07` Mục 7 yêu cầu 2), và công cụ nạp lại đọc từ đó chứ không đọc lại file gốc (T1.5) | ~3 MD rải ra |
| **6** | **Tám điểm mở S1–S8 đóng bằng cách thêm cơ chế, không phải bằng cách bỏ bớt** | `07` Mục 6: **S1** → vùng đệm tiền kiểm **tách khỏi kho dùng chung** (T2.7 — và với hai kho vật lý thì PostgreSQL cũng là kho dùng chung, nên vùng đệm phải thật); **S2** → đơn vị đọc parent-child + **ba quy tắc con** (T2.3 chia nhỏ tiếp, T3.5 khử trùng cha); **S6** → thứ tự xoá **đảo ngược** so với khuyến nghị nghiên cứu; **S8** → dừng quét khi **hai** điều kiện thoả đồng thời | ~6 MD |
| **7** | **Đo thật ngày 15/9 làm T0.3 và T2.2 nặng hơn dự kiến** | `08` T0.3 hộp *"Sửa 15/9/2026 sau khi dựng và đo thật"*: tầng phân tích bố cục của Docling **gộp dòng** làm mất tín hiệu cấu trúc; phần dùng được là **rút chữ kèm toạ độ**; và bẫy **khe hở ngang** đã làm hỏng im lặng **4/5 PDF** trước khi bị bắt. Bộ chuẩn hoá regex là **đường chính**, không phải dự phòng — cho cả `.docx` **và** PDF | đã tiêu ~4 MD ở T0.3 (không nằm trong 85.5 vì đã làm xong) |

### 6.2 Một cách đọc khác của cùng con số

Con số cũ 14.5–15.0 MD tương ứng khoảng **2–3 tuần một người**. Với phạm vi hiện tại đó là **vừa đủ để làm xong Nhóm 1 cộng một nửa Nhóm 2** — nghĩa là dừng lại đúng ở chỗ hệ thống nạp được tài liệu nhưng **chưa trả lời được câu nào**.

Đối chiếu độc lập bằng quy mô hệ cũ (Mục 2): hai service hệ cũ có quy mô cho một phạm vi **hẹp hơn** v2 và một chuẩn test **thấp hơn** v2. 14.5–15.0 MD cho khối lượng đó là không khả thi ở bất kỳ nhịp làm việc nào. **85.5 MD** thì nhất quán với cả hai đường tính.

---

## 7. Bảy chỗ có thể làm con số này sai, xếp theo mức nguy hiểm

| | Chỗ | Vì sao nguy hiểm | Hạng mục chịu ảnh hưởng |
|---|---|---|---|
| **1** | **T0.3 không đóng được vế 90%** | `08` T0.3 ghi việc này **có thể thất bại**. Rơi vào đường thoát 3 thì *"đơn vị ĐỌC ở S2 mất nền và cả `06` Mục 6.1 phải xem lại"* — khi đó phần lớn tài liệu này phải làm lại | T2.2, T2.3, T3.5, và gián tiếp toàn bộ |
| **2** | **T2.6 — không có mốc nào để soát lại** | Hệ cũ không có thứ tương đương; phép đo tỷ lệ dẫn chiếu tường minh — *"điểm chưa phân định quan trọng nhất"* (`06` Mục 10) — **chưa đo được**; và bước rút thực thể *"cùng đối tượng được nói tới"* không có đặc tả | T2.6 (±3.0), T3.3 |
| **3** | **Ba thực thể chưa có bảng trường ở bất kỳ đâu** | `07` Mục 4 liệt kê thẳng: nhật ký điều tra, lịch sử hội thoại, định nghĩa agent. Rút schema là **một phép kiểm thiết kế** (`07` Mục 6) — nó đã từng lộ ra tám điểm mở mới một lần rồi | T3.7, T3.9, T3.10 |
| **4** | **Điểm mở #4 của `06` Mục 10 chặn T2.3** | *Trần và sàn độ dài đơn vị cắt* chưa chốt — "khối cấu trúc quá dài" chưa có số. `CLAUDE.md` Mục 0.3 buộc **dừng và hỏi PO** | T2.3 |
| **5** | **T2.10 là một quyết định ranh giới, không chỉ là mã** | Nằm **ngoài** phạm vi `06` và `07`. Chốt nghiêng về Backend thì hạng mục rẻ đi nhưng **đẻ ra một hợp đồng API chưa ai ước lượng** | T2.10, T2.9 |
| **6** | **T4.2 là chỗ dễ bị cắt nhất** | `08` gọi nó là *"hạng mục dễ bị bỏ nhất và đáng giá nhất"*. Cắt nó không làm hệ thống chạy sai ngay — nó chỉ làm cả thiết kế mất tuyến kiểm chứng duy nhất | T4.2 |
| **7** | **Giả định kho vài nghìn tài liệu** | `07` Mục 3.2 ghi rõ: lớn hơn một bậc thì `cap_warning_multiple`, `scan_pair_budget`, `scan_time_budget` phải tính lại | T2.6, T3.1, T3.4 |

---

## 8. Việc còn lại của chính tài liệu này

1. **PO xác nhận đường dẫn mã nguồn hệ cũ ở Mục 2** — `08` Phần E việc 1 cho phép đọc nhưng không ghi vị trí; đường dẫn hiện dùng do người lập ước lượng tự xác định.
2. **PO chốt con số**, hoặc chốt dải. Tài liệu này là đề xuất.
3. **Cập nhật `08` Phần E việc 1** để trỏ tới tài liệu này, và ghi luôn đường dẫn hệ cũ sau khi PO xác nhận — để lần sau không ai phải đi tìm lại.
4. **Tính lại sau khi T0.3 đóng** và sau khi bảy chỗ ở Mục 7 rõ dần. Ước lượng này tính trên trạng thái ngày 16/9/2026.
