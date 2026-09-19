"""T1.4 (b) — Tám loại trường BỊ CẤM ở `docs/07` Mục 5, áp riêng cho `Chunk`.

Mỗi bài test dưới đây ứng với đúng một dòng của bảng "Những trường BỊ CẤM
có mặt" (07 Mục 5). Với mỗi loại, test khẳng định hai lớp phòng thủ:

(a) không trường nào trong `dataclasses.fields(Chunk)` mang tên hoặc họ tên
    gợi ý loại cấm đó (so khớp theo chuỗi con, không chỉ so khớp đúng tên —
    để bắt cả các biến thể đặt tên khác của cùng một ý tưởng cấm);
(b) đối chiếu lại toàn bộ tập field của `Chunk` khớp CHÍNH XÁC whitelist 10
    trường ở 07 Mục 2.2 — lưới an toàn tổng, bắt được cả trường lạ không
    nằm trong danh sách tên cụ thể ở (a).

t1_1_schema đã phủ một phần các mục cấm này cho CẢ BỐN thực thể; bộ này là
bộ ĐỘC LẬP, tập trung riêng cho `Chunk` và phủ đủ cả 8 dòng của Mục 5.
"""

from __future__ import annotations

import dataclasses

from conftest import CHUNK_WHITELIST
from schema.chunk import Chunk


def _chunk_field_names() -> set[str]:
    return {f.name for f in dataclasses.fields(Chunk)}


def _assert_whitelist_intact() -> None:
    assert _chunk_field_names() == CHUNK_WHITELIST, (
        "Lưới an toàn tổng đã đứt: tập field của Chunk không còn khớp "
        "whitelist 10 trường ở 07 Mục 2.2."
    )


def test_1_no_frozen_permission_or_group_field():
    """07 Mục 5, dòng 1 — NT3 + QT1: không danh sách người/nhóm/dấu hiệu
    quyền đóng băng lúc ingest. Đây đúng con bug đã có thật: người vừa
    được cấp quyền qua được bộ lọc tươi nhưng trượt bộ lọc đóng băng.
    """
    forbidden_substrings = ("permission", "role", "acl", "group", "member", "quyen", "thanh_vien")
    fields = _chunk_field_names()
    for name in fields:
        for bad in forbidden_substrings:
            assert bad not in name, f"'{name}' trông như mang dấu hiệu quyền/nhóm đóng băng"
    _assert_whitelist_intact()


def test_2_no_space_type_tree_or_membership_field():
    """07 Mục 5, dòng 2 — NT3: loại Space (kế thừa/riêng), cây Space, danh
    sách thành viên đều đổi vì con người thao tác, phải tính tươi mỗi lần
    hỏi — không được đóng băng trong `Chunk`.
    """
    forbidden_substrings = ("space_type", "space_tree", "inherited", "member")
    fields = _chunk_field_names()
    for name in fields:
        for bad in forbidden_substrings:
            assert bad not in name, f"'{name}' trông như mang loại Space/cây Space/thành viên"
    _assert_whitelist_intact()


def test_3_no_is_latest_version_or_newest_flag():
    """07 Mục 5, dòng 3 — cờ "mới nhất" cũ đi ngay khi có bản mới nạp vào;
    phải suy ra từ chuỗi phiên bản, không phải một cờ đóng băng.
    """
    fields = _chunk_field_names()
    assert "is_latest_version" not in fields
    assert "is_active" not in fields
    for name in fields:
        assert "latest" not in name
        assert "newest" not in name
        assert "current" not in name
    _assert_whitelist_intact()


def test_4_no_relation_approval_state_next_to_chunk():
    """07 Mục 5, dòng 4 — `approval_state` của `relation` đặt cạnh mẩu buộc
    phải nạp lại mẩu mỗi lần Manager duyệt (06 Mục 6.4). `Chunk` không sở
    hữu quan hệ nào cả.
    """
    fields = _chunk_field_names()
    assert "approval_state" not in fields
    for name in fields:
        assert "approval" not in name
    _assert_whitelist_intact()


def test_5_no_document_title_or_status_fields_owned_by_document():
    """07 Mục 5, dòng 5 — `title`, `doc_number`, `effective_date`, hay bất
    kỳ trạng thái tài liệu nào (`removed_as_wrong`, `superseded`, ...) chỉ
    thuộc `Document`; dùng để ĐỌC và DẪN NGUỒN thì lấy sau từ hồ sơ, không
    đặt cạnh mẩu (06 Mục 6.4).
    """
    forbidden_exact = {
        "title",
        "doc_number",
        "effective_date",
        "effective_date_source",
        "issued_date",
        "issued_date_source",
        "removed_as_wrong",
        "removed_reason",
        "removed_by",
        "removed_at",
        "superseded",
        "superseded_by",
        "superseded_at",
        "publication_state",
    }
    fields = _chunk_field_names()
    assert forbidden_exact.isdisjoint(fields)
    _assert_whitelist_intact()


def test_6_no_merged_status_field_for_wrong_vs_superseded():
    """07 Mục 5, dòng 6 — một trường trạng thái GỘP "gỡ vì sai" với "hết
    hiệu lực" làm mất khả năng trả lời câu hỏi về quá khứ (06 Mục 6.3).
    Với `Chunk`, cả hai khái niệm này còn không được phép xuất hiện dưới
    bất kỳ tên nào — kể cả tách riêng — vì chúng chỉ thuộc `Document`.
    """
    fields = _chunk_field_names()
    assert "status" not in fields
    assert "document_state" not in fields
    for name in fields:
        assert "status" not in name, f"'{name}' trông như một trường trạng thái gộp"
        assert "state" not in name, f"'{name}' trông như một trường trạng thái gộp"
    _assert_whitelist_intact()


def test_7_no_document_sensitivity_level_field():
    """07 Mục 5, dòng 7 — mức nhạy cảm tối đa của tài liệu là PHÁN ĐOÁN nên
    NT4 cấm dùng để loại trừ; và 06 Mục 7.1 chốt v1 không triển khai cơ chế
    che nào — GĐ4 hoãn, không xây.
    """
    fields = _chunk_field_names()
    assert "sensitivity" not in fields
    assert "max_sensitivity_level" not in fields
    for name in fields:
        assert "sensitiv" not in name
    _assert_whitelist_intact()


def test_8_no_verbatim_question_or_answer_text_field():
    """07 Mục 5, dòng 8 — nguyên văn câu hỏi/câu trả lời chỉ có chỗ đứng
    trong nhật ký điều tra (và ngay ở đó cũng bị cấm — 06 Mục 9.2), tuyệt
    đối không phải một trường của `Chunk` trong kho vector dùng chung.
    """
    forbidden_exact = {"question_text", "answer_text", "verbatim_query", "verbatim_answer"}
    fields = _chunk_field_names()
    assert forbidden_exact.isdisjoint(fields)
    for name in fields:
        assert "question" not in name
        assert "answer" not in name
        assert "verbatim" not in name
        assert "query" not in name
    _assert_whitelist_intact()


def test_no_agent_field_on_chunk():
    """07 Mục 5 (chốt cuối) — agent chuyên miền không sinh trường nào trong
    dữ liệu dùng chung Ingestion–Retrieval. Không nằm trong 8 dòng đánh số
    của bảng nhưng là điều cấm tường minh ngay dưới bảng, nên phủ luôn để
    bộ test T1.4 không bỏ sót.
    """
    fields = _chunk_field_names()
    for name in fields:
        assert "agent" not in name
    _assert_whitelist_intact()


def test_9_no_verbatim_chunk_text_next_to_chunk():
    """07 Mục 2.2 + 2.1 — mẩu KHÔNG giữ bản sao chữ của mình; chữ nằm một
    bản duy nhất ở `Document.extracted_text`. Hai bản chữ thì sẽ có ngày
    lệch nhau (CLAUDE.md Mục 3 #3).
    """
    forbidden_exact = {"text", "chunk_text", "content", "extracted_text", "body", "raw_text"}
    fields = _chunk_field_names()
    assert forbidden_exact.isdisjoint(fields)
    _assert_whitelist_intact()
