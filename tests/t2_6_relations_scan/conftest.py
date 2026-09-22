"""Shared fixtures for T2.6 (relation scan orchestration) tests — inserts
`packages/` into `sys.path` to import `ingestion.*` and `schema.*`, same as
`tests/t2_6_relations/conftest.py`.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import date, datetime

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from schema.document import DateSource, Document  # noqa: E402

# A real Vietnamese administrative citation clause — same shape as the one
# in `data/test-corpus-vn-admin/phap-che-tuan-thu/30_2020_ND_CP.docx`, with
# the amendment vocabulary deliberately absent so it stays a REFERENCES.
CITATION_110 = (
    "Căn cứ Nghị định số 110/2004/NĐ-CP ngày 08 tháng 4 năm 2004 "
    "của Chính phủ về công tác văn thư;"
)
DOC_NUMBER_110 = "110/2004/NĐ-CP"
ISSUED_110 = date(2004, 4, 8)


def make_document(
    *,
    document_id: str,
    doc_number: str,
    extracted_text: str = "Văn bản không dẫn chiếu văn bản nào.",
    space_id: str = "space-own",
    tenant_id: str = "tenant-1",
    title: str = "Văn bản thử",
    issued_date: date = date(2020, 1, 1),
    issued_date_source: DateSource = DateSource.EXTRACTED,
    subject_entities: list[str] | None = None,
    category_labels: list[str] | None = None,
) -> Document:
    """A minimally-filled `Document` — every field outside the explicit
    parameters is fixed to a value irrelevant to `ingestion.relations_scan`.

    `subject_entities` defaults to empty, which GATES OFF K3
    (`detect_inferred_amendment_relations`): a test that wants an inferred
    AMENDS_OR_REPLACES must set it on both documents on purpose.
    """
    return Document(
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        title=title,
        doc_number=doc_number,
        issued_date=issued_date,
        issued_date_source=issued_date_source,
        effective_date=issued_date,
        effective_date_source=issued_date_source,
        ingested_at=datetime(2026, 9, 22, 11, 0),
        source_format="docx",
        content_fingerprint=f"fp-{document_id}",
        extracted_text=extracted_text,
        version_chain_id=f"chain-{document_id}",
        version_ordinal=1,
        subject_entities=subject_entities if subject_entities is not None else [],
        category_labels=category_labels if category_labels is not None else [],
    )


class StubClock:
    """A clock that only moves when a test moves it — the whole reason
    `scan_relations_for_new_document` takes `clock` instead of calling
    `time.monotonic` itself (no test may need to wait ten real minutes to
    exercise `scan_time_budget`).

    Returns `readings` in order, then repeats the last one forever.
    """

    def __init__(self, readings: list[float]) -> None:
        self._readings = list(readings)
        self.calls = 0

    def __call__(self) -> float:
        index = min(self.calls, len(self._readings) - 1)
        self.calls += 1
        return self._readings[index]
