"""Đo độ trễ một lượt biểu diễn của BGE-M3.

⚠️ **SỐ LIỆU TẠM.** Máy đích chính thức CHƯA CHỐT. Mọi con số ở đây đo trên máy
dev hiện có và **phải đo lại khi có máy đích** — `docs/08` T0.2 đòi *"mô hình
chạy được trên phần cứng đích, đo được độ trễ một lượt biểu diễn"*, và máy dev
không phải phần cứng đích.

Chạy: .venv/bin/python tools/infra/measure_embedding_latency.py
"""

from __future__ import annotations

import os
import pathlib
import platform
import statistics
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ["HF_HOME"] = str(REPO_ROOT / ".runtime" / "models")
os.environ["HF_HUB_OFFLINE"] = "1"

MODEL_NAME = "BAAI/bge-m3"
ROUNDS = 20
WARMUP = 3

# Ba cỡ đầu vào phản ánh ba thứ hệ này thật sự đem đi biểu diễn.
CAU_HOI = "Ai có thẩm quyền phê duyệt kế hoạch lựa chọn nhà thầu?"
KHOAN = (
    "1. Khi phát hiện hành vi vi phạm quy định của pháp luật về đấu thầu, "
    "người có thẩm quyền hoặc chủ đầu tư có trách nhiệm tạm dừng ngay các hoạt "
    "động có liên quan và lập biên bản ghi nhận sự việc, trong đó nêu rõ thời "
    "điểm phát hiện, nội dung vi phạm, tổ chức và cá nhân có liên quan.\n"
)


def _median_ms(fn, rounds: int = ROUNDS) -> tuple[float, float]:
    for _ in range(WARMUP):
        fn()
    samples = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    return statistics.median(samples), samples[int(len(samples) * 0.95) - 1]


def main() -> None:
    import torch
    from sentence_transformers import SentenceTransformer

    print("=" * 78)
    print("ĐO ĐỘ TRỄ BIỂU DIỄN — BGE-M3")
    print("=" * 78)
    print(f"⚠️  SỐ LIỆU TẠM: máy đích chưa chốt, phải đo lại khi có máy đích.")
    print(f"máy dev   : {platform.machine()} / {platform.processor() or 'Apple Silicon'}")
    print(f"python    : {platform.python_version()}  torch: {torch.__version__}")
    print(f"MPS       : {'có' if torch.backends.mps.is_available() else 'không'}")
    print()

    dau_vao = {
        "câu hỏi (1 câu)": CAU_HOI,
        "một Khoản": KHOAN,
        "Điều dài (~20 Khoản)": KHOAN * 20,
        # ~7.800 token: sát trần 8192 mà KHÔNG vượt. Vượt trần thì bị cắt đuôi
        # và phép đo sẽ đo nhầm một đầu vào ngắn hơn nó tưởng.
        "sát trần ngữ cảnh": KHOAN * 113,
    }

    for device in ("cpu", "mps"):
        if device == "mps" and not torch.backends.mps.is_available():
            continue
        model = SentenceTransformer(MODEL_NAME, device=device)
        print(f"--- thiết bị: {device.upper()} "
              f"(ngữ cảnh mặc định {model.max_seq_length} token) ---")
        for nhan, text in dau_vao.items():
            n_tok = len(model.tokenizer.encode(text))
            med, p95 = _median_ms(
                lambda t=text: model.encode([t], normalize_embeddings=True))
            print(f"  {nhan:<24} {n_tok:>6,} token | trung vị {med:8.1f} ms | p95 {p95:8.1f} ms")

        # Nạp theo lô — hình dạng thật của Ingestion GĐ6
        lo = [KHOAN] * 16
        med, _ = _median_ms(lambda: model.encode(lo, normalize_embeddings=True), rounds=10)
        print(f"  {'lô 16 Khoản':<24} {'':>6}       | trung vị {med:8.1f} ms "
              f"({med / 16:.1f} ms/mẩu)")
        print()

    print("=" * 78)
    print("⚠️  NHẮC LẠI: đây là số liệu TẠM trên máy dev, KHÔNG phải nghiệm thu")
    print("    phần cứng đích. docs/08 T0.2 đòi đo trên phần cứng đích.")
    print("=" * 78)


if __name__ == "__main__":
    main()
