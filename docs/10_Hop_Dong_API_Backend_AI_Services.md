# 10 — Hợp đồng API giữa Backend C.Brain và AI Services (Ingestion v2 + Retrieval v2)

| | |
|---|---|
| **Phiên bản** | v0.2 — **BẢN NHÁP** (Cowork soạn 23/9/2026) |
| **Lịch sử** | v0.2 — 23/9/2026, PO chốt: T1–T3 ở §1; lịch sử hội thoại do BE lưu, AI không giữ trạng thái giữa các lượt, thêm trạng thái hội thoại dạng biểu mẫu (§6.1–6.2); hồ sơ cá nhân hoá ra khỏi phiên bản hiện tại. Đã sửa theo: 06 v1.10, 07 v1.10, 08 v1.4, 09 (ghi chú), CLAUDE.md. v0.1 — bản nháp đầu |
| **Trạng thái** | Đã chốt: §1 T1–T3, §2, §6.1–6.2. Còn chờ PO: T4–T6 ở §1, các mục **[Đề xuất]**, và 8 điểm mở ở §8 |
| **Nguồn chân lý** | `06` v1.9+, `07` v1.8+, `08` v1.3 — tài liệu này **không** được đổi quyết định nào trong ba tài liệu đó; chỗ nào cần đổi thì ghi ở §9 |
| **Phạm vi** | Mọi lời gọi giữa Backend C.Brain (BE) và AI Services, theo **cả hai chiều**. Lấp đúng khoảng trống mà `07` Mục 0 loại trừ và `08` T2.10 yêu cầu phải chốt tường minh |

**Ký hiệu nguồn gốc của từng mục** — để PO kiểm được tài liệu này không bịa thêm cơ chế sản phẩm:

- **[Suy ra]** — rút thẳng từ một quyết định đã chốt ở 06/07/08, có cột *Truy về*.
- **[Đề xuất]** — yêu cầu kỹ thuật của chính việc gọi API (ví dụ idempotency, mã lỗi), không phải hành vi sản phẩm mới. Cần PO duyệt nhưng không cần quyết lại sản phẩm.
- **[Mở]** — thiết kế sản phẩm **chưa nói**. Không tự điền, gom về §8.

---

## 0. Tài liệu này là gì, và không là gì

**Là**: danh sách đầy đủ các thao tác đi qua ranh giới BE ↔ AI Services, kèm dữ liệu vào/ra, ai được gọi, bên nào kiểm cái gì, và lỗi nào phải trả về.

**Không là**: API giữa BE và giao diện; cách BE xác thực người dùng; cách hạ tầng xác thực giữa các service (chỉ nêu yêu cầu); hợp đồng dữ liệu nội bộ Ingestion ↔ Retrieval (đó là `07`).

**Cách đọc**: §1–§3 là luật chung, áp cho mọi endpoint. §4–§7 là danh mục thao tác. §8 là những gì PO phải chốt. §9 là những tài liệu khác phải sửa theo.

---

## 1. Mô hình tin cậy — T1–T3 ĐÃ CHỐT 23/9/2026; T4–T6 chờ PO

Rút từ trao đổi ngày 23/9/2026. Viet nêu hai ý: AI Services chỉ nhận lời gọi từ BE C.Brain, và bên thứ ba được chặn bằng giải pháp bảo mật hạ tầng. Viet xác nhận thêm: BE gửi danh sách Space, và Qdrant chỉ tìm trong các Space đó.

| # | Luật | Loại |
|---|---|---|
| **T1** | AI Services **chỉ nhận lời gọi từ BE C.Brain**. Mọi lời gọi không qua xác thực dịch vụ đều bị từ chối. Cách xác thực (mTLS, khoá dịch vụ, chính sách mạng) do hạ tầng chọn. Chiều ngược lại (AI gọi BE ở §7) cũng phải xác thực như vậy. | [Suy ra từ PO 23/9] |
| **T2** | **BE quyết quyền, AI thực thi quyền.** BE xác thực người dùng, tra vai trò, và tính phạm vi Space người đó đọc được **tươi tại thời điểm gọi**. AI **không kiểm lại** người dùng, vai trò hay cây Space. | [Suy ra từ PO 23/9] |
| **T3** | AI **áp đúng phạm vi BE gửi sang làm bộ lọc cứng tại nơi lấy dữ liệu** (Qdrant và PostgreSQL), không lấy rộng ra rồi lọc sau. Với Qdrant, điều kiện `space_id` nằm **trong** lời gọi tìm, không lọc sau khi đã lấy top-k. Tài liệu kéo theo họ hàng đọc từ PostgreSQL nên phải áp lại cùng danh sách. Đây là cách đọc R4 dưới mô hình này: *quyết định* quyền ở BE, *kiểm quyền tại nơi lấy dữ liệu* vẫn ở AI. | [Suy ra — R4, NT4; PO chốt 23/9] |
| **T4** | **Mỗi bên chỉ khẳng định sự thật thuộc dữ liệu của mình.** BE khẳng định *"người này có vai trò X ở Space S"*. AI tự kiểm *"đối tượng này có thật sự nằm ở Space S không"*. Nếu không nằm ở đó, AI từ chối với `OBJECT_NOT_IN_SPACE`. | [Đề xuất] |
| **T5** | Mọi trường dấu vết `*_by` (07: `removed_by`, `approved_by`, `labels_confirmed_by`, người xoá trong nhật ký xoá…) lấy từ `actor.user_id` do BE khẳng định. AI lưu nó như một **định danh không trong suốt**: không tra, không diễn giải. | [Suy ra — QT1] |
| **T6** | Không bên nào giữ bản sao dữ liệu của bên kia lâu hơn một lời gọi. Có hai ngoại lệ đã chốt: `space_id` trên tài liệu (nơi tài liệu nằm, bất biến ở v1), và "phạm vi quyền tại thời điểm đó" trong nhật ký điều tra (sự kiện lịch sử, 06 §9.2). | [Suy ra — NT3] |

> **Vì sao cần T4 dù đã có T2.** T2 tin BE về *con người*. Nhưng nếu BE có lỗi, ví dụ gửi `space_id` của Space A kèm `document_id` của một tài liệu ở Space B, thì thiếu T4 AI sẽ để một Manager của A gỡ tài liệu của B. Đây là loại lỗi truy cập đối tượng phổ biến nhất trong API. T4 chặn nó mà không bắt AI biết gì về người dùng, vì *tài liệu nằm ở Space nào* là dữ liệu của chính AI.

> **Khi nào phải xem lại §1.** Khi có bên gọi thứ hai ngoài BE C.Brain, ví dụ CAgentPlatform hoặc một tích hợp gọi thẳng vào. Lúc đó AI không thể tin mọi bên gọi như nhau, và cần token mang danh tính người dùng có chữ ký.

### Hệ quả phải ghi nhận

- **Luật kế thừa Space (06 §0.1) được thực thi ở BE**: kế thừa một chiều xuống, cắt tại nhánh riêng, tính cả quyền qua nhóm. Nếu BE tính sai, AI vẫn lọc "đúng" theo danh sách sai, và **không có lỗi nào báo**. Vì vậy các ca thử ở §10 là bài nghiệm thu chung, không phải của riêng bên nào.
- **T3.1 thu nhỏ lại**: Retrieval không còn duyệt cây Space, chỉ áp danh sách nhận được. Bước 1 của 06 §6.2 chuyển sang BE (xem §9).

---

## 2. Sở hữu dữ liệu

| Dữ liệu | Chủ sở hữu | Bên kia được gì |
|---|---|---|
| Tài khoản, nhóm, thành viên nhóm | BE | Chỉ `user_id` trong từng lời gọi |
| Cây Space, cờ kế thừa, loại Space, thành viên và vai trò | BE | Trong từng lời gọi: phạm vi đọc được. Ngoài lời gọi: API cấu trúc Space (§7.1), chỉ phục vụ GĐ7 |
| File gốc | BE, hoặc nơi công ty lưu file (06 §5.6: C.Brain không phải kho file) | AI nhận file để đọc, **không lưu file gốc**, chỉ giữ `extracted_text` |
| `document`, `chunk`, `relation`, `pending_version_claim`, vùng đệm tiền kiểm | AI | Đọc và ghi qua §4–§5 |
| Nhật ký xoá, nhật ký điều tra | AI | Admin đọc qua §6.4 |
| Lịch sử hội thoại | **BE** (chốt 23/9) | AI nhận K lượt gần nhất trong từng lời gọi hỏi, không lưu (§6.1) |
| Trạng thái hội thoại | **AI dựng, BE lưu** (chốt 23/9) | BE gửi lại ở lượt sau (§6.1) |
| Hồ sơ cá nhân hoá (06 §9.3) | — | **Không có ở phiên bản hiện tại** (chốt 23/9) |
| Định nghĩa agent chuyên miền | AI (07 §4) | Admin quản lý qua §6.3 |
| Cấu hình mô hình và tham số | AI (07 §3) | **Không qua API.** Chỉ đổi bằng file cấu hình. Cố ý không đưa lên giao diện quản trị |
| `tenant_id` | Cấu hình cài đặt (R6: mỗi khách hàng một bản) | **Không truyền theo từng lời gọi** |

---

## 3. Quy ước chung

### 3.1 Giao thức — [Đề xuất]

HTTP + JSON, tiền tố phiên bản `/v1`. Tài liệu này là nguồn để sinh OpenAPI. Mọi thời điểm dùng ISO-8601 UTC, mọi ngày dùng `YYYY-MM-DD`. Danh sách có phân trang theo con trỏ (`cursor`, `limit`).

### 3.2 Ngữ cảnh người gọi `actor` — có mặt trong **mọi** lời gọi nhân danh một người

```json
"actor": { "user_id": "string", "acting_as": "viewer | contributor | manager | admin" }
```

- `acting_as` là **vai trò BE khẳng định người này đang dùng cho đúng thao tác này, ở đúng Space nêu trong lời gọi**. Ba giá trị đầu là ba vai trò v1 dùng (06 §0.1). `admin` là vai trò hệ thống.
- AI ghi `acting_as` vào dấu vết. Cần thiết vì `version_declared_by` (07 §2.1) phải phân biệt *người upload* với *Manager* khi xác nhận bản mới.
- Tác vụ nền do AI tự chạy (GĐ7) không có `actor`.

### 3.3 Hai dạng khẳng định phạm vi

| Dạng | Dùng cho | Trường |
|---|---|---|
| **Thao tác trên một Space** | mọi thao tác ghi | `space_id` + `actor.acting_as`. AI áp T4 |
| **Đọc qua nhiều Space** | hỏi–đáp, danh sách, hàng việc | `readable_space_ids` (hoặc `managed_space_ids` cho hàng việc), do BE tính tươi. **Danh sách rỗng là hợp lệ và nghĩa là không đọc được gì**, không phải "không lọc" |

> ⚠️ **Cấm diễn giải "thiếu trường" hoặc "danh sách rỗng" thành "không giới hạn".** Hệ cũ từng có đúng lỗi này (`workspace=""` bỏ qua lọc quyền, xem ghi chú Chặng 0). Thiếu trường thì trả `400 SCOPE_MISSING`. Danh sách rỗng thì trả kết quả rỗng; với hỏi–đáp thì từ chối theo R1 **mà không gọi mô hình**.

### 3.4 Idempotency — [Đề xuất]

Mọi lời gọi ghi mang header `Idempotency-Key`. Gửi lại cùng khoá thì nhận lại đúng kết quả lần đầu, không ghi thêm. Xoá vĩnh viễn thì tự nó đã idempotent theo thiết kế (08 T2.8), nhưng vẫn dùng chung quy ước. Mọi lời gọi mang `X-Request-Id`, AI ghi kèm vào nhật ký của mình.

### 3.5 Lỗi — nguyên tắc "lên tiếng", không hỏng im lặng

Mọi lỗi có mã máy đọc được (`code`) và thông điệp tiếng Việt cho người (`message`). Danh sách mã:

| Mã | HTTP | Khi nào | Truy về |
|---|---|---|---|
| `SCOPE_MISSING` | 400 | Thiếu `space_id`, `readable_space_ids` hoặc `actor` | §3.3 |
| `OBJECT_NOT_IN_SPACE` | 404 | Đối tượng không nằm trong Space hoặc phạm vi khẳng định. Trả 404 chứ không trả 403, để không tiết lộ đối tượng tồn tại | T4; 06 §9.5 |
| `UNSUPPORTED_FORMAT` | 422 | Không thuộc 4 định dạng v1, hoặc PDF chỉ có ảnh quét | 06 §5.2 GĐ2 |
| `DUPLICATE_IN_SPACE` | 409 | Trùng khít vân tay trong cùng Space. Kèm `existing_document_id` | 06 §5.7 |
| `NEW_VERSION_OTHER_SPACE` | 422 | Khai "bản mới của X" nhưng X ở Space khác | code `BanMoiKhacSpace`; 06 §5.7 |
| `VERSION_ORDINAL_CONFLICT` | 409 | Hai người cùng khai bản mới của một tài liệu | 08 T2.2 cập nhật 21/9 |
| `INVALID_STATE` | 409 | Thao tác không hợp trạng thái, ví dụ duyệt một tài liệu không ở trạng thái chờ duyệt | — |
| `TOO_MANY_TURNS` | 400 | `recent_turns` vượt K. Không tự cắt | §6.1 |
| `STATE_VERSION_UNSUPPORTED` | 422 | `conversation_state` mang `schema_version` AI không đọc được | §6.1 |
| `CONTEXT_OVERFLOW` | 422 | Ngữ cảnh trả lời tràn. **Tuyệt đối không cắt ngầm** | 06 §6.5; 08 T3.4 |
| `SERVICE_MISCONFIGURED` | 503 | Lệch con dấu kho vector hoặc thiếu khoá cấu hình. Service không phục vụ | 07 §3.3 |

Ngoài lỗi còn có các trạng thái **không phải lỗi nhưng phải hiển thị được**: từ chối theo R1, chạm trần, chưa đối chiếu xong. Các trạng thái này nằm trong thân phản hồi (§6.1), không nằm trong mã lỗi.

### 3.6 Vị trí trong văn bản — [Đề xuất]

API **không bắt BE hay giao diện tự cắt chuỗi**. Mọi trích dẫn trả về kèm sẵn đoạn chữ đã cắt (`excerpt`). `span_start`/`span_end` nếu có mặt thì đếm theo **ký tự Unicode (code point)** như 07 §2.2. JavaScript đếm theo đơn vị UTF-16, nên giao diện tự cắt theo vị trí này sẽ lệch khi gặp ký tự ngoài BMP hoặc chuỗi chưa chuẩn hoá NFC. Trả sẵn đoạn chữ là cách chặn lỗi này bằng cấu trúc.

---

## 4. Nhập liệu — BE → AI

Tám thao tác ghi của con người mà thiết kế nêu được liệt kê trọn ở §4 và §5. `08` T2.10 hiện chỉ đếm 5. Ba thao tác thiếu được đánh dấu ★.

### 4.1 Nộp tài liệu — `POST /v1/ingestions` (multipart)

| | |
|---|---|
| **Ai** | `acting_as ∈ {contributor, manager}` ở `space_id` (06 §0.1: Contributor = đọc + đưa tài liệu vào) |
| **Vào** | `file` · `space_id` · `space_is_private` (bool, loại Space *tại thời điểm nộp*) · `declared_previous_document_id` (tuỳ chọn, người upload khai "đây là bản mới của X") · `actor` |
| **Ra** | `202` · `{ ingestion_id, status: "processing" }` |
| **Truy về** | 06 §5.2 GĐ1, §5.7; 08 T2.1, T2.7 |

- **Chạy bất đồng bộ** [Đề xuất]: GĐ2 phải đọc xong file mới biết trùng hay không (vân tay tính sau khi đọc chữ, 08 T2.1 cập nhật 19/9). GĐ6–GĐ7 còn lâu hơn nữa.
- `space_is_private = true` thì chạy GĐ2, GĐ3, GĐ5 rồi dừng ở vùng đệm (T2.7). Ngược lại thì chạy trọn và ghi vào kho. **Luật "Space riêng thì tiền kiểm" nằm ở AI. BE chỉ gửi sự thật về loại Space.**
- Vì sao BE gửi cờ này thay vì để AI tự tra: T2 (AI không giữ và không tra cây Space trong lời gọi của người dùng).

### 4.2 Theo dõi nạp — `GET /v1/ingestions/{ingestion_id}?space_id=`

`status` nhận một trong các giá trị:

| status | Nghĩa | Kèm theo |
|---|---|---|
| `processing` | đang chạy | — |
| `rejected` | từ chối | `code` (`UNSUPPORTED_FORMAT`, `NEW_VERSION_OTHER_SPACE`…) |
| `duplicate` | trùng khít cùng Space | `existing_document_id` |
| `awaiting_approval` | Space riêng, đang ở vùng đệm | `suggestions` |
| `active` | đã vào kho dùng chung | `document_id`, `suggestions`, `relations_scan_state` |
| `failed` | lỗi kỹ thuật | `code` |

`suggestions` gồm `category_labels`, `issued_date` + `issued_date_source`, `effective_date` + `effective_date_source`, `title`, `doc_number`. Đây là đầu vào cho màn hình "máy gợi ý, người xác nhận" (06 §5.2 GĐ5).

> Không có trường `publication_state` trong `document` (07 §2.1: mọi thứ trong kho đều đã dùng được). Trạng thái chờ duyệt chỉ tồn tại **trên đối tượng nạp**, không trên hồ sơ tài liệu. Hai khái niệm này tách rời nhau là có chủ ý.

### 4.3 ★ Xác nhận hoặc sửa nhãn, ngày, tên, số hiệu

- `PATCH /v1/ingestions/{ingestion_id}/metadata` (tài liệu còn ở vùng đệm)
- `PATCH /v1/documents/{document_id}/metadata` (tài liệu đã vào kho)

| | |
|---|---|
| **Ai** | người đưa tài liệu vào, hoặc Manager của Space |
| **Vào** | `space_id`, `actor`, và một hoặc nhiều trường: `category_labels`, `issued_date`, `effective_date`, `title`, `doc_number` |
| **Hiệu lực** | Ngày được sửa thì nguồn chuyển thành *người xác nhận*. Nhãn thì ghi `labels_confirmed_by`/`_at`. Sửa nhãn trên tài liệu đã vào kho thì AI tự cập nhật bản sao `category_labels` trên mọi mẩu (ngoại lệ QT2 đã quyết ở 06 §6.4) |
| **Truy về** | 06 §5.2 GĐ5, §6.4; 07 §2.1 |

### 4.4 ★ Duyệt hoặc từ chối tài liệu ở Space riêng

`POST /v1/ingestions/{ingestion_id}/approve` và `POST /v1/ingestions/{ingestion_id}/reject`

| | |
|---|---|
| **Ai** | `manager` của `space_id` |
| **Approve** | Chạy nốt GĐ6, GĐ7, ghi vào kho. Trạng thái nạp đi tiếp về `active` theo kiểu bất đồng bộ. Độ trễ này đã được chấp nhận (06 §5.2) |
| **Reject** | **[Mở — §8 Q3]** Thiết kế chưa nói số phận của tài liệu bị từ chối |
| **Truy về** | 06 §5.2 GĐ1; 08 T2.7 |

### 4.5 Danh sách chờ duyệt — `GET /v1/ingestions?space_ids=&status=awaiting_approval`

`space_ids` = các Space mà BE khẳng định người gọi là Manager. [Suy ra — T2.7 cần một nơi để Manager thấy việc phải duyệt]

---

## 5. Chăm sóc tri thức — BE → AI

### 5.1 Hàng việc — `GET /v1/work-items?managed_space_ids=&uploader_user_id=`

Có ba loại mục (08 T2.9). Mỗi mục mang `space_id` của Space mà nó thuộc về:

| `kind` | Nội dung trả về | Ràng buộc |
|---|---|---|
| `relation_proposal` | `relation_id`, hai tài liệu, `relation_type`, `confidence`, `origin` (để giao diện xếp "chắc chắn" lên đầu, 06 §5.3) | ⚠️ **[Mở — §8 Q1]** liên kết xuyên Space |
| `version_claim` | `claim_id`, `new_document_id`, `candidate_previous_document_id`, `similarity` | Hiện cho Manager của Space **và** cho người upload qua `uploader_user_id` (06 §5.7: nhắc cả hai) |
| `possibly_outdated` | `document_id` trong Space của người đọc | **Không có trường nào trỏ sang Space khác, tài liệu khác hay người khác.** Đây là cả cơ chế, không phải chi tiết trình bày (08 Phần B điều 23) |

### 5.2 Duyệt, từ chối hoặc sửa loại một liên kết — `PATCH /v1/relations/{relation_id}`

Vào: `space_id`, `actor(manager)`, `approval_state ∈ {approved, rejected}`, `relation_type` (tuỳ chọn, Manager sửa loại, 06 §5.3). Hiệu lực tức thì với câu hỏi kế tiếp, không nạp lại gì (06 §6.4). ⚠️ Câu hỏi *Manager của Space nào* được làm việc này đang là §8 Q1.

### 5.3 ★ Manager tự gắn liên kết — `POST /v1/relations`

Vào: `from_document_id`, `to_document_id`, `relation_type`, `space_id`, `readable_space_ids`, `actor(manager)`. AI kiểm **cả hai tài liệu** đều nằm trong `readable_space_ids` (T4). Liên kết khởi tạo với `origin = manager`, `approval_state = approved`, `confidence` **để trống** (07 §2.3).

### 5.4 Xác nhận hoặc bác đề nghị bản mới

`POST /v1/version-claims/{claim_id}/confirm` và `/dismiss`

Ai: người upload tài liệu mới, hoặc Manager của Space. AI ghi `version_declared_by` theo `acting_as` và theo việc `actor.user_id` có trùng người upload hay không (07 §2.1).

### 5.5 Gỡ vì sai, và hết hiệu lực — hai thao tác, hai endpoint

- `PUT /v1/documents/{document_id}/removal` · `{ removed_as_wrong: bool, removed_reason }`
- `PUT /v1/documents/{document_id}/supersession` · `{ superseded: bool }`

Ai: `manager` của `space_id`.

> ⛔ **Cấm gộp thành một endpoint "đổi trạng thái".** Lý do giống hệt lý do cấm gộp hai trường ở 07 §2.1. Nếu gộp, Manager đánh dấu một quyết định cũ là hết hiệu lực sẽ làm mất khả năng trả lời câu hỏi về quá khứ. Gỡ vì sai là **bộ lọc cứng** và có hiệu lực ngay với câu hỏi kế tiếp.

### 5.6 Xoá vĩnh viễn — `DELETE /v1/documents/{document_id}`

| | |
|---|---|
| **Ai** | `admin`, hoặc `manager` của `space_id` (06 §5.6) |
| **Vào** | `space_id`, `reason` (bắt buộc, vì nhật ký giữ lý do), `actor` |
| **Ra** | `{ outcome: "deleted" \| "already_deleted", background_cleanup_complete: bool }`. `false` là bình thường, vì Qdrant tự nén theo lịch riêng (TASKS E3) |
| **Hệ quả §1** | E2 (module không tự kiểm quyền) **đóng hợp lệ** dưới T1+T2+T4: người xoá do BE khẳng định, tài liệu thuộc Space do AI tự kiểm |
| **Chưa làm ở v1** | Không dọn lịch sử hội thoại có nhắc tới tài liệu này (06 §5.6, giới hạn đã chấp nhận). Giao diện nên nói rõ điều này với người xoá |

### 5.7 Xem tài liệu

- `GET /v1/documents?space_ids=&include_removed=` — danh sách trong phạm vi.
- `GET /v1/documents/{document_id}?readable_space_ids=` — hồ sơ tài liệu, đủ các trường người cần thấy trong 07 §2.1. Toàn văn chỉ trả theo đoạn khi có yêu cầu (07: "đọc theo đoạn").

[Suy ra — mọi màn hình ở §4–§5 cần một chỗ để xem tài liệu. Đây không phải tính năng mới]

---

## 6. Hỏi–đáp, lịch sử, agent, nhật ký — BE → AI

### 6.1 Hỏi — `POST /v1/answers`

**Vào**

| Trường | Ghi chú |
|---|---|
| `actor` | `acting_as = viewer` trở lên |
| `readable_space_ids` | BE tính **tươi ở từng lượt**, kể cả lượt tiếp nối trong cùng cuộc trò chuyện (06 §9.4: mỗi lượt kiểm quyền lại từ đầu) |
| `question` | nguyên văn |
| `recent_turns` | tuỳ chọn; tối đa K lượt gần nhất, mỗi lượt gồm `role` (`user`/`assistant`) và `text`. Lượt `assistant` chỉ gồm phần chữ câu trả lời, **không** kèm trích đoạn. K là khoá cấu hình của Retrieval và được công bố trong hợp đồng; gửi quá K thì AI trả `400 TOO_MANY_TURNS`, không tự cắt. Chỉ đi vào bước hiểu câu hỏi (06 §9.4) |
| `conversation_state` | tuỳ chọn; trạng thái AI trả về ở lượt trước, BE gửi lại nguyên vẹn. Thiếu thì coi là cuộc trò chuyện mới |
| `conversation_ref` | tuỳ chọn; mã cuộc trò chuyện phía BE. AI **chỉ ghi vào nhật ký điều tra** để nối các lượt của một sự cố, không dùng để tra dữ liệu gì |
| `agent_id` | tuỳ chọn; thiếu thì dùng agent tổng quát (06 §8.1–8.2: người dùng chọn trước khi hỏi) |
| `as_of` | **[Mở — §8 Q7]** mốc thời gian của câu hỏi |

**`conversation_state` — biểu mẫu, chốt 23/9/2026 (06 §9.4 v1.10)**

```json
{
  "schema_version": 1,
  "focus_document_ids": ["doc_45", "doc_12"],
  "topics": ["bổ nhiệm Giám đốc"],
  "entities": ["Giám đốc"],
  "question_thread": "người dùng đang tìm hiểu quá trình thay đổi Giám đốc"
}
```

- **Không có ô nào chứa được con số, điều khoản hay trích đoạn.** AI dựng trạng thái chỉ từ câu hỏi của người dùng và định danh hoặc tên tài liệu được dẫn, **không đọc `answer_text`**. Hai thủ pháp này lấy từ 06 §9.3.
- Mỗi trường có trần độ dài hoặc số phần tử, đặt bằng khoá cấu hình, để trạng thái không phình theo độ dài cuộc trò chuyện.
- Với BE, đây là dữ liệu **không trong suốt về ý nghĩa**: BE lưu và gửi lại nguyên vẹn, không sửa. `schema_version` để AI từ chối rõ ràng khi gặp trạng thái của phiên bản cũ, thay vì đọc sai.
- Ở lượt sau, `focus_document_ids` được lấy lại và cho qua **cùng bộ lọc quyền** như kết quả tìm mới. Còn quyền thì được **thêm** vào tập ứng viên và chịu chung trần. Mất quyền thì bị loại, không được nhắc tới, và nhật ký ghi lại việc loại. Tài liệu đã xoá vĩnh viễn tự rơi ra.
- BE sửa `conversation_state` thì không phá được quyền, vì mọi `document_id` trong đó vẫn phải qua bộ lọc. Trường hợp xấu nhất chỉ là mạch hội thoại lệch.

**Ra**

```json
{
  "outcome": "answered | refused_no_source",
  "answer_text": "…",
  "citations": [{
    "document_id": "…", "title": "…", "doc_number": "…",
    "structure_path": ["Chương II", "Điều 7", "Khoản 3"],
    "excerpt": "…",
    "issued_date": "…", "issued_date_source": "machine_extracted | human_confirmed | ingestion_default",
    "effective_date": "…", "effective_date_source": "…"
  }],
  "warnings": [{ "kind": "…", "document_ids": ["…"] }],
  "document_cap_reached": false,
  "conversation_state_next": { "schema_version": 1, "focus_document_ids": ["…"], "topics": ["…"], "entities": ["…"], "question_thread": "…" }
}
```

BE **lưu nguyên phản hồi** vào lịch sử (để mở lại cuộc trò chuyện vẫn hiện đủ nguồn và cảnh báo) và gửi `conversation_state_next` ở lượt sau. Với `refused_no_source`, AI vẫn trả `conversation_state_next`, để mạch không bị đứt.

`warnings[].kind` — mỗi loại truy về một cơ chế đã chốt, không thêm loại nào:

| kind | Truy về |
|---|---|
| `conflicting_sources` | 06 §5.4 |
| `relations_not_reconciled` | 06 §5.1 |
| `newer_version_exists` | 06 §5.7, §6.3 |
| `duplicate_copies_different_dates` | 06 §5.7 cơ chế 2 |
| `unreliable_date` | 06 §6.4 |
| `cap_exceeded_significantly` | 06 §6.5, chỉ khi số ứng viên vượt `cap_warning_multiple` lần trần |

> `document_cap_reached` và `cap_exceeded_significantly` là **hai thứ khác nhau** (08 T3.4). Chạm trần thì câu trả lời nói rõ đã giới hạn. Còn *cảnh báo* chỉ hiện khi vượt đáng kể. Gộp làm một sẽ tạo ra "cảnh báo luôn bật" mà 06 §6.5 cấm.

**Ràng buộc AI phải giữ dưới mô hình §1:**

- Mọi mẩu tìm được **và mọi tài liệu kéo theo họ hàng** phải nằm trong `readable_space_ids`. Liên kết có thể nối sang Space mà người hỏi không đọc được (GĐ7 quét dọc cây kế thừa). Nếu kéo họ hàng không đi qua bộ lọc cứng, nội dung ngoài quyền lọt vào ngữ cảnh. 08 T3.3 chưa ghi rõ điều này (xem §9).
- `readable_space_ids` rỗng, hoặc không tìm được tài liệu nào, thì `refused_no_source` **mà không gọi mô hình** (08 T3.11).
- Trả lời theo kiểu phát từng chữ (streaming) hay trả trọn một lần là **[Mở — §8 Q6]**.

### 6.2 Lịch sử hội thoại — thuộc BE, chốt 23/9/2026

AI Services **không có API lịch sử hội thoại** và không lưu bản sao nào. BE cam kết các tính chất mà 06 §9.1 và §9.4 đặt ra cho kho này:

- Lưu nguyên văn câu hỏi, phản hồi của AI và `conversation_state`.
- **Giữ nguyên kể cả khi quyền đã đổi**, không lọc lại theo quyền hiện tại.
- Chỉ chính người đó đọc. Người dùng xoá được, và xoá thì xoá luôn `conversation_state`.
- Lượt hỏi tiếp nối vẫn **tính lại** `readable_space_ids`, không dùng lại danh sách của lượt trước.

Vì lịch sử chỉ có một nhà, lời hứa "xoá được" chỉ cần thực thi ở một chỗ.

### 6.3 Agent chuyên miền — chỉ `admin`

| Endpoint | Việc |
|---|---|
| `POST /v1/agents` | Tạo từ **biểu mẫu có cấu trúc + một ô ghi chú** (06 §8.5): lĩnh vực chuyên môn, thuật ngữ ưu tiên, loại thông tin đưa lên trước, mức chi tiết, người đọc là ai, ví dụ câu trả lời mẫu, ghi chú. **Không có ô văn xuôi tự do nào khác.** Ra: `{ agent_id, state: "active" \| "flagged_pending_review", checker_findings[] }` |
| `POST /v1/agents/{id}/approve` | Admin tự duyệt agent bị đánh dấu. **`reason` bắt buộc** (06 §8.5) |
| `PUT /v1/agents/{id}/enabled` | Bật hoặc tắt |
| `GET /v1/agents?enabled=true` | Danh sách cho người dùng chọn |

Phụ thuộc: bảng trường định nghĩa agent **chưa có** (07 §4). Phần này hoàn chỉnh khi có bảng đó.

### 6.4 Nhật ký — chỉ `admin`, và chỉ khi có việc

- `GET /v1/audit/queries?user_id=&from=&to=&document_id=`
- `GET /v1/audit/queries/export`
- `GET /v1/audit/deletions?from=&to=`

Truy về R3 và 06 §9.2. Nội dung trả về đúng các trường ở 06 §9.2. **Không có nguyên văn câu hỏi hay câu trả lời, vì chúng không tồn tại trong kho này.**

> Dưới T2, chỉ BE chặn được việc Manager đọc nhật ký. 06 §9.2 coi việc để Manager đọc là biến nhật ký thành công cụ theo dõi nhân viên. **Hợp đồng ghi rõ: BE không được mở endpoint này cho vai trò nào khác ngoài Admin.** Bộ phận Đo lường cũng không được đọc (08 Phần B điều 18).

### 6.5 Số tài liệu theo Space — `POST /v1/document-counts`

Vào: `{ space_ids }`. Ra: số tài liệu đang dùng được trong từng Space.

[Suy ra — R11] Khi Manager tắt kế thừa, BE phải cảnh báo *"bao nhiêu người mất quyền đọc bao nhiêu tài liệu"* (08 Phần E mục 2). BE biết phần *người*. Phần *tài liệu* chỉ AI biết. Không có endpoint này thì cảnh báo R11 **không làm được**, dù R11 đã được đẩy sang BE.

---

## 7. Chiều ngược lại — AI → BE

### 7.1 Cấu trúc Space cho GĐ7 — BE cung cấp: `GET {BE}/internal/v1/space-topology?space_ids=`

Ra: với mỗi Space: `space_id`, `parent_space_id`, `inherits_from_parent`, `child_space_ids`.

- **Ai dùng**: bản cài đặt thật của `SpaceScanScope.expand()` trong `relations_scan.py`, hiện chỉ là Protocol.
- **Vì sao AI phải tự hỏi**: GĐ7 chạy ngầm, nhiều vòng, không có lời gọi nào của người dùng đi kèm. Chụp lại cây lúc nộp tài liệu sẽ cũ đi giữa chừng (NT3). Nếu một Space vừa chuyển sang riêng, vòng quét có thể đề nghị liên kết vượt nhánh riêng. **Đây là chỗ duy nhất AI đọc dữ liệu của BE ngoài lời gọi**, và nó chỉ đọc *cấu trúc*, không đọc *người*.
- Phương án thay thế và đánh đổi: §8 Q2.

### 7.2 Dòng sự kiện — [Đề xuất]: `GET /v1/events?after=<cursor>` (BE kéo về)

Các loại sự kiện: `ingestion.status_changed`, `work_item.created`, `version_claim.created`. Dùng để BE gửi thông báo cho người upload và Manager (06 §5.7: "nhắc cả hai").

Dùng kiểu kéo (BE hỏi theo con trỏ) thay vì đẩy (AI gọi webhook), vì hai lý do. Kiểu kéo không bắt AI biết địa chỉ hay trạng thái của BE. Và mất kết nối thì chỉ trễ, không mất sự kiện. ⚠️ Kéo theo một câu hỏi về ý nghĩa hai trường `notified_uploader`/`notified_manager` trong 07 §2.4 (§8 Q8).

---

## 8. Điểm mở — PO phải chốt

| # | Mức | Câu hỏi | Vì sao chưa tự điền được |
|---|---|---|---|
| **Q1** | **CAO** | **Liên kết xuyên Space: ai thấy, ai duyệt?** GĐ7 quét dọc cây kế thừa, nên một liên kết có thể nối tài liệu ở Space con với tài liệu ở Space cha. Thành viên chỉ có ở Space con **không đọc được** Space cha. Nếu đưa đề nghị này vào hàng việc của Manager Space con, hàng việc tiết lộ sự tồn tại của tài liệu ngoài quyền, **vi phạm 06 §9.5**. | 06 §5.4 chỉ nói "Manager Space đó", mà một liên kết xuyên Space thì có hai Space. Ba hướng có thể: (a) chỉ hiện cho Manager đọc được cả hai đầu; (b) chỉ hiện cho Manager Space chứa tài liệu `from`, khi và chỉ khi họ đọc được `to`; (c) liên kết xuyên Space chỉ Admin duyệt. Cần BE gửi kèm `readable_space_ids` của Manager thì AI mới lọc được, và điều này ảnh hưởng hình dạng §5.1. |
| **Q2** | **CAO** | GĐ7 lấy cấu trúc Space bằng cách nào: AI gọi ngược BE (§7.1, khuyến nghị) hay BE gửi ảnh chụp cây lúc nộp? | Gọi ngược: đúng NT3, nhưng AI phụ thuộc BE sẵn sàng khi chạy nền. Ảnh chụp: không phụ thuộc, nhưng cũ đi giữa các vòng quét. |
| Q3 | TB | Tài liệu bị Manager từ chối ở tiền kiểm: bỏ khỏi vùng đệm ngay, hay giữ dấu vết ai từ chối và vì sao? | 06 §5.2 chỉ mô tả đường được duyệt. |
| Q4 | TB | BE xoá một Space, hoặc đổi Space riêng ↔ kế thừa khi còn tài liệu (kể cả tài liệu trong vùng đệm): AI phải làm gì? | Chưa tài liệu nào nói. Nếu không quyết, tài liệu mồ côi vẫn nằm trong kho với một `space_id` không còn tồn tại. |
| Q5 | TB | File đi sang AI bằng cách nào: gửi nguyên file trong lời gọi (khuyến nghị cho v1, ít phụ thuộc nhất) hay gửi tham chiếu tới kho lưu chung? | Hệ cũ dùng Kafka + MinIO. 07 Mục 0 để việc này cho lúc tráo v2 vào. |
| **Q6** | **CAO** | Trả lời phát từng chữ hay trả trọn một lần? | 06 §8.4 bắt **kiểm dẫn nguồn trước khi phát ra** ("không có dẫn nguồn hợp lệ thì không phát ra"). Phát từng chữ mâu thuẫn trực tiếp với ràng buộc này, trừ khi giữ lại toàn bộ rồi mới phát, mà như vậy thì mất lợi ích của phát từng chữ. **Khuyến nghị: v1 trả trọn một lần.** |
| Q7 | TB | Hỏi theo mốc thời gian (06 §4): người dùng chọn mốc bằng tham số tường minh `as_of`, hay hệ thống tự hiểu từ câu hỏi, hay cả hai? | 06 §4 chốt "phải lùi về được" nhưng không chốt cách người dùng nói ra mốc đó. |
| Q8 | THẤP | `notified_uploader`/`notified_manager` (07 §2.4) nghĩa là "AI đã phát sự kiện" hay "người đã thật sự được báo"? | Dưới §7.2, AI chỉ biết vế đầu. |
| ~~Q9~~ | — | ~~"Lịch sử hội thoại đi theo người dùng khi nghỉ việc"~~ | **Không còn thuộc hợp đồng này (23/9).** Lịch sử ở BE, nên đây là việc nội bộ của BE. |

---

## 9. Tài liệu phải sửa theo, nếu PO duyệt

| Tài liệu | Sửa |
|---|---|
| `06` §6.2 bước 1 | "Xác định phạm vi đọc được" chuyển từ Retrieval sang BE. Retrieval nhận danh sách và áp làm bộ lọc cứng |
| `06` bảng R4 hoặc §3 | Thêm một dòng về cách đọc R4 theo §1 T2–T3 |
| `07` Mục 0 | Trỏ sang tài liệu này cho hợp đồng với Backend |
| `08` T2.10 | Đóng bằng tài liệu này. Sửa từ 5 thao tác thành 8 (§4.3, §4.4, §5.3) |
| `08` T3.1 | Thu nhỏ còn "áp danh sách nhận được". Thêm ca thử cho §3.3 (thiếu trường ≠ không lọc) |
| `08` T3.3 | Ghi rõ: tài liệu kéo theo họ hàng **cũng phải qua bộ lọc quyền** |
| `08` Phần E mục 2 (R11) | Ghi phần việc phía AI: §6.5 |
| `09` | Ước lượng lại. T2.10 nghiêng về Backend nên sinh ra phần việc tầng API này, đúng như 09 đã cảnh báo |
| `TASKS.md` | E2 của T2.8 đổi lý do đóng: đóng nhờ T1+T2+T4, không phải vì "bên gọi tự lo" |

---

## 10. Nghiệm thu chung BE + AI

Các ca dưới đây **không bên nào tự nghiệm thu được một mình**. Mỗi ca dựng đúng tình huống rồi khẳng định hệ thống lên tiếng:

| Ca | Phải xảy ra | Hỏng thường nằm ở |
|---|---|---|
| Người vừa được gắn vào Space hỏi ngay | Ra kết quả của Space đó | BE tính phạm vi từ bản lưu tạm |
| Người vừa bị gỡ khỏi Space hỏi ngay, **trong cùng cuộc trò chuyện** | Không ra tài liệu đó nữa | BE chỉ tính phạm vi một lần mỗi cuộc |
| Thành viên chỉ có ở Space con kế thừa hỏi | Không ra tài liệu của Space cha, **kể cả qua kéo họ hàng** | AI (T3.3) hoặc BE (luật kế thừa) |
| Lời gọi thiếu `readable_space_ids` | `400 SCOPE_MISSING`, không trả dữ liệu | AI |
| Manager Space A gỡ tài liệu với `space_id = A` và `document_id` thuộc B | `404 OBJECT_NOT_IN_SPACE` | AI (T4) |
| Tài liệu Space riêng chưa duyệt | Không có trong Qdrant lẫn PostgreSQL | AI |
| Mục "có thể lỗi thời" xuyên Space | Không chứa tên Space, tài liệu hay người nào của nơi khác | AI tạo mục, BE trình bày |
| Tắt kế thừa một Space có tài liệu | Cảnh báo nêu đúng số tài liệu | BE + §6.5 |
| Xoá vĩnh viễn gọi hai lần | Lần hai trả `already_deleted`, không lỗi | AI |
| Đề nghị liên kết xuyên Space | Theo đúng phương án chốt ở Q1; không Manager nào thấy tài liệu ngoài quyền | cả hai |
