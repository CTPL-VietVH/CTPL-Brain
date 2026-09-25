"""T1.4 (c) — `span_start`/`span_end` đếm theo KÝ TỰ UNICODE, không phải byte
(07 Mục 2.2; CLAUDE.md Mục 3 #4).

07 Mục 2.2 ghi rõ: "Tiếng Việt có dấu, một ký tự chiếm nhiều byte — một bên
đếm ký tự còn bên kia đếm byte thì đoạn cắt ra lệch đi, KHÔNG CÓ LỖI NÀO
BÁO, chỉ là câu trả lời dẫn nguồn sai chỗ." Đây chính là loại hỏng im lặng
mà bộ test này phải làm nó LÊN TIẾNG: không đủ để `Chunk` cắt đúng khi
dùng chỉ số ký tự — phải chứng minh thêm rằng dùng NHẦM chỉ số byte cho ra
kết quả SAI, để không ai tưởng nhầm hai cách đếm là tương đương.
"""

from __future__ import annotations

from schema.chunk import Chunk

# Chuỗi thử: nhiều tổ hợp dấu tiếng Việt ("ệ", "ữ", "ị", "ộ", "ỗ"...) đặt
# TRƯỚC đoạn mục tiêu, để độ lệch byte/ký tự tích luỹ đủ lớn trước khi tới
# `span_start`.
VAN_BAN_GIA_LAP = (
    "Điều 7: Người đại diện phải chịu trách nhiệm trước pháp luật, "
    "giữ vững kỷ luật nội bộ."
)
DOAN_MUC_TIEU = "chịu trách nhiệm"


def test_self_check_chuoi_thu_co_dau_that():
    """Phép thử tự hỏng nếu chuỗi thử không thật sự có dấu — cùng pattern
    `n_ky_tu`/`n_byte` đã dùng ở `tests/t0_3_reader/test_reader.py`.
    """
    n_ky_tu = len(VAN_BAN_GIA_LAP)
    n_byte = len(VAN_BAN_GIA_LAP.encode("utf-8"))
    assert n_byte != n_ky_tu, "Phép thử tự hỏng: chuỗi thử phải có dấu tiếng Việt"
    assert n_byte > n_ky_tu

    # Tính chất THẬT SỰ cần: độ lệch byte/ký tự phải tích luỹ TRƯỚC đoạn mục
    # tiêu, nếu không thì test cắt-theo-byte bên dưới mất ý nghĩa.
    span_start = VAN_BAN_GIA_LAP.index(DOAN_MUC_TIEU)
    assert len(VAN_BAN_GIA_LAP[:span_start].encode("utf-8")) > span_start


def _lam_chunk(span_start: int, span_end: int) -> Chunk:
    return Chunk(
        chunk_id="chunk-unicode-1",
        document_id="doc-unicode-1",
        space_id="space-1",
        tenant_id="tenant-1",
        structure_path=["Điều 7"],
        span_start=span_start,
        span_end=span_end,
        structure_block_start=span_start,
        structure_block_end=span_end,
        embedding=[0.0],
    )


def test_cat_theo_chi_so_ky_tu_cho_ra_dung_doan():
    """`span_start`/`span_end` là chỉ số KÝ TỰ — cắt bằng chỉ mục chuỗi
    Python (vốn đã là unicode-aware) phải khớp CHÍNH XÁC đoạn mong đợi.
    """
    span_start = VAN_BAN_GIA_LAP.index(DOAN_MUC_TIEU)
    span_end = span_start + len(DOAN_MUC_TIEU)

    chunk = _lam_chunk(span_start, span_end)

    cat_ra = VAN_BAN_GIA_LAP[chunk.span_start : chunk.span_end]
    assert cat_ra == DOAN_MUC_TIEU


def test_nham_dung_chi_so_byte_thay_vi_ky_tu_thi_cat_sai():
    """Ca thử LÊN TIẾNG: nếu ai đó (nhầm) lấy cùng cặp số của `span_start`/
    `span_end` rồi áp lên chuỗi BYTE (`encode("utf-8")`) thay vì chuỗi ký
    tự, kết quả phải SAI — chứng minh hai cách đếm không hoán đổi được
    cho nhau, và lỗi này không tự báo bằng exception rõ ràng ở mọi trường
    hợp (nên không thể chỉ dựa vào try/except để bắt).
    """
    span_start = VAN_BAN_GIA_LAP.index(DOAN_MUC_TIEU)
    span_end = span_start + len(DOAN_MUC_TIEU)
    chunk = _lam_chunk(span_start, span_end)

    van_ban_byte = VAN_BAN_GIA_LAP.encode("utf-8")
    doan_cat_theo_byte = van_ban_byte[chunk.span_start : chunk.span_end]

    # `errors="replace"` để phép thử không phụ thuộc việc lát cắt byte có
    # vô tình rơi đúng ranh giới ký tự UTF-8 hay không — bất kể rơi đúng
    # ranh giới hay giữa chừng một ký tự nhiều byte, kết quả giải mã vẫn
    # phải KHÁC đoạn mong đợi vì offset đã lệch từ trước đó.
    doan_giai_ma_lai = doan_cat_theo_byte.decode("utf-8", errors="replace")

    assert doan_giai_ma_lai != DOAN_MUC_TIEU, (
        "Cắt theo chỉ số byte trùng hợp cho ra đúng đoạn mong đợi — chuỗi "
        "thử không đủ lệch byte/ký tự để phép thử này có ý nghĩa, cần chọn "
        "lại VAN_BAN_GIA_LAP với nhiều dấu hơn trước DOAN_MUC_TIEU."
    )

    # Chứng minh thêm: chính lát cắt byte thô (chưa giải mã) khác lát cắt
    # ký tự đúng khi đem so ở dạng byte — nghĩa là đây thật sự là hai phép
    # cắt khác nhau, không phải khác biệt sinh ra bởi bước decode.
    assert doan_cat_theo_byte != DOAN_MUC_TIEU.encode("utf-8")
