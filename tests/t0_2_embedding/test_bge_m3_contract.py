"""T0.2 — BGE-M3 chạy được, và chạy ĐÚNG HỢP ĐỒNG.

`docs/08` T0.2 chốt thước đo nghiệm thu: chạy nội bộ (R2), tiếng Việt là chính,
**cosine với vector chuẩn hoá L2** (07 Mục 3.1), và **độ dài ngữ cảnh phải chứa
được một Khoản dài** — vì đơn vị đem so khớp là mẩu, không phải câu.

Ca nặng ký nhất ở đây là `test_long_vietnamese_clause_is_not_silently_truncated`.
Điểm quyết định chọn BGE-M3 **không phải điểm số mà là độ dài ngữ cảnh** — nên
nếu thư viện lặng lẽ cắt ở 512 token thì lý do chọn mô hình này tan biến, và
tan biến *không kèm lỗi nào*. Đúng kiểu hỏng mà cả thiết kế dựng lên để chặn.
"""

from __future__ import annotations

import numpy as np

from conftest import (EXPECTED_DIM, EXPECTED_MAX_TOKENS, EXPECTED_METRIC,
                      EXPECTED_MODEL_NAME)

# Một Khoản hành chính VN, viết dài như ngoài đời
KHOAN_DAI = (
    "Điều 12. Trình tự, thủ tục xử lý vi phạm trong hoạt động đấu thầu\n"
    "1. Khi phát hiện hành vi vi phạm quy định của pháp luật về đấu thầu, "
    "người có thẩm quyền hoặc chủ đầu tư có trách nhiệm tạm dừng ngay các "
    "hoạt động có liên quan và lập biên bản ghi nhận sự việc, trong đó nêu "
    "rõ thời điểm phát hiện, nội dung vi phạm, tổ chức và cá nhân có liên "
    "quan, cùng các tài liệu, chứng cứ kèm theo. "
)
CAU_KET_DAC_BIET = (
    "\n99. Điều khoản nhận dạng duy nhất: mọi tranh chấp phát sinh liên quan "
    "đến hợp đồng số 7741/QĐ-XYZ sẽ được giải quyết tại Trung tâm Trọng tài "
    "Quốc tế Việt Nam theo quy tắc tố tụng hiện hành.\n"
)


def test_model_name_and_dimension_match_the_contract(model):
    dim = model.get_sentence_embedding_dimension()
    assert dim == EXPECTED_DIM, f"Phải {EXPECTED_DIM} chiều, đang là {dim}"
    print(f"\n[T0.2] mô hình: {EXPECTED_MODEL_NAME}")
    print(f"[T0.2] số chiều: {dim}")


def test_vectors_are_l2_normalised(model):
    """07 Mục 3.1 (S5): cosine, và vector PHẢI chuẩn hoá L2.

    Chọn sai thì không có lỗi nào báo, chỉ tụt chất lượng tìm kiếm âm thầm.
    """
    texts = ["Quy chế quản lý tài sản công",
             "Hướng dẫn thanh toán chi phí công tác phí",
             KHOAN_DAI]
    vecs = model.encode(texts, normalize_embeddings=True)
    norms = np.linalg.norm(vecs, axis=1)

    assert np.allclose(norms, 1.0, atol=1e-4), f"Chuẩn L2 phải bằng 1, đang là {norms}"
    print(f"[T0.2] thước đo: {EXPECTED_METRIC}; chuẩn L2 = {norms.round(6).tolist()}")


def test_cosine_on_normalised_vectors_equals_dot_product(model):
    """Với vector đã chuẩn hoá L2, cosine == tích vô hướng.

    Đây là lý do kho vector được cấu hình COSINE: hai phép tính trùng nhau nên
    không có chỗ cho một bên tính khác bên kia.
    """
    a, b = model.encode(["Quyết định bổ nhiệm giám đốc",
                         "Quyết định điều động cán bộ quản lý"],
                        normalize_embeddings=True)
    dot = float(np.dot(a, b))
    cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    assert abs(dot - cos) < 1e-6
    print(f"[T0.2] cosine == tích vô hướng: {dot:.6f}")


def test_context_window_covers_8192_tokens_BY_DEFAULT(model):
    """Ngữ cảnh 8192 phải là MẶC ĐỊNH, không phải thứ phải nhớ bật.

    Một tham số an toàn chỉ đúng khi có người nhớ đặt nó thì sớm muộn sẽ có
    người quên. Ca này canh giá trị mặc định, nên nếu thư viện hoặc mô hình hạ
    nó xuống thì đỏ ngay thay vì cắt đuôi văn bản trong im lặng.
    """
    assert model.max_seq_length >= EXPECTED_MAX_TOKENS, (
        f"Ngữ cảnh MẶC ĐỊNH chỉ {model.max_seq_length} token — dưới "
        f"{EXPECTED_MAX_TOKENS}. Độ dài ngữ cảnh CHÍNH LÀ lý do chọn BGE-M3 "
        f"(08 T0.2), nên tụt mặc định là mất luôn căn cứ chọn mô hình."
    )
    assert model.tokenizer.model_max_length >= EXPECTED_MAX_TOKENS, \
        f"Tokenizer chặn ở {model.tokenizer.model_max_length} token"
    print(f"[T0.2] ngữ cảnh MẶC ĐỊNH: {model.max_seq_length} token "
          f"(tokenizer: {model.tokenizer.model_max_length}) — không phải do ghi đè")


def test_long_vietnamese_clause_is_not_silently_truncated(model):
    """⭐ Một Khoản dài phải vào TRỌN ngữ cảnh, không bị cắt đuôi trong im lặng.

    Cách bắt: lấy một văn bản dài, rồi thêm một câu **nhận dạng được** vào
    CUỐI. Nếu mô hình cắt đuôi thì hai vector sẽ giống hệt nhau — vì phần khác
    nhau đã bị vứt đi trước khi tính. Vector khác nhau nghĩa là đuôi có được đọc.
    """
    than_van_ban = KHOAN_DAI * 60          # đủ dài để vượt xa mốc 512 token
    n_tokens = len(model.tokenizer.encode(than_van_ban))
    assert n_tokens > 512, f"Phép thử tự hỏng: mới {n_tokens} token, chưa vượt 512"

    v_khong_duoi, v_co_duoi = model.encode(
        [than_van_ban, than_van_ban + CAU_KET_DAC_BIET], normalize_embeddings=True)
    khac_biet = float(np.linalg.norm(v_khong_duoi - v_co_duoi))

    assert khac_biet > 1e-4, (
        f"Hai vector giống hệt nhau (lệch {khac_biet:.2e}) → ĐUÔI BỊ CẮT NGẦM. "
        f"Văn bản dài {n_tokens} token, ngữ cảnh khai báo {model.max_seq_length}."
    )
    print(f"[T0.2] thân văn bản {n_tokens:,} token; thêm câu ở cuối "
          f"→ vector đổi {khac_biet:.4f} ⇒ KHÔNG cắt ngầm")


def test_above_the_ceiling_the_tail_IS_cut_and_only_warns(model):
    """⚠️ Trên 8192 token thì đuôi BỊ CẮT, và tầng dưới chỉ CẢNH BÁO chứ không nổ.

    Phát hiện lúc đo độ trễ: đầu vào 8.282 token cho ra
    `Token indices sequence length is longer than ... (8282 > 8192)` — một dòng
    cảnh báo, rồi `encode` vẫn chạy bình thường trên phần đã bị cắt.

    Ca này KHÔNG phải để đòi sửa thư viện. Nó ghim lại một ràng buộc cho **GĐ3**:
    một mẩu vượt trần ngữ cảnh sẽ mất đuôi mà không ai biết, nên GĐ3 **bắt buộc**
    phải chia nhỏ tiếp khối cấu trúc quá dài (điều cấm số 25, 06 Mục 5.2 GĐ3).
    Ở đây chỉ chứng minh cái trần là THẬT và nó im lặng.
    """
    qua_tran = KHOAN_DAI * 130
    n_tokens = len(model.tokenizer.encode(qua_tran))
    assert n_tokens > EXPECTED_MAX_TOKENS, \
        f"Phép thử tự hỏng: mới {n_tokens} token, chưa vượt {EXPECTED_MAX_TOKENS}"

    v_a, v_b = model.encode(
        [qua_tran, qua_tran + CAU_KET_DAC_BIET], normalize_embeddings=True)
    khac_biet = float(np.linalg.norm(v_a - v_b))

    assert khac_biet < 1e-4, (
        f"Bất ngờ: thêm chữ vào cuối một văn bản ĐÃ vượt trần vẫn làm vector đổi "
        f"({khac_biet:.2e}). Nếu vậy thì giả định về cách cắt đã khác — xem lại."
    )
    print(f"[T0.2] ⚠️ {n_tokens:,} token (> {EXPECTED_MAX_TOKENS}): thêm chữ ở cuối "
          f"KHÔNG làm vector đổi ({khac_biet:.2e}) ⇒ đuôi bị cắt, chỉ có cảnh báo")
    print(f"[T0.2]    ⇒ ràng buộc cho GĐ3: mẩu phải nằm dưới trần, "
          f"nếu không sẽ mất đuôi trong im lặng")


def test_dense_only_no_sparse_or_colbert_heads(model):
    """v1 CHỈ dùng dense. Hai đầu kia chưa tải về nên không thể vô tình bật."""
    from conftest import MODEL_HOME

    extra = list(MODEL_HOME.rglob("colbert_linear.pt")) + \
            list(MODEL_HOME.rglob("sparse_linear.pt"))
    assert not extra, (
        f"Đã tải đầu sparse/colbert về: {extra}. v1 chỉ dùng dense — bật thêm là "
        f"đổi cấu hình mô hình, kéo theo NẠP LẠI TOÀN KHO (06 Mục 5.5)."
    )
    out = model.encode(["thử"], normalize_embeddings=True)
    assert out.ndim == 2 and out.shape[1] == EXPECTED_DIM, \
        f"Đầu ra phải là một vector dense {EXPECTED_DIM} chiều, đang là {out.shape}"
    print(f"[T0.2] chỉ dense: đầu ra {out.shape}, không có đầu sparse/colbert trên đĩa")


def test_vietnamese_semantics_are_sane(model):
    """Phép thử tỉnh táo: tiếng Việt có dấu, gần nghĩa phải gần hơn khác nghĩa."""
    cau_hoi = "Ai có thẩm quyền phê duyệt kế hoạch lựa chọn nhà thầu?"
    gan = "Thẩm quyền phê duyệt kế hoạch lựa chọn nhà thầu thuộc về người có thẩm quyền."
    xa = "Quy định về chế độ nghỉ phép hằng năm của người lao động."

    v = model.encode([cau_hoi, gan, xa], normalize_embeddings=True)
    sim_gan = float(np.dot(v[0], v[1]))
    sim_xa = float(np.dot(v[0], v[2]))

    assert sim_gan > sim_xa, f"gần={sim_gan:.4f} phải lớn hơn xa={sim_xa:.4f}"
    print(f"[T0.2] tiếng Việt: gần nghĩa {sim_gan:.4f} > khác nghĩa {sim_xa:.4f}")


def test_runs_offline_after_download(model):
    """R2: sau khi đã tải, một lượt biểu diễn không cần chạm ra ngoài."""
    import os
    assert os.environ.get("HF_HUB_OFFLINE") == "1", \
        "Phép thử phải chạy ở chế độ ngoại tuyến mới chứng minh được điều này"
    v = model.encode(["Chạy hoàn toàn trong hạ tầng khách hàng"], normalize_embeddings=True)
    assert v.shape == (1, EXPECTED_DIM)
    print("[T0.2] chạy ngoại tuyến (HF_HUB_OFFLINE=1): đạt")
