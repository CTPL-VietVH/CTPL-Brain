"""T2.1 (l) — audit #6: bất biến nội bộ trước khi dựng `Document` (proceed=True
kéo theo `version_chain_id`/`version_ordinal` khác `None`) phải được kiểm bằng
`if ... raise AssertionError(...)` tường minh, KHÔNG dùng `assert` trần —
`assert` biến mất hoàn toàn khi chạy `python -O`, nghĩa là bất biến im lặng
không còn được kiểm và `Document` có thể được dựng với trường `None` sai kiểu.

Test này dựng lại đúng kịch bản: monkeypatch `decide_intake` để trả một
`IntakeDecision` vi phạm bất biến (`proceed=True`, `version_chain_id=None`),
rồi gọi `receive_and_validate` trong một tiến trình con — chạy CẢ hai lần,
có và không có cờ `-O` — và đòi hỏi cả hai lần đều raise `AssertionError`
tường minh giống nhau. Nếu code còn dùng `assert` trần, lần chạy `-O` sẽ
không raise gì (hoặc raise lỗi khác muộn hơn, ở chỗ khác) thay vì
`AssertionError` ngay tại chỗ.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

_SCRIPT = """
import sys
sys.path.insert(0, {packages_dir!r})

from datetime import date, datetime

import ingestion.intake as intake_mod
from schema.document import DateSource

def fake_decide_intake(**kwargs):
    return intake_mod.IntakeDecision(
        proceed=True,
        version_chain_id=None,
        version_ordinal=None,
        version_declared_by=None,
    )

intake_mod.decide_intake = fake_decide_intake

request = intake_mod.IntakeRequest(
    document_id="doc-a",
    space_id="space-a",
    tenant_id="tenant-1",
    title="T",
    doc_number="1/2024",
    issued_date=date(2024, 1, 1),
    issued_date_source=DateSource.EXTRACTED,
    effective_date=date(2024, 1, 1),
    effective_date_source=DateSource.EXTRACTED,
    ingested_at=datetime(2024, 1, 1),
    source_format="pdf",
    content_fingerprint="fp-a",
    extracted_text="x",
)

intake_mod.receive_and_validate(request, fingerprint_index=intake_mod.InMemoryFingerprintIndex())
"""


def _run(extra_flags: list[str]) -> subprocess.CompletedProcess:
    script = _SCRIPT.format(packages_dir=str(REPO_ROOT / "packages"))
    return subprocess.run(
        [sys.executable, *extra_flags, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_invariant_raises_assertion_error_normally():
    result = _run([])
    assert result.returncode != 0
    assert "AssertionError" in result.stderr


def test_invariant_still_raises_assertion_error_under_python_o():
    result = _run(["-O"])
    assert result.returncode != 0, (
        "Dưới python -O, receive_and_validate không raise gì — bất biến nội bộ "
        "đã bị `assert` trần bỏ qua thay vì `if ... raise AssertionError(...)` "
        f"tường minh.\\nstdout={result.stdout!r}\\nstderr={result.stderr!r}"
    )
    assert "AssertionError" in result.stderr
