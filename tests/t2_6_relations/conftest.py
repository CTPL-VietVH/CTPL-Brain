"""Shared fixtures for T2.6 (explicit relation detection) tests — inserts
`packages/` into `sys.path` to import `ingestion.*` and `schema.*`, same as
`tests/t2_1_intake/conftest.py`.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import date, datetime

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from schema.document import DateSource, Document  # noqa: E402

CORPUS_ROOT = REPO_ROOT / "data" / "test-corpus-vn-admin"


def make_document(
    *,
    document_id: str,
    doc_number: str,
    extracted_text: str,
    space_id: str = "space-a",
    tenant_id: str = "tenant-1",
    title: str = "Văn bản thử",
    issued_date: date | None = date(2020, 1, 1),
    issued_date_source: DateSource | None = None,
    subject_entities: list[str] | None = None,
    category_labels: list[str] | None = None,
) -> Document:
    """A minimally-filled `Document` — every field outside the explicit
    parameters is fixed to a value irrelevant to `ingestion.relations`.

    `issued_date_source` defaults to `EXTRACTED` whenever `issued_date` is
    given (`None` falls back to `DEFAULT_INGESTION_DATE`) — pass it
    explicitly to build the "date present but NOT reliable" shape that
    `detect_inferred_amendment_relations`'s date gate must reject (06 Mục
    6.4: only `EXTRACTED`/`CONFIRMED` are trusted).
    """
    resolved_issued_date = issued_date if issued_date is not None else date(2020, 1, 1)
    resolved_issued_date_source = (
        issued_date_source
        if issued_date_source is not None
        else (DateSource.EXTRACTED if issued_date is not None else DateSource.DEFAULT_INGESTION_DATE)
    )
    return Document(
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        title=title,
        doc_number=doc_number,
        issued_date=resolved_issued_date,
        issued_date_source=resolved_issued_date_source,
        effective_date=resolved_issued_date,
        effective_date_source=resolved_issued_date_source,
        ingested_at=datetime(2026, 9, 22, 9, 0),
        source_format="docx",
        content_fingerprint=f"fp-{document_id}",
        extracted_text=extracted_text,
        version_chain_id=f"chain-{document_id}",
        version_ordinal=1,
        subject_entities=subject_entities if subject_entities is not None else [],
        category_labels=category_labels if category_labels is not None else [],
    )
