"""T2.1 (i) — audit #3: `declared_previous_version` phải cùng Space với
request. Không kiểm điều này thì một chuỗi phiên bản có thể vắt qua ranh
giới Space — hai Space có thể có quyền đọc khác nhau, nên chuỗi phiên bản
vắt Space là một cách rò rỉ cấu trúc tài liệu ra ngoài Space gốc.
"""

from __future__ import annotations

import pytest

from ingestion.intake import BanMoiKhacSpace, receive_and_validate

from .conftest import make_request


def test_declared_previous_version_in_a_different_space_is_rejected(fingerprint_index):
    previous = receive_and_validate(
        make_request(document_id="doc-old", space_id="space-a", content_fingerprint="fp-v1"),
        fingerprint_index=fingerprint_index,
    ).document

    with pytest.raises(BanMoiKhacSpace):
        receive_and_validate(
            make_request(
                document_id="doc-new",
                space_id="space-b",
                content_fingerprint="fp-v2",
                declared_previous_version=previous,
            ),
            fingerprint_index=fingerprint_index,
        )
