"""Chạy bộ đọc T0.3 trên một tập văn bản và báo cáo kết quả.

⚠️ **Đây là công cụ khảo sát, KHÔNG phải công cụ nghiệm thu.** `docs/08` T0.3
đòi tập thử **có tên gọi** gồm ≥20 văn bản hành chính VN thật (≥5 soạn tay
không Heading style, ≥5 PDF) và tỷ lệ ≥90% dựng đúng **hoàn toàn** phân cấp.
"Dựng đúng hoàn toàn" phải do **người** đối chiếu với văn bản gốc — công cụ này
chỉ đếm được *có dựng ra cây hay không*, không tự phán được cây đó có ĐÚNG không.

Dùng: .venv/bin/python tools/infra/thu_bo_doc.py <thư mục hoặc file>...
"""

from __future__ import annotations

import pathlib
import sys
import traceback

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from ingestion.reader.readers import (DINH_DANG_NHAN, DinhDangKhongNhan,  # noqa: E402
                                      KhongDocDuocLopChu, doc_file)
from ingestion.reader.structure import Level, Outcome  # noqa: E402


def thu_mot_file(path: pathlib.Path) -> dict:
    ghi = {"file": path.name, "duoi": path.suffix.lower()}
    try:
        kq = doc_file(path)
    except DinhDangKhongNhan:
        return {**ghi, "ket_cuc": "TỪ CHỐI định dạng", "chuong": 0, "dieu": 0,
                "khoan": 0, "diem": 0, "ky_tu": 0}
    except KhongDocDuocLopChu as e:
        return {**ghi, "ket_cuc": "TỪ CHỐI ảnh quét", "chuong": 0, "dieu": 0,
                "khoan": 0, "diem": 0, "ky_tu": 0, "chi_tiet": str(e)[:80]}
    except Exception as e:  # noqa: BLE001
        return {**ghi, "ket_cuc": f"LỖI {type(e).__name__}", "chuong": 0,
                "dieu": 0, "khoan": 0, "diem": 0, "ky_tu": 0,
                "chi_tiet": str(e)[:120], "traceback": traceback.format_exc()}

    return {
        **ghi,
        "ket_cuc": {Outcome.DIEU_KHOAN: "điều khoản",
                    Outcome.TIEU_DE: "tiêu đề số",
                    Outcome.TIEU_DE_PHONG_DOAN: "tiêu đề HOA ⚠️",
                    Outcome.KHONG_DUNG_DUOC: "KHÔNG dựng được"}[kq.outcome],
        "chuong": len(kq.blocks(Level.CHUONG)),
        "dieu": len(kq.blocks(Level.DIEU)),
        "khoan": len(kq.blocks(Level.KHOAN)),
        "diem": len(kq.blocks(Level.DIEM)),
        "ky_tu": len(kq.full_text),
    }


def main(dau_vao: list[str]) -> None:
    files: list[pathlib.Path] = []
    for m in dau_vao:
        p = pathlib.Path(m).expanduser()
        if p.is_dir():
            for duoi in DINH_DANG_NHAN:
                files.extend(sorted(p.rglob(f"*{duoi}")))
        elif p.is_file():
            files.append(p)

    if not files:
        print("Không tìm thấy file nào trong bốn định dạng v1.")
        return

    print(f"{'file':<52} {'đuôi':<6} {'kết cục':<16} "
          f"{'Chg':>4} {'Điều':>5} {'Khoản':>6} {'Điểm':>5} {'ký tự':>8}")
    print("-" * 110)
    dem: dict[str, int] = {}
    for f in files:
        r = thu_mot_file(f)
        dem[r["ket_cuc"]] = dem.get(r["ket_cuc"], 0) + 1
        print(f"{r['file'][:51]:<52} {r['duoi']:<6} {r['ket_cuc']:<16} "
              f"{r['chuong']:>4} {r['dieu']:>5} {r['khoan']:>6} {r['diem']:>5} "
              f"{r['ky_tu']:>8,}")
        if r.get("chi_tiet"):
            print(f"    └─ {r['chi_tiet']}")

    print("-" * 110)
    print(f"Tổng {len(files)} file:")
    for k, v in sorted(dem.items(), key=lambda kv: -kv[1]):
        print(f"   {v:>3}  {k}")
    print()
    print("⚠️  Bảng trên KHÔNG phải nghiệm thu. Nó chỉ nói bộ đọc có dựng ra cây")
    print("    hay không — KHÔNG nói cây đó có ĐÚNG với văn bản gốc không.")
    print("    Việc đó cần người đối chiếu, trên tập thử có tên gọi ≥20 văn bản.")


if __name__ == "__main__":
    main(sys.argv[1:] or [str(REPO_ROOT / "tests" / "t0_3_reader" / "fixtures")])
