# T0.2 — Biên bản nghiệm thu mô hình biểu diễn

**Điều kiện xong** (`docs/08` Phần D, T0.2): *mô hình chạy được trên phần cứng
đích, đo được độ trễ một lượt biểu diễn; và tên mô hình, số chiều, thước đo đã
nằm trong nhóm cấu hình hợp đồng ở T1.2.*

> ⚠️ **NGHIỆM THU MỘT PHẦN.** Vế *"trên phần cứng đích"* **chưa đạt được** —
> máy đích chính thức chưa chốt. Mọi số đo dưới đây là **TẠM**, đo trên máy dev,
> và **phải đo lại khi có máy đích**. Vế cấu hình hợp đồng thuộc T1.2, chưa làm.

Chạy lại: `.venv/bin/python -m pytest tests/t0_2_embedding/ -s -q`
Đo lại độ trễ: `.venv/bin/python tools/infra/measure_embedding_latency.py`

## Ba giá trị giao cho nhóm cấu hình HỢP ĐỒNG (dùng ở T1.2)

| Khoá | Giá trị | Căn cứ |
|---|---|---|
| `embedding_model` | `BAAI/bge-m3` | 08 T0.2 (chốt 14/9) |
| `embedding_dim` | `1024` | đã kiểm bằng ca thử |
| `distance_metric` | `cosine` (vector chuẩn hoá L2) | 07 Mục 3.1, S5 |

**Chưa ghi vào `config/`** — dựng ba nhóm cấu hình là T1.2, không phải T0.2.

## Kết quả kiểm hợp đồng — 9/9 đạt

| Kiểm | Kết quả |
|---|---|
| Số chiều | **1024** |
| Chuẩn L2 | `[1.0, 1.0, 1.0]` — sai số < 1e-4 |
| cosine == tích vô hướng | `0.814512`, lệch < 1e-6 |
| Ngữ cảnh **mặc định** | **8192 token** (tokenizer cũng 8192) |
| Khoản dài không bị cắt ngầm | 5.702 token, thêm câu ở cuối → vector đổi **0.0761** |
| Chỉ dense | đầu ra `(1, 1024)`; `colbert_linear.pt` và `sparse_linear.pt` **không tải về đĩa** |
| Tiếng Việt | gần nghĩa **0.7817** > khác nghĩa **0.4033** |
| Chạy ngoại tuyến | `HF_HUB_OFFLINE=1` — đạt (R2) |

### Hai chỗ phép thử được viết chặt hơn mức tối thiểu

**1. Ngữ cảnh 8192 được canh ở MẶC ĐỊNH, không phải ở lệnh ghi đè.**
Bản đầu tôi đặt `max_seq_length = 8192` trong `conftest` rồi kiểm — nhưng như
vậy chỉ chứng minh lệnh ghi đè của chính mình chạy. Đã bỏ ghi đè: mô hình nạp
lên với mặc định nào thì kiểm mặc định đó. Hôm nào thư viện hoặc mô hình hạ
mặc định xuống, ca thử đỏ ngay thay vì cắt đuôi văn bản trong im lặng.

**2. "Chỉ dense" là sự thật vật lý, không phải ghi chú.**
Hai đầu `colbert_linear.pt` và `sparse_linear.pt` **cố ý không tải về**. Muốn
bật thêm dạng biểu diễn thì phải tải thêm file — một hành động nhìn thấy được,
đúng với việc bật thêm là *đổi cấu hình mô hình, kéo theo nạp lại toàn kho*
(06 Mục 5.5).

## ⚠️ Phát hiện: trần ngữ cảnh có thật, và nó IM LẶNG

Lúc đo độ trễ, một đầu vào 8.282 token cho ra:

```
Token indices sequence length is longer than the specified maximum sequence
length for this model (8282 > 8192). Running this sequence through the model
will result in indexing errors
```

— rồi `encode` **vẫn chạy bình thường** trên phần đã bị cắt. Đã kiểm lại bằng ca
thử riêng: với đầu vào 12.352 token, thêm hẳn một câu vào cuối làm vector đổi
**đúng 0.00e+00** — tức đuôi bị vứt sạch.

**Hệ quả bắt buộc cho GĐ3 (T2.3):** một mẩu vượt 8192 token sẽ mất đuôi mà
không ai biết. Đây là căn cứ kỹ thuật cộng thêm cho **điều cấm số 25** — cấu
trúc quyết định *ranh giới*, nhưng khối cấu trúc quá dài **bắt buộc** phải chia
nhỏ tiếp, giờ không chỉ vì "so khớp loãng" mà còn vì có một cái trần cứng.

## Độ trễ một lượt biểu diễn — ⚠️ SỐ LIỆU TẠM

Máy dev: Apple M2 Pro, 16GB, macOS 26.6.2, Python 3.12.13 **arm64**, torch 2.14.0.

| Đầu vào | Token | CPU (trung vị) | MPS (trung vị) |
|---|---|---|---|
| Câu hỏi (1 câu) | 15 | 74,5 ms | **26,3 ms** |
| Một Khoản | 71 | 90,6 ms | **27,0 ms** |
| Điều dài (~20 Khoản) | 1.382 | 826,1 ms | **246,0 ms** |
| Sát trần ngữ cảnh | 7.799 | 10.268 ms | **2.832 ms** |
| Lô 16 Khoản | — | 488 ms (30,5 ms/mẩu) | **164 ms (10,3 ms/mẩu)** |

**MPS nhanh hơn CPU khoảng 3,3–3,6 lần.**

### Vì sao phải dựng venv ARM native

`python3` mặc định trên máy này là **x86_64 chạy qua Rosetta** (Homebrew Intel).
Dưới Rosetta `torch.backends.mps.is_available()` là **False** — không có tăng
tốc GPU, và số đo sẽ sai lệch nhiều lần theo hướng bi quan. Đã dựng riêng
`.venv` bằng CPython 3.12.13 **aarch64** qua `uv`; `platform.machine()` trả
`arm64` và MPS khả dụng.

## Cái biên bản này KHÔNG khẳng định

- **Không** khẳng định độ trễ trên phần cứng đích — máy đích chưa chốt.
- **Không** khẳng định chất lượng tìm kiếm tiếng Việt. Phép thử ngữ nghĩa ở đây
  là *phép thử tỉnh táo* trên 3 câu, không phải phép đo chất lượng. Đo chất
  lượng cần kho tài liệu thật, và `docs/06` Mục 9.6 chốt v1 không phát sự kiện
  đo lường nào.
