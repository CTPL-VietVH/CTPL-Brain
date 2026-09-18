"""T1.2 (c) — HAI số phiên bản của module schema (07 Mục 3.1 ràng buộc 3, DX3).

| Số | Tăng khi | Hai bên lệch thì |
|---|---|---|
| phá vỡ tương thích | đổi tên trường, xoá trường, đổi ý nghĩa của trường | **từ chối chạy** |
| bổ sung tương thích | thêm trường mới mà bên cũ bỏ qua được | **ghi nhật ký, vẫn chạy** |

Hai kết cục KHÁC NHAU là toàn bộ giá trị của cơ chế. Nếu lệch số bổ sung cũng
làm dừng hệ thống thì "mỗi lần thêm một trường là một lần phải dừng cả hai
service — và người ta sẽ nhanh chóng ngừng tăng số, tức là mất luôn cơ chế"
(07 Mục 3.1; CLAUDE.md Mục 3 #22). Vì vậy ở đây kiểm cả hai chiều: chiều phải
nổ, VÀ chiều không được phép nổ.
"""

from __future__ import annotations

import logging

import pytest

from schema.version import (
    LOCAL_SCHEMA_VERSION,
    SCHEMA_ADDITIVE_VERSION,
    SCHEMA_BREAKING_VERSION,
    SchemaBreakingVersionMismatchError,
    SchemaVersion,
    assert_schema_versions_compatible,
)

VERSION_LOGGER = "schema.version"
INGESTION = "Ingestion v2"
RETRIEVAL = "Retrieval v2"


def test_module_exposes_two_separate_version_numbers():
    """⛔ HAI số, không phải một (CLAUDE.md Mục 3 #22).

    Gộp thành một số là điều cấm — ca này đỏ ngay nếu ai đó "dọn gọn" bằng cách
    bỏ đi một trong hai, hoặc cho hai tên cùng trỏ vào một ô.
    """
    assert isinstance(SCHEMA_BREAKING_VERSION, int)
    assert isinstance(SCHEMA_ADDITIVE_VERSION, int)
    assert LOCAL_SCHEMA_VERSION.breaking == SCHEMA_BREAKING_VERSION
    assert LOCAL_SCHEMA_VERSION.additive == SCHEMA_ADDITIVE_VERSION

    fields = {field for field in SchemaVersion.__dataclass_fields__}
    assert fields == {"breaking", "additive"}, (
        "Một cặp số phiên bản phải có ĐÚNG hai ô riêng biệt, không gộp, không thêm"
    )


def test_breaking_version_mismatch_refuses_to_start(caplog):
    """Lệch số PHÁ VỠ tương thích → raise, không có đường chạy tiếp."""
    local = SchemaVersion(breaking=1, additive=0)
    other = SchemaVersion(breaking=2, additive=0)

    with caplog.at_level(logging.WARNING, logger=VERSION_LOGGER):
        with pytest.raises(SchemaBreakingVersionMismatchError) as excinfo:
            assert_schema_versions_compatible(
                local, other, local_name=RETRIEVAL, other_name=INGESTION
            )

    message = str(excinfo.value)
    assert "breaking=1" in message and "breaking=2" in message
    assert RETRIEVAL in message and INGESTION in message, (
        "Thông báo phải nói rõ BÊN NÀO đang ở số nào"
    )


def test_breaking_mismatch_raises_even_when_additive_also_differs():
    """Lệch cả hai số: số phá vỡ thắng — vẫn từ chối chạy, không hạ xuống cảnh báo."""
    with pytest.raises(SchemaBreakingVersionMismatchError):
        assert_schema_versions_compatible(
            SchemaVersion(breaking=1, additive=7),
            SchemaVersion(breaking=2, additive=3),
            local_name=RETRIEVAL,
            other_name=INGESTION,
        )


def test_additive_version_mismatch_logs_and_keeps_running(caplog):
    """Lệch số BỔ SUNG tương thích → ghi nhật ký, VẪN CHẠY. Không raise."""
    local = SchemaVersion(breaking=1, additive=0)
    other = SchemaVersion(breaking=1, additive=4)

    with caplog.at_level(logging.WARNING, logger=VERSION_LOGGER):
        result = assert_schema_versions_compatible(
            local, other, local_name=RETRIEVAL, other_name=INGESTION
        )

    assert result is None
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(warnings) == 1, "Phải ghi đúng một bản ghi cảnh báo — im lặng là mất cơ chế"

    logged = warnings[0].getMessage()
    assert "additive=0" in logged and "additive=4" in logged
    assert RETRIEVAL in logged and INGESTION in logged


def test_identical_versions_neither_raise_nor_log(caplog):
    """Khớp cả hai số → im lặng. Cảnh báo lúc không có gì sai thì sẽ bị bỏ qua
    lúc có gì sai."""
    with caplog.at_level(logging.WARNING, logger=VERSION_LOGGER):
        result = assert_schema_versions_compatible(
            SchemaVersion(breaking=3, additive=5),
            SchemaVersion(breaking=3, additive=5),
            local_name=RETRIEVAL,
            other_name=INGESTION,
        )

    assert result is None
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_version_names_are_required_arguments():
    """Không có tên bên nào thì thông báo lỗi vô dụng — nên hai tên là BẮT BUỘC."""
    with pytest.raises(TypeError):
        assert_schema_versions_compatible(  # type: ignore[call-arg]
            SchemaVersion(breaking=1, additive=0),
            SchemaVersion(breaking=2, additive=0),
        )


def test_schema_version_is_frozen_and_keyword_only():
    """`SchemaVersion(1, 0)` phải nổ: hai số nguyên cạnh nhau thì có ngày bị đảo
    thứ tự mà không lỗi nào báo — cùng lý do bốn thực thể ở T1.1 dùng `kw_only`.
    """
    with pytest.raises(TypeError):
        SchemaVersion(1, 0)  # type: ignore[misc]

    version = SchemaVersion(breaking=1, additive=0)
    with pytest.raises(Exception):
        version.breaking = 2  # type: ignore[misc]
