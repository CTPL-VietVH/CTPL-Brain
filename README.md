# CTPL-Brain — Ingestion v2 & Retrieval v2

Xây lại từ đầu hai service lõi của C.Brain: **Ingestion v2** (đưa tri thức vào) và **Retrieval v2** (hỏi–đáp có dẫn nguồn).

## Bắt đầu từ đâu

👉 **Đọc [`CLAUDE.md`](CLAUDE.md) trước.** Cả người lẫn agent lập trình đều bắt đầu ở đó.

Nguồn chân lý nằm trong [`docs/`](docs/):

| File | Là gì |
|---|---|
| `docs/06_Thiet_Ke_Pipeline_Ingestion_Retrieval_v2.md` | Thiết kế — cơ chế nghiệp vụ và lý do đằng sau từng quyết định |
| `docs/07_Hop_Dong_Du_Lieu_Schema_v2.md` | Hợp đồng dữ liệu — tên trường, kiểu, nơi cư trú, ai được ghi |
| `docs/08_Ke_Hoach_Trien_Khai.md` | Kế hoạch — 32 hạng mục T0.1–T4.2 kèm điều kiện nghiệm thu |

`docs/` là **nhà chính thức** của ba tài liệu này. Sửa thiết kế thì sửa ở đây, không sửa bản nào khác.

## ⛔ Một điều cần biết ngay

Repo này **không kế thừa mã nguồn hệ cũ**. Mã nguồn v1 đặt ở repo khác và cố ý không có mặt ở đây. Khi tài liệu nhắc tới "hệ thống hiện tại", đó là dẫn chứng *một kiểu lỗi đã từng xảy ra*, không phải chuẩn phải theo. Chi tiết: `CLAUDE.md` Mục 0.

## Cấu trúc

```
docs/                 nguồn chân lý
config/               ba nhóm cấu hình, không chồng lấn
packages/schema/      module dùng chung — chặn cả hai service
packages/ingestion/
packages/retrieval/
tools/reindex/        nạp lại toàn kho khi đổi mô hình hoặc đổi cách cắt
tests/
```

Thứ tự: Nhóm 0 (nền) → Nhóm 1 (schema) → Nhóm 2 ∥ Nhóm 3 → Nhóm 4.
