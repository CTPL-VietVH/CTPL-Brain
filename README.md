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

## Chạy AI Services thật (`packages/api/main.py`)

Điểm khởi động thật — kho thật (PostgreSQL, Qdrant), BGE-M3 thật, bộ chạy nền
thật. Đọc `packages/api/main.py` (docstring đầu file) để hiểu đầy đủ; dưới
đây là các bước để chạy.

### 1. Chuẩn bị hạ tầng (một lần)

```bash
cp .env.example .env               # rồi điền cho máy của bạn
tools/infra/qdrant.sh fetch && tools/infra/qdrant.sh start   # xem tools/infra/README.md
createdb "$CBRAIN_PG_DATABASE"     # nếu chưa có
```

Tải BGE-M3 về `CBRAIN_MODEL_HOME` (mặc định `.runtime/models`) — xem
`tests/t0_2_embedding/README.md`.

### 2. Tạo bảng + đóng dấu kho vector (một lần, hoặc sau khi đổi mô hình)

```bash
.venv/bin/python tools/provision/provision_stores.py
```

Lệnh này **là nơi duy nhất được phép `CREATE TABLE`/`create_collection`** —
idempotent, chạy lại bao nhiêu lần cũng an toàn. `packages/api/main.py` chỉ
**kiểm** những gì lệnh này tạo ra; thiếu thì dịch vụ từ chối khởi động, không
tự tạo ngầm.

### 3. Chạy dịch vụ

```bash
.venv/bin/uvicorn api.main:app_factory --factory --app-dir packages \
    --host 0.0.0.0 --port 8000 --workers 1
```

⚠️ **`--workers 1` không phải một lựa chọn hiệu năng — là bắt buộc**
(docs/10 §4.1 *"Một bản sao duy nhất"*): `packages/api/background.py` giả
định đúng MỘT tiến trình duy nhất đọc hàng đợi `ingestion_record`, nền tảng
mà `recover_orphans()` dựa vào lúc khởi động lại. Chạy `--workers 2` trở lên
làm một file có thể bị nạp hai lần mà không lỗi nào báo.

`--factory` bắt buộc: `app_factory()` chỉ kết nối kho/nạp model khi được gọi,
không phải lúc import module (để `import api.main` trong test không vô tình
kết nối PostgreSQL thật).

Kiểm dịch vụ đã sẵn sàng:

```bash
curl -s http://localhost:8000/v1/meta -H "X-Service-Key: $CBRAIN_API_SERVICE_KEY"
```

### 4. Bài thử đầu-cuối (kho thật, model thật)

```bash
.venv/bin/python tools/e2e/run_e2e.py
```

Tự dựng một Space, một Qdrant collection và một tiến trình `uvicorn` dùng
một lần (không đụng dữ liệu dev thật), nộp một tài liệu thật từ
`data/test-corpus-vn-admin/`, đợi tới `active`, kiểm hồ sơ + vector trong cả
hai kho, xoá Space, kiểm cả hai kho sạch lại — rồi dọn dẹp. In từng bước kèm
thời gian.
