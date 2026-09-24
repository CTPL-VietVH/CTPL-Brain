# 10 — Hợp đồng API giữa Backend C.Brain và AI Services (Ingestion v2 + Retrieval v2)

| | |
|---|---|
| **Phiên bản** | v0.7 — **BẢN NHÁP** (Cowork soạn 23/9/2026, sửa 24/9/2026) |
| **Lịch sử** | v0.7 — 24/9/2026 (tối), sau khi cài `POST/GET /v1/ingestions` và bộ chạy nền: `DUPLICATE_IN_SPACE` chỉ còn là trạng thái §4.2, không phải mã HTTP; `VERSION_ORDINAL_CONFLICT` chưa phát sinh ở v1; BE gọi lại `DELETE /v1/spaces` khi việc xoá chưa xong sau lần AI khởi động lại (§4.0); ràng buộc triển khai *một bản sao duy nhất* (§4.1); `failed` → BE nộp lại (§4.2). v0.6 — 24/9/2026 (chiều), PO chốt: **Q5 — file đi bằng tham chiếu** (BE gửi đường dẫn có chữ ký, hạn ngắn, trỏ vào MinIO nơi FE đã lưu file), sửa §4.1 và §2; duyệt 9 escalation của kế hoạch API-nap-tai-lieu-va-chay-nen: `ingestion_id` khác `document_id`; `tenant_id` là biến môi trường; thân phản hồi `DELETE /v1/spaces` = thân `GET`; mã lỗi mới ở §3.5; tên và số hiệu văn bản do AI gợi ý, không thêm vào lời gọi của BE. v0.5 — 24/9/2026, sau khi dựng khung FastAPI (task API-khung-fastapi-va-be-gia), PO chốt: khoá dịch vụ T1 là biến môi trường `CBRAIN_API_SERVICE_KEY`, không nằm trong `config/`; `GET /v1/meta` vẫn đòi xác thực dịch vụ; thêm 4 mã lỗi tầng vận chuyển ở §3.5; thiếu `Idempotency-Key` trên lời gọi ghi thì từ chối; ghi nhận hai chỗ khung chưa đạt hợp đồng (xoá Space chạy đồng bộ, chưa đếm số tài liệu đã xoá) ở §4.0; thêm Q10 ở §8. v0.4 — 23/9/2026 (khuya), PO chốt: T4; đăng ký Space khi BE tạo Space (AI chỉ biết `space_id` tồn tại, không lưu cây); xoá Space (§4.0); xoá tài liệu chỉ theo `document_id`. Đóng Q4 (phần xoá/tạo Space). v0.3 — 23/9/2026 (tối), sau vòng phản biện độc lập (REVIEW-10) và nghiên cứu phương án (RESEARCH-10), PO chốt: `recent_turns` chỉ gồm câu hỏi người dùng; lọc trạng thái hội thoại ngay đầu lượt; Q1 liên kết xuyên Space; Q2 AI hỏi BE cây Space mỗi vòng quét; Q6 trả trọn một lần; định nghĩa dẫn nguồn hợp lệ; cảnh báo chỉ tính từ tài liệu đã qua bộ lọc cứng. Thêm `GET /v1/meta`. Sửa nhãn nguồn theo phản biện. Đã sửa theo: 06 v1.11, 08 v1.5. v0.2 — 23/9/2026, PO chốt: T1–T3 ở §1; lịch sử hội thoại do BE lưu, AI không giữ trạng thái giữa các lượt, thêm trạng thái hội thoại dạng biểu mẫu (§6.1–6.2); hồ sơ cá nhân hoá ra khỏi phiên bản hiện tại. Đã sửa theo: 06 v1.10, 07 v1.10, 08 v1.4, 09 (ghi chú), CLAUDE.md. v0.1 — bản nháp đầu |
| **Trạng thái** | Đã chốt: §1 T1–T4, §2, §4.0, §5.1–5.2, §5.6, §6.1–6.2, §7.1. Còn chờ PO: T5–T6 ở §1, các mục **[Đề xuất]**, và các điểm mở còn lại ở §8 (Q3, Q4 phần đổi loại Space, Q7, Q8, Q10). §4.1 cách truyền file đã chốt 24/9 |
| **Nguồn chân lý** | `06` v1.12, `07` v1.10, `08` v1.6 — tài liệu này **không** được đổi quyết định nào trong ba tài liệu đó; chỗ nào cần đổi thì ghi ở §9 |
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

## 1. Mô hình tin cậy — T1–T4 ĐÃ CHỐT 23/9/2026; T5–T6 chờ PO

Rút từ trao đổi ngày 23/9/2026. Viet nêu hai ý: AI Services chỉ nhận lời gọi từ BE C.Brain, và bên thứ ba được chặn bằng giải pháp bảo mật hạ tầng. Viet xác nhận thêm: BE gửi danh sách Space, và Qdrant chỉ tìm trong các Space đó.

| # | Luật | Loại |
|---|---|---|
| **T1** | AI Services **chỉ nhận lời gọi từ BE C.Brain**. Mọi lời gọi không qua xác thực dịch vụ đều bị từ chối. Cách xác thực (mTLS, khoá dịch vụ, chính sách mạng) do hạ tầng chọn. Chiều ngược lại (AI gọi BE ở §7) cũng phải xác thực như vậy. **Bản cài v1 (24/9):** khoá dịch vụ gửi trong header `X-Service-Key`, giá trị lấy từ biến môi trường `CBRAIN_API_SERVICE_KEY`. Đây là tham số triển khai, khác nhau ở từng bản cài (giống mật khẩu PostgreSQL), nên **không** nằm trong ba nhóm cấu hình của `config/`. Thiếu biến hoặc để rỗng thì AI Services từ chối khởi động; không có chế độ "không đặt khoá thì bỏ qua xác thực". | [PO chốt 23/9; cách cài PO chốt 24/9] |
| **T2** | **BE quyết quyền, AI thực thi quyền.** BE xác thực người dùng, tra vai trò, và tính phạm vi Space người đó đọc được **tươi tại thời điểm gọi**. AI **không kiểm lại** người dùng, vai trò hay cây Space. | [PO chốt 23/9] |
| **T3** | AI **áp đúng phạm vi BE gửi sang làm bộ lọc cứng tại nơi lấy dữ liệu** (Qdrant và PostgreSQL), không lấy rộng ra rồi lọc sau. Với Qdrant, điều kiện `space_id` nằm **trong** lời gọi tìm, không lọc sau khi đã lấy top-k. Tài liệu kéo theo họ hàng đọc từ PostgreSQL nên phải áp lại cùng danh sách. Đây là cách đọc R4 dưới mô hình này: *quyết định* quyền ở BE, *kiểm quyền tại nơi lấy dữ liệu* vẫn ở AI. | [Suy ra — R4, NT4; PO chốt 23/9] |
| **T4** | **Mỗi bên chỉ khẳng định sự thật thuộc dữ liệu của mình.** BE khẳng định *"người này có vai trò X ở Space S"*. AI tự kiểm *"đối tượng này có thật sự nằm ở Space S không"*. Nếu không nằm ở đó, AI từ chối với `OBJECT_NOT_IN_SPACE`. Xoá tài liệu **chỉ theo `document_id`**, không bao giờ theo vân tay nội dung, tên hay số hiệu. | [PO chốt 23/9 — lý do PO nêu: tránh xoá nhầm bản trùng ở Space khác] |
| **T5** | Mọi trường dấu vết `*_by` (07: `removed_by`, `approved_by`, `labels_confirmed_by`, người xoá trong nhật ký xoá…) lấy từ `actor.user_id` do BE khẳng định. AI lưu nó như một **định danh không trong suốt**: không tra, không diễn giải. | [Đề xuất — dựa trên QT1: `_by` là dấu vết, không phải phán quyết] |
| **T6** | Không bên nào giữ bản sao dữ liệu của bên kia lâu hơn một lời gọi. Có hai ngoại lệ đã chốt: `space_id` trên tài liệu (nơi tài liệu nằm, bất biến ở v1), và "phạm vi quyền tại thời điểm đó" trong nhật ký điều tra (sự kiện lịch sử, 06 §9.2). Ngoại lệ thứ ba, chốt 23/9: **danh sách `space_id` đã đăng ký và trạng thái của nó** (§4.0) — chỉ sự tồn tại, không có cây, cờ kế thừa hay thành viên. | [Đề xuất — áp NT3 sang ranh giới BE ↔ AI] |

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
| Danh sách `space_id` đã đăng ký + trạng thái (đang dùng / đang xoá / đã xoá) | AI (chốt 23/9) | BE đăng ký và xoá qua §4.0. **Chỉ sự tồn tại** — không cây, không cờ, không thành viên |
| Cây Space, cờ kế thừa, loại Space, thành viên và vai trò | BE | Trong từng lời gọi: phạm vi đọc được. Ngoài lời gọi: API cấu trúc Space (§7.1), chỉ phục vụ GĐ7 |
| File gốc | BE — nằm ở MinIO, nơi FE đã lưu khi người dùng tải lên (06 §5.6: C.Brain không phải kho file) | AI **tải về qua đường dẫn có chữ ký BE cấp** (§4.1), chỉ để đọc chữ; xoá bản tạm ngay sau khi đọc xong. **Không lưu file gốc**, chỉ giữ `extracted_text`. AI **không** cầm tài khoản MinIO |
| `document`, `chunk`, `relation`, `pending_version_claim`, vùng đệm tiền kiểm | AI | Đọc và ghi qua §4–§5 |
| Nhật ký xoá, nhật ký điều tra | AI | Admin đọc qua §6.4 |
| Lịch sử hội thoại | **BE** (chốt 23/9) | AI nhận **câu hỏi** của K lượt gần nhất trong từng lời gọi hỏi, không lưu (§6.1) |
| Trạng thái hội thoại | **AI dựng, BE lưu** (chốt 23/9) | BE gửi lại ở lượt sau (§6.1) |
| Hồ sơ cá nhân hoá (06 §9.3) | — | **Không có ở phiên bản hiện tại** (chốt 23/9) |
| Định nghĩa agent chuyên miền | AI (07 §4) | Admin quản lý qua §6.3 |
| Cấu hình mô hình và tham số | AI (07 §3) | **Không qua API.** Chỉ đổi bằng file cấu hình. Cố ý không đưa lên giao diện quản trị |
| `tenant_id` | Cấu hình cài đặt (R6: mỗi khách hàng một bản) | **Không truyền theo từng lời gọi.** Bản cài v1 (chốt 24/9): biến môi trường `CBRAIN_TENANT_ID`, thiếu thì từ chối khởi động — cùng loại tham số triển khai với khoá dịch vụ T1 |

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

Mọi lời gọi ghi mang header `Idempotency-Key`. Gửi lại cùng khoá thì nhận lại đúng kết quả lần đầu, không ghi thêm. Xoá vĩnh viễn thì tự nó đã idempotent theo thiết kế (08 T2.8), nhưng vẫn dùng chung quy ước. Mọi lời gọi mang `X-Request-Id`, AI ghi kèm vào nhật ký của mình. **Chốt 24/9:** lời gọi ghi thiếu `Idempotency-Key` bị từ chối (`IDEMPOTENCY_KEY_MISSING`), không mặc định bỏ qua chống lặp. Dùng lại một khoá cho thân lời gọi khác thì trả `IDEMPOTENCY_KEY_REUSED`.

### 3.5 Lỗi — nguyên tắc "lên tiếng", không hỏng im lặng

Mọi lỗi có mã máy đọc được (`code`) và thông điệp tiếng Việt cho người (`message`). Danh sách mã:

| Mã | HTTP | Khi nào | Truy về |
|---|---|---|---|
| `SCOPE_MISSING` | 400 | Thiếu `space_id`, `readable_space_ids` hoặc `actor` | §3.3 |
| `OBJECT_NOT_IN_SPACE` | 404 | Đối tượng không nằm trong Space hoặc phạm vi khẳng định. Trả 404 chứ không trả 403, để không tiết lộ đối tượng tồn tại | T4; 06 §9.5 |
| `UNSUPPORTED_FORMAT` | 422 | Không thuộc 4 định dạng v1, hoặc PDF chỉ có ảnh quét | 06 §5.2 GĐ2 |
| `DUPLICATE_IN_SPACE` | — (trả dưới dạng `status: duplicate` của §4.2) | Trùng khít vân tay trong cùng Space. Kèm `existing_document_id`. *Sửa 24/9: nạp chạy bất đồng bộ, việc trùng chỉ biết sau khi đọc chữ, nên không bao giờ là mã HTTP* | 06 §5.7 |
| `SPACE_NOT_REGISTERED` | 404 | `space_id` chưa từng được BE đăng ký (§4.0) | §4.0 |
| `SPACE_BEING_DELETED` | 409 | Space đang được xoá hoặc đã xoá; không nhận tài liệu hay thao tác ghi mới | §4.0 |
| `NEW_VERSION_OTHER_SPACE` | 422 | Khai "bản mới của X" nhưng X ở Space khác | code `BanMoiKhacSpace`; 06 §5.7 |
| `VERSION_ORDINAL_CONFLICT` | 409 | Hai người cùng khai bản mới của một tài liệu. *24/9: chưa phát sinh ở bản cài v1 — chỉ một luồng công nhân nên hai lượt nạp không chạy song song. Đưa vào lại khi có kho claim bền (cho phép nhiều bản sao)* | 08 T2.2 cập nhật 21/9 |
| `INVALID_STATE` | 409 | Thao tác không hợp trạng thái, ví dụ duyệt một tài liệu không ở trạng thái chờ duyệt | — |
| `TOO_MANY_TURNS` | 400 | `recent_turns` vượt K. Không tự cắt | §6.1 |
| `STATE_VERSION_UNSUPPORTED` | 422 | `conversation_state` mang `schema_version` AI không đọc được | §6.1 |
| `CONTEXT_OVERFLOW` | 422 | Ngữ cảnh trả lời tràn. **Tuyệt đối không cắt ngầm** | 06 §6.5; 08 T3.4 |
| `SERVICE_MISCONFIGURED` | 503 | Lệch con dấu kho vector hoặc thiếu khoá cấu hình. Service không phục vụ | 07 §3.3 |
| `UNAUTHENTICATED` | 401 | Thiếu hoặc sai khoá dịch vụ. *Thêm 24/9* | T1 |
| `IDEMPOTENCY_KEY_MISSING` | 400 | Lời gọi ghi thiếu `Idempotency-Key`. *Thêm 24/9* | §3.4 |
| `IDEMPOTENCY_KEY_REUSED` | 422 | Cùng `Idempotency-Key` nhưng thân lời gọi khác lần đầu. *Thêm 24/9* | §3.4 |
| `SOURCE_UNREACHABLE` | 422 | Không tải được file từ đường dẫn BE gửi: hết hạn, bị từ chối, quá thời gian. *Thêm 24/9* | §4.1 |
| `SOURCE_INTEGRITY_MISMATCH` | 422 | File tải về lệch `sha256` hoặc `size_bytes` BE khai. *Thêm 24/9* | §4.1 |
| `FILE_TOO_LARGE` | 413 | Vượt cỡ file tối đa (công bố ở `/v1/meta`). Ngừng tải ngay khi vượt, không tải hết rồi mới kiểm. *Thêm 24/9* | §4.1, §3.6 |
| `DOCUMENT_NOT_STRUCTURABLE` | — (trả trong `code` của §4.2) | Đọc được file nhưng không cắt hoặc tạo vector được (ví dụ một mẩu vượt trần ngữ cảnh mô hình). Không cắt ngầm. *Thêm 24/9* | 08 T2.3, T2.5 |
| `INTERNAL_ERROR` | 500 | Lỗi không lường trước. Luôn trả đúng dạng `code` + `message`, không lộ traceback. *Thêm 24/9* | — |

Ngoài lỗi còn có các trạng thái **không phải lỗi nhưng phải hiển thị được**: từ chối theo R1, chạm trần, chưa đối chiếu xong. Các trạng thái này nằm trong thân phản hồi (§6.1), không nằm trong mã lỗi.

### 3.6 Thông tin hợp đồng và trạng thái sẵn sàng — `GET /v1/meta` — [Đề xuất]

Trả về: `ready` (bool) và `not_ready_reason` (ví dụ lệch con dấu kho vector, thiếu khoá cấu hình — 07 §3.1, §3.3); `contract_version`; `limits` gồm `max_recent_turns` (K), trần độ dài/số phần tử từng trường của `conversation_state`, `conversation_state_schema_version`, cỡ file tối đa. BE gọi lúc khởi động và định kỳ, để **không phải đoán K** và biết AI đang từ chối phục vụ trước khi người dùng gặp lỗi `503`. Không cần `actor`, nhưng **vẫn phải qua xác thực dịch vụ** theo T1 (chốt 24/9). `contract_version` hiện lấy số phiên bản schema dùng chung (07 §3.1); khi tài liệu này rời bản nháp và có số phiên bản riêng thì xem Q10.

### 3.7 Vị trí trong văn bản — [Đề xuất]

API **không bắt BE hay giao diện tự cắt chuỗi**. Mọi trích dẫn trả về kèm sẵn đoạn chữ đã cắt (`excerpt`). `span_start`/`span_end` nếu có mặt thì đếm theo **ký tự Unicode (code point)** như 07 §2.2. JavaScript đếm theo đơn vị UTF-16, nên giao diện tự cắt theo vị trí này sẽ lệch khi gặp ký tự ngoài BMP hoặc chuỗi chưa chuẩn hoá NFC. Trả sẵn đoạn chữ là cách chặn lỗi này bằng cấu trúc.

---

## 4. Nhập liệu — BE → AI

### 4.0 Đăng ký và xoá Space — chốt 23/9/2026

**Vì sao có.** PO chốt: khi BE tạo Space thì báo cho AI, để AI biết Space nào đang tồn tại trước khi nhận tài liệu vào đó; khi xoá Space thì Space và **đúng** các tài liệu của nó phải bị xoá. AI **không** lưu cây Space hay cờ kế thừa — cấu trúc vẫn hỏi BE lúc cần (§7.1), vì cờ kế thừa là cờ sống và bản sao sẽ cũ đi (Q2).

**`POST /v1/spaces`** — `{ space_id, actor }`, `acting_as ∈ {manager, admin}`. Đăng ký `space_id` ở trạng thái *đang dùng*. Gọi lại cùng `space_id` đang dùng → trả kết quả như lần đầu (idempotent). `space_id` đã xoá thì **không được đăng ký lại** (`409 SPACE_BEING_DELETED`) — tránh tài liệu cũ trong nhật ký bị hiểu nhầm là thuộc Space mới trùng mã.
*Không cần chuẩn bị kho*: theo 07, mọi tài liệu nằm chung một kho, `space_id` là trường trên từng tài liệu và từng mẩu — không có kho riêng cho mỗi Space.

**`DELETE /v1/spaces/{space_id}`** — `{ reason, actor }`, `acting_as ∈ {manager, admin}`, `reason` bắt buộc. Trả `202` và chạy nền:
1. Chuyển Space sang *đang xoá*. Từ lúc này mọi lời gọi nộp tài liệu hay thao tác ghi vào Space trả `409 SPACE_BEING_DELETED`.
2. Xoá vĩnh viễn **từng tài liệu có `space_id` này**, mỗi tài liệu theo đúng quy trình 06 §5.6 (kho vector → quan hệ + hồ sơ trong một giao dịch → dọn nền), mỗi tài liệu một dòng nhật ký xoá với lý do dạng *"xoá Space: <reason>"*.
3. Xoá các tài liệu còn trong vùng đệm tiền kiểm của Space, và các mục hàng việc thuộc Space.
4. Chuyển Space sang *đã xoá*.

`GET /v1/spaces/{space_id}` — trạng thái và tiến độ (số tài liệu đã xoá / còn lại). Gọi `DELETE` lần hai: trả tiến độ hiện tại, không lỗi, không xoá lặp. **Thân phản hồi của `DELETE` (202) giống hệt thân của `GET`** (chốt 24/9), để BE chỉ phải hiểu một dạng.

> **Khung code 24/9 chưa đạt hai điểm của mục này** (đã ghi vào TASKS.md, phải xong trước khi chạm dữ liệu thật): (1) `DELETE` đang chạy **đồng bộ** trong lời gọi vì repo chưa có bộ chạy nền, nên Space nhiều tài liệu sẽ giữ lời gọi rất lâu; (2) `GET` chưa trả được số tài liệu **đã xoá**, chỉ trả số còn lại. Cùng đợt đó phải thay kho idempotency trong bộ nhớ bằng kho bền.

**Ba ràng buộc chống xoá nhầm:**
- Chọn tài liệu cần xoá **chỉ theo `space_id` trên hồ sơ tài liệu** — không theo vân tay nội dung, tên hay số hiệu. Bản trùng khít ở Space khác là tài liệu khác (`document_id` khác, 06 §5.7) và **không bị đụng tới**; chỉ các liên kết quan hệ nối tới tài liệu bị xoá mới bị gỡ (06 §5.6).
- AI **không tự suy ra phải xoá Space con**. Xoá Space nào thì BE gọi riêng cho Space đó — cây là dữ liệu của BE.
- **Thứ tự phía BE**: đánh dấu Space "đang xoá" ở BE → gọi AI → đợi AI báo *đã xoá* → mới xoá Space ở BE. Làm ngược lại mà hỏng giữa chừng thì tài liệu mồ côi nằm lại trong kho AI: không bị lộ (không ai còn Space đó trong danh sách quyền) nhưng dữ liệu vẫn còn.
- **BE gọi lại khi chưa xong** (chốt 24/9): nếu `GET` vẫn báo *đang xoá* một thời gian sau khi AI khởi động lại, BE gọi lại `DELETE`. Lời gọi lặp an toàn, không xoá lặp. Lý do: ở bản cài v1, việc xoá Space chạy nền **chưa bền qua lần khởi động lại** — Space nằm lại ở *đang xoá* (cửa đã đóng, không lộ, không mất dữ liệu) nhưng không tự chạy tiếp.

Tám thao tác ghi của con người mà thiết kế nêu được liệt kê trọn ở §4 và §5. `08` T2.10 hiện chỉ đếm 5. Ba thao tác thiếu được đánh dấu ★.

### 4.1 Nộp tài liệu — `POST /v1/ingestions` — file đi bằng tham chiếu, chốt 24/9/2026

| | |
|---|---|
| **Ai** | `acting_as ∈ {contributor, manager}` ở `space_id`. `space_id` phải đã đăng ký và đang dùng (§4.0), nếu không trả `404 SPACE_NOT_REGISTERED` / `409 SPACE_BEING_DELETED` (06 §0.1: Contributor = đọc + đưa tài liệu vào) |
| **Vào** | `source = { url, sha256, size_bytes, filename, content_type }` · `space_id` · `space_is_private` (bool, loại Space *tại thời điểm nộp*) · `declared_previous_document_id` (tuỳ chọn, người upload khai "đây là bản mới của X") · `actor` |
| **Ra** | `202` · `{ ingestion_id, status: "processing" }` |
| **Truy về** | 06 §5.2 GĐ1, §5.7; 08 T2.1, T2.7 |

- **File đi bằng tham chiếu** (Q5, PO chốt 24/9). Lý do PO nêu: FE đã lưu file lên MinIO lúc người dùng tải lên, nên gửi nguyên file sẽ khiến file đi mạng hai lần qua BE. Cách làm:
  - `url` là **đường dẫn có chữ ký, hạn ngắn** (presigned GET) do BE sinh cho đúng một file. AI chỉ gọi HTTP GET, không dùng thư viện MinIO, không cầm tài khoản MinIO — BE vẫn là bên quyết ai đọc được gì (T2).
  - **Thứ tự trong lời gọi, trước khi trả 202:** xác thực → kiểm thân → kiểm Space (§4.0) **trước khi tải byte nào** → tải thẳng ra file tạm, đếm byte khi ghi, vượt cỡ tối đa thì ngừng ngay (`413 FILE_TOO_LARGE`) → so `sha256` và `size_bytes` (lệch → `SOURCE_INTEGRITY_MISMATCH`) → tạo đối tượng nạp → trả 202. Tải trong lời gọi chứ không để cho bộ chạy nền, vì hàng đợi dài sẽ làm đường dẫn hết hạn.
  - Không tải được → `SOURCE_UNREACHABLE`, không tạo đối tượng nạp, không còn file tạm.
  - AI **không lưu `url`** ở bất cứ đâu (nhật ký, bảng, thông báo lỗi) — đường dẫn có chữ ký là một thứ quyền tạm thời. Bản tạm bị xoá ngay sau khi đọc xong chữ, kể cả khi từ chối giữa chừng.
  - **Mạng:** AI Services phải với tới MinIO của bản cài. Đây là một dòng trong checklist triển khai.
  - **Một bản sao duy nhất** (checklist triển khai, chốt 24/9): bản cài v1 chạy **đúng một** tiến trình AI Services. Lúc khởi động, mọi việc nạp đang dở được coi là mồ côi và chạy lại — quy tắc này chỉ đúng khi có một bản sao. Chạy hai bản sao trước khi có kho claim bền thì một file có thể bị nạp hai lần mà không lỗi nào báo.
- `declared_previous_document_id` không tồn tại hoặc không nằm ở `space_id` này → từ chối `OBJECT_NOT_IN_SPACE`. **Không được** im lặng coi như tài liệu mới.
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
| `failed` | lỗi kỹ thuật | `code`. BE **nộp lại** với đường dẫn mới. Ví dụ: AI khởi động lại đúng lúc đang đọc file — AI không lưu đường dẫn nên không tự tải lại được (chủ ý, §4.1) |

`ingestion_id` và `document_id` là **hai định danh khác nhau** (chốt 24/9): đối tượng nạp có thể kết thúc mà không sinh tài liệu (`rejected`, `duplicate`, `failed`). `duplicate` là một trạng thái duy nhất trên dây, dù bản trùng nằm ở kho dùng chung hay ở vùng đệm tiền kiểm; AI phân biệt hai trường hợp trong nhật ký nội bộ.

`suggestions` gồm `category_labels`, `issued_date` + `issued_date_source`, `effective_date` + `effective_date_source`, `title`, `doc_number`. Đây là đầu vào cho màn hình "máy gợi ý, người xác nhận" (06 §5.2 GĐ5). `title` và `doc_number` do AI gợi ý (07 §2.1: nguồn là Ingestion, người sửa được qua §4.3) — BE **không** gửi chúng khi nộp. Khi bộ trích hai trường này chưa có, AI trả `null`, **không** lấy tên file giả làm tên văn bản.

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

### 5.1 Hàng việc — `GET /v1/work-items?managed_space_ids=&readable_space_ids=&uploader_user_id=`

Có ba loại mục (08 T2.9). Mỗi mục mang `space_id` của Space mà nó thuộc về:

| `kind` | Nội dung trả về | Ràng buộc |
|---|---|---|
| `relation_proposal` | `relation_id`, hai tài liệu, `relation_type`, `confidence`, `origin` (để giao diện xếp "chắc chắn" lên đầu, 06 §5.3) | **Chốt 23/9 (06 §5.4):** đề nghị nối tài liệu ở **hai Space khác nhau** chỉ trả về khi **cả hai** Space nằm trong `readable_space_ids` BE gửi kèm cho người gọi, và người gọi là Manager của ít nhất một đầu. Gọi với `acting_as = admin` thì thấy mọi đề nghị xuyên Space (PO chốt: Admin được xem tên văn bản ở mọi Space cho mục đích quản trị), nên không đề nghị nào nằm mãi không ai duyệt. Đề nghị trong cùng một Space: Manager của Space đó |
| `version_claim` | `claim_id`, `new_document_id`, `candidate_previous_document_id`, `similarity` | Hiện cho Manager của Space **và** cho người upload qua `uploader_user_id` (06 §5.7: nhắc cả hai) |
| `possibly_outdated` | `document_id` trong Space của người đọc | **Không có trường nào trỏ sang Space khác, tài liệu khác hay người khác.** Đây là cả cơ chế, không phải chi tiết trình bày (08 Phần B điều 23) |

### 5.2 Duyệt, từ chối hoặc sửa loại một liên kết — `PATCH /v1/relations/{relation_id}`

Vào: `space_id`, `actor(manager)`, `approval_state ∈ {approved, rejected}`, `relation_type` (tuỳ chọn, Manager sửa loại, 06 §5.3). Hiệu lực tức thì với câu hỏi kế tiếp, không nạp lại gì (06 §6.4). **Ai được duyệt** theo đúng luật hiện đề nghị ở §5.1. Lời gọi mang thêm `readable_space_ids` của người duyệt; **AI kiểm lại lúc duyệt** rằng cả hai tài liệu còn trong phạm vi đó — không tin trạng thái lúc đề nghị được sinh ra (cờ kế thừa có thể đã bị tắt). Không thoả → `404 OBJECT_NOT_IN_SPACE`.

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
| **Hệ quả §1** | E2 (module không tự kiểm quyền) **đóng hợp lệ** dưới T1+T2+T4: người xoá do BE khẳng định; tài liệu thuộc Space do AI tự kiểm. **Chốt 23/9: chỉ xoá theo `document_id`, và `document_id` phải nằm ở đúng `space_id` được nêu** — bản trùng ở Space khác không bao giờ bị xoá theo |
| **Chưa làm ở v1** | Không dọn lịch sử hội thoại có nhắc tới tài liệu này (06 §5.6, giới hạn đã chấp nhận). Giao diện nên nói rõ điều này với người xoá |

### 5.7 Xem tài liệu

- `GET /v1/documents?space_ids=&include_removed=` — danh sách trong phạm vi.
- `GET /v1/documents/{document_id}?readable_space_ids=` — hồ sơ tài liệu, đủ các trường người cần thấy trong 07 §2.1. Toàn văn chỉ trả theo đoạn khi có yêu cầu (07: "đọc theo đoạn").

[Đề xuất — các màn hình ở §4–§5 cần một chỗ để xem tài liệu; không truy về mục cụ thể nào của 06/07/08]

---

## 6. Hỏi–đáp, lịch sử, agent, nhật ký — BE → AI

### 6.1 Hỏi — `POST /v1/answers`

**Vào**

| Trường | Ghi chú |
|---|---|
| `actor` | `acting_as = viewer` trở lên |
| `readable_space_ids` | BE tính **tươi ở từng lượt**, kể cả lượt tiếp nối trong cùng cuộc trò chuyện (06 §9.4: mỗi lượt kiểm quyền lại từ đầu) |
| `question` | nguyên văn |
| `recent_turns` | tuỳ chọn; **câu hỏi** của tối đa K lượt gần nhất, mỗi phần tử là một chuỗi — **chỉ câu hỏi của người dùng, không có phần chữ câu trả lời** (chốt 23/9 sau phản biện: phần chữ câu trả lời chứa nội dung tài liệu đã diễn đạt lại, đưa vào bước hiểu câu hỏi là cửa sau — 06 §9.4). K công bố qua `GET /v1/meta`; gửi quá K thì AI trả `400 TOO_MANY_TURNS`, không tự cắt |
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

- **Không có ô nào chứa được con số, điều khoản hay trích đoạn.** AI dựng trạng thái chỉ từ câu hỏi của người dùng và `document_id` của tài liệu được dẫn — **không đọc `answer_text`, không ghi tên văn bản** (kể cả vào `question_thread`). Hai thủ pháp này lấy từ 06 §9.3.
- Mỗi trường có trần độ dài hoặc số phần tử, đặt bằng khoá cấu hình, để trạng thái không phình theo độ dài cuộc trò chuyện.
- Với BE, đây là dữ liệu **không trong suốt về ý nghĩa**: BE lưu và gửi lại nguyên vẹn, không sửa. `schema_version` để AI từ chối rõ ràng khi gặp trạng thái của phiên bản cũ, thay vì đọc sai.
- **Ngay đầu lượt sau, trước mọi bước khác kể cả bước hiểu câu hỏi**, `focus_document_ids` được cho qua **cùng bộ lọc quyền** như kết quả tìm mới (`readable_space_ids` mới + danh sách gỡ vì sai). Lọc muộn hơn thì tên của tài liệu vừa mất quyền có thể lọt vào câu hỏi viết lại (phát hiện của REVIEW-10). Còn quyền thì được **thêm** vào tập ứng viên và chịu chung trần. Mất quyền thì bị loại, không được nhắc tới, và nhật ký ghi lại việc loại. Tài liệu đã xoá vĩnh viễn tự rơi ra.
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
- **Mọi cảnh báo chỉ được tính từ tài liệu đã qua hai bộ lọc cứng của lượt đó** (06 §9.5). Ví dụ bản mới hơn nằm ngoài quyền hoặc đã gỡ vì sai thì không có `newer_version_exists`.
- **Dẫn nguồn hợp lệ — chốt 23/9 (06 §8.4):** mô hình chỉ được trỏ tới mã của đơn vị đọc **đã được đưa vào ngữ cảnh ở chính lượt đó**. AI tự dựng `citations` từ hồ sơ tài liệu và tự cắt `excerpt` từ `extracted_text`; mô hình không tự viết trích đoạn. Có trích dẫn trỏ ra ngoài tập ngữ cảnh thì **không phát** câu trả lời.
- **v1 trả trọn câu trả lời một lần, không phát từng chữ — chốt 23/9.** Bước kiểm dẫn nguồn ở trên phải chạy xong trước khi phát bất kỳ chữ nào.

### 6.2 Lịch sử hội thoại — thuộc BE, chốt 23/9/2026

AI Services **không có API lịch sử hội thoại** và không lưu bản sao nào. BE cam kết các tính chất mà 06 §9.1 và §9.4 đặt ra cho kho này:

- Lưu nguyên văn câu hỏi, phản hồi của AI và `conversation_state`.
- **Giữ nguyên kể cả khi quyền đã đổi**, không lọc lại theo quyền hiện tại.
- Chỉ chính người đó đọc. Người dùng xoá được, và xoá thì xoá luôn `conversation_state`.
- Lượt hỏi tiếp nối vẫn **tính lại** `readable_space_ids`, không dùng lại danh sách của lượt trước.

Vì lịch sử chỉ có một nhà, lời hứa "xoá được" chỉ cần thực thi ở một chỗ. Lời hứa này áp cho **lịch sử hội thoại**. Nhật ký điều tra ở AI **cố ý không xoá được** (06 §9.1): nó ghi ai hỏi, lúc nào, tài liệu nào vào ngữ cảnh, nhưng **không** có nguyên văn câu hỏi hay câu trả lời (06 §9.2).

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

[Suy ra — 06 §7.3; 08 Phần E mục 2] Dùng cho **cả hai chiều** của cảnh báo khi bật/tắt kế thừa: chiều bật (tài liệu của Space này sẽ được thêm những ai đọc) và chiều tắt. Khi Manager tắt kế thừa, BE phải cảnh báo *"bao nhiêu người mất quyền đọc bao nhiêu tài liệu"* (08 Phần E mục 2). BE biết phần *người*. Phần *tài liệu* chỉ AI biết. Không có endpoint này thì cảnh báo R11 **không làm được**, dù R11 đã được đẩy sang BE.

---

## 7. Chiều ngược lại — AI → BE

### 7.1 Cấu trúc Space cho GĐ7 — BE cung cấp: `GET {BE}/internal/v1/space-topology?space_ids=`

Ra: với mỗi Space: `space_id`, `parent_space_id`, `inherits_from_parent`, `child_space_ids`.

- **Ai dùng**: bản cài đặt thật của `SpaceScanScope.expand()` trong `relations_scan.py`, hiện chỉ là Protocol.
- **Vì sao AI phải tự hỏi**: GĐ7 chạy ngầm, nhiều vòng, không có lời gọi nào của người dùng đi kèm. Chụp lại cây lúc nộp tài liệu sẽ cũ đi giữa chừng (NT3). Nếu một Space vừa chuyển sang riêng, vòng quét có thể đề nghị liên kết vượt nhánh riêng. **Đây là chỗ duy nhất AI đọc dữ liệu của BE ngoài lời gọi**, và nó chỉ đọc *cấu trúc*, không đọc *người*.
- **Chốt 23/9 (Q2):** AI hỏi BE **ở mỗi vòng quét**, không lưu bản sao cây. Không dùng danh sách quyền của người upload: quan hệ là hiểu biết về nội dung, không phụ thuộc người (NT1), và vòng quét còn chạy tiếp khi người upload đã không liên quan.
- **BE không trả lời:** hoãn vòng quét, giữ trạng thái "đang mở rộng", thử lại sau. Không đoán, không quét toàn kho. Trong lúc đó câu trả lời tự nói "chưa đối chiếu xong" — cơ chế đã có (06 §5.1).
- Việc BE báo cho AI khi tạo và xoá Space: đã chốt 23/9, xem §4.0. AI chỉ ghi nhận `space_id` tồn tại, không lưu cây — không mâu thuẫn với mục này.

### 7.2 Dòng sự kiện — [Đề xuất]: `GET /v1/events?after=<cursor>` (BE kéo về)

Các loại sự kiện: `ingestion.status_changed`, `work_item.created`, `version_claim.created`. Dùng để BE gửi thông báo cho người upload và Manager (06 §5.7: "nhắc cả hai").

Dùng kiểu kéo (BE hỏi theo con trỏ) thay vì đẩy (AI gọi webhook), vì hai lý do. Kiểu kéo không bắt AI biết địa chỉ hay trạng thái của BE. Và mất kết nối thì chỉ trễ, không mất sự kiện. ⚠️ Kéo theo một câu hỏi về ý nghĩa hai trường `notified_uploader`/`notified_manager` trong 07 §2.4 (§8 Q8).

---

## 8. Điểm mở — PO phải chốt

| # | Mức | Câu hỏi | Vì sao chưa tự điền được |
|---|---|---|---|
| ~~Q1~~ | — | ~~Liên kết xuyên Space: ai thấy, ai duyệt?~~ | **Đã chốt 23/9** — xem §5.1, §5.2, 06 §5.4 |
| ~~Q2~~ | — | ~~GĐ7 lấy cấu trúc Space bằng cách nào~~ | **Đã chốt 23/9** — AI hỏi BE mỗi vòng quét, xem §7.1 |
| Q3 | TB | Tài liệu bị Manager từ chối ở tiền kiểm: bỏ khỏi vùng đệm ngay, hay giữ dấu vết ai từ chối và vì sao? | 06 §5.2 chỉ mô tả đường được duyệt. |
| Q4 | TB | ~~Xoá Space~~ — **đã chốt 23/9, xem §4.0.** Còn lại: đổi Space riêng ↔ kế thừa khi còn tài liệu trong vùng đệm tiền kiểm — tài liệu đó vẫn chờ duyệt, hay được thả ra? | 06 §5.2 chỉ nói trạng thái ban đầu theo loại Space *lúc nộp* (§4.1 gửi `space_is_private`). |
| ~~Q5~~ | — | ~~File đi sang AI bằng cách nào?~~ | **Đã chốt 24/9** — tham chiếu qua đường dẫn có chữ ký tới MinIO, xem §4.1 |
| ~~Q6~~ | — | ~~Phát từng chữ hay trả trọn?~~ | **Đã chốt 23/9** — v1 trả trọn một lần, xem §6.1 |
| Q7 | TB | Hỏi theo mốc thời gian (06 §4): người dùng chọn mốc bằng tham số tường minh `as_of`, hay hệ thống tự hiểu từ câu hỏi, hay cả hai? | 06 §4 chốt "phải lùi về được" nhưng không chốt cách người dùng nói ra mốc đó. |
| Q8 | THẤP | `notified_uploader`/`notified_manager` (07 §2.4) nghĩa là "AI đã phát sự kiện" hay "người đã thật sự được báo"? | Dưới §7.2, AI chỉ biết vế đầu. |
| Q10 | THẤP | `contract_version` trong `/v1/meta`: dùng số phiên bản schema 07 (như khung code hiện nay) hay số phiên bản riêng của tài liệu này? | Chỉ cần chốt khi tài liệu này rời bản nháp. |
| ~~Q9~~ | — | ~~"Lịch sử hội thoại đi theo người dùng khi nghỉ việc"~~ | **Không còn thuộc hợp đồng này (23/9).** Lịch sử ở BE, nên đây là việc nội bộ của BE. |

---

## 9. Tài liệu phải sửa theo

| Tài liệu | Sửa | Trạng thái |
|---|---|---|
| `06` §5.2 GĐ5, §5.6; `08` T2.4, T2.8, T2.11 | Chốt khuya 23/9: nhãn lĩnh vực, T4, đăng ký/xoá Space | ✅ 06 v1.12, 08 v1.6 |
| `06` §5.3, §5.4, §8.4, §9.4, §9.5, điểm mở #7 | Các chốt tối 23/9 | ✅ 06 v1.11 |
| `08` T2.6, T2.9, T3.6, T3.8, T4.2 | Các chốt tối 23/9 | ✅ 08 v1.5 |
| `06` §6.2 bước 1 | Bước "xác định phạm vi đọc được" chuyển sang BE, Retrieval áp danh sách nhận được | ✅ 06 v1.10 |
| `06` §9.1, §9.3, §9.4, §5.6, §11 | Lịch sử hội thoại ở BE; trạng thái hội thoại; hồ sơ cá nhân hoá ra khỏi phiên bản hiện tại | ✅ 06 v1.10 |
| `06` bảng R4 hoặc §3 | Thêm một dòng về cách đọc R4 theo §1 T2–T3 | ⏳ chờ chốt T5–T6 rồi sửa một lần |
| `07` Mục 0, Mục 4 | Trỏ sang tài liệu này; lịch sử hội thoại ra khỏi danh sách thực thể của AI | ✅ 07 v1.10 |
| `08` T2.10, T3.1, T3.3, T3.6, T3.10, T4.2, Phần E | Như ghi ở từng hạng mục | ✅ 08 v1.4 |
| `09` | Ước lượng lại (T3.10 rút ra; tầng API phát sinh) | ⚠️ Đã ghi chú, **chưa tính lại số** |
| `CLAUDE.md` | Thêm tài liệu 10 vào bảng nguồn; thêm mục "Ranh giới với Backend C.Brain" | ✅ |
| **Đội Backend C.Brain** | Sinh đường dẫn có chữ ký, hạn ngắn cho từng file trên MinIO; gửi kèm `sha256` và `size_bytes` (§4.1). Bảo đảm mạng từ AI Services tới MinIO | ⏳ báo đội BE |
| `07` Mục 3.2, Mục 4 | Đối tượng nạp (`ingestion_record`) thuộc Ingestion; hai tham số cỡ file tối đa và thời gian tải tối đa | ⏳ bước A của API-nap-tai-lieu-va-chay-nen (qua `schema-guardian`) |
| `08` T2.4 | Thêm gợi ý `title`, `doc_number` theo khuôn GĐ5 — hiện chưa hạng mục nào trích hai trường này | ⏳ PO giao task riêng |
| `TASKS.md` | E2 của T2.8 đổi lý do đóng: đóng nhờ T1+T2+T4, không phải vì "bên gọi tự lo" | ⏳ |

---

## 10. Nghiệm thu chung BE + AI

Các ca dưới đây **không bên nào tự nghiệm thu được một mình**. Mỗi ca dựng đúng tình huống rồi khẳng định hệ thống lên tiếng:

> **Cách chạy — chốt 23/9/2026 (PO):** phía AI tự dựng một **Backend giả** đóng vai BE ở cả hai chiều (gọi vào AI, và trả lời API cấu trúc Space ở §7.1), rồi chạy các ca dưới như kiểm thử hợp đồng — không chờ đội BE. Khi Backend thật sẵn sàng thì chạy lại đúng các ca này với Backend thật. Backend giả phải tuân đúng hợp đồng này, không được "dễ dãi" hơn (ví dụ: không bao giờ gửi thiếu `readable_space_ids`, trừ ca kiểm đúng lỗi đó).

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
| Xoá tài liệu có bản trùng khít ở Space khác | Bản ở Space khác còn nguyên; truy vấn người đọc Space đó vẫn ra | AI |
| Xoá tài liệu với `space_id` sai (tài liệu thật ở Space khác) | `404 OBJECT_NOT_IN_SPACE`, không xoá gì | AI |
| Nộp tài liệu vào Space chưa đăng ký | `404 SPACE_NOT_REGISTERED` | BE + AI |
| Xoá Space | Mọi tài liệu của Space biến khỏi Qdrant **và** PostgreSQL (kiểm thẳng kho); tài liệu Space khác không đổi; nộp mới vào Space đó bị từ chối | BE + AI |
| Hỏi hai lượt, rồi gỡ người hỏi khỏi Space chứa tài liệu trong `focus_document_ids`, rồi hỏi tiếp | Lượt ba không dùng và không nhắc tới tài liệu đó; lịch sử ở BE vẫn còn nguyên hai lượt đầu | BE (tính lại phạm vi, giữ lịch sử) + AI (lọc trạng thái) |
| Hỏi → gỡ quyền → hỏi tiếp | Đầu vào của bước viết lại câu hỏi không chứa tên văn bản hay con số của tài liệu đã mất quyền | AI |
| Mô hình trả trích dẫn tới đơn vị đọc không có trong ngữ cảnh | Không phát câu trả lời | AI |
| Manager chỉ đọc được một đầu của đề nghị liên kết xuyên Space | Không thấy đề nghị đó | AI (lọc theo `readable_space_ids`) + BE (gửi đúng danh sách) |
| BE không trả lời API cấu trúc Space | Vòng quét GĐ7 hoãn, không đoán; câu trả lời nói "chưa đối chiếu xong" | AI |
| Đề nghị liên kết xuyên Space | Theo đúng phương án chốt ở Q1; không Manager nào thấy tài liệu ngoài quyền | cả hai |
