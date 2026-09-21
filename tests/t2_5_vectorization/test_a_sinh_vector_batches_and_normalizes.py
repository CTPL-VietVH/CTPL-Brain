"""T2.5 (a) — `sinh_vector` gọi BGE-M3 THẬT theo LÔ (docs/09 hàng T2.5), trả
về `Chunk` mới với `embedding` đã điền, chuẩn hoá L2 (07 Mục 3.1, S5), đúng
1024 chiều (`config/contract.yaml`). Không chạm Qdrant.
"""

from __future__ import annotations

import numpy as np

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc
from ingestion.vectorization import sinh_vector

from .conftest import DOC_ID, SPACE_ID, TENANT_ID

VAN_BAN = """CHƯƠNG I
QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
1. Quy chế này áp dụng cho toàn thể cán bộ, nhân viên của công ty.
2. Mọi cá nhân phải chịu trách nhiệm trước pháp luật về hành vi của mình.

Điều 2. Giải thích từ ngữ
Các từ ngữ trong quy chế này được hiểu theo quy định của pháp luật hiện hành."""


def _chunks_that():
    read_result = dung_cau_truc(VAN_BAN, source_format="txt")
    chunks = cat_thanh_mau(
        read_result, document_id=DOC_ID, space_id=SPACE_ID, tenant_id=TENANT_ID
    )
    return read_result, chunks


def test_moi_chunk_deu_co_embedding_1024_chieu_va_chuan_hoa_l2(model):
    read_result, chunks = _chunks_that()
    assert all(c.embedding == [] for c in chunks), "Phép thử tự hỏng: T2.3 phải để embedding=[]"

    ket_qua = sinh_vector(chunks, full_text=read_result.full_text, model=model)

    assert len(ket_qua) == len(chunks)
    for chunk in ket_qua:
        assert len(chunk.embedding) == 1024
        norm = float(np.linalg.norm(chunk.embedding))
        assert abs(norm - 1.0) < 1e-4, f"Chuẩn L2 phải bằng 1, đang là {norm}"


def test_khong_sua_doi_danh_sach_chunk_dau_vao(model):
    """`sinh_vector` phải trả DANH SÁCH MỚI — Chunk gốc (từ GĐ3) không bị
    sửa, giữ đúng bất biến "Chunk không tự mang chữ, không tự có vector cho
    tới khi GĐ6 chạy"."""
    read_result, chunks = _chunks_that()
    ket_qua = sinh_vector(chunks, full_text=read_result.full_text, model=model)

    assert all(c.embedding == [] for c in chunks), "Danh sách đầu vào bị sửa tại chỗ"
    assert ket_qua is not chunks
    for goc, moi in zip(chunks, ket_qua):
        assert moi.chunk_id == goc.chunk_id
        assert moi.structure_path == goc.structure_path
        assert moi.parent_chunk_id == goc.parent_chunk_id
        assert moi.span_start == goc.span_start and moi.span_end == goc.span_end


def test_danh_sach_rong_tra_ve_danh_sach_rong(model):
    assert sinh_vector([], full_text="", model=model) == []


def test_hai_mau_noi_dung_khac_nhau_ra_vector_khac_nhau(model):
    """Phép thử tỉnh táo tối thiểu: vector phải PHỤ THUỘC nội dung — hai mẩu
    nội dung khác nhau (Khoản 1 vs Khoản 2, cùng Điều nhưng khác câu chữ)
    không được ra cùng một vector (loại trừ ca hỏng "mọi mẩu ra cùng một
    embedding vô nghĩa")."""
    read_result, chunks = _chunks_that()
    ket_qua = sinh_vector(chunks, full_text=read_result.full_text, model=model)
    theo_path = {tuple(c.structure_path): c for c in ket_qua}

    khoan_1 = np.array(theo_path[("Chương I", "Điều 1", "Khoản 1")].embedding)
    khoan_2 = np.array(theo_path[("Chương I", "Điều 1", "Khoản 2")].embedding)

    khac_biet = float(np.linalg.norm(khoan_1 - khoan_2))
    assert khac_biet > 1e-3, "Hai mẩu nội dung khác nhau ra vector giống hệt nhau"
