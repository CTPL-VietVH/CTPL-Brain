"""Đo `SUBSTRING ... FROM ... FOR ...` so với lấy cả trường rồi cắt ở Python.

Nền: `docs/07` Mục 2.1 chốt `extracted_text` là **nguồn chân lý duy nhất của
chữ nghĩa**, mẩu chỉ giữ vị trí; Mục 7 yêu cầu 2 đòi *"kho lưu phải hỗ trợ đọc
theo đoạn — không lấy toàn văn về rồi mới cắt; với tài liệu dài thì đó là lãng
phí ở mọi lượt trả lời"*.

Công cụ này **chỉ đo và báo số**. Nó **không** đề xuất đổi thiết kế — theo
`CLAUDE.md` Mục 8, thấy số liệu ngược với lý lẽ trong thiết kế thì báo PO, không
tự đổi.

Ba độ dài lấy từ CHÍNH tập thử thật để số liệu có nghĩa, không phải văn bản chế.

Chạy: .venv/bin/python tools/infra/do_substring.py
"""

from __future__ import annotations

import os
import pathlib
import statistics
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

import psycopg  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

BANG = "t0_1_probe.do_substring"
VONG = 60
DOAN_DOC = 400          # cỡ một đơn vị ĐỌC điển hình đem trích dẫn

# Nguồn để RÚT ra bốn độ dài thật. Không chế văn bản — cắt từ chính tập thử,
# vì chi phí của SUBSTRING phụ thuộc cách mã hoá UTF-8 của chữ thật.
NGUON_RUT = "data/test-corpus-vn-admin/tai-chinh-ke-toan/tt-200-btc-22-12-2014.pdf"

# ~8192 token ngữ cảnh BGE-M3 ≈ chừng này ký tự tiếng Việt (đo ở T0.2:
# 7.799 token ứng với ~25.000 ký tự)
KY_TU_GAN_TRAN_NGU_CANH = 25_000


def _med_p95(fn) -> tuple[float, float]:
    fn()  # làm ấm cache
    s = []
    for _ in range(VONG):
        t0 = time.perf_counter()
        fn()
        s.append((time.perf_counter() - t0) * 1000)
    s.sort()
    return statistics.median(s), s[int(len(s) * 0.95) - 1]


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    dsn = (f"postgresql://{os.environ['CBRAIN_PG_USER']}@"
           f"{os.environ['CBRAIN_PG_HOST']}:{os.environ['CBRAIN_PG_PORT']}/"
           f"{os.environ['CBRAIN_PG_DATABASE']}")

    from ingestion.reader.readers import doc_file
    from ingestion.reader.structure import Level

    # --- Rút bốn độ dài THẬT từ một văn bản thật ---
    kq = doc_file(REPO_ROOT / NGUON_RUT)
    toan_van = kq.full_text
    khoan = sorted((n for n in kq.blocks(Level.KHOAN)),
                   key=lambda n: n.char_end - n.char_start)
    dieu = sorted((n for n in kq.blocks(Level.DIEU)),
                  key=lambda n: n.char_end - n.char_start)

    mau: list[tuple[str, str]] = [
        ("một Khoản ngắn", khoan[len(khoan) // 4].text(toan_van)),
        ("một Điều dài", dieu[-1].text(toan_van)),
        ("gần trần ngữ cảnh", toan_van[:KY_TU_GAN_TRAN_NGU_CANH]),
        ("cả tài liệu", toan_van),
    ]

    print("=" * 100)
    print("ĐO: SUBSTRING theo vị trí KÝ TỰ  vs  lấy cả trường rồi cắt ở Python")
    print("=" * 100)
    print(f"PostgreSQL cùng máy (loopback) · trung vị trên {VONG} lượt · "
          f"đoạn đọc {DOAN_DOC} ký tự")
    print()
    print(f"Văn bản nguồn: {pathlib.Path(NGUON_RUT).name}")
    print()
    print(f"{'độ dài văn bản':<20} {'ký tự':>10} {'byte':>11} {'SUBSTRING':>22} "
          f"{'cả trường':>22}  {'chênh':>7}")
    print("-" * 110)

    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute(f"CREATE TABLE IF NOT EXISTS {BANG} (id text PRIMARY KEY, body text)")
        for nhan, doc in mau:
            n = len(doc)
            c.execute(f"INSERT INTO {BANG} VALUES (%s,%s) "
                      f"ON CONFLICT (id) DO UPDATE SET body=EXCLUDED.body", (nhan, doc))

            # Đọc ở GIỮA tài liệu — chi phí của SUBSTRING tỉ lệ với ĐỘ LỆCH,
            # nên đọc ở đầu sẽ cho số đẹp một cách giả tạo.
            start = max(0, n // 2)
            length = min(DOAN_DOC, n - start)

            def _sub(s=start, l=length, nh=nhan):
                return c.execute(
                    f"SELECT SUBSTRING(body FROM %s FOR %s) FROM {BANG} WHERE id=%s",
                    (s + 1, l, nh)).fetchone()[0]

            def _whole(s=start, l=length, nh=nhan):
                return c.execute(
                    f"SELECT body FROM {BANG} WHERE id=%s", (nh,)).fetchone()[0][s:s + l]

            assert _sub() == _whole(), f"{nhan}: hai cách cho ra đoạn KHÁC NHAU"

            m1, p1 = _med_p95(_sub)
            m2, p2 = _med_p95(_whole)
            chenh = m1 / m2
            print(f"{nhan:<20} {n:>10,} {len(doc.encode('utf-8')):>11,} "
                  f"{m1:>9.3f} ms (p95{p1:6.2f}) {m2:>9.3f} ms (p95{p2:6.2f})  "
                  f"{chenh:>6.2f}x")

        c.execute(f"DROP TABLE IF EXISTS {BANG}")

    print("-" * 118)
    print("Cột 'chênh' = SUBSTRING / cả trường. >1 nghĩa là SUBSTRING CHẬM HƠN.")
    print()
    print("Đọc số này thế nào:")
    print("  · Cả hai cách đều cho ra ĐÚNG cùng một đoạn (đã assert mỗi lượt).")
    print("  · SUBSTRING theo vị trí KÝ TỰ trên văn bản đa byte không nhảy thẳng")
    print("    tới vị trí được — Postgres phải giải mã UTF-8 từ đầu, nên chi phí")
    print("    tỉ lệ với ĐỘ LỆCH chứ không phải độ dài đoạn.")
    print("  · Đổi lại, khối lượng đi qua dây nhỏ hơn nhiều bậc.")
    print()
    print("⚠️  Đây là SỐ LIỆU, không phải đề xuất. Kho nằm CÙNG MÁY với service ở")
    print("    phép đo này; qua mạng thì cán cân đổi. Quyết định thuộc về PO.")


if __name__ == "__main__":
    main()
