"""T2.3 (a) — `structure_path` đúng thứ tự NGOÀI → TRONG khi cấu trúc lồng
≥3 cấp (07 Mục 2.2: "danh sách các đoạn, theo thứ tự từ ngoài vào trong").

Văn bản thử: Chương I › Điều 1 › Khoản 1 (ba cấp). `Node.path` chỉ trả một
đoạn của chính nó (structure.py:127-135) — bài test này xác nhận tầng T2.3
đã TỰ TÍCH LUỸ đúng dọc đường từ gốc xuống, không chỉ lấy một đoạn cuối cùng.
"""

from __future__ import annotations

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, VAN_BAN_LONG_NHAU


def test_structure_path_ba_cap_dung_thu_tu_ngoai_vao_trong():
    read_result = dung_cau_truc(VAN_BAN_LONG_NHAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result, document_id=DOC_ID, space_id=SPACE_ID, tenant_id=TENANT_ID
    )

    theo_path = {tuple(c.structure_path): c for c in chunks}

    assert ("Chương I",) in theo_path
    assert ("Chương I", "Điều 1") in theo_path
    assert ("Chương I", "Điều 1", "Khoản 1") in theo_path
    assert ("Chương I", "Điều 1", "Khoản 2") in theo_path
    assert ("Chương I", "Điều 2") in theo_path

    khoan_1 = theo_path[("Chương I", "Điều 1", "Khoản 1")]
    assert khoan_1.structure_path == ["Chương I", "Điều 1", "Khoản 1"], (
        "Thứ tự phải NGOÀI vào TRONG — Chương trước, Điều giữa, Khoản cuối"
    )


def test_moi_khoi_cau_truc_sinh_dung_mot_chunk():
    """Gốc (Level.DOCUMENT) không sinh Chunk; mọi Node còn lại thì có — văn
    bản thử có 5 khối (1 Chương + 2 Điều + 2 Khoản) nên phải ra đúng 5 mẩu."""
    read_result = dung_cau_truc(VAN_BAN_LONG_NHAU, source_format="txt")
    chunks = cat_thanh_mau(
        read_result, document_id=DOC_ID, space_id=SPACE_ID, tenant_id=TENANT_ID
    )
    assert len(chunks) == 5
