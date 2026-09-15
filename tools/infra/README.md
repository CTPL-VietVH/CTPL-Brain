# Dựng hai kho trên máy mới

> **Ba kho trong `docs/06` và `docs/07` là ba kho LOGIC. Vật lý chỉ có hai.**
> Mọi câu "kho đồ thị" đọc là *lớp quan hệ trong PostgreSQL*.

## 1. Cấu hình kết nối

```bash
cp .env.example .env     # rồi điền CBRAIN_PG_USER cho máy của bạn
```

`.env` **không được commit**. Thiếu một khoá thì mọi thứ ở đây **từ chối chạy** và
báo rõ thiếu khoá nào — không có giá trị mặc định trong mã (`CLAUDE.md` Mục 4
quy tắc 2).

Các khoá ở `.env` là tham số **triển khai** (địa chỉ kho, đổi theo từng bản cài
của từng khách hàng — R6). Chúng **không chồng lấn** với ba nhóm cấu hình ở
`config/`, vốn chứa tham số điều chỉnh và hợp đồng mô hình.

## 2. PostgreSQL

Cần sẵn một PostgreSQL đang chạy (mã hoá **UTF8** — bắt buộc, vì vị trí đầu/cuối
đếm theo ký tự Unicode).

```bash
createdb "$CBRAIN_PG_DATABASE"
```

## 3. Qdrant

```bash
tools/infra/qdrant.sh fetch     # tải binary native đúng kiến trúc máy
tools/infra/qdrant.sh start
tools/infra/qdrant.sh status
tools/infra/qdrant.sh stop
```

Binary và dữ liệu nằm ở `.runtime/qdrant/` (đã `.gitignore`). Phiên bản được
**ghim** ở `CBRAIN_QDRANT_VERSION` để mọi máy dựng ra cùng một kho.

> ⛔ **Qdrant mặc định lắng nghe `0.0.0.0`** — mở ra mọi giao diện mạng. Kịch bản
> này ghim về `CBRAIN_QDRANT_BIND_HOST` (mặc định `127.0.0.1`) vì **R2 đòi mặc
> định chạy nội bộ**. Có ca thử canh điều này.

## 4. Nghiệm thu

```bash
.venv/bin/python -m pytest tests/t0_1_stores/ -s -q
```

Kết quả và ba điều phải đọc kèm: [`tests/t0_1_stores/README.md`](../../tests/t0_1_stores/README.md).
