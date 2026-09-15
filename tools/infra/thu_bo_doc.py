"""Chạy bộ đọc T0.3 trên một tập văn bản và báo cáo kết quả.

⚠️ **Đây là công cụ khảo sát, KHÔNG phải công cụ nghiệm thu.** `docs/08` T0.3
đòi tỷ lệ ≥90% dựng đúng **hoàn toàn** phân cấp. "Dựng đúng hoàn toàn" phải do
**người** đối chiếu với văn bản gốc — công cụ này chỉ đếm được *có dựng ra cây
hay không*, **không tự phán được cây đó có ĐÚNG không**.

Dùng:
    thu_bo_doc.py <thư mục|file>...              bảng kết quả
    thu_bo_doc.py --markdown <thư mục>           xuất markdown để dán vào README
    thu_bo_doc.py --heading-style <thư mục>      kiểm Heading style của .docx
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

TEN_KET_CUC = {
    Outcome.DIEU_KHOAN: "DIEU_KHOAN",
    Outcome.TIEU_DE: "TIEU_DE",
    Outcome.TIEU_DE_PHONG_DOAN: "TIEU_DE_PHONG_DOAN",
    Outcome.KHONG_DUNG_DUOC: "KHONG_DUNG_DUOC",
}


def phan_loai_nguon(path: pathlib.Path) -> str:
    """PDF / docx gốc / docx chuyển đổi từ .doc.

    Phân loại bằng **bằng chứng trên đĩa** chứ không bằng danh sách chép tay:
    nếu cạnh `X.docx` có `X.doc` thì bản .docx đó là sản phẩm chuyển đổi cơ học
    từ Word 97-2003. Cách này không lệch được khi tập thử thay đổi.
    """
    if path.suffix.lower() == ".pdf":
        return "PDF"
    if path.suffix.lower() == ".docx":
        for duoi in (".doc", ".DOC"):
            if path.with_suffix(duoi).exists():
                return "docx chuyển đổi"
        return "docx gốc"
    return path.suffix.lower()


def gom_file(dau_vao: list[str]) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for m in dau_vao:
        p = pathlib.Path(m).expanduser()
        if p.is_dir():
            for duoi in DINH_DANG_NHAN:
                files.extend(
                    f for f in p.rglob(f"*{duoi}")
                    # bỏ rác của LibreOffice: .~lock.*.docx#
                    if not f.name.startswith(".~lock") and not f.name.endswith("#")
                    # bỏ tài liệu MÔ TẢ tập thử — nó không phải mẫu thử
                    and f.stem.upper() not in ("MANIFEST", "README")
                )
        elif p.is_file():
            files.append(p)
    return sorted(set(files))


def thu_mot_file(path: pathlib.Path) -> dict:
    ghi = {
        "file": path.name,
        "phong_ban": path.parent.name,
        "nguon": phan_loai_nguon(path),
        "preview": [],
    }
    try:
        kq = doc_file(path)
    except DinhDangKhongNhan:
        return {**ghi, "ket_cuc": "TỪ CHỐI định dạng",
                "chuong": 0, "dieu": 0, "khoan": 0, "diem": 0, "ky_tu": 0}
    except KhongDocDuocLopChu as e:
        return {**ghi, "ket_cuc": "TỪ CHỐI ảnh quét",
                "chuong": 0, "dieu": 0, "khoan": 0, "diem": 0, "ky_tu": 0,
                "chi_tiet": str(e)[:90]}
    except Exception as e:  # noqa: BLE001
        return {**ghi, "ket_cuc": f"LỖI {type(e).__name__}",
                "chuong": 0, "dieu": 0, "khoan": 0, "diem": 0, "ky_tu": 0,
                "chi_tiet": str(e)[:140], "traceback": traceback.format_exc()}

    return {
        **ghi,
        "ket_cuc": TEN_KET_CUC[kq.outcome],
        "chuong": len(kq.blocks(Level.CHUONG)),
        "dieu": len(kq.blocks(Level.DIEU)),
        "khoan": len(kq.blocks(Level.KHOAN)),
        "diem": len(kq.blocks(Level.DIEM)),
        "ky_tu": len(kq.full_text),
        "preview": preview_cay(kq, so_dong=5),
    }


def preview_cay(kq, so_dong: int = 5) -> list[str]:
    """Vài dòng đầu của cây, để PO đối chiếu nhanh mà không phải mở lại công cụ."""
    ra: list[str] = []
    for node in kq.root.walk():
        if node.level is Level.DOCUMENT:
            continue
        if node.level in (Level.KHOAN, Level.DIEM) and len(ra) >= 2:
            continue  # ưu tiên khoe bậc ngoài
        thut = "  " * max(0, int(node.level) - 2)
        nhan = f"{node.level.nhan} {node.marker}".strip()
        tieu_de = node.heading.strip()[:58]
        ra.append(f"{thut}{nhan}{' — ' if tieu_de else ''}{tieu_de}")
        if len(ra) >= so_dong:
            break
    return ra


# --------------------------------------------------------------- Heading style

def kiem_heading_style(path: pathlib.Path) -> dict:
    """Đếm đoạn dùng Heading style trong một .docx.

    Đây là phép kiểm **khách quan** — đọc thẳng `paragraph.style.name` — nên
    không cần người mở Word. Nó trả lời đúng câu hỏi mà `docs/08` T0.3 đặt ra:
    tập thử có đủ ≥5 văn bản **không** dùng Heading style hay không.
    """
    import docx

    d = docx.Document(str(path))
    tong = 0
    co_heading = 0
    ten_style: dict[str, int] = {}
    for p in d.paragraphs:
        if not p.text.strip():
            continue
        tong += 1
        ten = (p.style.name or "") if p.style is not None else ""
        ten_style[ten] = ten_style.get(ten, 0) + 1
        if ten.startswith("Heading") or ten.startswith("Tiêu đề"):
            co_heading += 1
    return {
        "file": path.name,
        "phong_ban": path.parent.name,
        "nguon": phan_loai_nguon(path),
        "doan": tong,
        "doan_heading": co_heading,
        "dung_heading": co_heading > 0,
        "style_hay_gap": sorted(ten_style.items(), key=lambda kv: -kv[1])[:3],
    }


def chay_heading_style(dau_vao: list[str]) -> None:
    files = [f for f in gom_file(dau_vao) if f.suffix.lower() == ".docx"]
    if not files:
        print("Không có .docx nào.")
        return

    ket = [kiem_heading_style(f) for f in files]
    khong_style = [k for k in ket if not k["dung_heading"]]

    print(f"{'file':<58} {'nguồn':<16} {'đoạn':>5} {'H-style':>8}  style hay gặp")
    print("-" * 118)
    for k in ket:
        dau = "✅ KHÔNG" if not k["dung_heading"] else f"⚠️ {k['doan_heading']}"
        style = ", ".join(f"{t or '(rỗng)'}×{n}" for t, n in k["style_hay_gap"][:2])
        print(f"{k['file'][:57]:<58} {k['nguon']:<16} {k['doan']:>5} {dau:>8}  {style[:40]}")

    print("-" * 118)
    print(f"Tổng {len(ket)} file .docx: "
          f"{len(khong_style)} KHÔNG dùng Heading style, "
          f"{len(ket) - len(khong_style)} có dùng.")
    print(f"docs/08 T0.3 đòi ≥5 văn bản soạn tay không Heading style — "
          f"đang có {len(khong_style)}.")


# ------------------------------------------------------------------- xuất bảng

def chay_bang(dau_vao: list[str]) -> list[dict]:
    files = gom_file(dau_vao)
    if not files:
        print("Không tìm thấy file nào trong bốn định dạng v1.")
        return []

    print(f"{'file':<50} {'nguồn':<16} {'kết cục':<19} "
          f"{'Chg':>4} {'Điều':>5} {'Khoản':>6} {'Điểm':>5} {'ký tự':>9}")
    print("-" * 122)
    ket: list[dict] = []
    for f in files:
        r = thu_mot_file(f)
        ket.append(r)
        print(f"{r['file'][:49]:<50} {r['nguon']:<16} {r['ket_cuc']:<19} "
              f"{r['chuong']:>4} {r['dieu']:>5} {r['khoan']:>6} {r['diem']:>5} "
              f"{r['ky_tu']:>9,}")
        if r.get("chi_tiet"):
            print(f"    └─ {r['chi_tiet']}")

    print("-" * 122)
    dem: dict[str, int] = {}
    for r in ket:
        dem[r["ket_cuc"]] = dem.get(r["ket_cuc"], 0) + 1
    print(f"Tổng {len(ket)} file:")
    for k, v in sorted(dem.items(), key=lambda kv: -kv[1]):
        print(f"   {v:>3}  {k}")
    print()
    print("⚠️  Bảng trên KHÔNG phải nghiệm thu. Nó chỉ nói bộ đọc có dựng ra cây")
    print("    hay không — KHÔNG nói cây đó có ĐÚNG với văn bản gốc không.")
    print("    Việc đó cần người đối chiếu tay với từng bản gốc.")
    return ket


def chay_markdown(dau_vao: list[str]) -> None:
    """Xuất markdown để dán thẳng vào README — tránh chép tay sai số."""
    files = gom_file(dau_vao)
    ket = [thu_mot_file(f) for f in files]

    print("| # | File | Phòng ban | Nguồn | Kết cục | Chương | Điều | Khoản | Điểm | Ký tự |")
    print("|---|---|---|---|---|---:|---:|---:|---:|---:|")
    for i, r in enumerate(ket, 1):
        print(f"| {i} | `{r['file']}` | {r['phong_ban']} | {r['nguon']} | "
              f"`{r['ket_cuc']}` | {r['chuong']} | {r['dieu']} | {r['khoan']} | "
              f"{r['diem']} | {r['ky_tu']:,} |")

    print()
    dem: dict[str, int] = {}
    for r in ket:
        dem[r["ket_cuc"]] = dem.get(r["ket_cuc"], 0) + 1
    print("**Tổng theo kết cục:** " +
          " · ".join(f"`{k}` {v}" for k, v in sorted(dem.items(), key=lambda kv: -kv[1])))

    print()
    print("### Preview cây dựng ra — để PO đối chiếu nhanh với bản gốc")
    print()
    for i, r in enumerate(ket, 1):
        print(f"**{i}. `{r['file']}`** — {r['nguon']} · `{r['ket_cuc']}`")
        print()
        if r["preview"]:
            print("```")
            for ln in r["preview"]:
                print(ln)
            print("```")
        else:
            print("> _(không dựng ra khối nào)_")
        print()


def chay_cay_day_du(dau_vao: list[str]) -> None:
    """Xuất cây ĐẦY ĐỦ tới tận Khoản/Điểm — phục vụ PO đối chiếu tay.

    Khác `--markdown` (chỉ in 5 dòng đầu mỗi file): ở đây **không cắt ngắn gì**,
    vì mục đích là để người mở bản gốc bên cạnh và soát từng mục.
    """
    files = gom_file(dau_vao)

    print("# Cây cấu trúc ĐẦY ĐỦ — 21 văn bản hành chính VN")
    print()
    print("Sinh bằng `tools/infra/thu_bo_doc.py --cay-day-du "
          "data/test-corpus-vn-admin/`.")
    print()
    print("> ⚠️ **Đây là bản in để ĐỐI CHIẾU TAY, không phải kết quả nghiệm thu.** "
          "Công cụ chỉ in ra cây nó dựng được; việc cây đó có **đúng** với bản "
          "gốc hay không thì chỉ người mở bản gốc mới phán được. Đó chính là vế "
          "≥90% còn treo của T0.3.")
    print()
    print("Cách dùng: mở bản gốc bên cạnh, soát từng Điều — đặc biệt chú ý "
          "**Điều có số hiệu trùng nhau** hoặc **tiêu đề bắt đầu bằng dấu câu** "
          "(`;` `,`), vì đó là dấu hiệu một dẫn chiếu giữa câu bị nhận nhầm "
          "thành mốc cấu trúc.")
    print()
    print("---")
    print()

    for i, f in enumerate(files, 1):
        nguon = phan_loai_nguon(f)
        try:
            kq = doc_file(f)
        except Exception as e:  # noqa: BLE001
            print(f"## {i}. `{f.name}`\n")
            print(f"- **Phòng ban**: {f.parent.name}\n- **Nguồn**: {nguon}\n")
            print(f"> ❌ LỖI: {type(e).__name__}: {e}\n")
            continue

        nodes = [n for n in kq.root.walk() if n.level is not Level.DOCUMENT]
        print(f"## {i}. `{f.name}`")
        print()
        print(f"- **Phòng ban**: {f.parent.name}")
        print(f"- **Nguồn**: {nguon}")
        print(f"- **Kết cục**: `{TEN_KET_CUC[kq.outcome]}`")
        print(f"- **Đếm được**: {len(kq.blocks(Level.CHUONG))} Chương · "
              f"{len(kq.blocks(Level.DIEU))} Điều · "
              f"{len(kq.blocks(Level.KHOAN))} Khoản · "
              f"{len(kq.blocks(Level.DIEM))} Điểm · "
              f"{len(kq.full_text):,} ký tự")
        print()
        print("```")
        for n in nodes:
            thut = "  " * max(0, int(n.level) - 2)
            nhan = f"{n.level.nhan} {n.marker}".strip()
            tieu_de = n.heading.strip()
            print(f"{thut}{nhan}{' — ' if tieu_de else ''}{tieu_de}")
        print("```")
        print()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--heading-style":
        chay_heading_style(args[1:])
    elif args and args[0] == "--markdown":
        chay_markdown(args[1:])
    elif args and args[0] == "--cay-day-du":
        chay_cay_day_du(args[1:])
    else:
        chay_bang(args or [str(REPO_ROOT / "tests" / "t0_3_reader" / "fixtures")])
