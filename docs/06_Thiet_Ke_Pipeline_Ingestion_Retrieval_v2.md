# 06 — Thiết kế pipeline Ingestion v2 & Retrieval v2

| | |
|---|---|
| **Phiên bản** | v1.12 |
| **Ngày** | 23/9/2026 |
| **Trạng thái** | Bản thiết kế cấp khái niệm — đã chốt phần lớn quyết định, còn một số điểm mở được liệt kê ở Mục 10 |
| **Người quyết định** | Viet (PO) |
| **Phạm vi** | Thiết kế lại từ đầu hai service Ingestion và Retrieval. KHÔNG bao gồm schema/hợp đồng dữ liệu — schema là OUTPUT rút ra từ thiết kế này và **đã có ở `07_Hop_Dong_Du_Lieu_Schema_v2.md`**. |
| **Liên quan** | `01_Kien_Truc_Muc_Tieu.md` (v1.1: **KHÔNG còn đề xuất sửa R4** — xem Mục 7.4), `04_Thiet_Ke_Phan_Quyen_PII.md`, `research/R11_Phan_Quyen.md` |
| **Lịch sử** | v1.12 — 23/9/2026 (khuya): nhãn lĩnh vực — danh mục cố định trong file cấu hình theo từng bản cài (GĐ5); xoá chỉ theo `document_id`, kiểm tài liệu nằm đúng Space; đăng ký và xoá Space (5.6) — xem `10` Mục 4.0. v1.11 — 23/9/2026 (tối), sau vòng phản biện độc lập `docs/10`: câu hỏi các lượt trước chỉ gồm câu hỏi người dùng, trạng thái hội thoại lọc quyền ngay đầu lượt (9.4); đề nghị liên kết xuyên hai Space (5.4); GĐ7 hỏi Backend cấu trúc cây Space (5.3); cảnh báo chỉ tính từ tài liệu đã qua bộ lọc cứng (9.5); định nghĩa dẫn nguồn hợp lệ (8.4); v1 trả trọn câu trả lời một lần (điểm mở #7). v1.10 — 23/9/2026, theo `10_Hop_Dong_API_Backend_AI_Services.md`: phạm vi Space đọc được do Backend C.Brain tính và gửi kèm từng lượt hỏi (6.2 bước 1); lịch sử hội thoại do Backend lưu, AI Services không giữ trạng thái giữa các lượt, thêm trạng thái hội thoại dạng biểu mẫu (9.1, 9.4); hồ sơ cá nhân hoá ra khỏi kế hoạch phiên bản hiện tại (9.3). v1.9 — sửa câu "thừa hưởng gần trọn điểm" ở 6.2 vì nó mâu thuẫn với ví dụ ba dòng ngay trên, và thêm ràng buộc phép nhân phải áp trên điểm đã chuẩn hoá; ghi giá trị khởi đầu của ngưỡng kéo liên kết ở 5.3; chú thích điểm mở #1 và #2 đã có giá trị khởi đầu. v1.8 — sau vòng kiểm nhất quán và bàn giao (14/9): làm rõ "kết hợp" ở GĐ3 là có thứ tự (cấu trúc quyết định ranh giới, ý nghĩa chỉ chia nhỏ tiếp); biến quy tắc "lấy lại nguồn từ tài liệu" ở 9.4 thành một BƯỚC tách rời thay vì một câu dặn mô hình; sửa một chỗ đếm lệch ở Mục 10. v1.7 — xử lý xong bốn kịch bản pre-mortem còn lại: K1 ghi thành rủi ro tồn dư đã chấp nhận (5.2), K3 mở rộng nguồn đề nghị quan hệ và hoãn cảnh báo có điều kiện (5.3, 6.2), K4 cảnh báo hai chiều lúc Manager thao tác (7.3, đóng điểm mở #13), K5 hai cơ chế bù cho bản sao xuyên Space (5.7). v1.6 — hoãn GĐ4 ở v1 và sửa năm chỗ cho khớp (Mục 3, 5.1, 5.2, 5.5, 6.4); tách ngày ký khỏi ngày hiệu lực, mỗi ngày mang nguồn, trục thời gian chỉ tin ngày có nguồn tin được (6.4, GĐ5); Mục 12 ghi bốn kịch bản pre-mortem còn lại. v1.5 — chốt điểm dừng của chuỗi giai đoạn ở Space riêng (GĐ1) và bất biến "kho dùng chung chỉ chứa thứ đã dùng được"; thêm ghi chú ở NT4 giải thích vì sao "chờ duyệt" không thành bộ lọc cứng thứ ba; viết lại Mục 12 theo trạng thái sau khi rút schema và sau vòng pre-mortem. v1.4 — đóng tám điểm mở quyết định trực tiếp nội dung schema: bản mới của cùng tài liệu và trùng lặp (Mục 5.7 mới), ngưỡng tin cậy liên kết (5.3), quan hệ đọc lúc truy vấn (6.4), nhật ký không lưu nguyên văn câu trả lời (9.2), điểm cắm đo lường (9.6 mới), danh sách định dạng v1 (5.2). v1.3 — phát biểu lại NT2 thành ba ý, bổ sung Mục 5.6 (xoá vĩnh viễn). v1.0 — tổng hợp lần đầu. v1.1 — chốt phạm vi che thông tin cá nhân cho v1, rút đề xuất sửa R4, bổ sung điểm mở từ phản biện. v1.2 — bổ sung Mục 0.1 (bối cảnh tối thiểu để tài liệu đứng độc lập), Mục 6.2 (giới hạn kéo họ hàng + xếp hạng thừa hưởng điểm), Mục 6.5 (trần số lượng tài liệu), Mục 9 (nhật ký và bộ nhớ); sửa các chỗ không nhất quán còn sót |

---

## 0. Tài liệu này là gì, và không là gì

**Là**: bản ghi các quyết định thiết kế cho hai pipeline mới, cùng lý do đằng sau mỗi quyết định. Viết ở cấp *cơ chế nghiệp vụ*, không ở cấp cấu trúc dữ liệu hay tên hàm.

**Không là**: đặc tả kỹ thuật để lập trình ngay. Bước tiếp theo sau tài liệu này mới là hợp đồng dữ liệu và ước lượng công sức.

**Nguyên tắc soạn**: mọi cơ chế nêu ở đây phải truy được về một quyết định sản phẩm đã có, hoặc về user journey đã chốt. Chỗ nào là đề xuất chưa được duyệt thì ghi rõ.

---

## 0.1 Bối cảnh tối thiểu để đọc tài liệu này

Phần này tóm tắt những gì đã được chốt ở nơi khác nhưng cần thiết để hiểu và kiểm tra tài liệu này. Người đọc không cần tài liệu nào khác.

**Sản phẩm.** C.Brain là trợ lý hỏi–đáp trên kho tri thức nội bộ của một doanh nghiệp: người dùng đặt câu hỏi bằng ngôn ngữ tự nhiên, hệ thống tìm trong tài liệu của công ty và trả lời kèm dẫn nguồn. **Nó không phải nơi lưu trữ file** như một ổ đĩa dùng chung.

**Space — đơn vị tổ chức tri thức và phân quyền.**
- Space là *phạm vi tri thức mà AI được phép dùng để trả lời*, không phải thư mục chứa file.
- Space tổ chức thành cây. Space con có hai loại: **kế thừa** (người có quyền đọc ở Space cha giữ nguyên quyền tương đương ở Space con, đồng bộ liên tục) và **riêng** (phải chia sẻ riêng, không kế thừa gì). Khi tạo Space mới mà không chỉ định thì mặc định là **riêng**.
- Quyền kế thừa là **một chiều xuống**: người của Space cha đọc được tài liệu trong Space con kế thừa; người chỉ được gắn ở Space con **không** đọc được tài liệu của Space cha.
- Cờ kế thừa là **cờ sống**: bật/tắt lúc nào cũng được, và được kiểm lại mỗi lần hệ thống tính quyền.
- Cơ sở dữ liệu có sẵn 6 vai trò (Owner, Manager, Editor, Contributor, Commenter, Viewer). **v1 chỉ dùng ba**: *Viewer* (đọc), *Contributor* (đọc + đưa tài liệu vào), *Manager* (thêm quyền duyệt, quản lý thành viên, tạo Space con trong nhánh mình quản).
- **Quyền mặc định của một tài khoản mới là 0.** Không có kênh cấp quyền nào khác ngoài việc được gắn vào Space. Phòng ban và chức danh nếu hiển thị thì chỉ là thông tin tham khảo, **không tự cấp quyền**.
- Người dùng được nhóm lại thành **nhóm có thực thể riêng trong hệ thống** (không phải chỉ là tiện ích chọn nhiều người một lúc trên giao diện): gắn nhóm vào Space thì mọi thành viên nhóm có quyền; thêm người vào nhóm là thêm quyền ở mọi Space nhóm đó đã được gắn.

**Sáu ràng buộc bất khả xâm phạm của kiến trúc mục tiêu** (tài liệu này phải thoả mãn cả sáu):

| | |
|---|---|
| **R1** | Không có nguồn thì không trả lời |
| **R2** | Dữ liệu không rời ranh giới hạ tầng khi chưa qua lớp bảo vệ; mặc định chạy nội bộ |
| **R3** | Nhật ký phải tra cứu và xuất được |
| **R4** | Kiểm quyền tại nơi lấy dữ liệu, không phải nơi hiển thị |
| **R5** | Đổi mô hình bằng cấu hình, không phải sửa mã |
| **R6** | Mỗi khách hàng một bản cài đặt độc lập |

Kiến trúc mục tiêu còn chia hệ thống thành **11 khối năng lực** và **3 luồng**. Ba luồng là: đưa tri thức vào, hỏi–đáp, và **chăm sóc tri thức** (vòng lặp giữ cho kho không cũ đi). Trong 11 khối, tài liệu này chỉ nhắc tới hai khối mà nó có nghĩa vụ phục vụ nhưng chưa phục vụ đủ:
- **Khối Đo lường** — thu thập số liệu để biết chất lượng trả lời đang ra sao.
- **Khối Bảo vệ & Tuân thủ** — ghi nhật ký mọi hành vi, phục vụ tra cứu và kiểm toán (gắn với R3).

**Bảng phân loại thông tin cá nhân — 4 tier** (đặc tả sản phẩm; xem Mục 7 về phạm vi triển khai ở v1):

| Tier | Điều kiện hiển thị | Nhóm trường |
|---|---|---|
| Công khai | không giới hạn | tên nội bộ; liên hệ công việc của người giữ vai trò đại diện công khai |
| Tối thiểu có điều kiện | bất kỳ ai đọc được tài liệu | liên hệ công việc của nhân viên thường |
| Nâng cao có điều kiện | **chỉ khi tài liệu nằm trong Space loại riêng** — Space kế thừa không đủ điều kiện dù đọc được tài liệu | lương/thưởng; hồ sơ nhân sự; nhân thân; liên hệ cá nhân |
| Tuyệt đối cấm | không hiển thị qua AI trong mọi trường hợp | định danh pháp lý; tài chính rủi ro gian lận; sức khoẻ và đặc biệt nhạy cảm |

**Bối cảnh kỹ thuật.** Hai service này đang được **viết lại từ đầu**, chạy song song với bản đang vận hành rồi mới tráo vào. Tài liệu này cố tình **không** kế thừa cách làm của bản cũ. Khi tài liệu nhắc tới "hệ thống hiện tại", đó luôn là dẫn chứng *một kiểu lỗi đã từng xảy ra thật*, không phải chuẩn phải theo.

---

## 1. Cơ sở — user journey đặt ra tám sự thật

Toàn bộ thiết kế xuất phát từ cách Space được dựng và người dùng được gắn vào, không xuất phát từ kiến trúc RAG có sẵn.

1. Tri thức tổ chức thành **cây Space**; quyền chảy **một chiều xuống** (người của Space cha đọc được tài liệu trong Space con kế thừa), và **cắt tại nhánh riêng**.
2. Quyền đổi liên tục, và phải có hiệu lực **ngay ở câu hỏi kế tiếp**.
3. Người dùng được nhóm lại thành **thực thể nhóm thật** → "ai được biết gì" là một hàm của *người + nhóm + cây Space* tại **thời điểm hỏi**.
4. Tài liệu vào qua một cửa: người có quyền đóng góp đặt nó vào **đúng một Space** (v1 — một tài liệu thuộc một Space).
5. Mức soi xét trước khi dùng **khác nhau tuỳ loại Space**: Space riêng thì tiền kiểm (Manager duyệt mới dùng được), Space kế thừa/thông thường thì hậu kiểm (dùng ngay, gỡ sau).
6. Tài liệu có đời sống: có bản mới (thêm phiên bản, không ghi đè), có thể bị gỡ, nhưng **không biến mất**.
7. Người hỏi **mặc định hỏi trên toàn bộ những gì họ được biết**, có tuỳ chọn thu hẹp về một hay vài Space.
8. Cùng một tài liệu, hai người khác nhau được thấy **mức chi tiết khác nhau** (bảng PII 4 tier).

---

## 2. Bốn nguyên tắc thiết kế

### NT1 — Ranh giới "được biết" đi qua từng CÂU HỎI; ranh giới "hiểu gì" đi qua từng TÀI LIỆU

Mọi thứ trả lời câu *"ai được biết"* thì tính lúc hỏi. Mọi thứ trả lời câu *"tài liệu này nói gì"* thì làm lúc nạp, một lần.

Đây là đường cắt giữa hai service, và nó lý giải vì sao **agent không gắn vào Space**: agent thuộc phía "hiểu và trả lời", Space thuộc phía "được biết" — hai phía không chạm nhau.

### NT2 — Sự kiện lọc trước; phán đoán đứng sau và chấp nhận bỏ sót; chỗ nào bỏ sót gây hại thì phải nhìn thấy được

**"Loại bỏ" ở đây nghĩa là**: một tài liệu lẽ ra có thể dùng để trả lời, nhưng cuối cùng không được dùng — nó rơi ra ở đâu đó trên đường từ kho tới câu trả lời. Đường đi đó có bốn chỗ rơi:

| Bước | Ví dụ: kho 10.000 tài liệu | Rơi ra vì |
|---|---|---|
| Kho | 10.000 | |
| **1. Lọc quyền** | còn 1.500 | Người hỏi không ở trong Space chứa nó — **sự kiện** |
| **2. Bỏ tài liệu gỡ vì sai** | còn 1.480 | Manager đã đánh dấu là sai — **sự kiện** |
| **3. Tìm theo độ giống, xếp hạng** | còn 60 | Máy chấm là ít liên quan — **phán đoán** |
| **4. Cắt theo trần** | còn 6 | Xếp hạng thấp hơn 6 tài liệu kia — **phán đoán** |
| → đưa vào viết câu trả lời | 6 | |

**Nguyên tắc, ba ý:**

> **1. Sự kiện lọc trước** — vì nó chính xác, tra được, không bao giờ loại oan. Để nó làm hết phần việc nó làm được, phán đoán chỉ phải xử lý phần còn lại.
> **2. Phán đoán chỉ đứng sau, và chấp nhận nó có thể bỏ sót** — máy chấm điểm mức liên quan thì sẽ có lúc chấm sai.
> **3. Chỗ nào việc bỏ sót đó gây hại thì phải nhìn thấy được** — nếu không, "chấp nhận bỏ sót" sẽ trượt thành "bỏ sót mà không ai biết".

Ý 3 là thứ ngăn nguyên tắc này thoái hoá. Ví dụ đối chiếu:
- Cắt theo trần (bước 4) **được phép**, vì câu trả lời nói rõ đã giới hạn (Mục 6.5) — người đọc biết mà hỏi hẹp lại.
- Lọc cứng theo nhãn phân loại **bị cấm**, vì nhãn gán nhầm thì tài liệu biến mất và người dùng thấy một câu trả lời gọn gàng, có dẫn nguồn, không dấu hiệu nào cho thấy đang thiếu.
- Cắt bớt âm thầm ở tầng dưới khi tràn ngữ cảnh **bị cấm**, cùng lý do (Mục 6.5).

> Cả ba lớp lỗi im lặng đã tìm thấy trong hệ thống hiện tại đều là **một phán đoán được trao quyền loại trừ mà không ai nhìn thấy**.

Hai hệ quả hay dùng:

- **Ngày là sự kiện, "tài liệu này nói về thời điểm nào" là phán đoán.** Khi hỏi về một mốc quá khứ, KHÔNG được cắt bỏ tài liệu có ngày sau mốc đó — báo cáo tổng kết, biên bản hồi tố, văn bản đính chính đều ra đời sau nhưng nói về trước.
- **Ngưỡng chỉ chặn việc THÊM thì luôn an toàn.** Đặt sai chỉ làm thêm được ít hơn, không bao giờ làm mất cái đã có.

### NT3 — Không lưu thứ sẽ cũ đi

Thứ gì thay đổi vì con người thao tác — thành viên, nhóm, cấu trúc cây, loại Space — thì **không được nằm trong dữ liệu đã nạp**. Nó được tính tươi mỗi lần truy vấn.

Nguyên tắc này một mình giải quyết yêu cầu "quyền có hiệu lực tức thì" mà **không cần bất kỳ tiến trình đồng bộ nào** — không có gì để đồng bộ, vì không có bản sao nào tồn tại.

### NT4 — Chỉ có HAI bộ lọc cứng: quyền đọc, và tài liệu bị gỡ vì sai

Mọi thứ còn lại — nhãn phân loại, lĩnh vực, agent, ngày, trạng thái "hết hiệu lực" — đều **mềm**, chỉ được xếp thứ tự.

Đây là cách áp NT2 vào thực tế cho gọn: hai bộ lọc cứng ở bước 1 và 2 (bảng trên) đúng là hai sự kiện duy nhất mà hệ thống có. Thay vì mỗi lần lại phải xét một bộ lọc mới xem nó dựa trên sự kiện hay phán đoán, chỉ còn một câu — *chỉ quyền và quyết định gỡ của người mới được loại trừ*. Nó bịt trước cả những bộ lọc chưa ai nghĩ ra.

Hệ quả phụ đáng giá: yêu cầu về độ chính xác của việc gán nhãn giảm mạnh. Nhãn sai chỉ làm lệch thứ tự, không làm tài liệu biến mất khỏi kết quả.

> **Vì sao "tài liệu chờ Manager duyệt" KHÔNG trở thành bộ lọc cứng thứ ba.** Câu hỏi này nhất định sẽ được đặt ra: tiền kiểm ở Space riêng nghĩa là tài liệu chưa duyệt không được dùng để trả lời, mà đó là một loại trừ dựa trên sự kiện — sao không phải bộ lọc thứ ba?
>
> Vì tài liệu chờ duyệt **không có mặt trong kho** (Mục 5.2, GĐ1). Không có gì để lọc thì không cần bộ lọc. Nếu thiết kế chọn đường ngược lại — nạp trước rồi lọc lúc truy vấn — thì NT4 đã phải sửa thành ba. Đây là một ví dụ cho thấy chặn bằng cấu trúc rẻ hơn chặn bằng quy tắc, không chỉ an toàn hơn.

---

## 3. Ranh giới giữa hai service

|                     | **Ingestion v2 sản xuất**                                       | **Retrieval v2 sản xuất**                                              |
| ------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Trả lời câu hỏi     | *Tài liệu này nói gì và cấu trúc ra sao?* (ở phiên bản sau, thêm: *chỗ nhạy cảm nằm đâu* — xem 5.2 GĐ4)   | *Người này được biết gì, và trong đó cái gì trả lời được câu hỏi này?* |
| Đầu ra              | Hiểu biết về nội dung — **bất biến theo người hỏi**             | Phán quyết về quyền + câu trả lời có dẫn nguồn                         |
| Tuyệt đối không làm | Không quyết định ai đọc được gì; không che thông tin theo người | Không suy diễn thêm về nội dung ngoài những gì đã hiểu lúc nạp         |

Hai service **không chia sẻ quyết định nào**, chỉ chia sẻ một mô tả về nội dung. Đó là điều làm chúng thực sự độc lập và tráo vào được từng bên.

---

## 4. Nguyên tắc chi phối toàn bộ: kho là BẢN GHI LỊCH SỬ

Ba quyết định sản phẩm hội tụ về cùng một điểm:

- Gỡ tài liệu thì ẩn khỏi truy vấn nhưng **giữ dữ liệu**.
- Bản mới thì **thêm phiên bản**, không ghi đè.
- Câu hỏi có thể hỏi theo **một mốc thời gian bất kỳ** ("tại thời điểm DD/MM/YYYY ai là giám đốc").

→ **Thời gian là chiều hạng nhất của hệ thống.** Mặc định là hiện tại, nhưng phải lùi về được.

Hệ quả bắt buộc: **lớp quan hệ giữa các tài liệu là thành phần cốt lõi, không phải trang trí.** Một tài liệu tự nó chỉ biết ngày nó bắt đầu có hiệu lực — nó **không thể tự biết ngày nó hết hiệu lực**, vì điều đó do tài liệu ra sau quyết định. Không có lớp quan hệ thì câu hỏi theo mốc thời gian không trả lời được, dù mọi tài liệu đều nằm sẵn trong kho.


---

## 5. INGESTION V2

### 5.1 Bốn sản phẩm, hai tốc độ

| Sản phẩm | Phạm vi | Tốc độ |
|---|---|---|
| **Chữ nghĩa** — văn bản, bảng biểu, bố cục đọc ra được | trong một tài liệu | nhanh |
| **Đơn vị cắt + biểu diễn vector** | trong một tài liệu | nhanh |
| **Nhãn phân loại** | trong một tài liệu | nhanh |
| **Quan hệ với tài liệu khác** | **cần cả hàng xóm** | chậm, chạy ngầm, mở rộng dần |

Ba sản phẩm đầu chỉ cần bản thân tài liệu nên xong sớm. Sản phẩm thứ tư về bản chất phải đi hỏi xung quanh.

**→ Điều này tạo ra "cửa sổ chưa đối chiếu xong".** Ở nhánh hậu kiểm, tài liệu dùng được ngay khi upload; nhưng nếu quan hệ chưa tính xong thì bước kéo theo họ hàng (Mục 6.2) không có gì để kéo.

**Quyết định**: tài liệu **ĐƯỢC dùng để trả lời** trước khi quan hệ tính xong, nhưng câu trả lời phải **nói rõ là chưa đối chiếu xong**.

### 5.2 Chuỗi giai đoạn

**GĐ1 — Nhận và xác thực.** Tài liệu vào đúng một Space. Trạng thái ban đầu theo loại Space: Space riêng → chờ Manager duyệt; Space kế thừa/thông thường → dùng được ngay. Ở bước này người đưa tài liệu vào cũng được chọn *"đây là bản mới của tài liệu X"* nếu đúng như vậy — xem Mục 5.7.

> **⭐ Ở Space riêng, chuỗi giai đoạn DỪNG LẠI cho tới khi Manager duyệt — chốt 14/9/2026.**
>
> Chạy GĐ2, GĐ3 và GĐ5 (đọc file, cắt, gán nhãn — GĐ4 hoãn ở v1), rồi **dừng trước GĐ6 và GĐ7**. Kết quả nằm trong vùng làm việc riêng của Ingestion, **chưa ghi vào ba kho dùng chung**. Manager duyệt xong mới chạy nốt GĐ6, GĐ7 và ghi ra.
>
> Chọn điểm dừng ở đó vì bốn bước đầu chỉ cần bản thân tài liệu và cho người quyết thấy được nhãn phân loại lúc duyệt; hai bước sau mới là thứ chạm vào kho dùng chung và làm tài liệu tìm được.
>
> **Bất biến rút ra: mọi thứ trong kho dùng chung đều ĐÃ DÙNG ĐƯỢC.** Đây là lý do chọn đường này thay vì nạp trước rồi lọc sau: tiền kiểm được chặn **bằng cấu trúc** chứ không bằng một bộ lọc phải chạy đúng — cùng cách mà Mục 8.4 bắt ràng buộc bất khả xâm phạm phải là *bước* chứ không phải *câu*, và Mục 9.3 bịt cửa sau cá nhân hoá bằng cách cắt đường đọc.
>
> *Cái giá đã chấp nhận*: có độ trễ giữa lúc Manager bấm duyệt và lúc tài liệu tìm được; và chưa mở đường cho tính năng "Manager thử hỏi AI về tài liệu trước khi duyệt" — muốn có sau này thì phải xem lại quyết định này.

**GĐ2 — Đọc file.** ⚠️ **Đây bắt buộc là một ĐIỂM CẮM.** Mọi bước phía sau chỉ được nhận đúng ba thứ: *văn bản, cấu trúc, vị trí xuất xứ*. Chúng không được biết file gốc là định dạng gì. Nhờ vậy, thêm một định dạng mới về sau là cắm thêm một bộ đọc, không phải sửa các bước phía sau.

> **Một điều phải nói rõ để không ai hiểu nhầm điểm cắm này là phép màu**: bộ đọc OCR tương lai **bắt buộc phải bao gồm phân tích bố cục**, không chỉ trích chữ. Bản OCR trần trụi trả về văn bản mất hết cấu trúc điều/khoản — mà cắt theo cấu trúc (GĐ3) và dẫn nguồn theo vị trí (Mục 6.1) đều dựa vào cấu trúc đó. Nếu bộ đọc OCR không dựng lại được cấu trúc, tài liệu scan sẽ lặng lẽ rơi về cắt theo độ dài trong khi mọi thứ khác tưởng vẫn bình thường.

- **v1 chỉ xử lý văn bản đọc được chữ.** Danh sách định dạng nhận ở v1 — **CHỐT**:

| Nhận ở v1 | Ghi chú |
|---|---|
| **PDF có lớp chữ** | PDF chỉ chứa ảnh quét → từ chối, xem bên dưới |
| **.docx** | |
| **.txt** | |
| **.md** | |

Bốn định dạng này được chọn vì cả bốn đều giữ được cấu trúc điều/khoản mà GĐ3 dựa vào để cắt và Mục 6.1 dựa vào để dẫn nguồn theo vị trí.

- Tài liệu scan, ảnh chụp, tài liệu có cấu trúc (bảng tính, slide), file nén, và các định dạng văn bản cũ (.doc, .rtf, .odt) → **từ chối nhận, báo rõ chưa hỗ trợ**; đưa vào kế hoạch phát triển sau (khi đó bắt buộc dùng model OCR và các model phân tích).
- *Đã cân nhắc và không làm ở v1*: đếm số lần từ chối dù không giữ file — đó là con số để biết kho đang thiếu bao nhiêu và khi nào đáng đầu tư OCR. Bị loại cùng với quyết định "v1 chưa phát sự kiện đo lường nào" ở Mục 9.6.

> **⚠️ RỦI RO TỒN DƯ ĐÃ CHẤP NHẬN — kho có thể toàn bản nháp, còn bản ký ở ngoài. Chốt 14/9/2026: v1 không xử lý.**
>
> Ở Việt Nam, bản ban hành thật của một quyết định là bản in **đã ký và đóng dấu**, lưu lại dưới dạng ảnh quét. v1 từ chối ảnh quét. Người văn thư cần đưa tài liệu vào sẽ mở thư mục và đưa **bản Word dùng để in** vào thay — mà bản đó khác bản đã ký ở đúng những dòng người ký sửa tay trước lúc ký.
>
> Hậu quả: mọi câu trả lời về tài liệu đó dẫn nguồn tới bản nháp, **kèm tên văn bản và vị trí điều khoản, trông không khác gì một câu trả lời đúng**.
>
> Ba lý do vì sao thiết kế hiện tại không bắt được: không trường nào phân biệt bản ký với bản soạn thảo; vân tay nội dung (5.7) vô dụng vì bản ký không bao giờ vào tới hệ thống để mà so; và vì không đếm số lần từ chối nên **không ai biết kho lọt vào là một tập bị thiên lệch** — nó chỉ gồm những gì tình cờ còn tồn tại dưới dạng Word.
>
> [stated] Lý do chấp nhận: **phiên bản hiện tại chưa tính tới việc phân tích tài liệu scan.** Hai cách bù đã cân nhắc và cùng gác lại: bật lại việc đếm số lần từ chối, và thêm một trường cho người đưa tài liệu vào khai đây là bản ký hay bản soạn thảo. Cả hai nên được xem lại cùng lúc với việc quyết định đầu tư OCR.

**GĐ3 — Cắt thành đơn vị nhỏ.** Kết hợp **cắt theo cấu trúc văn bản** (điều / khoản / mục / tiêu đề) và **cắt theo ý nghĩa**. Cắt theo độ dài cố định bị loại vì làm giảm chất lượng phân tích và trả lời.

> **⭐ "Kết hợp" ở đây có thứ tự, không phải hai cách ngang hàng — làm rõ 14/9/2026.**
>
> **Cấu trúc quyết định ranh giới. Ý nghĩa chỉ được dùng để chia nhỏ TIẾP một khối cấu trúc quá dài.**
>
> Cụ thể ba điều cấm: không được **gộp** hai khối cấu trúc làm một mẩu; không được cắt **ngang** ranh giới điều/khoản; và khi một khối cấu trúc đủ ngắn thì nó là một mẩu, ý nghĩa không có việc gì ở đó.
>
> Vì sao phải nói rõ: câu "kết hợp" cho phép hai cách đọc, và người lập trình sẽ chọn một cách rồi đi tiếp mà không hỏi ai. Chọn sai thì hai thứ gãy cùng lúc — lý do nghiệp vụ của chính GĐ3 (*người ta sửa đổi văn bản theo điều khoản*), và quy tắc đơn vị ĐỌC ở Mục 6.1 vốn lấy **khối cấu trúc cha một cấp** làm đơn vị đọc; ranh giới mẩu mà không trùng ranh giới cấu trúc thì không có cha để lên.

> Lý do là nghiệp vụ, không phải kỹ thuật: **người ta sửa đổi văn bản theo điều khoản.** Khi đơn vị cắt trùng với đơn vị mà thực tế người ta sửa đổi, thì mọi việc về sau — đối chiếu, chỉ chỗ mâu thuẫn, dẫn nguồn — đều rơi vào đúng khớp.

*Hệ quả cần tính đến khi lập trình*: đơn vị cắt sẽ dài ngắn rất chênh nhau (một điều luật hai dòng, một mục phân tích ba trang). Cách so khớp phải chịu được điều đó thay vì giả định mọi mẩu xấp xỉ bằng nhau.

**GĐ4 — Quét chỗ nhạy cảm. ⛔ HOÃN Ở v1 — chốt 14/9/2026.**

Khi làm ở phiên bản sau: chỉ **đánh dấu vị trí**, không cắt bỏ vĩnh viễn. Xem Mục 7.

> **Vì sao hoãn.** Mục 7.1 chốt v1 không triển khai cơ chế che nào, nên vị trí chỗ nhạy cảm quét ra ở v1 sẽ **không có ai đọc** — một nhóm dữ liệu không người dùng là loại dễ mục nát nhất, hỏng mà không ai biết.
>
> Lập luận quyết định không phải là tiền quét, mà là: **quy định "cái gì là nhạy cảm" gần như chắc chắn sẽ đổi trước khi phiên bản sau làm che.** Bảng 4 tier hiện mới là đặc tả chưa triển khai, và chính Mục 5.5 ghi rằng việc quét lại được kích hoạt bởi đúng chuyện đó. Vậy dữ liệu quét ở v1 nhiều khả năng phải quét lại toàn bộ dù sao.
>
> **⚠️ Điều kiện bắt buộc để quyết định này rẻ khi đảo ngược: phải giữ toàn văn đã đọc ra.** Mục 5.5 ghi phạm vi của việc quét lại là *từng tài liệu*, và nó chỉ cần văn bản chứ không cần đọc lại file gốc, cũng không phải tạo lại vector. Trường giữ toàn văn nằm ở tài liệu 07 (`extracted_text`).
>
> *Đã cân nhắc và loại*: giữ GĐ4 để biết kho có bao nhiêu chỗ nhạy cảm — con số đó hữu ích khi quyết có đáng đầu tư che không, nhưng lấy được bằng một lượt quét mẫu lúc cần, không cần quét mọi tài liệu mọi lúc.

**GĐ5 — Gán nhãn phân loại và trích ngày.** **Máy gợi ý, người đưa tài liệu vào xác nhận.** Kết hợp với NT4 (nhãn chỉ là tín hiệu mềm) thì rủi ro gán nhãn sai gần như bằng không.

> **Nhãn lĩnh vực (domain) — chốt 23/9/2026 cho v1.** Ngoài *thể loại văn bản* (Quyết định, Nghị định…), máy gợi ý cả **lĩnh vực** của tài liệu (ví dụ tài chính, nhân sự). **Danh mục lĩnh vực cố định trong file cấu hình, theo từng bản cài của khách hàng** (R6) — máy chỉ được chọn trong danh mục đó, không tự đặt nhãn mới; người đưa tài liệu vào xác nhận như mọi nhãn khác. Đổi danh mục thì gán nhãn lại theo từng tài liệu (5.5), không phải tạo lại vector. *Cách còn lại — Admin quản lý danh mục qua giao diện, Backend gửi sang AI — để phiên bản sau.* **Còn mở, quyết lúc làm work-order qua `schema-guardian`:** nhãn lĩnh vực đi chung trường `category_labels` hay tách trường riêng (07 Mục 2.1).

Bước này cũng **trích ngày ký và ngày có hiệu lực từ chính văn bản** rồi đưa ra cho người xác nhận — cùng một khuôn, không thêm cơ chế mới. Trích được thì ngày mang nguồn *máy trích*; người sửa lại thì thành *người xác nhận*; không trích được và không ai điền thì rơi về *mặc định ngày nạp* và trục thời gian không tin nó. Xem Mục 6.4.

**GĐ6 — Tạo biểu diễn vector.** Ràng buộc bắt buộc: cấu hình mô hình biểu diễn phải **dùng chung một nguồn với Retrieval**, hoặc được kiểm tra khớp lúc khởi động. Đây là chỗ đóng lại một rủi ro thật đã phát hiện trong hệ thống hiện tại (hai service có file cấu hình độc lập; lệch mô hình mà cùng số chiều thì hỏng ngầm, không có lỗi nào báo).

**GĐ7 — Ghi và phát hiện quan hệ.** Xem 5.3.

### 5.3 Quan hệ giữa các tài liệu

**Nguồn quan hệ**: máy suy luận từ nội dung → **đưa ra đề nghị để Manager duyệt** (approve / reject). Manager cũng được **tự gắn liên kết** bằng tay.

> **⭐ Máy đề nghị KHÔNG chỉ dựa vào dẫn chiếu tường minh — chốt 14/9/2026.**
>
> Lý do là một sự thật về văn bản hành chính Việt Nam: **quyết định nhân sự mới thường không nhắc quyết định cũ.** Một quyết định bổ nhiệm chỉ căn cứ Điều lệ và Quy chế tổ chức; nó phủ định quyết định trước **bằng thực tế, không bằng câu chữ**. Nếu chỉ dò dẫn chiếu tường minh thì cả lớp văn bản này không có liên kết nào, bước kéo họ hàng im lặng đúng như thiết kế yêu cầu, và hệ thống trả lời tên người cũ — đúng nguyên văn ví dụ "ban giám đốc" mà Mục 6.2 dựng ra để cảnh báo.
>
> Vì vậy máy còn đề nghị quan hệ **sửa đổi/thay thế** dựa trên dấu hiệu: *cùng đối tượng được nói tới + cùng loại văn bản + ngày ban hành sau*. Vẫn là đề nghị, vẫn qua Manager duyệt, vẫn chịu ngưỡng tin cậy — **không thêm cơ chế nào mới**, chỉ mở rộng nguồn đề nghị.
>
> **Cách này chỉ khả thi vì ngày đã được sửa** (Mục 6.4, GĐ5): "ngày ban hành sau" là dấu hiệu trung tâm ở đây, mà trước khi tách ngày ký khỏi ngày hiệu lực và ghi nguồn của ngày thì ngày là rác nên dấu hiệu đó vô nghĩa.
>
> *Cái giá*: hàng việc của Manager nặng hơn. Ngưỡng tin cậy ở dưới là thứ điều tiết.

**⚠️ Quan hệ phải có PHÂN LOẠI, không chỉ có hay không.** Máy phải nói được *quan hệ loại gì* — sửa đổi/thay thế, phụ lục, dẫn chiếu, hay chỉ cùng chủ đề — và Manager duyệt cả loại quan hệ chứ không chỉ duyệt việc có liên kết. Lý do: quy tắc kéo họ hàng ở Mục 6.2 xử lý bốn loại này hoàn toàn khác nhau; không phân loại được thì quy tắc đó không chạy.

**Dẫn chiếu tường minh** trong văn bản ("sửa đổi Quyết định số X ngày Y"): vẫn qua Manager, nhưng **đánh dấu là chắc chắn** — hiện đầu hàng việc, duyệt nhanh.

**Phạm vi xét**: mở rộng dần, chạy ngầm — bắt đầu từ Space chứa tài liệu, mở rộng dần cho tới khi xác định không nên mở thêm. *(Cập nhật 23/9/2026: cây Space do Backend C.Brain sở hữu; GĐ7 hỏi Backend cấu trúc cây **ở mỗi vòng quét**, không dùng danh sách quyền của người upload — quan hệ là hiểu biết về nội dung, không phụ thuộc người (NT1). Backend không trả lời thì **hoãn vòng quét**, giữ trạng thái "đang mở rộng", và câu trả lời tự nói "chưa đối chiếu xong" như 5.1 — `10` Mục 7.1.)*

**Hai vai của một liên kết:**

| | Liên kết **chưa duyệt** | Liên kết **đã duyệt** |
|---|---|---|
| Kéo tài liệu vào ngữ cảnh trả lời | **Được**, tuỳ độ tin cậy của đề xuất | Được |
| Câu chữ trong câu trả lời | "có một văn bản khác có thể liên quan" | "văn bản này đã được sửa đổi bởi…" |
| Làm căn cứ để Manager đánh dấu hết hiệu lực | Không | Được |

> **Vì sao liên kết chưa duyệt vẫn được kéo**: theo NT2, máy suy luận là phán đoán nên không được **loại bỏ** — nhưng hoàn toàn được **thêm vào**. Kéo một văn bản liên quan vào ngữ cảnh là *thêm*. Ngưỡng độ tin cậy ở đây chỉ chặn việc thêm, nên đặt sai chỉ làm kéo được ít hơn, không bao giờ làm mất tài liệu.

> **Hệ quả tốt của việc ghép hai quyết định trên**: dẫn chiếu tường minh có độ tin cậy cao nhất nên được kéo vào ngay trong lúc vẫn đang chờ duyệt. Việc duyệt của Manager **không nằm trên đường găng** của các trường hợp chắc chắn — nó chỉ nâng cấp mức khẳng định của câu trả lời.

**Độ tin cậy và ngưỡng kéo — CHỐT.** Mỗi liên kết do máy đề xuất mang một **điểm tin cậy liên tục**, và có **một ngưỡng chung duy nhất** để được kéo vào ngữ cảnh. Ngưỡng đặt **rộng rãi lúc đầu**, siết lại khi thấy nhiễu thật: hậu quả hai chiều không cân nhau — kéo thừa một văn bản không liên quan chỉ tốn chỗ trong ngữ cảnh, kéo thiếu một văn bản thay thế thì ra câu trả lời sai mà không ai biết.

Không đặt ngưỡng riêng cho từng loại quan hệ: Mục 6.2 đã giới hạn sẵn loại nào được kéo, thêm ba tham số nữa chỉ là cơ chế thứ hai chồng lên cơ chế đã có.

**Giá trị khởi đầu: 0.3 trên thang 0–1** (chốt 14/9) — rộng rãi đúng như lập luận trên. Xem 07 Mục 3.2.

**Dẫn chiếu tường minh** vẫn được đánh dấu là chắc chắn, nhưng dấu đó dùng để **đổi câu chữ** trong câu trả lời và để duyệt nhanh — **không dùng để đổi ngưỡng**.

### 5.4 Chăm sóc tri thức — vòng lặp KM

Luồng "chăm sóc tri thức" (một trong ba luồng của kiến trúc mục tiêu) từ đây có cơ chế cụ thể, dùng đúng những vai và thao tác đã có, không thêm vai trò mới:

máy phát hiện xung đột / quan hệ → **đưa vào hàng việc của Manager Space đó** → Manager duyệt liên kết, hoặc đánh dấu tài liệu hết hiệu lực, hoặc gỡ tài liệu sai.

> **Đề nghị liên kết nối tài liệu ở hai Space khác nhau — chốt 23/9/2026.** GĐ7 quét dọc cây kế thừa, nên một đề nghị có thể nối tài liệu ở Space con với tài liệu ở Space cha. Đề nghị đó chỉ hiện cho **Manager đọc được cả hai đầu**, và **Admin luôn thấy** để không đề nghị nào nằm mãi không ai duyệt (PO chốt: Admin được xem tên văn bản ở mọi Space cho mục đích quản trị). Lúc duyệt, AI **kiểm lại** cả hai tài liệu còn trong phạm vi quyền của người duyệt. Hiện đề nghị cho Manager chỉ đọc được một đầu là tiết lộ tài liệu ngoài quyền (9.5). Chi tiết: `10` Mục 5.1–5.2.

Song song, khi một câu trả lời phải dựa trên các tài liệu có mâu thuẫn, hệ thống **cảnh báo ngay trong câu trả lời**, nêu rõ có nhiều nguồn và ngày của từng nguồn.

### 5.5 "Hiểu lại" — bốn việc khác nhau, đừng gộp

| Việc | Cũ đi khi nào | Phạm vi làm lại |
|---|---|---|
| Gán nhãn lại | cách phân loại của công ty thay đổi | từng tài liệu, không đụng chữ nghĩa và vector |
| Quét lại chỗ nhạy cảm *(chưa áp dụng ở v1 — GĐ4 hoãn)* | quy định về cái gì là nhạy cảm thay đổi | từng tài liệu; chỉ cần toàn văn đã đọc ra, không phải tạo lại vector |
| Biểu diễn lại | đổi mô hình hoặc đổi cách cắt | toàn kho — hiếm, đắt, nhưng có kế hoạch trước |
| **Tái cơ cấu quan hệ** | **ngay khi có tài liệu mới vào kho** | mở rộng dần từ Space chứa nó |

Ba việc đầu chỉ đổi khi ta chủ động đổi thứ gì đó, nên đoán trước được. Việc thứ tư là việc duy nhất mang tính liên-tài-liệu và bản chất không thể đứng yên.


### 5.6 Xoá vĩnh viễn

Ngoài "gỡ" (ẩn khỏi truy vấn, giữ dữ liệu) còn có **xoá vĩnh viễn** — xoá tài liệu cùng mọi dữ liệu đã nạp từ nó.

| | |
|---|---|
| **Ai làm được** | Admin, và Manager của Space chứa tài liệu. *Chốt 23/9/2026: lời gọi xoá mang `space_id`; hệ thống kiểm tài liệu thật sự nằm ở Space đó trước khi xoá, và **chỉ xoá theo `document_id`** — không theo vân tay nội dung, tên hay số hiệu, nên bản trùng khít ở Space khác (tài liệu riêng, 5.7) không bao giờ bị xoá theo* |
| **Xoá những gì** | Tài liệu, các đơn vị cắt, vector, và các liên kết quan hệ của nó |
| **Nhật ký giữ lại** | Việc đã xoá: ai, khi nào, tài liệu nào, lý do. **Không giữ nội dung** |

**Vì sao xoá không phá nguyên tắc "kho là bản ghi lịch sử".** C.Brain không phải nơi lưu trữ file của công ty — Space là *phạm vi tri thức AI được phép dùng*, không phải thư mục chứa file (Mục 0.1). Xoá một tài liệu khỏi C.Brain làm mất khả năng AI trả lời về nó, **không phải huỷ bản ghi của công ty**; file gốc vẫn ở nơi công ty lưu file.

**Xoá cả một Space — chốt 23/9/2026.** Khi Backend xoá một Space, AI xoá vĩnh viễn **từng tài liệu có `space_id` đó** theo đúng quy trình ở mục này, cùng tài liệu còn trong vùng đệm tiền kiểm và các mục hàng việc của Space. AI không tự suy ra Space con — cây là dữ liệu của Backend, xoá Space nào thì Backend báo riêng Space đó. Để việc này làm được, **Backend báo cho AI khi tạo Space** (AI chỉ ghi nhận `space_id` tồn tại, không lưu cây hay thành viên). Chi tiết và thứ tự gọi: `10` Mục 4.0.

**Ba loại xoá, và loại nào v1 làm được:**

| Loại | v1 xử lý được không |
|---|---|
| Đưa nhầm — nhầm file, file cá nhân, file của khách hàng khác | Được. Không có giá trị lịch sử nào để bảo vệ |
| Theo yêu cầu xoá dữ liệu cá nhân | Được, nhưng chỉ ở mức **cả tài liệu** — xem giới hạn bên dưới |
| Theo chính sách lưu trữ (hết thời hạn giữ) | Chưa bàn |

**⚠️ Hai giới hạn đã biết và chấp nhận:**

1. **Không xoá được từng trường, chỉ xoá được cả tài liệu.** Cách chuẩn để đáp ứng một yêu cầu xoá dữ liệu cá nhân là gỡ đúng phần dữ liệu cá nhân ra khỏi tài liệu. v1 không làm che ở mức trường (Mục 7) nên cũng không gỡ được từng trường — chỉ còn lựa chọn được ăn cả ngã về không. **Đây là hệ quả thứ hai của quyết định bỏ che PII ở v1**, ngoài hệ quả đã nêu ở Mục 7.3.
2. **Xoá không dọn lịch sử hội thoại.** Nội dung tài liệu bị xoá vẫn nằm trong lịch sử hội thoại của những người từng hỏi về nó (Mục 9.4 — lịch sử giữ nguyên kể cả khi quyền đổi). Xoá chỉ tác động tới kho tri thức và các câu trả lời **tương lai**. Việc dọn lịch sử hội thoại là một năng lực riêng, **chưa có ở v1**. *(Cập nhật 23/9/2026: lịch sử hội thoại nay do Backend C.Brain lưu — năng lực dọn, nếu làm, là việc của Backend. Trạng thái hội thoại ở 9.4 chỉ giữ `document_id`, nên tài liệu đã xoá tự rơi khỏi mạch ở lượt sau vì không còn gì để lấy lại.)*


### 5.7 Trùng lặp và bản mới của cùng một tài liệu

Hai việc này dùng chung một cơ chế: **vân tay nội dung**, tính ở GĐ2 sau khi đã đọc được chữ ra.

**Phải phân biệt trước, vì hai thứ hay bị gọi chung.** *Văn bản sửa đổi* là hai tài liệu riêng, cả hai đều là bản ghi thật của công ty (Quyết định 15 sửa Quyết định 10) — đó là **quan hệ**, xử lý ở 5.3. *Bản mới của cùng một tài liệu* là cùng một danh tính tài liệu được đưa vào lại (Sổ tay nhân sự bản 2 thay bản 1) — đó là **chuỗi phiên bản**, xử lý ở đây.

**Ai tuyên bố "đây là bản mới" — hai đường, người đi trước:**

1. **Người đưa tài liệu vào chọn ngay lúc upload.** Đã chọn thì máy không đoán nữa.
2. **Không chọn thì máy phân tích rồi đề nghị**, đúng khuôn GĐ5 (máy gợi ý, người xác nhận). Đề nghị được nhắc cho **cả người đưa tài liệu vào lẫn Manager của Space** — người upload biết rõ nhất nhưng có thể đã rời đi, Manager thì luôn còn đó; ai xác nhận trước cũng được.

Trong lúc đề nghị chưa được ai xác nhận, hai tài liệu vẫn là hai tài liệu rời. Đúng NT2: máy phán đoán thì được **thêm**, không được **gộp**.

**Bản cũ sau khi đã có bản mới**: vẫn tìm được. **Không thêm bộ lọc cứng thứ ba** (NT4) — bản cũ không sai, nó chỉ cũ. Nó tụt hạng qua trục thời gian, và **câu trả lời phải nói rõ là có bản mới hơn**. Nhờ vậy câu hỏi về quá khứ vẫn trả lời được, cùng lý do đã dùng cho "hết hiệu lực" ở 6.3.

**Bản mới thừa hưởng nhãn phân loại và quan hệ của bản cũ, dưới dạng gợi ý**, người xác nhận lại — nhãn theo khuôn GĐ5, quan hệ theo khuôn 5.3. Không phải gắn lại từ đầu, cũng không kế thừa mù khi nội dung đã đổi nhiều.

**Trùng lặp — CHỐT:**

| Tình huống | v1 làm gì |
|---|---|
| Trùng khít, **cùng Space** | **Báo trùng, không nạp lại** — chỉ đến nơi tài liệu đã có. Tránh một câu trả lời dẫn hai nguồn y hệt nhau |
| Trùng khít, **khác Space** | **Hợp lệ, không cảnh báo cho người upload.** Một tài liệu thuộc đúng một Space ở v1, và hai Space là hai phạm vi quyền khác nhau. Báo cho người upload biết "Space kia cũng có tài liệu này" chính là tiết lộ sự tồn tại của tài liệu ngoài quyền đọc của họ — ngược Mục 9.5. **Nhưng xem hai cơ chế bù bên dưới** |
| Gần giống, cùng Space | Không phải trùng lặp — đi đường "bản mới" ở trên |

> **⭐ Hai cơ chế bù cho bản sao xuyên Space — chốt 14/9/2026.**
>
> Quyết định "không cảnh báo cho người upload" ở trên đúng, nhưng nó để lại một hệ quả chưa được đếm lúc chốt: **cùng một tài liệu nằm ở năm Space là chuyện rất thường** — mỗi phòng đều muốn phòng mình tra được. Khi ra bản mới, chỉ Manager của một Space cập nhật; bốn bản kia vẫn nguyên. Hai người ngồi cạnh nhau hỏi cùng một câu và nhận hai con số khác nhau, **cả hai đều tin mình đúng**. Chuỗi phiên bản không với tới nhau được vì mỗi bản sao là một tài liệu riêng.
>
> **Cơ chế 1 — báo cho Manager của các Space giữ bản trùng.** Khi một tài liệu có bản mới, hệ thống đưa vào **hàng việc chăm sóc tri thức** (Mục 5.4) của Manager các Space đang giữ tài liệu trùng vân tay một mục: *"tài liệu này có thể đã lỗi thời"*.
>
> > **Không nêu Space nào, không nêu ai, không nêu ở đâu.** Đó là điều làm cơ chế này **không vi phạm Mục 9.5**: Manager chỉ biết hệ thống nghĩ tài liệu của họ có thể cũ, không biết thêm bất cứ điều gì về nơi khác. Cách phát biểu này là cả cơ chế — nếu câu thông báo nêu tên Space thì nó thành một ngoại lệ của 9.5 và phải quyết lại.
>
> **Cơ chế 2 — câu trả lời tự nói khi thấy hai bản.** Khi người hỏi đọc được nhiều Space và câu trả lời dùng **hai tài liệu trùng vân tay nhưng khác ngày**, nói rõ là có hai bản của cùng một tài liệu. Cơ chế này **không tiết lộ gì** vì người đó vốn đọc được cả hai, và gần như miễn phí vì vân tay đã có sẵn.
>
> **Giới hạn**: cơ chế 2 chỉ cứu người đọc được nhiều Space. Nạn nhân chính của tình huống này — người chỉ đọc một Space và nhận bản cũ — phụ thuộc hoàn toàn vào cơ chế 1, tức là phụ thuộc Manager có xử lý hàng việc hay không.

> **Vân tay nội dung giờ có ba người dùng**, không chỉ một: phát hiện trùng lặp, nhận diện bản mới, và hai cơ chế bù ở trên. Nó cần được đánh chỉ mục để tra ngược từ vân tay ra danh sách tài liệu.


---

## 6. RETRIEVAL V2

### 6.1 Ba đơn vị tri thức — đừng gộp làm một

| | Trả lời câu hỏi | Chốt |
|---|---|---|
| Đơn vị để **TÌM** | cái gì được đem so với câu hỏi | **mẩu nhỏ** — chỉ là kim chỉ đường, không phải bằng chứng |
| Đơn vị để **ĐỌC** | cái gì đưa vào cho bước viết câu trả lời | **phần liên quan của tài liệu + thông tin nhận dạng đầy đủ** (tên văn bản, ngày ký và ngày hiệu lực, vị trí) |
| Đơn vị để **DẪN NGUỒN** | người dùng kiểm chứng ở đâu | **tên văn bản + vị trí cụ thể bên trong** |

Ép ba đơn vị này phải giống nhau là chỗ phần lớn hệ thống RAG đi sai.

**Vì sao mẩu văn bản trần trụi không dùng làm đơn vị đọc được**: một mẩu ghi "ông A giữ chức giám đốc" mà không mang theo *văn bản nào, ban hành ngày nào* thì không đối chiếu được với cái gì cả — và nó trông y hệt mẩu ghi "ông C giữ chức giám đốc". Hai mẩu mâu thuẫn, không có cách nào phân xử.

### 6.2 Vòng trả lời — tìm rồi kéo theo họ hàng

> **Vì sao một lượt tìm theo độ giống là không đủ.** Hỏi "ban giám đốc gồm những ai": văn bản 1 (nêu đủ giám đốc và phó giám đốc) xếp hạng **cao hơn** văn bản 2 (chỉ đổi mỗi chức giám đốc). Hệ thống lấy văn bản 1, trả lời rằng ông A là giám đốc — **sai, im lặng, không cảnh báo**. Cách duy nhất chắc chắn tránh được là: sau khi có văn bản 1, **đi theo quan hệ đã biết** để kéo văn bản 2 về — và chấm điểm nó theo tài liệu nó gắn vào, chứ không theo độ giống của chính nó với câu hỏi.

Cần phân biệt hai thứ hay bị gọi chung là "tìm nhiều lượt":

- **Mở rộng theo quan hệ** — đường đi xác định, rẻ, đoán trước được thời gian. Theo NT2 luôn hợp lệ.
- **Tìm lại theo phán đoán của máy** — mạnh hơn với câu hỏi phức tạp, nhưng chi phí và độ trễ không đoán trước được. Chỉ được **thêm** ứng viên, không được bỏ bớt cái đã tìm ra.

**Chuỗi bước đã chốt:**

1. Xác định phạm vi đọc được của người hỏi — duyệt cây Space **tươi tại thời điểm hỏi** (người + nhóm + kế thừa một chiều xuống, cắt tại nhánh riêng). *(Cập nhật 23/9/2026: bước này do **Backend C.Brain** thực hiện và gửi danh sách Space kèm từng lượt hỏi; Retrieval áp danh sách đó làm bộ lọc cứng ngay tại nơi lấy dữ liệu, kể cả cho tài liệu kéo theo ở bước 3 — xem `10` Mục 1 và 6.1.)*
2. Tìm theo độ giống trong phạm vi đó, ở cấp mẩu nhỏ.
3. **Kéo theo họ hàng** — đưa vào các tài liệu nối với kết quả qua quan hệ đã biết; chúng được chấm điểm bằng cách **thừa hưởng điểm của tài liệu chúng gắn vào** chứ không theo độ giống với câu hỏi.
4. Lấy phần liên quan của từng tài liệu, kèm tên văn bản, ngày ký và ngày hiệu lực, vị trí — từ hồ sơ tài liệu, không từ dữ liệu cạnh vector. Ngày nào có nguồn là *mặc định ngày nạp* thì không được trình bày như ngày thật (Mục 6.4).
5. Chọn agent chuyên miền theo mục tiêu câu hỏi và vai trò người hỏi (Mục 8).
6. Sinh câu trả lời có dẫn nguồn; nêu cảnh báo nếu có tài liệu mâu thuẫn hoặc chưa đối chiếu xong.
7. **Ghi nhật ký** — ai hỏi, phạm vi quyền lúc đó, tài liệu nào vào ngữ cảnh, tài liệu nào bị loại và vì lý do nào (Mục 9.2).

*(v1 không có bước che thông tin cá nhân — xem Mục 7. Ở phiên bản sau, bước che sẽ nằm TRƯỚC bước 6, không phải sau. Mỗi lượt trong một cuộc trò chuyện đều chạy lại trọn bộ các bước trên — nội dung lượt trước không được dùng làm nguồn, xem Mục 9.4.)*

**Giới hạn kéo họ hàng.** 
Câu hỏi thật không phải *"đi mấy bước"* mà là **"quan hệ loại gì"**. Bốn loại quan hệ khác nhau rất xa về giá trị:

| Loại quan hệ | Ví dụ | Kéo tự động |
|---|---|---|
| **Sửa đổi / thay thế** | Quyết định 2 đổi chức giám đốc do Quyết định 1 quy định | **Có** — không kéo thì trả lời sai |
| **Phụ lục / kèm theo** | Bảng biểu đính kèm một quy chế | **Có** — tách ra thì cả hai đều vô nghĩa |
| **Dẫn chiếu / căn cứ** | Quyết định "căn cứ Quy chế tổ chức" | **Có, nhưng chỉ một bước** — không đi tiếp |
| **Cùng chủ đề** | Biên bản họp và quyết định ra sau nó | **Không** — tìm theo độ giống đã làm việc này rồi |

Dẫn chiếu bị giới hạn một bước vì mỗi văn bản hành chính thường "căn cứ" ba đến năm văn bản khác, và mỗi cái lại căn cứ tiếp — đi không giới hạn là bùng nổ theo cấp số nhân trong khi giá trị mang lại thấp.

**Với quan hệ sửa đổi: đi hết chuỗi, cả hai chiều, mọi nhánh.** Ngược lên để có bối cảnh gốc; xuôi xuống để biết tài liệu còn hiệu lực không (đây là chiều cứu ví dụ "ban giám đốc"); hai văn bản cùng sửa một bản gốc theo hai hướng thì đi cả hai. **Độ sâu do bản thân chuỗi quyết định, không do một con số ai đó chọn.**

**Cách xếp hạng họ hàng — thừa hưởng điểm, giảm dần theo chuỗi.**

> **Giá trị của một văn bản họ hàng không nằm ở chỗ nó giống câu hỏi bao nhiêu, mà ở chỗ nó gắn vào tài liệu nào.**

Bản sửa đổi của một tài liệu quan trọng thì quan trọng, dù bản thân nó nói rất ít. Nên họ hàng **không** được chấm theo độ giống với câu hỏi, mà **thừa hưởng điểm của tài liệu nó gắn vào, giảm dần khi đi xa trong chuỗi**.

Kiểm lại bằng hai tình huống:

*"Ban giám đốc gồm những ai"* — văn bản sửa đổi tự nó điểm thấp (chỉ nói mỗi chức giám đốc, không giống câu hỏi bằng bản gốc liệt kê cả ban), nhưng nó gắn vào tài liệu hạng nhất và là mắt xích gần nhất → thừa hưởng gần trọn điểm hạng nhất → **vào**.

*"Ban giám đốc và ban kiểm soát gồm những ai"* — hai chuỗi cùng lúc, thứ tự thành:

| | Tài liệu | Điểm từ đâu |
|---|---|---|
| 1 | Bản sửa đổi mới nhất của Quy chế tổ chức (hạng 1) | thừa hưởng hạng 1, mắt xích gần |
| 2 | Quyết định thay thế danh sách ban kiểm soát (gắn vào hạng 4) | thừa hưởng hạng 4, mắt xích gần |
| 3 | Bản sửa đổi cũ hơn của Quy chế tổ chức | thừa hưởng hạng 1, mắt xích xa → giảm |

Cách này **thay thế hai cơ chế từng được cân nhắc** và bị loại: *phần dành riêng cho họ hàng* và *ưu tiên trọn chuỗi của tài liệu hạng cao nhất*. Cả hai đều mù với việc chuỗi nào đáng hơn cho chính câu hỏi đang được hỏi. Kết quả: chỉ còn **một cái trần duy nhất và một quy tắc chấm điểm** — ít cơ chế hơn, ít chỗ sai hơn.

**Cái mất phải ghi rõ**: không còn gì được bảo đảm một chỗ. Trước đây phần dành riêng là một lời hứa cứng; giờ mọi thứ đều cạnh tranh.

Mô hình thừa hưởng điểm thu hẹp chỗ hở này, **nhưng chỉ ở phần trên của bảng xếp hạng**: con của một hai tài liệu đầu bảng gần như chắc chắn vào theo cha, còn con của tài liệu nằm giữa trần thì không.

> **⚠️ Sửa 14/9/2026 — bản trước viết "thừa hưởng gần trọn điểm của tài liệu cha", và câu đó SAI so với chính ví dụ ở ngay trên.** Ví dụ ba dòng đòi *thừa hưởng từ hạng 1 qua hai mắt xích* phải xếp **dưới** *thừa hưởng từ hạng 4 qua một mắt xích*. Ràng buộc đó ép hệ số giảm phải khá mạnh — không thể vừa "gần trọn" vừa thoả ví dụ. Đã chọn giữ ví dụ và sửa câu chữ; hệ số khởi đầu chốt ở **0.5**, xem tài liệu 07 Mục 3.2.
>
> **Và phép nhân này áp trên điểm ĐÃ CHUẨN HOÁ trên tập ứng viên, không phải điểm giống thô.** Điểm thô dồn cục trong dải hẹp; nhân vào đó thì con của hạng nhất tụt xuống dưới cả chục tài liệu không liên quan và cơ chế mất tác dụng.

Trường hợp lọt lưới xảy ra khi tài liệu cha không nằm ở đầu bảng — con bị chiết khấu là rơi ra ngoài trần.

**Đã cân nhắc và HOÃN**: một cơ chế báo cho người dùng biết *"tài liệu này đã có bản sửa đổi mà tôi chưa đưa vào"* — tra một lần trong lớp quan hệ, không chiếm chỗ trong trần.

> **⚠️ Lý do loại ban đầu đã được chứng minh là SAI trong một trường hợp — 14/9/2026.** Bản trước viết: *không báo, vì trường hợp này đã hiếm sau khi có mô hình thừa hưởng điểm*. Lập luận đó **chỉ đúng khi liên kết tồn tại** — thừa hưởng điểm không cứu được gì khi không có liên kết nào để thừa hưởng, mà đó chính là tình trạng của cả lớp văn bản nhân sự (xem 5.3).
>
> **Cách xử lý đã chọn là làm cho quan hệ được phát hiện (5.3), không phải dán cảnh báo.** Chữa gốc thay vì báo triệu chứng.
>
> **Cảnh báo vẫn để mở, kích hoạt có điều kiện.** Lý do chưa làm ngay: nếu bật với điều kiện *"tài liệu không có liên kết nào"* trong khi lớp quan hệ còn thưa, cảnh báo sẽ hiện ở gần như mọi câu trả lời — đúng lỗi mà Mục 6.5 đã chỉ ra khi đặt ngưỡng cho cảnh báo chạm trần: *một cảnh báo luôn bật thì tương đương không có cảnh báo, và tệ hơn là nó dạy người dùng bỏ qua*.
>
> **Điều kiện để xem lại**: phép đo tỷ lệ dẫn chiếu tường minh (Mục 10) cho thấy lớp quan hệ đã đủ dày.
**Rủi ro tồn dư đã chấp nhận**: trong những trường hợp hiếm đó, câu trả lời dựa trên một tài liệu đã có bản sửa đổi, và không có tín hiệu nào cho người đọc biết.

### 6.3 Bộ lọc và tín hiệu

| | Cứng (loại trừ tuyệt đối) | Mềm (chỉ xếp thứ tự) |
|---|---|---|
| Quyền đọc theo Space và nhóm | ✅ | |
| Tài liệu bị **gỡ vì sai** | ✅ | |
| Tài liệu **hết hiệu lực** | | ✅ (câu hỏi về quá khứ vẫn cần) |
| Tài liệu **đã có bản mới hơn** | | ✅ (xếp sau, và câu trả lời nói rõ — Mục 5.7) |
| Nhãn phân loại, lĩnh vực | | ✅ |
| Agent chuyên miền | | không lọc gì cả |
| Ngày hiệu lực | | ✅ (xếp thứ tự và trình bày) |

*(Ngoài hai lý do ẩn còn có **xoá vĩnh viễn** — xem Mục 5.6. Tài liệu đã xoá thì không còn gì để lọc.)*

**Hai lý do ẩn tài liệu phải là hai hành động khác nhau**: "gỡ vì sai / kém chất lượng" thì không dùng cho bất kỳ câu hỏi nào kể cả câu hỏi về quá khứ; "hết hiệu lực" thì vẫn dùng cho câu hỏi hỏi về thời điểm nó còn hiệu lực. Nếu gộp làm một, Manager gỡ một quyết định bổ nhiệm cũ vì nó đã hết hiệu lực sẽ vô tình làm câu hỏi "tháng 1/2024 ai là giám đốc" không trả lời được nữa.

### 6.4 Quy tắc dữ liệu đi kèm mẩu

> **Cạnh vector chỉ đặt thứ dùng để CẮT KHÔNG GIAN TÌM KIẾM, và những thứ đó phải bất biến. Mọi thứ dùng để ĐỌC và DẪN NGUỒN thì lấy sau, từ hồ sơ tài liệu.**

Cụ thể: Space, tenant, con trỏ về tài liệu và vị trí trong tài liệu — bất biến, nằm cạnh mẩu. Tên văn bản, số hiệu, ngày ký, ngày hiệu lực, trạng thái, toàn văn — nằm ở hồ sơ tài liệu, lấy sau khi đã có kết quả. *(Vị trí chỗ nhạy cảm cũng sẽ nằm ở hồ sơ tài liệu khi có — v1 không quét, xem 5.2 GĐ4.)*

> **Space nằm được cạnh mẩu vì ở v1 nó BẤT BIẾN.** Một tài liệu thuộc đúng một Space và **không có thao tác chuyển tài liệu sang Space khác** (Mục 1, sự thật 4). Đây là tiền đề, không phải chi tiết — nếu về sau thêm tính năng chuyển Space thì Space **thôi là bất biến**, và khi đó nó phải rời khỏi dữ liệu cạnh mẩu (tính lúc truy vấn như quyền), hoặc mọi lần chuyển phải kéo theo việc cập nhật lại toàn bộ mẩu của tài liệu đó. Không làm một trong hai thì phân quyền sẽ sai một cách im lặng — đúng kiểu hỏng mà Nguyên tắc 3 sinh ra để chặn.

Lý do: **ngày là trường cho phép chỉnh sửa.** Nếu chép nó vào cạnh từng mẩu thì sửa một lần phải cập nhật hàng trăm mẩu — đúng kiểu "lưu thứ sẽ cũ đi" mà NT3 cấm. Và vì ngày **không được dùng để loại bỏ** ở bước tìm (Mục 6.3 — ngày chỉ xếp thứ tự và trình bày), nó không cần có mặt lúc tìm.

> **⭐ HAI LOẠI NGÀY, KHÔNG PHẢI MỘT — chốt 14/9/2026.** Bản trước của tài liệu này gộp *ngày ký* và *ngày có hiệu lực* vào một trường duy nhất, mặc định bằng ngày đưa vào hệ thống. Đó là một lỗ hổng nghiêm trọng, tìm ra ở vòng phản biện theo góc pre-mortem.
>
> | | Là gì | Trích tự động |
> |---|---|---|
> | **Ngày ký** | ngày ban hành, ở đầu văn bản | **dễ** — văn bản hành chính Việt Nam có khuôn mẫu chuẩn hoá cho dòng này |
> | **Ngày có hiệu lực** | ở điều khoản thi hành cuối văn bản | **khó hơn** — phải định vị đúng điều khoản, và tránh nhầm với ngày của văn bản bị thay thế nhắc trong cùng câu |
>
> Gộp một trường là ép hai độ tin cậy rất khác nhau vào cùng một ô.
>
> **Mỗi ngày mang theo NGUỒN của nó**, ba giá trị: *máy trích từ chính văn bản* / *người xác nhận* / *mặc định ngày nạp*. Đối xứng với cách nhãn phân loại đã có người xác nhận.
>
> **Trục thời gian chỉ tin hai nguồn đầu.** Ngày thuộc nguồn thứ ba thì câu trả lời phải nói rõ là không biết ngày hiệu lực, thay vì đọc ra một con số trông hợp lý.
>
> Ngày nạp vẫn giữ, nhưng đọc đúng nghĩa của nó: nó là **cận trên** — tài liệu chắc chắn ban hành *trước* ngày đó — chứ không phải ngày ban hành.

> **Vì sao chỗ này quan trọng hơn vẻ ngoài của nó.** Bốn cơ chế trong tài liệu này đều đứng trên trường ngày: Mục 4 tuyên bố thời gian là chiều hạng nhất của hệ thống; Mục 6.3 dùng ngày để xếp thứ tự; Mục 5.4 in ngày của từng nguồn vào cảnh báo mâu thuẫn; Mục 8.4 dựng cảnh báo bằng bước so ngày. Nếu ngày mặc định bằng ngày nạp thì nạp hàng loạt tài liệu cũ trong vài ngày sẽ làm cả bốn cơ chế đứng trên một trường vô nghĩa — và **cảnh báo mâu thuẫn còn chạy ngược**: hai văn bản mâu thuẫn thật, nạp cùng buổi, ngày gần nhau nên không kích hoạt gì.

> **Trạng thái quan hệ cũng không nằm cạnh mẩu — đọc lúc truy vấn.** Một liên kết được Manager duyệt hôm nay và có thể bị gỡ tháng sau, nên nó đúng là thứ *sẽ cũ đi*. Chép trạng thái liên kết xuống cạnh mẩu thì mỗi lần Manager duyệt một liên kết là phải nạp lại toàn bộ mẩu của hai tài liệu — đúng kiểu NT3 sinh ra để cấm. Vì vậy bước kéo họ hàng (6.2, bước 3) **hỏi kho quan hệ tại thời điểm truy vấn**, và chỉ hỏi cho những tài liệu đã lọt vào hạng đầu nên chi phí có trần. Hệ quả: Manager duyệt hoặc gỡ xong thì **câu hỏi ngay sau đó đã thấy**, không phải chờ nạp lại gì.
>
> Cần tách việc này khỏi việc **máy phát hiện quan hệ mới** — đó là sản phẩm thứ tư ở Mục 5.1, chậm, chạy ngầm, mở rộng dần theo bản chất, và không cần tức thì. Chỉ thao tác duyệt/gỡ của con người mới cần.

**Ngoại lệ đã quyết**: nhãn phân loại được chép xuống cạnh từng mẩu để lọc nhanh một nhịp. Chấp nhận rằng khi đổi cách phân loại thì phải gán lại toàn bộ mẩu của tài liệu bị ảnh hưởng. *(Lưu ý: sau khi NT4 hạ nhãn xuống thành tín hiệu mềm, vai trò của bản sao này đổi từ lọc sang xếp hạng.)*

### 6.5 Trần số lượng tài liệu

**Cái trần này bản thân nó là một cơ chế loại trừ im lặng.** Nó lấy N tài liệu tốt nhất theo xếp hạng và bỏ phần còn lại — mà xếp hạng là *phán đoán*, còn Nguyên tắc 2 nói phán đoán chỉ được xếp thứ tự, không được loại bỏ. Không thể vá bằng cách bỏ trần đi, vì không có trần thì hệ thống không chạy được.

> Chỗ thoát nằm ở tinh chỉnh thứ hai của chính NT2: *điều làm phán đoán nguy hiểm là loại trừ **im lặng**.* Vậy **cái trần chấp nhận được khi và chỉ khi việc chạm trần là nhìn thấy được.** Đây không phải chuyện trải nghiệm — đó là điều kiện để NT2 còn đứng vững.

**Quyết định:**

| | |
|---|---|
| **Đếm theo** | **số tài liệu** — vì cái trần được công bố cho người dùng, nên con số phải là con số họ hiểu được. Đơn vị đọc vốn là *phần liên quan của tài liệu* (Mục 6.1) nên chênh lệch độ dài nhỏ hơn nhiều so với đếm cả tài liệu |
| **Khi chạm trần** | trả lời bình thường, và **nói rõ là đã giới hạn** |
| **Khi nào lời cảnh báo hiện ra** | khi **số ứng viên vượt trần một cách đáng kể** (bội số của trần), không phải mọi lần vượt |
| **Kéo theo họ hàng** | không có phần dành riêng — họ hàng cạnh tranh trong cùng cái trần, bằng cách **thừa hưởng điểm** của tài liệu nó gắn vào (Mục 6.2) |
| **Van an toàn theo khối lượng** | **không có** |

**Vì sao lời cảnh báo phải có ngưỡng.** Trong một kho vài nghìn tài liệu thì câu hỏi nào cũng có nhiều tài liệu liên quan hơn cái trần — nếu cứ vượt là báo thì cảnh báo hiện ra ở mọi câu trả lời. **Một cảnh báo luôn bật thì tương đương không có cảnh báo**, và tệ hơn là nó dạy người dùng bỏ qua — khi đó tính "nhìn thấy được" mất giá trị thật dù trên giấy tờ vẫn còn.

*Điểm yếu đã biết của ngưỡng theo bội số*: nó không phân biệt được "nhiều tài liệu nhưng đều kém liên quan" với "nhiều tài liệu đều đáng dùng". Chấp nhận, và chỉnh được bằng tham số.

**Vì sao họ hàng không cần phần riêng.** Ban đầu thiết kế dự tính dành riêng một phần trần cho họ hàng, vì trong ví dụ "ban giám đốc gồm những ai" thì văn bản sửa đổi xếp hạng thấp và sẽ bị đẩy ra ngoài. Nhưng quy tắc **thừa hưởng điểm** ở Mục 6.2 đã giải quyết đúng vấn đề đó ở tầng xếp hạng — văn bản sửa đổi vào được vì nó gắn vào tài liệu hạng cao, chứ không phải vì có ai giữ chỗ cho nó. Giữ thêm phần dành riêng chỉ là cơ chế thứ hai chồng lên, và nó còn mù với việc chuỗi nào đáng hơn cho chính câu hỏi đang được hỏi.

**Rủi ro tồn dư đã chấp nhận (không có van khối lượng).** Năm tài liệu mà mỗi phần liên quan đều dài thì vẫn có thể tràn. *Ràng buộc khi lập trình*: nếu xảy ra tràn thì phải **báo lỗi và ghi nhật ký**, tuyệt đối không cắt bớt âm thầm ở tầng dưới — cắt ngầm ở đó là loại trừ im lặng nằm dưới cả tầm nhìn của thiết kế, tệ hơn mọi trường hợp mà tài liệu này đang chống.

---

## 7. Che thông tin cá nhân

### 7.1 Phạm vi v1 — KHÔNG che gì

> **Quyết định (10/9/2026): v1 KHÔNG triển khai cơ chế che thông tin cá nhân nào. Kiểm soát hoàn toàn dựa vào phân quyền Space.**

Lý do: **tuyến phòng thủ thật không phải là che, mà là chỗ đặt tài liệu.** Bảng lương nằm trong một Space riêng chỉ nhân sự được gắn vào thì với mọi người khác tài liệu ấy không bao giờ được lấy ra — bộ lọc quyền đã chặn từ đầu; còn với người nhân sự thì họ được phép xem. Cả hai đầu đều không cần tới cơ chế che.

Cơ chế che theo trường chỉ thực sự phải chạy trong một tình huống: **một tài liệu chứa trường nhạy cảm lại đọc được bởi người không nên xem trường đó** — tức là khi tài liệu bị đặt sai chỗ. v1 chấp nhận không xử lý tình huống này.

### 7.2 Bảng 4 tier vẫn là đặc tả sản phẩm

Bảng PII 4 tier trong `04_Thiet_Ke_Phan_Quyen_PII.md` **không thay đổi** — nó là đặc tả cho các phiên bản sau. Tài liệu đó cần thêm một ghi chú phạm vi nói rõ v1 chưa triển khai, để sau này không ai tưởng đã xây rồi.

Ghi lại phân tích chi phí/hậu quả từng tier, để dùng khi quyết định phiên bản sau — **thứ đắt nhất lại là thứ hậu quả nhẹ hơn, thứ rẻ nhất lại là thứ hậu quả nặng nhất**:

| Tier | Chi phí nhận diện | Hậu quả nếu lọt |
|---|---|---|
| Công khai | 0 | không có |
| Tối thiểu có điều kiện | 0 — **không cần cơ chế nào**, vì điều kiện là "bất kỳ ai đọc được tài liệu", mà người đã nhận được tài liệu thì đương nhiên đọc được | không có |
| **Nâng cao** (lương, hồ sơ nhân sự, nhân thân) | **cao** — cần hiểu ngữ nghĩa, cần biết xuất xứ theo loại Space, cần ngữ cảnh riêng theo từng người hỏi | khó chịu, nhưng thường là chuyện nội bộ |
| **Tuyệt đối cấm** (số định danh, số tài khoản, số thẻ) | **rất thấp** — nhận ra bằng khuôn mẫu, không cần hiểu nghĩa | nặng: có thể chạm luật bảo vệ dữ liệu cá nhân; AI đọc số căn cước ra trong một buổi demo đủ để hỏng thương vụ |

Khi mở rộng ở phiên bản sau, đường cắt tự nhiên nằm giữa hai hàng cuối.

### 7.3 Rủi ro tồn dư đã chấp nhận

Khi một tài liệu chứa bảng lương bị đặt nhầm vào Space kế thừa, **v1 không còn lớp chặn nào** — ai đọc được tài liệu là thấy hết. Đây là rủi ro đã được cân nhắc và chấp nhận có ý thức, không phải sót.

Một cách bù rẻ hơn nhiều so với xây cơ chế che — **ĐÃ CHỐT 14/9/2026, và mở rộng thành hai chiều**: nói thẳng cho Manager biết hệ quả **ngay lúc họ thao tác với cờ kế thừa**. Tức là chuyển việc bảo vệ từ lúc chạy sang **lúc quyết định, nơi có người đang đứng đó** — cùng tinh thần với bộ kiểm lúc tạo agent ở Mục 8.5.

| Thao tác | Câu phải nói cho Manager |
|---|---|
| **Bật** kế thừa | mọi thành viên Space cha sẽ đọc được tài liệu trong Space này |
| **Tắt** kế thừa | **N người sẽ mất quyền đọc M tài liệu** |

> **Vì sao chiều TẮT mới là chiều nguy hiểm, và vì sao nó từng bị bỏ sót.** Bản trước chỉ nghĩ tới chiều bật, vì đó là chiều làm lộ dữ liệu. Nhưng chiều tắt gây ra một hỏng im lặng khác: Manager dọn cây Space cho gọn, hàng chục người mất quyền đọc mà **không ai được báo**. Họ vẫn hỏi như mọi khi và vẫn nhận câu trả lời trôi chảy có dẫn nguồn — từ mấy tài liệu cũ còn sót ngoài nhánh — nên có thể làm sai quy trình mới hàng tháng mà vẫn tin mình đúng. R1 không cứu được, vì hệ thống vẫn tìm ra *một* nguồn nên vẫn trả lời.
>
> **Giới hạn phải nói rõ: cách này không giải quyết trọn vấn đề.** Nó biến "không ai biết" thành "người bấm nút biết mình vừa làm gì" — phần rẻ và chắc chắn. **Người bị mất quyền vẫn không được báo.** Báo cho họ là một năng lực riêng, phụ thuộc hạ tầng thông báo chưa được xác định ở thiết kế nào, và còn treo.
>
> Đã cân nhắc và loại: để câu trả lời tự nói khi phạm vi vừa bị thu hẹp. Muốn biết phạm vi *vừa* đổi thì phải so với phạm vi cũ, tức là đọc nhật ký — mà Mục 9.2 chốt nhật ký chỉ Admin đọc khi có việc, không phải thứ phục vụ câu trả lời hàng ngày.
>
> **Việc thực thi thuộc tài liệu phân quyền, không thuộc tài liệu này** — hai service Ingestion và Retrieval không có phần nào trong thao tác quản lý Space.

### 7.4 Ràng buộc R4 giữ nguyên — đề xuất sửa đã được RÚT

Bản v1.0 của tài liệu này đề xuất sửa phát biểu R4 để cho phép che ở đầu ra. **Đề xuất đó đã được rút.** Vì v1 không che gì ở mức trường, mọi kiểm soát quyền đều nằm ở tầng lấy dữ liệu — đúng phát biểu R4 gốc. **Không cần sửa `01_Kien_Truc_Muc_Tieu.md`.**

Ghi lại kết luận phân tích để phiên bản sau không phải phát hiện lại: **nếu sau này làm tier "Nâng cao", việc che BẮT BUỘC phải xảy ra trước khi mô hình đọc**, vì hai lý do độc lập nhau:

1. **R2.** Che sau khi sinh nghĩa là gửi đoạn văn bản thô cho mô hình rồi mới che. Nếu mô hình sinh là dịch vụ ngoài — mà R5 (đổi mô hình bằng cấu hình) khiến đó là một cấu hình hợp lệ — thì thông tin cá nhân đã rời ranh giới trước khi bộ lọc kịp chạy.
2. **Tier "Nâng cao" phụ thuộc loại Space chứa tài liệu.** Vì mặc định quét toàn bộ, một câu trả lời có thể trộn tài liệu từ cả Space riêng lẫn Space kế thừa. Bộ lọc chạy sau khi mô hình viết xong chỉ nhìn thấy một khối văn bản và **không có cách nào biết câu nào rút từ loại Space nào** — mà đó chính là điều kiện quyết định có che hay không. Đây không phải chuyện khó, mà là **thiếu dữ kiện để quyết định**, và nó đúng kể cả khi mô hình chạy nội bộ.

Kèm theo: che ở đầu ra chỉ bắt được chuỗi ký tự, không bắt được suy luận. Mô hình đã đọc các con số lương thì vẫn xếp hạng được và nói ra kết luận, dù từng con số bị xoá.

## 8. Agent chuyên miền

### 8.1 Vai trò

Agent **chỉ tổng hợp thông tin từ nội dung đã tìm ra và trả lời câu hỏi**. Việc tìm nguồn tham khảo **hoàn toàn không phụ thuộc** vào agent nào đang được dùng.

Agent được chọn theo **mục tiêu của câu hỏi và vai trò người hỏi**, không theo tài liệu đang đọc — vì cùng một tài liệu, đọc từ các góc chuyên môn khác nhau sẽ có cách hiểu và cách trả lời khác nhau. Nhân viên kỹ thuật hỏi chuyện kỹ thuật khác với chính người đó hỏi chuyện nhân sự.

*(Việc dùng chức danh để chọn giọng trả lời không đụng gì tới quyết định bỏ trục phòng ban trong v1: ở đó chức danh bị loại khỏi việc **cấp quyền**; ở đây nó chỉ là thông tin tham khảo.)*

**Vì agent không siết phạm vi tìm, chọn agent là quyết định không có rủi ro** — chọn sai chỉ làm câu trả lời lệch giọng, không bao giờ làm mất tài liệu. Đây là điểm khác căn bản so với hệ thống hiện tại, nơi ràng buộc taxonomy của agent là bộ lọc cứng và chọn sai agent cho ra đúng 0 kết quả.

Khi không agent chuyên miền nào rõ ràng phù hợp: **dùng agent tổng quát, trả lời trên toàn phạm vi đọc được**.

### 8.2 Ai tạo, chọn lúc nào

- **v1: chỉ admin được tạo agent.** Mô hình "admin tạo dùng chung + người dùng tạo cho riêng mình" là hướng tương lai.
- **Người dùng chọn agent trước khi hỏi.**

*Lưu ý thiết kế*: hai lựa chọn này ăn khớp ở v1 — bắt chọn trước chỉ thành gánh nặng khi danh sách dài, mà v1 giới hạn chỉ admin tạo nên danh sách sẽ ngắn. Rủi ro chỉ xuất hiện khi cho người dùng tự tạo agent. **Vì vậy cần thiết kế v1 sao cho về sau thêm được đường tự động chọn agent mà không phải làm lại giao diện.**

*Ý bổ sung chưa chốt*: vì chọn agent không rủi ro, có thể cho **đổi agent sau khi đọc câu trả lời và viết lại từ bằng chứng đã có, không cần tìm lại** — thao tác rẻ, và làm cho danh sách dài không còn là gánh nặng.

### 8.3 Hai tầng hướng dẫn

| Tầng | Ai giữ | Trả lời câu hỏi |
|---|---|---|
| **Tầng hệ thống** — bất khả xâm phạm | Nhà cung cấp | *Được phép trả lời cái gì, theo cách làm việc nào* |
| **Tầng chuyên môn** | Admin của khách hàng (tương lai: cả người dùng) | *Trả lời như một người am hiểu lĩnh vực nào* |

Tầng chuyên môn giống việc **trang bị kỹ năng** cho agent, không phải quy định quy trình cho nó. Admin của khách hàng chạm được tầng trên, không chạm được tầng dưới.

### 8.4 ⭐ Ràng buộc bất khả xâm phạm phải là BƯỚC, không phải CÂU

Một hướng dẫn nằm trong prompt **không thể được bảo vệ bằng chính prompt**. Nếu tầng hệ thống chỉ là một đoạn chữ đặt trước đoạn chữ của admin, nó chỉ là *lời khuyên đặt sớm hơn*.

> **Ràng buộc nào thật sự bất khả xâm phạm thì phải là một BƯỚC trong quy trình, không phải một CÂU trong prompt.**

| Ràng buộc | Cách thực thi bắt buộc |
|---|---|
| Chỉ dùng tài liệu người hỏi được đọc | Lọc ngay khi lấy dữ liệu — mô hình không bao giờ nhìn thấy thứ ngoài quyền |
| Không có nguồn thì không trả lời (R1) | Không tìm được tài liệu nào thì **không gọi mô hình**, trả lời từ chối luôn |
| Che thông tin theo vai trò *(chưa áp dụng ở v1 — xem Mục 7)* | Khi làm ở phiên bản sau: lọc ngay lúc gom ngữ cảnh, **trước khi mô hình đọc** — lý do ở Mục 7.4 |
| Luôn dẫn nguồn | Kiểm đầu ra — không có dẫn nguồn hợp lệ thì không phát ra. *"Hợp lệ" — chốt 23/9/2026: mô hình chỉ được trỏ tới mã của đơn vị đọc **đã được đưa vào ngữ cảnh ở chính lượt đó**; AI tự dựng trích dẫn và tự cắt trích đoạn từ `extracted_text`, mô hình không tự viết. Có trích dẫn trỏ ra ngoài tập ngữ cảnh thì không phát. Vì bước kiểm này phải chạy trước khi phát bất kỳ chữ nào, v1 trả trọn câu trả lời một lần (`10` Mục 6.1)* |
| Cảnh báo khi tài liệu mâu thuẫn | Bước so ngày / quan hệ trước khi sinh, đưa cảnh báo vào như dữ kiện |

Nghĩa là "tầng hệ thống" chủ yếu **không phải là một prompt**, mà là các bước bao quanh mô hình. Phần còn lại nằm trong prompt chỉ hướng dẫn văn phong — và phần đó thì admin ghi đè cũng không gây hại. Cách này cũng xử lý trước nỗi lo về agent do người dùng tự tạo ở tương lai.

### 8.5 Chặn can thiệp ngay lúc tạo agent

**Dạng nhập tầng chuyên môn: biểu mẫu có cấu trúc + một ô ghi chú nhỏ** — không phải văn xuôi tự do.

Lý do: khả năng can thiệp bị chặn **bởi cấu trúc** chứ không bởi kiểm duyệt — không có ô nào nhận câu "bỏ qua bước che". Bộ kiểm chỉ còn phải soi một ô ghi chú, phạm vi hẹp nên chính xác hơn hẳn.

Trường biểu mẫu đề xuất: lĩnh vực chuyên môn; thuật ngữ và cách gọi ưu tiên; loại thông tin đưa lên trước; mức chi tiết; người đọc là ai; ví dụ câu trả lời mẫu.

**Khi bộ kiểm nghi ngờ**: cho tạo nhưng **đánh dấu chờ người duyệt** (bộ kiểm chỉ cảnh báo, người có thẩm quyền quyết). Vì v1 chỉ admin tạo agent nên **admin tự duyệt được, nhưng bắt buộc phải ghi lý do** — buộc dừng lại suy nghĩ và để lại dấu vết tra cứu được.

**Sáu loại câu bộ kiểm soi** (soi theo loại câu, không theo từ khoá):

1. Nói về việc có hay không trả lời khi tài liệu không đủ căn cứ
2. Nói về việc nới lỏng hoặc bỏ qua che thông tin, gồm cả yêu cầu trích nguyên văn không giới hạn
3. Nói về việc mở rộng phạm vi tài liệu hoặc dùng kiến thức ngoài nguồn
4. Nói về việc bỏ dẫn nguồn hoặc gộp nguồn cho gọn
5. Nói về việc suy đoán, điền vào chỗ trống khi tài liệu không nói
6. Tự nhận là hệ thống, hoặc yêu cầu bỏ qua hướng dẫn đặt trước nó

**Ba chỗ bộ kiểm không chạm tới được** — cần biết để không ỷ lại vào nó:

- **Can thiệp không nằm ở câu chữ.** "Luôn trả lời ngắn gọn, đi thẳng vào con số" là yêu cầu văn phong chính đáng, nhưng gặp câu hỏi về lương thì nó đẩy mô hình về phía nêu con số thay vì nói không hiển thị được.
- **Nội dung tài liệu cũng là một nguồn hướng dẫn.** Tài liệu do người dùng upload có thể chứa câu yêu cầu bỏ qua hạn chế, và nó đi thẳng vào ngữ cảnh cùng với bằng chứng. Bộ kiểm agent không đứng ở đường này.
- **Bộ kiểm sẽ bị áp lực nới lỏng dần** khi admin bị chối vài lần vì những câu họ cho là hợp lý.

---

## 9. Ghi nhật ký, hồ sơ cá nhân hoá và lịch sử hội thoại

### 9.1 Ba kho khác nhau — không được gộp

| | **Nhật ký điều tra** | **Hồ sơ cá nhân hoá** | **Lịch sử hội thoại** |
|---|---|---|---|
| Để làm gì | chứng minh chuyện đã xảy ra | trả lời hợp với người này hơn | người dùng tự đọc lại, hỏi tiếp mạch cũ |
| Của ai | công ty | người dùng | người dùng |
| Ai đọc | Admin, khi có việc | hệ thống, khi trả lời cho họ | chỉ chính họ |
| Nội dung | ai, lúc nào, tài liệu nào được xét và loại, vì lý do gì | biểu mẫu về đặc điểm con người | nguyên văn câu hỏi và câu trả lời |
| **Xoá được không** | **không** | **được** | **được** |
| Khi người đó nghỉ việc | vẫn giữ | đi theo | đi theo |

Lý do bắt buộc tách nằm ở hàng "xoá được không". Nhật ký điều tra mà xoá được thì mất giá trị làm chứng; dữ liệu cá nhân mà người dùng không xoá được thì không tôn trọng họ. Gộp làm một kho thì buộc phải hy sinh một trong hai.

**Phạm vi v1**: tập trung hoàn thiện **nhật ký điều tra** ở phía AI Services; **lịch sử hội thoại** đã chuyển hẳn sang Backend C.Brain — chốt 23/9/2026 (xem khung dưới). **Hồ sơ cá nhân hoá KHÔNG nằm trong kế hoạch phiên bản hiện tại — chốt 23/9/2026**; thiết kế ở 9.3 giữ lại làm đặc tả cho phiên bản sau.

> **Nơi lưu — chốt 23/9/2026.** Ba kho vẫn tách như bảng trên, nhưng không cùng nằm ở AI Services: **nhật ký điều tra** do AI Services (Retrieval) ghi và giữ; **lịch sử hội thoại** do **Backend C.Brain** lưu — Backend vốn đã lưu lịch sử chat, và AI Services **không giữ bản sao nào**. Lý do: có hai bản thì lời hứa "xoá được" ở bảng trên chỉ đúng một nửa — người dùng xoá trên giao diện, bản ở phía kia vẫn còn mà không ai biết. Chi tiết ở 9.4 và `10` Mục 6.1–6.2.

### 9.2 Nhật ký điều tra

**Vì sao cần, ngoài chuyện tuân thủ**: Nguyên tắc 2 và Nguyên tắc 4 chỉ nói *cái gì được phép loại trừ* — chúng không tạo ra cách nào để **biết sau sự việc rằng một lần loại trừ đã xảy ra**. Nhật ký chính là chỗ đó. Thiếu nó thì mọi lớp bảo vệ trong tài liệu này đều là lời hứa không kiểm chứng được. Nói cách khác, **nhật ký là thứ biến một lần loại trừ từ "im lặng" thành "nhìn thấy được"**.

Vì chỉ còn hai bộ lọc cứng (NT4), thứ cần ghi rất nhỏ. Mỗi lần truy vấn ghi lại:

- ai hỏi, lúc nào
- **phạm vi quyền tại thời điểm đó** — danh sách Space người đó đọc được
- tài liệu nào được đưa vào ngữ cảnh, và **con trỏ tới đúng những đơn vị cắt đã dùng**
- tài liệu nào bị loại, và theo lý do nào trong hai lý do cứng
- agent nào được dùng

**Không lưu nguyên văn câu hỏi, cũng không lưu nguyên văn câu trả lời** — CHỐT. Thay vào đó nhật ký giữ **con trỏ tới đúng những đơn vị cắt đã đưa vào ngữ cảnh**: đủ để tái hiện một sự cố (biết hệ thống đã đọc gì để trả lời), mà không tạo bản sao thứ hai của nội dung tài liệu.

> **Vì sao không lưu nguyên văn câu trả lời.** Nguyên văn đã nằm ở **lịch sử hội thoại** (9.1) — kho *của người dùng*, *xoá được*. Chép thêm một bản vào nhật ký là đặt nội dung tài liệu vào một kho **không xoá được**, mà cả người dùng lẫn thao tác xoá vĩnh viễn ở Mục 5.6 đều không với tới. Đó đúng là kiểu cửa sau mà 9.3 đã phải bịt một lần.

**Không ghi chuyện xếp hạng.** Thứ tự cao thấp thì vô hạn và không nói lên điều gì; chỉ ghi hai loại loại trừ cứng.

**Ai đọc**: chỉ Admin, và chỉ khi có việc. Nhật ký là công cụ điều tra khi có sự cố, **không phải bảng điều khiển xem hàng ngày** — nếu Manager đọc được nhật ký Space mình quản thì nó thành công cụ theo dõi nhân viên.

> **Về trường "phạm vi quyền tại thời điểm đó" — không nghịch với Nguyên tắc 3.** NT3 cấm lưu quyền ở **nơi quyền được dùng để ra quyết định**, vì ở đó nó sẽ cũ đi và cho phán quyết sai. Nhật ký thì ngược lại: nó ghi quyền **đã từng là gì**, như một sự kiện lịch sử. Không có trường này thì ba tháng sau không ai giải thích nổi vì sao một tài liệu bị loại.

### 9.3 Hồ sơ cá nhân hoá

> ⛔ **Không nằm trong kế hoạch phiên bản hiện tại — chốt 23/9/2026.** Toàn bộ mục này là đặc tả cho phiên bản sau; `08` không có hạng mục nào triển khai nó. Giữ lại vì hai thủ pháp của nó — *chỉ đọc câu hỏi, không đọc câu trả lời* và *biểu mẫu thay cho văn xuôi* — được **tái dùng** cho trạng thái hội thoại ở 9.4.

Không lưu toàn bộ lịch sử trò chuyện rồi đọc lại mỗi khi mở cuộc mới. Thay vào đó **tổng hợp thành một hồ sơ**, cập nhật chạy nền khi kết thúc phiên hoặc theo ngày.

Ưu điểm của cách dựng lại thay vì cộng dồn: mối quan tâm cũ **tự nhạt đi** thay vì chất đống mãi — hành vi đúng cho một hồ sơ về con người.

**⚠️ Bước tổng hợp này là một cửa sau, phải chặn bằng cấu trúc.** Để dựng hồ sơ, một mô hình phải đọc lại cuộc trò chuyện — mà câu trả lời trong đó chứa nội dung tài liệu. Nếu bản tóm tắt bắt được những câu kiểu *"người này đang xử lý hợp đồng với khách hàng Z, mức phí đã chốt là ..."* thì tri thức vừa được sao chép ra khỏi tài liệu và cất vào một chỗ **phân quyền Space không với tới**. Hôm sau gỡ người đó khỏi Space, trợ lý vẫn nhắc lại được — quyền "tức thì" bị phá qua cửa sau.

Theo Mục 8.4, dặn bộ tổng hợp "đừng nhớ nội dung tài liệu" là **không đủ**. Hai lớp chặn bằng cấu trúc, dùng cả hai:

1. **Bộ tổng hợp chỉ được đọc câu hỏi của người dùng, không được đọc câu trả lời của hệ thống.** Nội dung tài liệu đi vào cuộc trò chuyện qua đường câu trả lời; cắt đường đó thì không có gì để sao chép.
2. **Hồ sơ là một biểu mẫu có sẵn các trường**, không phải văn xuôi tự do — độ dài câu trả lời ưa thích, ngôn ngữ, thuật ngữ quen dùng, mảng chuyên môn. Không có ô nào để nhét tên khách hàng vào. Cùng thủ pháp đã dùng cho tầng chuyên môn của agent ở Mục 8.5.

> **Nguyên tắc**: cá nhân hoá được phép nhớ về **con người**, không được phép nhớ **tri thức**. Cái gì rút ra từ tài liệu thì mỗi lần cần đều phải lấy lại từ tài liệu và chịu kiểm quyền lại.

### 9.4 Lịch sử hội thoại

Có trong v1. **Giữ nguyên kể cả khi quyền đã đổi**: người dùng đã được phép xem vào thời điểm đó, và giữ lại bản ghi của một điều đã được nói với mình không phải là một lần tiết lộ mới.

> Đường phân định: **quyền tức thì áp dụng cho việc LẤY tri thức mới, không áp dụng cho việc đọc lại thứ mình đã được cho xem.**

**⚠️ Nhưng "người dùng đọc lại" khác hẳn "hệ thống dùng lại".** Khi ai đó hỏi tiếp trong cùng mạch — *"còn điều khoản thứ hai thì sao"* — nếu hệ thống lấy nội dung từ lượt trước thay vì lấy lại từ tài liệu, thì nó đang phục vụ tri thức **không đi qua kiểm quyền lần nào nữa**, và quyền đổi giữa chừng cũng không ai biết. Đó là một lần phục vụ mới, không phải một bản ghi cũ.

> **Quy tắc (phục vụ luôn R1):** mỗi lượt trả lời phải **lấy lại nguồn từ tài liệu**. Nội dung của lượt trước chỉ được dùng để **hiểu người ta đang hỏi gì**, không bao giờ dùng làm nguồn để trả lời.

Lượt trước cho biết "họ đang nói về hợp đồng nào"; còn nội dung hợp đồng thì phải lấy lại, và chịu kiểm quyền lại từ đầu.

> **⭐ Quy tắc này phải là một BƯỚC, không phải một CÂU dặn mô hình — làm rõ 14/9/2026.**
>
> Nếu cách thực thi là đưa cả lịch sử hội thoại vào cho mô hình rồi dặn *"đừng dùng nội dung lượt trước làm nguồn"*, thì đó đúng là thứ Mục 8.4 nói không bao giờ được bảo vệ bằng chính prompt. Mô hình đã đọc rồi thì nó dùng được, và không ai biết nó có dùng hay không.
>
> **Cách thực thi bắt buộc: bước hiểu câu hỏi và bước trả lời tách rời nhau.** Lịch sử chỉ đi vào bước thứ nhất — bước biến *"còn điều khoản thứ hai thì sao"* thành một câu hỏi đứng một mình. Bước sinh câu trả lời **chỉ nhận câu hỏi đã đứng một mình đó cộng với tài liệu vừa lấy lại**, không nhận lịch sử.
>
> Cắt đường như vậy thì nội dung lượt trước không có cách nào lọt vào câu trả lời mới — cùng thủ pháp đã dùng ở Mục 9.3 để bịt cửa sau hồ sơ cá nhân hoá.

> **⭐ Nơi lưu lịch sử và trạng thái hội thoại — chốt 23/9/2026.**
>
> **Backend C.Brain lưu lịch sử hội thoại; AI Services không giữ trạng thái giữa các lượt.** Mỗi lượt hỏi, Backend gửi sang: câu hỏi mới, **câu hỏi của K lượt gần nhất** (chỉ câu hỏi người dùng — **không** kèm phần chữ câu trả lời, chốt 23/9/2026 sau vòng phản biện độc lập; lý do ở dưới), và **trạng thái hội thoại** của lượt trước. AI trả về câu trả lời kèm trạng thái hội thoại mới; Backend lưu cả hai. K là tham số cấu hình.
>
> **Trạng thái hội thoại là một BIỂU MẪU, không phải bản tóm tắt văn xuôi** — dùng để nối mạch khi cuộc trò chuyện dài hơn K lượt. Ba nhóm trường: *tài liệu đang được nói tới* (chỉ định danh `document_id`), *chủ đề và đối tượng đang bàn*, *mạch câu hỏi người dùng đang theo đuổi*. **Không có ô nào chứa được con số, điều khoản hay trích đoạn.** AI dựng trạng thái này chỉ từ **câu hỏi của người dùng và định danh (`document_id`) của tài liệu được dẫn nguồn** — không đọc phần chữ câu trả lời, và **không ghi tên văn bản** vào trạng thái. Cả hai thủ pháp lấy nguyên từ 9.3.
>
> **Vì sao phải chặt như vậy.** Một bản tóm tắt tự do sẽ tích luỹ nội dung tài liệu qua nhiều lượt (*"mức phí đã chốt là ..."*). Gỡ người đó khỏi Space thì tài liệu không còn tìm được, nhưng con số vẫn nằm trong bản tóm tắt, đi vào bước hiểu câu hỏi, được viết lại vào câu hỏi đứng một mình, rồi tới thẳng bước sinh câu trả lời — quyền "tức thì" bị phá qua đường vòng. Đó đúng là cửa sau 9.3 đã phải bịt, chỉ khác là nằm trong một cuộc trò chuyện.
>
> **Vì sao câu hỏi các lượt trước cũng chỉ gồm câu hỏi của người dùng — chốt 23/9/2026.** Phần chữ câu trả lời chứa nội dung tài liệu đã diễn đạt lại (*"mức phụ cấp là 2 triệu"*). Đưa nó vào bước hiểu câu hỏi thì con số được viết lại vào câu hỏi đứng một mình, rồi tới bước sinh câu trả lời — cùng cửa sau ở trên, chỉ khác đường vào. Chỉ bỏ trích đoạn là không đủ. *Cái giá*: không nối được tham chiếu chỉ xuất hiện trong câu trả lời (ví dụ một tên riêng người dùng chưa từng gõ); bước hiểu câu hỏi nối mạch bằng các câu hỏi trước cộng trạng thái hội thoại.
>
> **Tài liệu đang được nói tới đi qua kiểm quyền lại mỗi lượt.** **Ngay đầu lượt sau — trước mọi bước khác, kể cả bước hiểu câu hỏi —** AI cho các `document_id` trong trạng thái qua **cùng bộ lọc quyền** với kết quả tìm mới (chốt 23/9/2026: lọc muộn hơn thì tên của tài liệu vừa mất quyền có thể lọt vào câu hỏi viết lại): còn quyền thì được **thêm** vào tập ứng viên (NT2 — phán đoán được thêm, không được loại) và chịu chung trần ở 6.5; mất quyền thì bị loại, không được nhắc tới (9.5), nhật ký ghi việc loại. Mạch được nối bằng cách **lấy lại tài liệu**, không bằng cách mang văn bản theo từng lượt — đúng quy tắc *mỗi lượt lấy lại nguồn* ở trên.
>
> *Cái giá đã chấp nhận*: mạch hội thoại dài chỉ được nối ở mức "đang nói về tài liệu nào, chủ đề gì", không nhớ chi tiết đã trả lời — chi tiết thì lấy lại từ tài liệu.
>
> Trí nhớ **xuyên nhiều cuộc trò chuyện** là hồ sơ cá nhân hoá (9.3) — khác hẳn trạng thái trong một cuộc, và không nằm trong phiên bản hiện tại.

### 9.5 Không nói về tài liệu ngoài quyền

Khi có tài liệu liên quan nhưng người hỏi không có quyền đọc: **không nói gì cả** — trả lời trong phạm vi họ đọc được, không đề cập tới phần còn lại.

**Hệ quả cho cảnh báo — chốt 23/9/2026:** mọi cảnh báo trong câu trả lời (mâu thuẫn, bản mới hơn, trùng bản khác ngày, chưa đối chiếu xong, ngày không đáng tin) **chỉ được tính từ tài liệu đã qua hai bộ lọc cứng của lượt đó**. Ví dụ: bản mới hơn nằm ngoài quyền hoặc đã bị gỡ vì sai thì không cảnh báo "đã có bản mới".

Cái giá đã chấp nhận: người dùng có thể tưởng tri thức đó không tồn tại, và không biết để đi xin quyền.

### 9.6 Số liệu đo lường — v1 chỉ chừa điểm cắm

**Số liệu đo lường là một dòng thứ tư, và không được lấy từ ba kho ở 9.1.** Cám dỗ tự nhiên là đọc nhật ký điều tra để dựng bảng theo dõi chất lượng. Không được: 9.2 đã định nghĩa nhật ký là công cụ điều tra, chỉ Admin đọc và chỉ khi có việc, **không phải bảng điều khiển xem hàng ngày**. Khối Đo lường mà đọc được nhật ký thì ranh giới đó mất, và nhật ký thành công cụ theo dõi nhân viên.

**Phạm vi v1 — CHỐT**: thiết kế **chừa sẵn điểm cắm** cho khối Đo lường — một dòng sự kiện ẩn danh, tách khỏi cả ba kho trên — nhưng **v1 chưa phát sự kiện nào**.

**⚠️ Ba hệ quả đã biết và chấp nhận:**

1. **Không chỉnh được tham số từ dữ liệu chạy thật.** Điểm mở #1 (mức giảm dần của thừa hưởng điểm) và #2 (giá trị trần) đều ghi là "cần đo trên dữ liệu thật" — không có dòng sự kiện thì không có dữ liệu đó. Hai tham số này sẽ phải đặt bằng phán đoán và chỉnh bằng quan sát thủ công.
2. **Không kiểm chứng được quy tắc thừa hưởng điểm có chạy đúng không** sau khi hệ thống đã chạy, và không thu được phản hồi người dùng trên từng câu trả lời.
3. **Không đếm số lần từ chối file chưa hỗ trợ** — mất con số để biết khi nào đáng đầu tư OCR (Mục 5.2).

## 10. Những gì CHƯA chốt

Danh sách này được rà lại sau bốn vòng phản biện độc lập (xem Phụ lục), rồi rà lại lần nữa ngày 12/9/2026 theo tiêu chí *"điểm này có quyết định trực tiếp một trường dữ liệu trong schema không"*.

### ✅ Chín điểm đã đóng (12/9 và 14/9/2026)

Tám điểm đầu được đóng trước khi rút schema, vì mỗi cái đều sinh ra trường dữ liệu — để mở thì schema phải rút hai lần. Điểm #13 đóng sau, ngày 14/9, khi xử lý các kịch bản pre-mortem.

| # | Điểm mở | Đã chốt thế nào | Viết ở |
|---|---|---|---|
| 3 | Nhật ký có lưu nguyên văn câu trả lời không | **Không.** Chỉ lưu con trỏ tới các đơn vị cắt đã dùng | 9.2 |
| 6 | Ngưỡng độ tin cậy kéo liên kết chưa duyệt | Điểm tin cậy liên tục, **một ngưỡng chung**, đặt rộng lúc đầu | 5.3 |
| 8 | Phát hiện tài liệu trùng lặp | Trùng khít cùng Space → báo, không nạp lại. Khác Space → hợp lệ, không cảnh báo | 5.7 |
| 9 | Bản mới của cùng một tài liệu | Người upload khai trước, không khai thì máy đề nghị cho cả người upload lẫn Manager. Bản cũ vẫn tìm được, xếp sau, câu trả lời nói rõ | 5.7 |
| 10 | Điểm cắm xuất số liệu cho khối Đo lường | **Chừa điểm cắm, v1 chưa phát sự kiện nào** — ba hệ quả đã ghi | 9.6 |
| 11 | Đếm số lần từ chối file chưa hỗ trợ | **Không làm ở v1**, theo cùng quyết định trên. ⚠️ 14/9: xem lại cùng lúc với quyết định đầu tư OCR — xem rủi ro tồn dư ở 5.2 | 5.2, 9.6 |
| 13 | Cách bù cho rủi ro tồn dư ở Mục 7.3 | **ĐÃ CHỐT 14/9**: cảnh báo cho Manager ngay lúc thao tác, **hai chiều** — bật và tắt kế thừa. Việc thực thi thuộc tài liệu phân quyền | 7.3 |
| 14 | Danh sách định dạng file nhận ở v1 | PDF có lớp chữ, .docx, .txt, .md | 5.2 |
| 16 | Cập nhật đồ thị quan hệ lan tới truy vấn thế nào | **Đọc kho quan hệ lúc truy vấn** → duyệt/gỡ có hiệu lực tức thì, không nạp lại | 6.4 |

### Bảy điểm còn mở

| # | Điểm mở | Ảnh hưởng |
|---|---|---|
| 1 | **Cách chấm điểm thừa hưởng cụ thể** — cơ chế đã chốt ở Mục 6.2. ✅ 14/9: **đã có giá trị khởi đầu** (0.5 trên điểm chuẩn hoá) kèm dấu hiệu nhận biết đặt sai — xem 07 Mục 3.2. Vẫn để mở vì con số thật cần đo trên dữ liệu thật | Không còn chặn việc lập trình |
| 2 | **Giá trị cụ thể của trần** — cơ chế đã chốt ở Mục 6.5. ✅ 14/9: **đã có giá trị khởi đầu** (trần 6 tài liệu, cảnh báo ở bội số 3) — xem 07 Mục 3.2. Vẫn để mở vì con số thật cần đo | Không còn chặn việc lập trình |
| 4 | **Trần và sàn độ dài đơn vị cắt** — cắt theo cấu trúc tạo ra đơn vị dài ngắn rất chênh nhau, gây thiên vị đoạn ngắn khi so khớp. ✅ 22/9: **trần đã có giá trị khởi đầu** (5000 ký tự Unicode — T2.3 bước 2/2, `cat_thanh_mau()` chia nhỏ TIẾP Chunk LÁ vượt trần tại ranh giới đoạn/câu an toàn) — xem 07 Mục 3.2/3.3, khoá `chunk_length_cap`. **Sàn vẫn để mở**, chưa có tham số nào | Không còn chặn việc lập trình (trần); sàn vẫn ảnh hưởng chất lượng tìm kiếm |
| 5 | **Gộp hạng khi agent mở rộng truy vấn** — với trần số lượng cố định, thêm từ khoá đồng nghĩa với đẩy tài liệu khác ra ngoài. Chỉ giữ được "chỉ thêm, không bớt" nếu chạy cả truy vấn gốc lẫn truy vấn mở rộng rồi gộp hạng | Cần trước khi cho agent góp vào cách tìm |
| 7 | ~~**Cơ chế truyền tải câu trả lời**~~ — ✅ **Đã chốt cho v1 ngày 23/9/2026: trả trọn câu trả lời một lần.** Bước kiểm dẫn nguồn ở 8.4 phải chạy xong trước khi phát bất kỳ chữ nào; phát từng chữ thì hoặc vi phạm ràng buộc đó, hoặc phải giữ lại toàn bộ rồi mới phát (mất lợi ích). Phát từng chữ để phiên bản sau, khi đã đo thời gian chờ thực tế | Không còn mở cho v1 |
| 12 | Có cho **đổi agent và viết lại** sau khi đọc câu trả lời không | UX |
| 15 | **Dọn lịch sử hội thoại khi xoá tài liệu** — cơ chế xoá vĩnh viễn đã chốt ở Mục 5.6, nhưng nội dung vẫn còn trong lịch sử hội thoại của người từng hỏi. Cần khi có yêu cầu xoá dữ liệu cá nhân thật sự | Chưa có ở v1, đã ghi là giới hạn |

**Không điểm nào trong bảy điểm còn lại sinh ra trường dữ liệu mới** — #4, #5, #7, #12 là tham số hoặc luồng xử lý, #1 và #2 là con số điền vào trường đã có, #15 là năng lực chưa làm.

### Ba phép đo rẻ và dứt điểm, chưa chạy

| Đo cái gì | Cách làm | Quyết định điều gì |
|---|---|---|
| Tỷ lệ văn bản có **dẫn chiếu tường minh** tới văn bản nó thay thế | Quét khoảng 1.000 file thật, đếm khớp mẫu "căn cứ / sửa đổi / thay thế" | Bước "kéo theo họ hàng" (6.2) có giá trị thật hay chỉ bảo vệ được thiểu số tài liệu. **Đây là điểm chưa phân định quan trọng nhất.** ⚠️ **Hiện CHƯA đo được** — chưa có kho tài liệu thật để quét. Hệ quả bắt buộc: thiết kế **không được dựa vào giả định tỷ lệ này cao**; khi lớp quan hệ thưa thì bước kéo họ hàng phải im lặng không làm gì, và nó không được coi là tuyến bảo vệ chính cho tới khi có số liệu. Đã đo sơ bộ trên 21 văn bản của tập thử T0.3 (16/9/2026): 19/21 có dẫn chiếu tường minh kèm số hiệu (~90%), 2/21 chưa chắc (chỉ bãi bỏ một phần). ⚠️ KHÔNG dùng số này để kết luận cho toàn kho — cả 21 văn bản đều là Luật/Nghị định/Thông tư cấp trung ương, thể loại này theo quy ước soạn thảo gần như luôn có điều khoản thi hành nêu rõ văn bản bị thay thế. Tỷ lệ cao có thể chỉ phản ánh đặc điểm thể loại này, chưa đại diện cho văn bản cấp thấp/nội bộ (quyết định, công văn, biên bản) mà kho thật sẽ còn chứa. Câu hỏi gốc — "bước kéo họ hàng có giá trị thật cho TOÀN kho hay chỉ bảo vệ thiểu số" — vẫn CHƯA đo được, vẫn cần kho ~1.000 file đa dạng thể loại |
| Mô hình có tự **suy luận thời gian** được không | 10 ca thử chứa mâu thuẫn phiên bản tài liệu | Bước tính sẵn trục thời gian có bắt buộc không |
| Độ trễ **xếp hạng lại** theo số lượng đầu vào | Đo A/B với các mức trần khác nhau | Đặt trần ở điểm mở số 2 |

## 11. Ảnh hưởng tới các tài liệu khác

| Tài liệu | Cần cập nhật |
|---|---|
| `01_Kien_Truc_Muc_Tieu.md` | **Không cần sửa gì.** (Bản v1.0 của tài liệu này từng đề xuất sửa R4; đề xuất đó đã được rút — xem Mục 7.4.) |
| `04_Thiet_Ke_Phan_Quyen_PII.md` | Thêm **ghi chú phạm vi**: bảng 4 tier là đặc tả sản phẩm cho các phiên bản sau; **v1 không triển khai cơ chế che nào**. Ghi rõ để sau này không ai tưởng đã xây rồi |
| `research/R11_Phan_Quyen.md` | ⚠️ **Thêm 14/9**: cảnh báo cho Manager **hai chiều** khi thao tác với cờ kế thừa — bật thì báo ai sẽ đọc được, tắt thì báo bao nhiêu người sẽ mất quyền (xem 7.3). Đây là nơi thực thi, không phải hai service. · Tiền kiểm / hậu kiểm **tuỳ loại Space** (thay cho tiền kiểm cho mọi trường hợp); **nhóm user là thực thể thật**; **tách hai lý do ẩn tài liệu** (gỡ vì sai ≠ hết hiệu lực) |
| `02_Ke_Hoach_Phat_Trien.md` | Link 1–2 dòng tới tài liệu này và tới `07_Hop_Dong_Du_Lieu_Schema_v2.md` |
| `07_Hop_Dong_Du_Lieu_Schema_v2.md` | Tài liệu con của tài liệu này — hợp đồng dữ liệu giữa hai service. Sửa gì ở đây mà đụng tới trường dữ liệu thì phải soi lại bên đó |
| `10_Hop_Dong_API_Backend_AI_Services.md` | Hợp đồng API giữa Backend C.Brain và AI Services (23/9/2026). Sửa gì ở đây mà đụng tới *ai tính quyền*, *ai lưu gì*, hay *thứ gì đi qua ranh giới* thì phải soi lại bên đó |
| Khung 6 nhóm công việc (ghi chú nội bộ về kiến trúc thông tin) | Thu hẹp mô tả Nhóm 1 — bỏ phân cấp phòng ban, chỉ còn gán vai trò trong từng Space |

## 12. Bước tiếp theo

**Schema đã rút xong** — xem `07_Hop_Dong_Du_Lieu_Schema_v2.md`, hiện không còn điểm mở nào thuộc về nó.

**Năm kịch bản pre-mortem ngày 14/9 đã xử lý xong cả năm.** Vòng phản biện độc lập theo góc *"giả sử xây đúng y đặc tả, chạy sáu tháng rồi nổ sự cố"* tìm ra năm cách hệ thống trả lời sai mà không ai biết, tất cả đều bắt nguồn từ hành vi con người và bản chất văn bản hành chính Việt Nam.

| | Kịch bản | Quyết định | Viết ở |
|---|---|---|---|
| **K1** | Bản ký đóng dấu là ảnh quét nên bị từ chối; người ta đưa bản Word soạn thảo vào thay, khác bản đã ký ở đúng những dòng sửa tay trước lúc ký | **KHÔNG XỬ LÝ Ở v1** — ghi thành rủi ro tồn dư đã chấp nhận. Lý do: phiên bản hiện tại chưa tính tới việc phân tích tài liệu scan. Hai cách bù (đếm số lần từ chối, khai bản ký hay bản soạn thảo) cùng gác lại, xem lại khi quyết định đầu tư OCR | 5.2 |
| **K2** | `effective_date` mặc định là ngày nạp → nạp hàng loạt tài liệu cũ làm trục thời gian thành rác, kéo theo bốn cơ chế đứng trên một trường vô nghĩa | **ĐÃ SỬA** — tách ngày ký khỏi ngày hiệu lực, mỗi ngày mang nguồn, trục thời gian chỉ tin ngày do máy trích hoặc người xác nhận | 6.4, GĐ5 |
| **K3** | Quyết định bổ nhiệm mới không nhắc quyết định cũ → không có quan hệ để kéo → trả lời tên người cũ | **ĐÃ SỬA — chữa gốc, không dán cảnh báo.** Máy đề nghị quan hệ dựa trên *cùng đối tượng + cùng loại + ngày ban hành sau*, không chỉ dựa vào dẫn chiếu tường minh. Cảnh báo "có thể đã bị sửa đổi" để mở, kích hoạt khi phép đo cho thấy lớp quan hệ đủ dày | 5.3, 6.2 |
| **K4** | Tắt cờ kế thừa làm hàng chục người mất quyền đọc mà không ai được báo | **ĐÃ SỬA MỘT NỬA** — cảnh báo cho Manager ngay lúc thao tác, hai chiều. Người bị mất quyền vẫn chưa được báo; phần đó phụ thuộc hạ tầng thông báo, còn treo. Việc thực thi thuộc tài liệu phân quyền | 7.3, điểm mở #13 |
| **K5** | Cùng một tài liệu ở nhiều Space; ra bản mới ở một nơi thì các bản kia vẫn cũ | **ĐÃ SỬA** — hai cơ chế bù: đưa vào hàng việc chăm sóc tri thức của Manager các Space giữ bản trùng vân tay (không nêu Space nào), và câu trả lời tự nói khi thấy hai bản trùng vân tay khác ngày | 5.7 |

### Việc còn lại

1. **Viết module mã nguồn** từ tài liệu 07. Đây là việc chính.
2. **Ước lượng công sức lại từ đầu** trên thiết kế thật (tài liệu này + tài liệu 07). Con số 14.5–15.0 MD trước đây chỉ tính thiết kế cơ bản, không còn đúng — phạm vi đã mở rộng nhiều lần kể từ đó.
3. Cập nhật các tài liệu ở Mục 11.
4. **Chạy phép đo tỷ lệ dẫn chiếu tường minh ngay khi có kho tài liệu thật** (Mục 10). Ngoài giá trị vốn có, nó còn là điều kiện để bật cảnh báo đang treo ở K3.
5. Xem lại K1 cùng lúc với quyết định đầu tư OCR.

---

## Phụ lục — Ghi chú về quá trình phản biện

Tài liệu này đã qua **năm vòng phản biện độc lập**: ba vòng trước khi lên v1.1, một vòng cách ly ngày 11/9, và một vòng pre-mortem ngày 14/9. Ba mục dưới đây kể lại theo thứ tự.

**Hai vòng đầu có sai lầm phương pháp**, và lỗi thuộc về đề bài: đề bài yêu cầu đối chiếu với **mã nguồn hiện tại**, trong khi đây là thiết kế xây lại từ đầu, cố tình không kế thừa cách làm cũ. Hậu quả là một số kết luận nghe rất chắc chắn nhưng thực chất dựa trên tham số của hệ cũ — ví dụ kết luận "chi phí không bùng nổ" dựa trên một giá trị giới hạn đọc từ code cũ, trong khi thiết kế mới chưa chọn giá trị nào.

**Vòng ba làm lại với thước đo đúng** — chấm theo sáu ràng buộc kiến trúc, tám sự thật user journey, bảng PII và mô hình phân quyền — và chính vòng này mới tìm ra ba phát hiện quan trọng nhất: lỗ hổng R2 khi che ở đầu ra, việc tier "Nâng cao" không thực thi được ở đầu ra, và việc vắng hẳn khối năng lực 10 và 11.

**Vòng bốn — cách ly (11/9/2026).** Người đánh giá chỉ được đọc tài liệu này, được tra cứu bên ngoài, cấm mở file khác của dự án. Mục tiêu kép: kiểm chất lượng thiết kế, **và** kiểm xem tài liệu có tự đứng được không khi giao cho người chưa biết gì về dự án. Ba kết quả: (a) tiền đề *"vì sao Space bất biến"* ở Mục 6.4 chưa từng được viết ra — đã bổ sung; (b) **thiếu hẳn đường xoá vĩnh viễn**, ba vòng trước không ai thấy — đã thành Mục 5.6; (c) NT2 ở dạng cũ là một luật không tuân được, chính thiết kế có hai chỗ vi phạm — đã phát biểu lại thành ba ý. Vòng này cũng xác nhận từ nguồn ngoài rằng việc tách đơn vị tìm khỏi đơn vị đọc, và lọc quyền trước khi lấy dữ liệu, đều là thực hành chuẩn của ngành.

**Bài học để lần sau không lặp lại**: khi đánh giá một thiết kế xây mới, mã nguồn hiện tại chỉ được dùng làm bằng chứng *"lỗi kiểu này đã từng xảy ra"* — không bao giờ được dùng làm chuẩn *"hệ thống phải hoạt động như vậy"*. Và khi nhận kết quả phản biện, cần phân loại phát hiện theo mức độ nhiễm: cái dựa trên tham số hệ cũ thì đáng ngờ, cái dựa trên hành vi con người và bản chất tài liệu thì đứng vững.

**Vòng năm — pre-mortem (14/9/2026), và đây là vòng tìm ra nhiều thứ nhất.** Người đánh giá hoàn toàn chưa biết gì về dự án và chưa thấy kết quả của bốn vòng trước. Đề bài không hỏi *"tài liệu có đầy đủ không"* mà hỏi: *giả sử đội lập trình đã xây đúng y hai tài liệu này, không sai một chữ, hệ thống chạy sáu tháng, rồi một sự cố nổ ra — kiểu sự cố mà người ta chỉ phát hiện muộn vì suốt sáu tháng đó hệ thống vẫn trả lời trôi chảy, có dẫn nguồn, không báo lỗi lần nào.* Đề bài yêu cầu ưu tiên kịch bản bắt nguồn từ **hành vi con người thật** và **bản chất văn bản hành chính Việt Nam**.

Kết quả: năm kịch bản, bốn ở mức CAO, toàn bộ đã được xử lý và ghi ở Mục 12. Hai điểm đáng rút ra:

1. **Góc nhìn quan trọng hơn người đánh giá.** Bốn vòng trước tìm ra lỗi *cấp tài liệu* — tên trường, kiểu dữ liệu, chiều quan hệ. Vòng này tìm ra lỗi *cấp thiết kế*, và phần lớn nằm ở tài liệu này chứ không ở tài liệu schema. Khác biệt nằm ở câu hỏi được đặt ra, không nằm ở ai trả lời. Nó xác nhận lại đúng bài học của hai vòng đầu, từ phía ngược lại.
2. **Một vòng phản biện hỏi lại chính người vừa kết luận thì gần như vô giá trị.** Vòng ba (hỏi lại người đã đánh giá ở vòng một, sau khi cho họ đọc phản biện) rút sáu trên mười phát hiện và không tìm được gì mới — hội tụ hoàn toàn về phía người phản biện. Đó không phải bằng chứng người phản biện đúng, mà là dấu hiệu của thiên hướng đồng thuận. **Vòng phản biện ngược phải giao cho người chưa thấy kết quả vòng trước.**

**Một lỗ hổng mà cả năm vòng đều bỏ sót**, tìm ra khi rà lại để áp quyết định: tài liệu schema không có trường nào chứa văn bản — không ở tài liệu, không ở mẩu. Cả năm vòng đều soi vào các trường *điều khiển* (quyền, trạng thái, quan hệ, phiên bản) vì đó là chỗ có quyết định thiết kế đáng bàn; chữ nghĩa thì hiển nhiên tới mức không ai nghĩ phải liệt kê. **Bài học: rà theo danh sách SẢN PHẨM của thiết kế, không chỉ rà theo danh sách trường đã viết** — mỗi sản phẩm ở Mục 5.1 phải truy được về ít nhất một trường.
