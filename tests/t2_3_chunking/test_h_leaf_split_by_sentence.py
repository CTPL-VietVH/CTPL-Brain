"""T2.3 bước 2/2 (h) — khi MỘT ĐOẠN (không dòng trống bên trong) tự nó đã
vượt trần, việc chia tiếp phải rơi xuống ranh giới CÂU, và các mẩu con phải
LIỀN MẠCH tuyệt đối (không mất, không lặp ký tự nào) — khác ranh giới đoạn,
ranh giới câu không loại bỏ nội dung nào giữa hai mẩu.

06 Mục 5.2 GĐ3 bước 2, Điểm mở #4.
"""

from __future__ import annotations

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU

_CAU = "Nội dung minh hoạ cho phép thử chia theo ranh giới câu khi đoạn quá dài. "
# 90 câu liền nhau, KHÔNG dòng trống bên trong -> một ĐOẠN duy nhất vượt trần.
_DOAN_MOT_KHOI = _CAU * 90

VAN_BAN_KHOAN_MOT_DOAN_DAI = f"""Điều 1. Phạm vi điều chỉnh
1. {_DOAN_MOT_KHOI}

Điều 2. Hiệu lực thi hành
Quy chế có hiệu lực kể từ ngày ký."""


def test_tu_thu_doan_vuot_tran_that_va_khong_co_dong_trong_ben_trong():
    assert len(_DOAN_MOT_KHOI) > TRAN_DO_DAI_MAU_THU
    assert "\n\n" not in _DOAN_MOT_KHOI, (
        "Phép thử tự hỏng: cần MỘT đoạn liền khối, không có ranh giới đoạn "
        "bên trong, để buộc phải chia xuống cấp câu"
    )


def test_doan_vuot_tran_duoc_chia_thanh_nhieu_mau_theo_cau():
    read_result = dung_cau_truc(VAN_BAN_KHOAN_MOT_DOAN_DAI, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    khoan_1 = sorted(
        (c for c in chunks if c.structure_path == ["Điều 1", "Khoản 1"]),
        key=lambda c: c.span_start,
    )
    assert len(khoan_1) >= 2, "Một đoạn vượt trần phải bị chia thành nhiều mẩu"
    for c in khoan_1:
        assert c.span_end - c.span_start <= TRAN_DO_DAI_MAU_THU


def test_mau_con_theo_cau_lien_mach_tuyet_doi_khong_mat_ky_tu():
    read_result = dung_cau_truc(VAN_BAN_KHOAN_MOT_DOAN_DAI, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    khoan_1 = sorted(
        (c for c in chunks if c.structure_path == ["Điều 1", "Khoản 1"]),
        key=lambda c: c.span_start,
    )
    node_khoan_1 = next(n for n in read_result.root.walk() if n.path == ["Khoản 1"])

    assert khoan_1[0].span_start == node_khoan_1.char_start
    assert khoan_1[-1].span_end == node_khoan_1.char_end
    # Ranh giới CÂU không loại bỏ gì — liền mạch tuyệt đối, không như ranh
    # giới ĐOẠN (có thể hụt đúng phần dòng trống phân cách).
    for a, b in zip(khoan_1, khoan_1[1:]):
        assert a.span_end == b.span_start

    ghep_lai = "".join(
        read_result.full_text[c.span_start : c.span_end] for c in khoan_1
    )
    doan_goc = read_result.full_text[node_khoan_1.char_start : node_khoan_1.char_end]
    assert ghep_lai == doan_goc


def test_mau_con_theo_cau_cung_structure_path_va_parent_chunk_id():
    read_result = dung_cau_truc(VAN_BAN_KHOAN_MOT_DOAN_DAI, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    theo_path: dict[tuple, list] = {}
    for c in chunks:
        theo_path.setdefault(tuple(c.structure_path), []).append(c)

    khoan_1 = theo_path[("Điều 1", "Khoản 1")]
    dieu_1 = theo_path[("Điều 1",)][0]

    for c in khoan_1:
        assert c.structure_path == ["Điều 1", "Khoản 1"]
        assert c.parent_chunk_id == dieu_1.chunk_id
