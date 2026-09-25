"""T2.3 (k) — ca HỒI QUY TRỰC TIẾP của lỗi CHUNK-mau-noi-bo: không mẩu nào
`cat_thanh_mau` sinh ra được vượt trần ngữ cảnh của mô hình biểu diễn.

Đây là bài test mà lỗi cũ KHÔNG qua được. Trước 25/9/2026, một Chương gồm
nhiều Điều ngắn sinh ra một mẩu mang trọn cây con, vượt xa 8192 token, và
GĐ6 (`vectorization.sinh_vector`) nổ `ChunkVuotTranNguCanh` — đo thật:
18/36 tài liệu của kho thử không nạp được vì đúng chuyện này.

⚠️ Vì sao đếm token ở T2.3 chứ không để T2.5 lo: `tran_do_dai_mau` đếm KÝ TỰ,
còn trần của mô hình đếm TOKEN. Hai thước đo khác nhau, và chỉ có bài test
này nối chúng lại. Không có nó, T2.3 có thể "đúng" theo ký tự trong khi vẫn
sinh ra mẩu mà T2.5 không nhận — đúng khe hở đã xảy ra thật.

Test dùng TOKENIZER thật của BGE-M3 (không nạp 2.5GB trọng số): `dem_token`
của `vectorization` cũng chỉ gọi `model.tokenizer.encode(...)`, nên con số ở
đây khớp từng token với con số GĐ6 sẽ đếm. Trần đọc từ chính
`sentence_bert_config.json` của mô hình, không gõ cứng 8192 vào mã test —
đổi mô hình thì bài test này đi theo.
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

from ingestion.chunking import cat_thanh_mau
from ingestion.reader.vn_normalizer import dung_cau_truc

from .conftest import DOC_ID, SPACE_ID, TENANT_ID, TRAN_DO_DAI_MAU_THU
from .test_i_internal_node_not_split import VAN_BAN_CHUONG_VUOT_TRAN

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODEL_HOME = REPO_ROOT / ".runtime" / "models"
_SNAPSHOTS = MODEL_HOME / "hub" / "models--BAAI--bge-m3" / "snapshots"


@pytest.fixture(scope="module")
def bge_m3_tokenizer_and_ceiling():
    if not _SNAPSHOTS.exists():
        pytest.fail(
            f"Chưa tải mô hình về {MODEL_HOME}. Xem tests/t0_2_embedding/README.md"
        )
    snapshot = next(_SNAPSHOTS.iterdir())
    os.environ["HF_HOME"] = str(MODEL_HOME)
    os.environ["HF_HUB_OFFLINE"] = "1"

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True)
    ceiling = json.loads((snapshot / "sentence_bert_config.json").read_text())[
        "max_seq_length"
    ]
    return tokenizer, ceiling


def test_chuong_80_dieu_khong_sinh_mau_nao_vuot_tran_ngu_canh(
    bge_m3_tokenizer_and_ceiling,
):
    tokenizer, ceiling = bge_m3_tokenizer_and_ceiling
    read_result = dung_cau_truc(VAN_BAN_CHUONG_VUOT_TRAN, source_format="txt")
    chunks = cat_thanh_mau(
        read_result,
        document_id=DOC_ID,
        space_id=SPACE_ID,
        tenant_id=TENANT_ID,
        tran_do_dai_mau=TRAN_DO_DAI_MAU_THU,
    )
    assert chunks, "phép thử tự hỏng: phải sinh ra mẩu thì mới có gì để đếm"

    # Phép thử tự kiểm: trọn Chương PHẢI vượt trần ngữ cảnh, nếu không thì bài
    # test này xanh vì văn bản quá ngắn chứ không vì mã đã đúng.
    tron_chuong = len(
        tokenizer.encode(read_result.full_text, add_special_tokens=True, truncation=False)
    )
    assert tron_chuong > ceiling, (
        f"phép thử tự hỏng: cả văn bản chỉ {tron_chuong} token, chưa chạm trần "
        f"{ceiling} — không tái hiện được lỗi cũ"
    )

    qua_tran = [
        (chunk.structure_path, so_token)
        for chunk in chunks
        for so_token in [
            len(
                tokenizer.encode(
                    read_result.full_text[chunk.span_start : chunk.span_end],
                    add_special_tokens=True,
                    truncation=False,
                )
            )
        ]
        if so_token > ceiling
    ]
    assert qua_tran == [], (
        f"{len(qua_tran)} mẩu vượt trần ngữ cảnh {ceiling} token — GĐ6 sẽ từ "
        f"chối cả tài liệu: {qua_tran}"
    )
