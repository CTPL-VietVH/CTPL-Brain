"""T2.1 (k) — audit #5: `content_fingerprint` rỗng hoặc chỉ toàn khoảng trắng
phải bị từ chối ngay ở `decide_intake`, để `receive_and_validate` tự động
thừa hưởng việc kiểm tra này (không cần lặp lại ở hai chỗ).

`content_fingerprint` là khoá tra trùng-lặp duy nhất (07 Mục 2.1) — một giá
trị rỗng lọt qua sẽ khiến mọi tài liệu "không vân tay" bị coi là trùng nhau
trong cùng một Space.
"""

from __future__ import annotations

import pytest

from ingestion.intake import VanTayNoiDungRong, decide_intake, receive_and_validate

from .conftest import make_request


@pytest.mark.parametrize("bad_fingerprint", ["", "   ", "\t\n"])
def test_decide_intake_rejects_empty_or_blank_fingerprint(fingerprint_index, space_registry, bad_fingerprint):
    with pytest.raises(VanTayNoiDungRong):
        decide_intake(
            space_id="space-a",
            content_fingerprint=bad_fingerprint,
            fingerprint_index=fingerprint_index,
            space_registry=space_registry,
        )


def test_receive_and_validate_inherits_the_same_rejection(fingerprint_index, space_registry):
    with pytest.raises(VanTayNoiDungRong):
        receive_and_validate(
            make_request(document_id="doc-a", space_id="space-a", content_fingerprint=""),
            fingerprint_index=fingerprint_index,
            space_registry=space_registry,
        )
