# 07 — Hợp đồng dữ liệu & module schema dùng chung (Ingestion v2 ↔ Retrieval v2)

| | |
|---|---|
| **Phiên bản** | v1.10 |
| **Ngày** | 23/9/2026 (bản rút lần đầu: 12/9/2026) |
| **Lịch sử** | v1.10 — 23/9/2026: lịch sử hội thoại ra khỏi danh sách thực thể của AI Services ở Mục 4 (Backend C.Brain lưu, 06 Mục 9.4 v1.10); trỏ hợp đồng với Backend sang `10_Hop_Dong_API_Backend_AI_Services.md`. Không đổi trường nào của bốn thực thể dùng chung. v1.9 — sửa dòng `labels_confirmed_by` ở 2.1 cho khớp cột Kiểu: tách thành hai trường `labels_confirmed_by` + `labels_confirmed_at`, cùng mẫu với ba cặp `_by`/`_at` khác trong cùng bảng (phát hiện lúc rút module mã nguồn T1.1, PO chốt 18/9). v1.8 — ghi chú ba kho logic nhưng hai kho vật lý (Qdrant + PostgreSQL), và hệ quả cho thứ tự xoá ở S6. v1.7 — chốt tám giá trị tham số kèm dấu hiệu nhận biết đặt sai (3.2); thêm quy tắc cấu hình: ba nhóm không chồng lấn, mỗi tham số một nhà, thiếu khoá thì từ chối chạy, cấm con số cứng trong mã (3.3). v1.6 — sau vòng kiểm nhất quán và bàn giao (14/9): sửa hai tham chiếu sai và một chỗ đếm lệch; chốt `structure_path` là danh sách các đoạn chứ không phải chuỗi nối; làm rõ ô đúng/sai là ô có thẩm quyền trong mỗi cặp trạng thái; thêm bảng sáu tham số PO phải chốt giá trị khởi đầu trước khi code. v1.5 — sau khi chốt bốn kịch bản pre-mortem còn lại: `content_fingerprint` có thêm hai người dùng và phải đánh chỉ mục (K5); các quyết định K1/K3/K4 không sinh trường mới nào ở đây. v1.4 — bổ sung `extracted_text` (lỗ hổng bốn vòng phản biện đều bỏ sót: không trường nào chứa văn bản) theo phương án nguồn chân lý duy nhất + vị trí đầu/cuối trên mẩu, đếm theo ký tự Unicode; tách `issued_date` khỏi `effective_date`, mỗi ngày mang nguồn. v1.3 — chốt S1 (tài liệu chờ duyệt không vào kho dùng chung, NT4 giữ nguyên hai bộ lọc cứng), chốt S2 (đơn vị đọc là khối cấu trúc cha một cấp, kèm ba quy tắc con), duyệt DX1/DX2/DX3 (con dấu trên kho vector, hai số phiên bản, quy trình đổi mô hình ở v1). v1.2 — sau gói nghiên cứu 14/9: đóng S4, S5, S6, S7, S8; chốt cosine + chuẩn hoá L2 ở Mục 3; đề xuất parent-child cho S2 kèm trường `parent_chunk_id`; thêm Phụ lục A. v1.1 — sau hai vòng phản biện độc lập: phát biểu lại QT1 (dấu vết khác phán quyết), chốt quy ước chiều quan hệ `from` tác động lên `to`, tách các trường kiểu gộp, định nghĩa liên kết do người gắn tay, bổ sung nhánh Manager cho `version_declared_by`, thêm mục ba thứ nằm ngoài phạm vi. Thêm điểm mở S8; S3 đổi bản chất thành mâu thuẫn của tài liệu 06. v1.0 — bản rút lần đầu |
| **Trạng thái** | **Đủ để chuyển thành module mã nguồn.** Tám điểm mở đã đóng, ba đề xuất đã duyệt. **Không còn điểm mở nào** — S3 đã chốt ở tài liệu 06 ngày 14/9 (hoãn bước quét chỗ nhạy cảm ở v1). Xem Mục 7 |
| **Người quyết định** | Viet (PO) |
| **Phạm vi** | **Chỉ hợp đồng dữ liệu giữa Ingestion v2 và Retrieval v2.** Không bao gồm hợp đồng với Backend/Frontend — hợp đồng đó nằm ở `10_Hop_Dong_API_Backend_AI_Services.md` |
| **Nguồn** | Toàn bộ trường trong tài liệu này được **rút ra từ** `06_Thiet_Ke_Pipeline_Ingestion_Retrieval_v2.md` v1.9. Mỗi trường đều có cột truy về mục sinh ra nó |

---

## 0. Tài liệu này là gì, và không là gì

**Là**: danh sách mọi mẩu dữ liệu mà Ingestion v2 ghi ra và Retrieval v2 đọc vào, kèm tên, kiểu, nơi cư trú, và ai được ghi. Đây là đặc tả của **một module mã nguồn duy nhất** mà cả hai service import — thay vì mỗi bên tự gõ lại tên trường trong code của mình.

**Không là**: thiết kế lại kho dữ liệu, quyết định chọn công nghệ lưu trữ, kịch bản chuyển đổi dữ liệu, hay hợp đồng API với Backend.

**Vì sao bắt buộc phải dùng chung.** Trong hệ thống hiện tại, Ingestion ghi một trường tên `doc_profile_code` còn Retrieval đi tìm trường tên `profile_code`. Hai chuỗi ký tự ở hai file khác nhau, không ai đối chiếu với ai. Hậu quả: mọi truy vấn có bộ lọc đó trả về **0 kết quả, im lặng** — không lỗi, không log. Đây đúng là kiểu hỏng mà cả tài liệu 06 chống, chỉ khác là nó nằm ở tầng kỹ thuật: tài liệu biến mất mà không ai biết. Khi tên trường chỉ được định nghĩa một lần, lỗi này chuyển từ *im lặng lúc chạy* thành *ồn ào lúc build*.

**Quy ước đặt tên**: chữ thường, nối bằng gạch dưới, tiếng Anh. Chính việc chốt được một cái tên duy nhất là thứ chặn được lớp bug trên, nên tài liệu này đặt tên cụ thể chứ không dừng ở mức khái niệm.

---

## 1. Ba quy tắc quyết định chỗ đứng của một trường

Không phải quy tắc mới — cả ba đều rút thẳng từ tài liệu 06. Khi phân vân một trường nên nằm đâu, chạy qua ba quy tắc này theo thứ tự.

### QT1 — Không mang PHÁN QUYẾT về quyền; được ghi DẤU VẾT của hành động đã xảy ra
*(Mục 3, và NT1)*

Ingestion sản xuất *hiểu biết về nội dung, bất biến theo người hỏi*. Retrieval sản xuất *phán quyết về quyền*. Hai service **không chia sẻ quyết định nào**, chỉ chia sẻ một mô tả về nội dung.

→ **Cấm**: mọi trường trả lời câu *"ai được đọc cái này"* — danh sách người, nhóm, vai trò, dấu hiệu quyền đóng băng.
→ **Được phép**: trường ghi lại *một hành động đã xảy ra* — ai duyệt liên kết này, ai xác nhận nhãn này, ai gỡ tài liệu này và lúc nào. Đó là **dấu vết**, không phải luật.

> **Vì sao phân biệt này đứng vững.** Tài liệu 06 Mục 9.2 đã bảo vệ đúng lập luận đó cho trường "phạm vi quyền tại thời điểm đó" trong nhật ký: *"NT3 cấm lưu quyền ở nơi quyền được dùng để ra quyết định, vì ở đó nó sẽ cũ đi và cho phán quyết sai. Nhật ký thì ngược lại: nó ghi quyền đã từng là gì, như một sự kiện lịch sử."* `approved_by` cùng loại — không ai dùng nó để quyết định ai được đọc gì.
>
> Phép thử: *nếu xoá trường này đi, hệ thống có còn quyết định đúng ai được đọc gì không?* Còn → đó là dấu vết, giữ được. Không còn → đó là phán quyết, phải rời khỏi dữ liệu dùng chung.

`space_id` không thuộc cả hai nhóm: nó là *chỗ tài liệu nằm*, một sự kiện bất biến ở v1, và Retrieval mới là bên biến nó thành phán quyết bằng cách tính tươi cây Space lúc hỏi.

> ⚠️ **Lần thứ hai cùng một kiểu lỗi.** Bản v1.0 của tài liệu này phát biểu QT1 tuyệt đối ("không trường nào được nói về người") rồi bị chính bảng trường của nó vi phạm — đúng như NT2 của tài liệu 06 từng bị. Thành thói quen: viết xong một nguyên tắc dạng cấm đoán thì kiểm ngay chính thiết kế của mình có vi phạm không.

### QT2 — Cạnh mẩu vector chỉ đặt thứ BẤT BIẾN dùng để CẮT KHÔNG GIAN TÌM
*(Mục 6.4, và NT3)*

Mọi thứ dùng để **đọc và dẫn nguồn** thì lấy sau, từ hồ sơ tài liệu. Mọi thứ **sẽ đổi vì con người thao tác** thì không được nằm trong dữ liệu đã nạp.

Phép thử một câu: *nếu trường này đổi giá trị, có phải nạp lại các mẩu không?* Nếu có, nó không được đặt cạnh mẩu.

### QT3 — Chỉ HAI trường được xuất hiện trong mệnh đề loại trừ
*(NT4)*

Quyền đọc, và tài liệu bị gỡ vì sai. Mọi trường khác — nhãn phân loại, lĩnh vực, ngày, hết hiệu lực, đã có bản mới — chỉ được dùng để **xếp thứ tự**. Module schema nên đánh dấu rõ trường nào thuộc nhóm nào, để một lập trình viên sau này không vô tình đưa nhãn vào mệnh đề lọc cứng.

---

## 2. Bốn thực thể dùng chung

> **Ba kho trong tài liệu này là ba kho LOGIC. Về vật lý, v1 chỉ có HAI** — chốt 14/9/2026: **Qdrant** (kho vector) và **PostgreSQL** (hồ sơ tài liệu **và** lớp quan hệ). Đồ thị vài nghìn nút không đáng một kho chuyên dụng; truy vấn đệ quy trong PostgreSQL đủ cho việc đi hết chuỗi sửa đổi.
>
> Mọi chỗ tài liệu này viết "kho đồ thị" đọc là *lớp quan hệ trong PostgreSQL*. Hệ quả tốt cho S6: hai bước xoá **quan hệ** và **hồ sơ** nằm chung một cơ sở dữ liệu nên thành **một giao dịch nguyên khối** — ranh giới duy nhất còn thiếu giao dịch chung là giữa Qdrant và PostgreSQL. Chi tiết ở `08_Ke_Hoach_Trien_Khai.md` Phần B2.

### 2.1 Hồ sơ tài liệu — `document`

Nơi cư trú: kho hồ sơ (quan hệ). Retrieval đọc **sau khi** đã có kết quả tìm, để dựng đơn vị ĐỌC và dẫn nguồn (Mục 6.1).

| Tên trường | Kiểu | Đổi được? | Ai ghi | Truy về |
|---|---|---|---|---|
| `document_id` | định danh | bất biến | Ingestion | 6.1, 6.4 — con trỏ về tài liệu |
| `space_id` | định danh | **bất biến ở v1** | Ingestion | sự thật 4; tiền đề ghi ở 6.4 |
| `tenant_id` | định danh | bất biến | Ingestion | 6.4 |
| `title` | chuỗi | đổi được | Ingestion, người sửa | 6.1 — thông tin nhận dạng |
| `doc_number` | chuỗi | đổi được | Ingestion, người sửa | 5.3, 6.1 — "Quyết định số X" |
| `issued_date` | ngày | **đổi được** | Ingestion trích (GĐ5), người sửa | 6.4 — **ngày ký**, ở đầu văn bản, trích dễ |
| `issued_date_source` | máy trích / người xác nhận / mặc định ngày nạp | đổi được | Ingestion hoặc người | 6.4 — trục thời gian chỉ tin hai giá trị đầu |
| `effective_date` | ngày | **đổi được** | Ingestion trích (GĐ5), người sửa | 6.4 — **ngày có hiệu lực**, ở điều khoản thi hành, trích khó hơn |
| `effective_date_source` | máy trích / người xác nhận / mặc định ngày nạp | đổi được | Ingestion hoặc người | 6.4 |
| `ingested_at` | thời điểm | bất biến | Ingestion | 6.4 |
| `source_format` | chuỗi | bất biến | Ingestion (GĐ2) | 5.2; S4 ở Mục 6 — ghi lại nhưng **cấm mọi bước rẽ nhánh theo nó** |
| `content_fingerprint` | chuỗi | bất biến | Ingestion (GĐ2) | 5.7 — **ba người dùng**: phát hiện trùng lặp, nhận diện bản mới, và hai cơ chế bù cho bản sao xuyên Space. **Phải đánh chỉ mục** để tra ngược từ vân tay ra danh sách tài liệu |
| `extracted_text` | văn bản dài | bất biến | Ingestion (GĐ2) | 5.1 sản phẩm 1 — **nguồn chân lý duy nhất của chữ nghĩa** |
| `removed_as_wrong` | đúng/sai | đổi được | Manager | **NT4 — một trong hai bộ lọc cứng** |
| `removed_reason` | chuỗi | đổi được | Manager | 6.3 |
| `removed_by` + `removed_at` | định danh người + thời điểm | đổi được | Manager | dấu vết theo QT1 |
| `superseded` | đúng/sai | đổi được | Manager | 6.3 — tín hiệu **mềm** |
| `superseded_by` + `superseded_at` | định danh người + thời điểm | đổi được | Manager | dấu vết theo QT1 |
| `category_labels` | danh sách nhãn | đổi được | Ingestion gợi ý (GĐ5) | 5.2 GĐ5, NT4 — tín hiệu mềm |
| `labels_confirmed_by` + `labels_confirmed_at` | định danh người + thời điểm | đổi được | người đưa tài liệu vào | 5.2 GĐ5 — máy gợi ý, người xác nhận |
| `subject_entities` | danh sách chuỗi | đổi được | Ingestion gợi ý (GĐ5) | 5.3, 6.2 K3 — tín hiệu mềm nuôi GĐ7 |
| `version_chain_id` | định danh | bất biến | Ingestion | 5.7 |
| `version_ordinal` | số | bất biến | Ingestion | 5.7 |
| `version_declared_by` | người upload khai lúc nạp / người upload xác nhận đề nghị máy / **Manager xác nhận đề nghị máy** | bất biến sau khi chốt | 5.7 | 5.7 — hai đường tuyên bố, và cả hai người đều xác nhận được |
| `relations_scan_state` | đang mở rộng / đã dừng | đổi được | Ingestion (GĐ7) | 5.1 — "cửa sổ chưa đối chiếu xong" |

> **⚠️ `removed_as_wrong` và `superseded` phải là HAI TRƯỜNG RIÊNG, không được gộp thành một trường trạng thái.** Mục 6.3 nói rõ: "gỡ vì sai" thì không dùng cho bất kỳ câu hỏi nào kể cả câu hỏi về quá khứ; "hết hiệu lực" thì vẫn dùng cho câu hỏi hỏi về thời điểm nó còn hiệu lực. Gộp làm một thì Manager đánh dấu một quyết định bổ nhiệm cũ là hết hiệu lực sẽ vô tình làm câu hỏi *"tháng 1/2024 ai là giám đốc"* không trả lời được nữa. Đây là chỗ dễ bị một lập trình viên gộp thành `status` cho gọn — module schema phải chặn bằng cấu trúc.

> **⭐ `extracted_text` là nguồn chân lý DUY NHẤT của chữ nghĩa — CHỐT 14/9.**
>
> Toàn văn đọc ra được ở GĐ2, kèm cấu trúc, lưu **một bản duy nhất ở hồ sơ tài liệu**. Mẩu không giữ bản sao chữ của mình; nó giữ **vị trí đầu và cuối** trong văn bản này (Mục 2.2). Muốn đọc một mẩu hay một đơn vị ĐỌC thì lấy đoạn theo vị trí.
>
> Đổi lại việc mỗi lần trả lời phải lấy văn bản rồi cắt: **không có hai bản chữ nào có thể lệch nhau.** Nếu cắt lại theo cách khác (5.5 — "biểu diễn lại, đổi cách cắt") thì chỉ vị trí đổi, chữ không đụng tới.
>
> Trường này còn là **điều kiện để hoãn GĐ4 mà vẫn rẻ khi đảo ngược**: quét lại chỗ nhạy cảm ở phiên bản sau chỉ cần văn bản này, không cần đọc lại file gốc và không phải tạo lại vector (06 Mục 5.2 GĐ4, Mục 5.5).
>
> *Ghi chú lập trình*: với tài liệu dài, kho lưu phải hỗ trợ **đọc theo đoạn** thay vì lấy toàn văn về rồi mới cắt.

> **Hai loại ngày, và mỗi ngày mang NGUỒN của nó.** Ngày ký và ngày có hiệu lực là hai thứ khác nhau, độ khó trích rất khác nhau, và bản trước của thiết kế đã gộp làm một — đó là lỗ hổng tìm ra ở vòng pre-mortem 14/9. Chi tiết và lý do ở 06 Mục 6.4.
>
> **Quy tắc bắt buộc cho bên đọc**: chỉ được coi một ngày là đáng tin khi nguồn của nó là *máy trích* hoặc *người xác nhận*. Nguồn *mặc định ngày nạp* nghĩa là **chưa ai biết ngày thật** — nó chỉ là cận trên (tài liệu chắc chắn ban hành trước ngày đó), và câu trả lời phải nói rõ là không biết ngày hiệu lực thay vì đọc ra một con số trông hợp lý.

> **⭐ Bất biến của kho dùng chung — CHỐT 14/9 (S1): mọi thứ trong kho dùng chung đều ĐÃ DÙNG ĐƯỢC; thứ chưa dùng được thì chưa vào.**
>
> Vì vậy **không có trường `publication_state`** trong hợp đồng này. Ở Space riêng (tiền kiểm), tài liệu chờ Manager duyệt **chưa được ghi vào ba kho dùng chung** — Ingestion giữ nó trong vùng làm việc riêng, chỉ ghi ra sau khi được duyệt (tài liệu 06 Mục 5.2). Ở Space kế thừa và thông thường (hậu kiểm), tài liệu vào kho ngay vì nó dùng được ngay; Manager muốn rút lại thì dùng `removed_as_wrong` hoặc `superseded`.
>
> **Hệ quả quan trọng: NT4 giữ nguyên hai bộ lọc cứng.** Không cần bộ lọc thứ ba cho "chờ duyệt", vì không có gì để lọc. Đây là lý do chọn đường này: tiền kiểm được chặn **bằng cấu trúc** chứ không bằng một bộ lọc phải chạy đúng — cùng cách mà 06 Mục 8.4 bắt ràng buộc bất khả xâm phạm phải là *bước* chứ không phải *câu*, và 9.3 bịt cửa sau cá nhân hoá bằng cách cắt đường đọc.

> **Trong mỗi cặp trạng thái, ô đúng/sai là ô có thẩm quyền.** `removed_as_wrong` và `superseded` là nơi duy nhất quyết định tài liệu có bị gỡ hay đã hết hiệu lực hay không. Các ô `_by` và `_at` đi kèm là **dấu vết**, không phải nguồn phán quyết — không được suy trạng thái từ việc `_at` có giá trị hay không, vì một bản ghi cũ có thể thiếu dấu vết mà vẫn đúng trạng thái.

> **Quy tắc chung cho cả module: không trường nào được mô tả bằng một cụm gộp.** "Có/không + lý do + ai + khi nào" không phải một kiểu dữ liệu — nó là bốn trường viết tắt lại, và viết tắt ở đặc tả nghĩa là mỗi người lập trình tự chọn một hình dạng khác nhau. Mọi thành phần phải có tên riêng.

> **Không có trường `is_latest_version`.** Cờ đó cũ đi ngay khi có bản mới nạp vào (NT3). "Bản nào mới nhất" được suy ra từ `version_chain_id` + `version_ordinal` lúc cần.

> **⭐ `subject_entities` — TRƯỜNG MỚI, CHỐT 22/9/2026 (PO quyết, sau 2 vòng nghiên cứu Gemini có kiểm chứng trên corpus thật 21 văn bản).**
>
> Danh sách chuỗi — đối tượng được nói tới của tài liệu: chức danh/vị trí (KHÔNG phải tên người) cho văn bản áp dụng cá biệt, lĩnh vực/chuyên đề quản lý cho văn bản quy phạm chung (Luật/Nghị định/Thông tư). Dùng làm một trong ba tín hiệu của cơ chế K3 (5.3): *cùng đối tượng + cùng loại văn bản + ngày ban hành sau* → gợi ý quan hệ sửa đổi/thay thế. Ví dụ neo ở 6.2: "bổ nhiệm ông X làm giám đốc" và "bổ nhiệm bà Y làm giám đốc" chỉ nối được nếu đối tượng rút ra là CHỨC DANH ("Giám đốc"), không phải TÊN NGƯỜI — lấy tên người thì hai quyết định không có gì chung, máy không đề nghị được quan hệ.
>
> **Chỉ đặt ở `document`, KHÔNG đặt ở `chunk`** — khác `category_labels`. `category_labels` cần bản sao cạnh mẩu vì nó dùng để **xếp hạng lúc truy vấn**, mỗi lượt hỏi đều chạy (ngoại lệ QT2 đã quyết ở 6.4). `subject_entities` chỉ được dùng lúc **Ingestion so sánh tài liệu với tài liệu** ở GĐ7 (phát hiện quan hệ, 5.3) — một thao tác chạy khi có tài liệu mới, không phải mỗi truy vấn — nên không có lý do xin thêm một ngoại lệ QT2 thứ hai.
>
> **Tín hiệu mềm, không phải bộ lọc** — cùng vị trí với `category_labels` trong NT4/QT3: dùng để GỢI Ý quan hệ (qua Manager duyệt ở `relation.approval_state`, 5.3/2.3), không bao giờ dùng để loại trừ tài liệu khỏi kết quả tìm.
>
> **Không thêm cặp `subject_entities_confirmed_by`/`_at`** — khác `category_labels` (có `labels_confirmed_by`/`_at`). Lý do: `category_labels` là thứ người dùng cuối nhìn thấy và cần xác nhận trực tiếp; `subject_entities` chỉ là tín hiệu nội bộ nuôi đề nghị ở `relation`, và đề nghị đó đã tự có vòng duyệt riêng (`relation.approval_state`) — xác nhận thêm một lớp ở đây là dư, đi ngược "không trường nào được mô tả bằng một cụm gộp" nhưng theo chiều khác: thêm cơ chế xác nhận cho một thứ không ai trực tiếp nhìn vào.
>
> **Cách trích (theo vị trí neo: trích yếu "V/v", tiêu đề, Điều 1 dự phòng) — ĐÃ CÀI ĐẶT 22/9/2026** (`packages/ingestion/labeling.py`, hàm `extract_subject_entities()`, task `T2.4-add-subject-entities` — đúng nhà GĐ5 như dòng 93 ghi "Ingestion gợi ý (GĐ5)", không phải GĐ7). Cách so khớp (chuỗi hay vector embedding cho các cách gọi tương đương như "Giám đốc"/"Viện trưởng") **vẫn còn để mở**, là chi tiết cài đặt của GĐ7 khi K3 dùng trường này — chưa cố định ở đây, chờ work-order suy luận quan hệ ngầm định (T2.6 bước sau).

### 2.2 Đơn vị cắt và vector — `chunk`

Nơi cư trú: kho vector. Đây là đơn vị để **TÌM**, không phải đơn vị để đọc (Mục 6.1).

Áp QT2: payload chỉ được chứa những trường dưới đây.

| Tên trường | Kiểu | Đổi được? | Ai ghi | Truy về |
|---|---|---|---|---|
| `chunk_id` | định danh | bất biến | Ingestion | 6.1 |
| `document_id` | định danh | bất biến | Ingestion | 6.4 — con trỏ về tài liệu |
| `space_id` | định danh | bất biến ở v1 | Ingestion | 6.4 — cắt không gian tìm |
| `tenant_id` | định danh | bất biến | Ingestion | 6.4 |
| `structure_path` | **danh sách các đoạn, theo thứ tự từ ngoài vào trong** — ví dụ [Chương II, Điều 7, Khoản 3]; với tài liệu không có điều khoản thì là chuỗi tiêu đề lồng nhau. **Không phải một chuỗi nối lại**: quy tắc "cha là đúng một cấp lên" ở dưới cần đọc được từng cấp mà không phải tách chuỗi | bất biến | Ingestion (GĐ3) | 6.1 — dẫn nguồn theo vị trí |
| `parent_chunk_id` | định danh, **có thể trống** | bất biến | Ingestion (GĐ3) | 6.1 — con trỏ tới khối cấu trúc cha, chính là đơn vị ĐỌC (S2, chốt 14/9) |
| `span_start` | số nguyên | bất biến | Ingestion (GĐ3) | 6.4 — vị trí trong tài liệu, được phép nằm cạnh mẩu |
| `span_end` | số nguyên | bất biến | Ingestion (GĐ3) | 6.4 |
| `category_labels` | danh sách nhãn | **đổi được — ngoại lệ đã quyết** | Ingestion | 6.4 — bản sao để xếp hạng nhanh một nhịp |
| `embedding` | vector | bất biến với một cấu hình mô hình | Ingestion (GĐ6) | 5.2 GĐ6 |

> **⚠️ `span_start` và `span_end` đếm theo KÝ TỰ UNICODE, không phải byte.**
>
> Đây đúng loại chi tiết mà module dùng chung sinh ra để chặn. Tiếng Việt có dấu, một ký tự chiếm nhiều byte — một bên đếm ký tự còn bên kia đếm byte thì đoạn cắt ra lệch đi, **không có lỗi nào báo**, chỉ là câu trả lời dẫn nguồn sai chỗ và trích nhầm đoạn. Cùng loại hỏng im lặng với việc lệch thước đo vector ở Mục 3.

> **Mẩu không giữ bản sao chữ của mình.** Chữ nằm ở `extracted_text` của tài liệu (Mục 2.1); mẩu chỉ giữ vị trí. Đơn vị ĐỌC lấy được bằng cách theo `parent_chunk_id` rồi cắt theo vị trí của mẩu cha. Hai vị trí này được phép nằm cạnh mẩu vì 06 Mục 6.4 liệt kê tường minh *"con trỏ về tài liệu và vị trí trong tài liệu"* vào nhóm bất biến đặt cạnh mẩu.

> **`category_labels` là ngoại lệ duy nhất của QT2**, đã được quyết ở 6.4: chấp nhận rằng đổi cách phân loại thì phải gán lại toàn bộ mẩu của tài liệu bị ảnh hưởng. Sau khi NT4 hạ nhãn xuống thành tín hiệu mềm, bản sao này dùng để **xếp hạng**, không dùng để lọc.

> **⭐ Đơn vị ĐỌC — CHỐT 14/9 (S2): khối cấu trúc CHA MỘT CẤP của mẩu tìm được.**
>
> Tìm bằng mẩu nhỏ, đọc trọn khối cha. Với tài liệu có điều khoản: tìm bằng Khoản, đọc trọn Điều. Với tài liệu không có điều khoản (quy trình, biên bản, báo cáo): tìm bằng đoạn, đọc trọn mục dưới một tiêu đề.
>
> **Ba quy tắc con, cũng đã chốt** — thiếu chúng thì đây chỉ là khẩu hiệu:
>
> 1. **Cha là đúng một cấp lên** trong `structure_path`, không phải cấp bất kỳ.
> 2. **Mẩu đã là đơn vị cấu trúc cao nhất của tài liệu thì đơn vị đọc là chính nó** — khi đó `parent_chunk_id` để trống. Ví dụ một Điều ngắn không bị cắt nhỏ thì không có cha để lên.
> 3. **Hai mẩu cùng một cha thì cha chỉ được lấy MỘT lần.** Nếu không, một Điều trúng ba Khoản sẽ chiếm ba suất trong trần số lượng tài liệu (06 Mục 6.5).
>
> Hai cách còn lại bị loại có lý do: *cửa sổ câu lân cận* cắt ngang ranh giới điều/khoản nên làm đứt mạch quy phạm — đúng cái mà GĐ3 cố tránh khi bỏ cắt theo độ dài; *gộp theo ngưỡng thống kê* để số liệu quyết định ranh giới thay vì cấu trúc văn bản, cùng vấn đề. Lấy trọn tài liệu thì tràn ngữ cảnh.
>
> **⚠️ Cái giá đã chấp nhận.** Cách này làm kích thước đơn vị đọc biến thiên mạnh — một Điều có thể hai dòng, có thể ba trang. Nó làm nặng thêm đúng rủi ro tồn dư mà 06 Mục 6.5 đã ghi nhận: không có van khối lượng, năm tài liệu mà phần liên quan đều dài thì vẫn tràn. Ràng buộc ở 6.5 giữ nguyên và càng quan trọng hơn: **tràn thì báo lỗi và ghi nhật ký, tuyệt đối không cắt ngầm ở tầng dưới.**

### 2.3 Liên kết quan hệ — `relation`

Nơi cư trú: kho đồ thị. **Retrieval đọc kho này tại thời điểm truy vấn** (quy tắc mới ở 6.4), nên trạng thái duyệt có hiệu lực tức thì mà không phải nạp lại gì.

| Tên trường | Kiểu | Đổi được? | Ai ghi | Truy về |
|---|---|---|---|---|
| `relation_id` | định danh | bất biến | Ingestion / Manager | 5.3 |
| `from_document_id` | định danh | bất biến | Ingestion / Manager | 6.2 — **bên TÁC ĐỘNG**, xem quy ước bên dưới |
| `to_document_id` | định danh | bất biến | Ingestion / Manager | 6.2 — **bên BỊ TÁC ĐỘNG** |
| `relation_type` | sửa đổi-thay thế / phụ lục / dẫn chiếu / cùng chủ đề | đổi được khi Manager sửa | Ingestion đề xuất, Manager duyệt | **5.3 — quan hệ phải có phân loại**; 6.2 xử lý bốn loại khác nhau hoàn toàn |
| `confidence` | điểm liên tục, **để TRỐNG khi người gắn tay** | bất biến sau khi tính | Ingestion | 5.3 — một ngưỡng chung, đặt rộng |
| `approval_state` | chưa duyệt / đã duyệt / đã từ chối. **Liên kết người gắn tay khởi tạo thẳng ở "đã duyệt"** | **đổi được** | Manager | 5.3 — hai vai của một liên kết |
| `origin` | máy suy luận / máy đọc dẫn chiếu tường minh / Manager tự gắn | bất biến | Ingestion / Manager | 5.3 |
| `approved_by` + `approved_at` | định danh người + thời điểm | đổi được | Manager | 5.4 — vòng lặp chăm sóc tri thức |

> **⭐ Quy ước chiều — đọc thành một câu: `from` TÁC ĐỘNG LÊN `to`.**
>
> | Loại quan hệ | `from` | `to` |
> |---|---|---|
> | Sửa đổi / thay thế | văn bản ra sau, văn bản sửa | văn bản gốc bị sửa |
> | Phụ lục / kèm theo | phụ lục | văn bản chính |
> | Dẫn chiếu / căn cứ | văn bản viện dẫn | văn bản được viện dẫn |
> | Cùng chủ đề | *(không có chiều — quy ước: sắp theo `document_id` để mỗi cặp chỉ có một bản ghi)* | |
>
> Ví dụ: Quyết định 15 sửa Quyết định 10 → `from` = QĐ15, `to` = QĐ10.
>
> Nhờ quy ước này, hai chiều đi của Mục 6.2 có định nghĩa máy móc: **"ngược lên để có bối cảnh gốc"** = đi theo `to`; **"xuôi xuống để biết còn hiệu lực không"** = đi ngược lại theo `from`. Không có quy ước, hai service vẫn biên dịch được nhưng một bên sẽ đi ngược chiều bên kia và không có lỗi nào báo — nguy hiểm hơn lệch tên trường.

> **Liên kết do người gắn tay.** Mục 5.3 cho Manager tự gắn liên kết. Khi đó: `confidence` **để trống**, không phải 0 — 0 nghĩa là "máy đã chấm và chấm rất thấp", trống nghĩa là "không máy nào chấm". `approval_state` khởi tạo thẳng ở *đã duyệt*, `approved_by` chính là người gắn. Kèm theo một quy tắc bắt buộc: **ngưỡng kéo ở 5.3 chỉ áp cho liên kết có `origin` là máy** — liên kết người gắn luôn được kéo, vì ngưỡng sinh ra để lọc phán đoán của máy, không phải để xét lại quyết định của người.

> **`origin` gánh luôn dấu "chắc chắn" — CHỐT 14/9 (DX1). Không có trường `is_certain` riêng.**
>
> Mục 5.3 của tài liệu 06 nói dẫn chiếu tường minh được đánh dấu là chắc chắn, và dấu đó dùng để **đổi câu chữ** trong câu trả lời (*"có một văn bản khác có thể liên quan"* so với *"văn bản này đã được sửa đổi bởi..."*) và để duyệt nhanh — **không dùng để đổi ngưỡng kéo**.
>
> **Phép suy ra, viết rõ để không ai phải đoán:**
>
> > chắc chắn ⇔ `origin` ∈ { *máy đọc dẫn chiếu tường minh*, *Manager tự gắn* }
>
> Cả hai đều chắc chắn: máy chỉ đọc lại câu ghi sẵn trong văn bản chứ không suy diễn, còn người tự tay gắn thì càng chắc chắn hơn. Chỉ *máy suy luận* là không chắc chắn.
>
> Lý do không thêm ô riêng: hai ô phải khớp nhau thì sẽ có ngày lệch nhau — ai đó đặt `origin` là Manager rồi quên bật ô chắc chắn. Một ô không tự mâu thuẫn với chính nó được.
>
> **⚠️ Chỗ mong manh, phải nhớ:** mỗi lần thêm một giá trị `origin` mới thì **bắt buộc xét lại tập hai giá trị trên**. Đây là cái giá của việc gộp, đã chấp nhận có ý thức.

> **`approval_state` tuyệt đối không được chép xuống payload của `chunk`.** Đó chính là quy tắc mới ở 6.4: liên kết duyệt hôm nay có thể bị gỡ tháng sau, chép xuống thì mỗi lần duyệt phải nạp lại mẩu của hai tài liệu.

### 2.4 Đề nghị chờ xác nhận — `pending_version_claim`

Sinh ra từ 5.7, đường thứ hai: người upload không khai thì máy phân tích rồi đề nghị.

| Tên trường | Kiểu | Ai ghi | Truy về |
|---|---|---|---|
| `claim_id` | định danh | Ingestion | 5.7 |
| `new_document_id` | định danh | Ingestion | 5.7 |
| `candidate_previous_document_id` | định danh | Ingestion | 5.7 |
| `similarity` | điểm | Ingestion | 5.7 — dựa trên vân tay nội dung |
| `notified_uploader` + `notified_manager` | có/không | Ingestion | 5.7 — nhắc cả hai, ai xác nhận trước cũng được |
| `state` | chờ / đã xác nhận / đã bác | người upload hoặc Manager | 5.7 |

> **Vì sao đây là thực thể riêng, không phải một `relation` loại thứ năm.** Chuỗi phiên bản và quan hệ là hai trục khác nhau (5.7): *văn bản sửa đổi* là hai tài liệu riêng cùng là bản ghi thật, còn *bản mới* là cùng một danh tính. Quan trọng hơn, hai loại đề nghị hành xử ngược nhau: một liên kết **chưa duyệt vẫn được kéo** vào ngữ cảnh (5.3), còn một đề nghị bản mới **chưa xác nhận thì hai tài liệu vẫn hoàn toàn rời** (5.7). Trộn vào một bảng là mời gọi nhầm lẫn đúng chỗ nguy hiểm nhất.

---

## 3. Cấu hình

### 3.1 Cấu hình mô hình biểu diễn — nằm trong cùng module

[stated] Viet 12/9: **gộp vào chính module schema dùng chung**, không tách hạng mục riêng. Lý do: đây cùng một loại hỏng — hai bên lệch nhau mà không ai báo — nên chữa cùng một chỗ. Một thứ phải đồng bộ, không phải hai.

| Mục cấu hình | Vì sao phải dùng chung |
|---|---|
| `embedding_model` | Lệch mô hình mà **cùng số chiều** thì vector do Ingestion tạo và vector Retrieval tạo cho câu hỏi nằm ở hai không gian ngữ nghĩa khác nhau. Phép so vẫn chạy, kết quả sai lệch âm thầm, không lỗi nào báo. Đây là rủi ro nặng nhất trong nhóm |
| `embedding_dim` | Lệch số chiều thì kho vector báo lỗi ngay — phát hiện nhanh, ít nguy hiểm hơn |
| `distance_metric` | **CHỐT: cosine, và vector phải chuẩn hoá L2.** Phải khớp giữa lúc ghi và lúc tìm — xem S5 |

**Ba ràng buộc bắt buộc khi lập trình — CHỐT 14/9 (DX2, DX3):**

**1. Một nguồn duy nhất.** Hai service đọc cùng một nơi, không mỗi bên một file cấu hình riêng như hệ thống hiện tại.

**2. Kiểm khớp lúc khởi động với CON DẤU TRÊN KHO, không khớp thì TỪ CHỐI CHẠY.**

Lúc tạo kho vector, đóng dấu lên chính cái kho đó: tên mô hình, số chiều, thước đo. Mỗi service khi khởi động so cấu hình của mình với **con dấu của kho nó đang đọc** — không phải so với service kia.

> Vì sao so với kho chứ không so với nhau: cách này bắt được cả trường hợp hai service khớp nhau nhưng **cả hai cùng lệch với kho** — tức là kho được tạo bằng mô hình cũ mà cả hai service đã đổi sang mô hình mới. So hai service với nhau thì trường hợp đó lọt.

Không khớp thì không khởi động, không có chế độ cảnh báo rồi chạy tiếp. Một service chạy với cấu hình lệch chính là loại trừ im lặng ở tầng thấp nhất — cùng loại với việc cắt bớt ngầm khi tràn ngữ cảnh mà 06 Mục 6.5 đã cấm.

> 📌 **`model_version` (T1.3, `packages/schema/embedding_registry.py`)**: bảng catalog `embedding_models` trên PostgreSQL — nơi cư trú thật của `embedding_model` cho ràng buộc 2 ở trên — có thêm một cột `model_version` để ghi lịch sử/audit (biết chính xác bản nào từng active cho collection nào). Đây **KHÔNG phải trường thứ tư của hợp đồng mô hình**: hợp đồng vẫn đúng ba trường `embedding_model` / `embedding_dim` / `distance_metric` như bảng đầu Mục 3.1, và phép so khớp con dấu chỉ dựa trên ba trường đó. `model_version` không nằm trong `ContractConfig` hay `StoreStamp`.

**3. Module schema mang HAI số phiên bản của chính nó.**

| Số | Tăng khi | Hai bên lệch thì |
|---|---|---|
| **Số phá vỡ tương thích** | đổi tên trường, xoá trường, đổi ý nghĩa của trường | **từ chối chạy** |
| **Số bổ sung tương thích** | thêm trường mới mà bên cũ bỏ qua được | **ghi nhật ký, vẫn chạy** |

Hai số chứ không một, vì nếu chỉ có một số thì mỗi lần thêm một trường là một lần phải dừng cả hai service — và người ta sẽ nhanh chóng ngừng tăng số, tức là mất luôn cơ chế.

### Đổi mô hình biểu diễn — quy trình ở v1

Đổi mô hình bắt buộc kéo theo **biểu diễn lại toàn kho** (06 Mục 5.5), và trong lúc nạp lại thì hai bên **hợp lệ mà vẫn lệch nhau** — ràng buộc 2 ở trên sẽ chặn đúng lúc ta chủ động muốn nó chạy.

**Cách xử lý ở v1 — CHỐT: dừng dịch vụ.** Tắt cả hai service, chạy lại toàn kho bằng mô hình mới, bật lại cùng lúc. Chấp nhận hệ thống không dùng được trong thời gian đó.

Lý do chọn cách đơn giản: 06 Mục 5.5 đã ghi việc này là *hiếm, đắt, nhưng có kế hoạch trước* — hiếm và có kế hoạch thì làm ngoài giờ được, không đáng xây thêm cơ chế.

> **Cách viết ràng buộc 2 đã mở sẵn đường cho phương án không gián đoạn về sau**, mà không tốn gì thêm bây giờ: vì con dấu nằm trên kho chứ không phải giữa hai service, nên hai kho có hai con dấu khác nhau vẫn cùng tồn tại được — kho cũ phục vụ truy vấn trong lúc kho mới đang dựng, xong thì đổi công tắc. Không phải thiết kế lại gì.

> **Thước đo khoảng cách là THUỘC TÍNH CỦA MÔ HÌNH, không phải lựa chọn tự do** *(nghiên cứu 14/9)*. Các dòng mô hình đang cân nhắc — multilingual-e5, BGE-M3, gte-Qwen2, và mô hình tiếng Việt vietnamese-bi-encoder — đều huấn luyện bằng hàm mất mát tương phản trên cosine và đều yêu cầu chuẩn hoá L2. Dùng dot product không chuẩn hoá hoặc Euclid thì **không có lỗi nào báo**, chỉ tụt chất lượng tìm kiếm một cách âm thầm.
>
> Điều này làm ràng buộc "không khớp thì từ chối chạy" ở trên **mạnh hơn hẳn**: nó không còn là biện pháp phòng xa mà là điều kiện đúng đắn. Và nó thêm một hệ quả: đổi mô hình thì **phải đổi cả thước đo theo mô hình**, không được giữ nguyên thước đo cũ.

Cấu hình này phải đọc được từ bên ngoài mã nguồn (**R5** — đổi mô hình bằng cấu hình, không sửa mã), và đổi nó là một sự kiện có kế hoạch trước vì kéo theo **biểu diễn lại toàn kho** (5.5).

---

### 3.2 Chín giá trị tham số — CHỐT 14/9/2026

Chín con số dưới đây trước nay chỉ có **cơ chế**, không có **giá trị**, vì đều ghi là "cần đo trên dữ liệu thật". Nhưng Mục 9.6 của tài liệu 06 chốt v1 không phát sự kiện đo lường nào — nên sẽ không có dữ liệu thật để đo, và vẫn phải có người điền số.

Vì vậy mỗi giá trị đi kèm **một dấu hiệu con người nhìn thấy được**. Đó không phải phần trang trí: khi không có dòng số liệu nào, dấu hiệu quan sát bằng mắt là cách duy nhất biết mình đặt sai.

| Tham số | Giá trị | Của service | Dấu hiệu đặt sai |
|---|---|---|---|
| `inheritance_decay` — hệ số giảm thừa hưởng điểm mỗi mắt xích | **0.5**, áp trên **điểm đã chuẩn hoá** trên tập ứng viên | Retrieval | Người dùng gặp câu trả lời dựa trên văn bản đã bị sửa đổi mà bản sửa không được nhắc → giảm nhẹ hệ số |
| `document_cap` — trần số tài liệu đưa vào ngữ cảnh | **6** | Retrieval | Câu trả lời thường xuyên thiếu nguồn mà người hỏi biết là có → tăng lên 8 |
| `cap_warning_multiple` — bội số kích hoạt cảnh báo chạm trần | **3** (báo khi có trên 18 ứng viên) | Retrieval | Cảnh báo hiện ở quá nửa số câu trả lời → tăng. Không bao giờ hiện → giảm |
| `relation_pull_threshold` — ngưỡng tin cậy để kéo liên kết chưa duyệt | **0.3** trên thang 0–1 | Retrieval | Ngữ cảnh thường xuyên có văn bản họ hàng chẳng liên quan → nâng lên 0.5 |
| `saturation_epsilon` — ngưỡng tỷ lệ phát hiện quan hệ mới | **1%** | Ingestion | Quét chạy mãi không báo xong → nới. Manager liên tục phải gắn tay liên kết máy bỏ sót → siết |
| `saturation_rounds` — số vòng liên tiếp dưới ngưỡng | **3** | Ingestion | Cùng dấu hiệu với `saturation_epsilon` |
| `scan_pair_budget` — trần số cặp đối chiếu mỗi tài liệu mới | **500** | Ingestion | Thường xuyên chạm trần trước khi bão hoà → kho đã lớn hơn giả định thiết kế |
| `scan_time_budget` — trần thời gian mỗi tài liệu | **10 phút** | Ingestion | Tài liệu mới lâu ngày vẫn mang nhãn "chưa đối chiếu xong" → nới |
| `chunk_length_cap` — trần độ dài một mẩu (Điểm mở #4, 06 Mục 10) | **5000 ký tự Unicode** | Ingestion | Mẩu vượt trần bị chia tại ranh giới câu quá thường xuyên, làm mẩu quá ngắn và loãng so khớp → nới. Một khối cấu trúc dài (vài trang) vẫn lọt thành một mẩu duy nhất, so khớp không trúng → siết |

> `chunk_length_cap` chốt **21/9/2026** — khác ngày với tám tham số còn lại trong bảng (14/9/2026): đây là giá trị đóng nửa **trần** của Điểm mở #4 (06 Mục 10 — "Trần và sàn độ dài đơn vị cắt"); nửa **sàn** vẫn còn mở.

> **Giả định nằm dưới cả bảng: kho cỡ vài nghìn tài liệu** — chính con số mà 06 Mục 6.5 dùng khi lập luận về ngưỡng cảnh báo. Nếu kho thật lớn hơn một bậc thì ít nhất `cap_warning_multiple`, `scan_pair_budget` và `scan_time_budget` phải tính lại.

> **Vì sao `inheritance_decay` phải áp trên điểm ĐÃ CHUẨN HOÁ.** Điểm giống thô thường dồn cục trong một dải hẹp; nhân một hệ số vào đó thì con của tài liệu hạng nhất tụt xuống dưới cả chục tài liệu không liên quan, và cơ chế thừa hưởng mất tác dụng. Chuẩn hoá về khoảng đầy trên tập ứng viên rồi mới nhân thì hệ số mới có ý nghĩa như thiết kế mô tả.

**Chín tham số này chia sạch theo service** — bốn cái của Retrieval, năm cái của Ingestion, không cái nào cần hai bên cùng biết. Khác hẳn cấu hình mô hình ở 3.1, vốn là **hợp đồng** mà lệch nhau là hỏng.

### 3.3 Quy tắc cấu hình — CHỐT 14/9/2026

[stated] Viet: **không được có con số cứng trong mã.** Đây không phải nguyên tắc mới mà là **R5** ("đổi mô hình bằng cấu hình, không phải sửa mã") mở rộng từ mô hình sang mọi tham số điều chỉnh.

**1. Ba nhóm cấu hình, ba nơi khác nhau, không chồng lấn:**

| Nhóm | Gồm | Ai đọc | Lệch thì sao |
|---|---|---|---|
| **Hợp đồng** | mô hình biểu diễn, số chiều, thước đo (3.1) | cả hai service | **hỏng ngầm** — nên phải kiểm với con dấu trên kho và từ chối chạy |
| **Ingestion** | `saturation_*`, `scan_*`, danh sách định dạng nhận | chỉ Ingestion | không ảnh hưởng bên kia |
| **Retrieval** | `inheritance_decay`, `document_cap`, `cap_warning_multiple`, `relation_pull_threshold` | chỉ Retrieval | không ảnh hưởng bên kia |

**2. Mỗi tham số có ĐÚNG MỘT nhà.** Không tham số nào xuất hiện ở hai nhóm. Nhóm nào chứa nó thì module khai báo rõ — đây là cùng một thuốc chữa cho cùng một bệnh đã sinh ra module dùng chung: hai nơi cùng giữ một giá trị thì sẽ có ngày lệch nhau.

**3. ⛔ Thiếu khoá cấu hình thì TỪ CHỐI CHẠY — không có giá trị mặc định trong mã.**

Một giá trị mặc định nằm trong mã chính là **cái nhà thứ hai** của tham số đó. Khi file cấu hình thiếu khoá, service vẫn chạy bằng con số ẩn trong mã, và không ai biết giá trị đang sống là bao nhiêu — đúng loại hỏng im lặng mà cả hai tài liệu này dựng lên để chặn. Cùng hình dạng với ràng buộc ở 3.1 và với số phiên bản phá vỡ tương thích ở DX3.

*Đánh đổi đã chấp nhận*: thêm một tham số mới nghĩa là phải cập nhật cấu hình trước khi service lên lại. Đúng bằng cái giá của DX3, và cùng lý do.

**4. Dấu hiệu đặt sai phải nằm NGAY CẠNH giá trị trong file cấu hình**, dưới dạng ghi chú. Người mở file ra để đổi một con số cần thấy ngay bằng chứng nào đáng làm họ đổi nó. Vì v1 không có dòng số liệu nào, đây là chỗ duy nhất tri thức đó sống được ở nơi người ta dùng tới.

**5. Tài liệu này ghi lý do; file cấu hình là nơi có thẩm quyền lúc chạy.** Hai chỗ có thể lệch nhau theo thời gian và đó là chuyện bình thường — giá trị đang sống luôn là giá trị trong file. Bảng 3.2 ghi **giá trị khởi đầu và vì sao chọn nó**, không phải trạng thái hiện hành.

## 4. Định danh dùng lại ngoài phạm vi dùng chung

Nhật ký điều tra do **Retrieval ghi**, Ingestion không đọc — nên nó không phải dữ liệu dùng chung. Nhưng nó **dùng lại định danh** do Ingestion định nghĩa, nên phải import từ cùng module:

- Bản ghi nhật ký chứa danh sách `chunk_id` đã đưa vào ngữ cảnh, và `document_id` bị loại kèm lý do (Mục 9.2).
- **Không chứa nguyên văn câu hỏi, không chứa nguyên văn câu trả lời** (9.2, chốt 12/9).

Điểm cắm dòng sự kiện đo lường (Mục 9.6) cũng dùng lại các định danh này, nhưng **v1 chưa phát sự kiện nào** nên chưa cần đặc tả trường.

### ⚠️ Những thứ nằm NGOÀI phạm vi tài liệu này (không phải dữ liệu hai service trao cho nhau)

Phần trên dễ đọc nhầm thành "đã xong". Không phải. Ba thực thể dưới đây đều đã được tài liệu 06 đặc tả ở mức khái niệm, nhưng **chưa ai chuyển thành bảng trường**, và chúng không thuộc tài liệu này vì không phải dữ liệu hai service trao cho nhau.

| Thực thể | Ai dùng | Đặc tả khái niệm ở | Bảng trường |
|---|---|---|---|
| **Nhật ký điều tra** | Retrieval ghi, Admin đọc | 06 Mục 9.2 — ai hỏi, lúc nào, phạm vi quyền tại thời điểm đó, tài liệu vào ngữ cảnh, tài liệu bị loại và lý do, agent nào được dùng | **chưa có** |
| ~~**Lịch sử hội thoại**~~ | **Không còn thuộc AI Services — chốt 23/9/2026: Backend C.Brain lưu.** Retrieval chỉ nhận K lượt gần nhất và trạng thái hội thoại qua lời gọi, không lưu | 06 Mục 9.1, 9.4 (v1.10); `10` Mục 6.1 | **không cần ở phía AI** |
| **Sổ đăng ký Space** (`space_registry`) *(thêm 24/9/2026)* | Ingestion ghi và đọc; Retrieval không đọc | `10` Mục 4.0 — chỉ `space_id` + trạng thái đang dùng / đang xoá / đã xoá; **không** cây, cờ kế thừa hay thành viên | có trong mã: `packages/schema/space_registry.py`, DDL ở `store_schema.py` (commit `8751270`) |
| **Nhật ký xoá** (`deletion_log`) *(thêm 24/9/2026)* | Ingestion ghi; Admin đọc qua `10` Mục 6.4 | 06 Mục 5.6 — ai, khi nào, tài liệu nào, `space_id`, lý do; không giữ nội dung | có trong mã: `packages/schema/deletion_log.py`, DDL ở `store_schema.py` |
| **Định nghĩa agent chuyên miền** | Retrieval | 06 Mục 8.2–8.5 — ai tạo, hai tầng hướng dẫn, ràng buộc bất khả xâm phạm là BƯỚC chứ không phải CÂU, bộ kiểm lúc tạo | **chưa có** |

Hai thứ còn lại — nhật ký điều tra và định nghĩa agent — là **việc nội bộ của Retrieval v2**, cần một tài liệu riêng. *(Trạng thái hội thoại — 06 Mục 9.4 — cũng không phải dữ liệu dùng chung Ingestion–Retrieval: hình dạng của nó nằm ở `10` Mục 6.1, và nó chỉ mang `document_id` import từ module dùng chung.)* Chúng chỉ chạm tài liệu này ở một điểm: đều dùng lại `document_id` và `chunk_id` do module dùng chung định nghĩa, nên phải import từ đó chứ không tự khai báo lại.

*(Agent thì khác hai cái trên: nó cần bảng trường cho định nghĩa agent, nhưng **không** sinh ra trường nào trong dữ liệu Ingestion–Retrieval dùng chung — xem Mục 5.)*

---

## 5. Những trường BỊ CẤM có mặt

Danh sách này quan trọng ngang danh sách trường được phép, vì mỗi dòng đều là một kiểu hỏng đã có thật hoặc đã được thiết kế chặn.

| Cấm | Vì sao |
|---|---|
| Mọi danh sách người, nhóm, hay dấu hiệu quyền đóng băng trong dữ liệu đã nạp | **NT3 + QT1.** Hệ thống hiện tại đóng băng danh sách quyền vào payload lúc nạp và không có cơ chế đồng bộ lại; người vừa được cấp quyền qua được bộ lọc tươi nhưng trượt bộ lọc đóng băng → im lặng không ra kết quả. Đúng thứ NT3 sinh ra để chặn |
| Loại Space (kế thừa/riêng), cấu trúc cây Space, danh sách thành viên | **NT3** — đổi vì con người thao tác, phải tính tươi mỗi lần hỏi |
| `is_latest_version` hoặc bất kỳ cờ "mới nhất" nào | Cũ đi ngay khi có bản mới; suy ra từ chuỗi phiên bản |
| `approval_state` của liên kết, đặt cạnh mẩu | **6.4** — buộc phải nạp lại mẩu mỗi lần Manager duyệt |
| `title`, `doc_number`, `effective_date`, trạng thái tài liệu, đặt cạnh mẩu | **6.4** — thứ dùng để ĐỌC và DẪN NGUỒN thì lấy sau từ hồ sơ |
| Một trường trạng thái gộp "gỡ vì sai" với "hết hiệu lực" | **6.3** — làm mất khả năng trả lời câu hỏi về quá khứ |
| Mức nhạy cảm tối đa của tài liệu | **7.1** — v1 không triển khai cơ chế che nào; và nó là phán đoán nên **NT4** cấm dùng để loại trừ |
| Nguyên văn câu hỏi hoặc câu trả lời trong nhật ký | **9.2** — tạo bản sao nội dung ở kho không xoá được, ngoài tầm với của xoá vĩnh viễn 5.6 |

> **Agent chuyên miền không sinh ra trường nào trong dữ liệu dùng chung.** Mục 8.1: việc tìm nguồn tham khảo hoàn toàn không phụ thuộc agent nào đang được dùng; NT1: agent thuộc phía "hiểu và trả lời", Space thuộc phía "được biết", hai phía không chạm nhau. Nếu sau này có ai đề xuất một trường gắn agent vào tài liệu hoặc vào mẩu, đó là dấu hiệu ranh giới hai service đã bị vi phạm.

---

## 6. Những điểm mở phát sinh khi rút schema — và cách chúng được đóng

Tám điểm dưới đây **không nằm trong 16 điểm mở của tài liệu 06** — chúng lộ ra chính vì việc rút schema buộc phải trả lời "trường này tên gì, giá trị nào". Đúng như dự đoán: rút schema là một phép kiểm thiết kế.

Ngày 14/9 chạy một gói nghiên cứu ngoài (sáu câu hỏi, xem Phụ lục A) để gỡ những điểm mà câu trả lời nằm ở **thực hành ngành** chứ không nằm ở sở thích của người quyết. Năm điểm đóng được nhờ đó.

### ✅ Bảy điểm đã đóng ở tài liệu này

**S1 — Tài liệu chờ Manager duyệt KHÔNG vào kho dùng chung** *(chốt 14/9)*.
Ở Space riêng, Ingestion chạy hết đọc file, cắt, quét chỗ nhạy cảm, gán nhãn — rồi **dừng trước bước tạo vector và bước dò quan hệ**, giữ kết quả trong vùng làm việc riêng. Manager duyệt xong mới chạy nốt và ghi vào ba kho dùng chung.
Rút ra bất biến: **mọi thứ trong kho dùng chung đều đã dùng được.** Hệ quả: `publication_state` không có trong hợp đồng này, và **NT4 giữ nguyên hai bộ lọc cứng** — không cần bộ lọc thứ ba vì không có gì để lọc. Chi tiết và lập luận: Mục 2.1.
*Cái giá đã chấp nhận*: có độ trễ giữa lúc Manager bấm duyệt và lúc tài liệu tìm được; và chưa mở đường cho tính năng "xem thử AI trả lời trước khi duyệt".

**S2 — Đơn vị ĐỌC là khối cấu trúc cha một cấp** *(chốt 14/9)*, kèm ba quy tắc con và cái giá về kích thước biến thiên. Chi tiết: Mục 2.2. `parent_chunk_id` và `structure_path` phân cấp đã hết trạng thái đề xuất.

**S4 — `source_format`: GHI, nhưng cấm rẽ nhánh theo nó.**
Vẫn ghi định dạng gốc làm thông tin vận hành và dẫn nguồn, nhưng **không một bước xử lý nào được rẽ nhánh theo giá trị này**. Điểm cắm ở GĐ2 nói mọi bước sau đó không được *biết* định dạng — cách hiểu đúng là chúng không được *hành xử khác nhau* theo định dạng, chứ không phải cấm ghi lại.

**S5 — Thước đo khoảng cách: COSINE, vector chuẩn hoá L2.**
Và quan trọng hơn con số: **đây là thuộc tính của mô hình, không phải lựa chọn tự do.** Mọi dòng mô hình đang cân nhắc đều huấn luyện bằng hàm mất mát tương phản trên cosine. Chọn sai thì không có lỗi nào báo, chỉ tụt chất lượng âm thầm. Chi tiết và hệ quả: Mục 3.

**S6 — Thứ tự xoá vĩnh viễn: kho vector → kho đồ thị → hồ sơ tài liệu → dọn nền.**

> ⚠️ **Đây là chỗ khuyến nghị của nghiên cứu bị ĐẢO NGƯỢC cho kiến trúc này.** Nghiên cứu đề xuất xoá mềm ở kho quan hệ trước, vì trong phần lớn hệ thống kho quan hệ là cổng vào truy vấn. Ở đây thì **không**: đường đọc là *tính phạm vi quyền → tìm trong kho vector → kéo họ hàng ở kho đồ thị → đọc hồ sơ để dựng đơn vị đọc và dẫn nguồn*. Cổng chặn nằm ở **kho vector**.
>
> Xoá theo thứ tự trên thì ngay từ lượt hỏi kế tiếp tài liệu không còn được tìm thấy, và không lúc nào có một mẩu trỏ tới hồ sơ đã biến mất. Làm ngược lại — xoá hồ sơ trước — thì mẩu vẫn tìm được nhưng bước dựng đơn vị đọc không đọc được gì: đúng con trỏ treo mà S6 sinh ra để tránh.

Hai điều giữ nguyên từ nghiên cứu: mỗi bước phải **làm lại được mà không hỏng thêm**, để hỏng giữa chừng thì chạy tiếp chứ không phải dọn tay; và **xoá ở kho vector thường chỉ là xoá logic, dữ liệu chỉ thật sự mất sau bước dọn nền**. Điều thứ hai đáng chú ý với Mục 5.6 của tài liệu 06: nghĩa vụ xoá dữ liệu cá nhân chỉ được coi là hoàn thành khi bước dọn nền **đã chạy xong**, không phải khi người dùng bấm xoá.

**S7 — Bộ lọc "gỡ vì sai": tính tươi lúc truy vấn, truyền vào như danh sách loại trừ.**
Nghiên cứu xác nhận khả thi: kho vector cho phép loại trừ theo danh sách định danh, chi phí tỷ lệ với **kích thước danh sách** chứ không phải kích thước kho. Danh sách "gỡ vì sai" bản chất là nhỏ — nó chỉ chứa tài liệu Manager đã chủ động đánh dấu là sai, không phải danh sách quyền. Nếu có ngày nó phình to bất thường thì đó là tín hiệu vận hành cần xem, không phải vấn đề kỹ thuật cần vá.

> **Một ghi chú vận hành mới, không phải điểm mở.** Bộ lọc quyền chạy trước có một đặc tính đáng biết: khi người hỏi chỉ đọc được một phần rất nhỏ của kho, tỷ lệ điểm thoả bộ lọc thấp và kho vector có thể tự chuyển từ duyệt đồ thị sang quét toàn bộ. Không sai kết quả, chỉ chậm. Cần đánh chỉ mục trên trường Space và theo dõi khi có người dùng quyền hẹp.

**S8 — Tiêu chí dừng quét quan hệ: hai điều kiện phải thoả ĐỒNG THỜI.**

| Điều kiện | Nội dung |
|---|---|
| **Bão hoà** | K vòng liên tiếp mà tỷ lệ phát hiện quan hệ mới dưới ngưỡng ε |
| **Trần chi phí** | tối đa N cặp đối chiếu, hoặc T thời gian |

Bão hoà một mình thì có thể không bao giờ đạt; trần chi phí một mình thì dừng khi hết tiền chứ không phải khi đã đủ. Chỉ khi cả hai cùng thoả, `relations_scan_state` mới được chuyển sang *đã dừng* — và chỉ khi đó câu trả lời mới được thôi nói "chưa đối chiếu xong".

**Cơ chế đã chốt; ε, K, N, T là tham số cần đo trên dữ liệu thật** — cùng nhóm với điểm mở #1 và #2 của tài liệu 06, và chịu cùng giới hạn đã ghi ở Mục 9.6: v1 không phát sự kiện đo lường nên bốn con số này phải đặt bằng phán đoán.

### ✅ Ba đề xuất đã duyệt — 14/9/2026

| | Nội dung | Viết ở |
|---|---|---|
| **DX1** | Không có trường `is_certain` riêng; chắc chắn suy ra từ `origin` ∈ { máy đọc dẫn chiếu tường minh, Manager tự gắn }. Mỗi lần thêm giá trị `origin` mới phải xét lại tập này | 2.3 |
| **DX2** | Kiểm cấu hình với **con dấu trên kho vector**, không khớp thì từ chối chạy. Đổi mô hình ở v1 = dừng dịch vụ, nạp lại toàn kho, bật lại | 3 |
| **DX3** | Module mang **hai** số phiên bản: phá vỡ tương thích thì từ chối chạy, bổ sung tương thích thì ghi nhật ký và vẫn chạy | 3 |

### Điểm thứ tám: S3 — đã chốt ở tài liệu 06 ngày 14/9

Điểm này không phải điểm mở của schema mà là **mâu thuẫn nội tại của tài liệu 06**: Mục 7.1 chốt v1 không triển khai cơ chế che nào, nhưng năm chỗ khác đều giả định bước quét chỗ nhạy cảm (GĐ4) có chạy — Mục 3, 5.1, 5.2 GĐ4, 5.5, 6.4. Hai vòng phản biện độc lập cùng kết luận đây là mâu thuẫn thật.

**Đã chốt: HOÃN GĐ4 ở v1**, và năm chỗ trên đã sửa cho khớp. Lập luận quyết định không phải là tiền quét, mà là: quy định "cái gì là nhạy cảm" gần như chắc chắn sẽ đổi trước khi phiên bản sau làm che PII, nên dữ liệu quét ở v1 nhiều khả năng phải quét lại toàn bộ dù sao.

**Ảnh hưởng tới tài liệu này: nhóm trường về vị trí chỗ nhạy cảm KHÔNG có mặt.** Và điều kiện để quyết định đó rẻ khi đảo ngược chính là `extracted_text` ở Mục 2.1 — quét lại ở phiên bản sau chỉ cần văn bản đó, không phải đọc lại file gốc, không phải tạo lại vector.

---

## 7. Bước tiếp theo

**Không còn điểm mở nào, và không còn quyết định thiết kế nào đang chặn.** Tám điểm đã đóng, ba đề xuất đã duyệt. S3 cũng đã chốt ở tài liệu 06 ngày 14/9 (hoãn bước quét chỗ nhạy cảm ở v1), nên nhóm trường về vị trí chỗ nhạy cảm **không có mặt ở đây**.

1. **Chuyển tài liệu này thành module mã nguồn thật.** Đây là việc chính còn lại.
2. **Ước lượng công sức lại từ đầu** cho cả Ingestion v2 và Retrieval v2, trên thiết kế thật (tài liệu 06 + tài liệu này). Con số 14.5–15.0 MD trước đây chỉ tính thiết kế cơ bản, không còn đúng.
3. Cập nhật các tài liệu ở Mục 11 của tài liệu 06.

### Ba yêu cầu kỹ thuật kèm theo, dễ bị bỏ sót khi lập trình

| | Yêu cầu | Vì sao |
|---|---|---|
| 1 | `content_fingerprint` **phải đánh chỉ mục** để tra ngược từ vân tay ra danh sách tài liệu | Ba người dùng: phát hiện trùng lặp, nhận diện bản mới, và hai cơ chế bù cho bản sao xuyên Space (06 Mục 5.7) |
| 2 | Kho lưu `extracted_text` **phải hỗ trợ đọc theo đoạn** | Không lấy toàn văn về rồi mới cắt — với tài liệu dài thì đó là lãng phí ở mọi lượt trả lời |
| 3 | Trường Space **phải đánh chỉ mục** | Khi người hỏi chỉ đọc được một phần rất nhỏ của kho, tỷ lệ điểm thoả bộ lọc thấp và kho vector có thể tự chuyển sang quét toàn bộ. Không sai kết quả, chỉ chậm |

## Phụ lục A — Gói nghiên cứu 14/9/2026

Sáu câu hỏi giao ra ngoài để gỡ những điểm mà câu trả lời nằm ở thực hành ngành chứ không ở sở thích của người quyết. Chạy hai lượt: lượt đầu ba câu hỏng vì công cụ tìm kiếm lỗi, chạy lại thì đủ cả sáu.

| Câu hỏi | Gỡ điểm nào | Kết quả |
|---|---|---|
| Xác định đơn vị ĐỌC từ mẩu tìm được | S2 | Parent-child; đòi thêm `parent_chunk_id` và `structure_path` phân cấp |
| Loại trừ tài liệu bằng danh sách truyền vào — có chịu được quy mô không | S7 | Chịu được; chi phí tỷ lệ với kích thước danh sách, không phải kích thước kho |
| Thứ tự xoá một thực thể trải trên ba kho | S6 | Có khuôn chuẩn, nhưng **phải đảo thứ tự** cho kiến trúc này |
| Thước đo khoảng cách cho vector | S5 | Cosine + chuẩn hoá L2; là thuộc tính mô hình, không phải lựa chọn |
| Trích ngày hiệu lực từ văn bản hành chính Việt Nam | kịch bản K2 | Khả thi; ngày ký có khuôn chuẩn, ngày hiệu lực cần định vị điều khoản thi hành |
| Tiêu chí dừng mở rộng đồ thị quan hệ | S8 | Bão hoà + trần chi phí, phải thoả đồng thời |

**Về câu hỏi ngày tháng** (chưa áp vào tài liệu này vì nó thuộc tài liệu 06): ngày ký trong văn bản hành chính Việt Nam có khuôn mẫu chuẩn hoá ở đầu văn bản, trích bằng khuôn mẫu là đủ. Ngày hiệu lực thì khó hơn — nằm ở điều khoản thi hành cuối văn bản, và phải tránh nhầm với ngày của văn bản bị thay thế được nhắc trong cùng câu. Đã có tập dữ liệu và nghiên cứu tiếng Việt cho việc này với độ chính xác cao. Kết luận: **trích tự động rồi để người xác nhận là khả thi**, đúng khuôn "máy gợi ý, người xác nhận" đã dùng cho nhãn phân loại.

**Cảnh báo về độ tin cậy**: gói nghiên cứu này tự chấm độ chắc chắn là *trung bình* cho bốn trong sáu câu. Các con số cụ thể (ngưỡng danh sách loại trừ, ε và K của tiêu chí bão hoà) nên coi là điểm khởi đầu để đo, không phải kết luận.
