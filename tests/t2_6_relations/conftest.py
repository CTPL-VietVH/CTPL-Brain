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
) -> Document:
    """A minimally-filled `Document` — every field outside `document_id`,
    `space_id`, `doc_number`, `extracted_text` and `issued_date` is fixed to
    a value irrelevant to `ingestion.relations`.
    """
    return Document(
        document_id=document_id,
        space_id=space_id,
        tenant_id=tenant_id,
        title=title,
        doc_number=doc_number,
        issued_date=issued_date if issued_date is not None else date(2020, 1, 1),
        issued_date_source=DateSource.EXTRACTED if issued_date is not None else DateSource.DEFAULT_INGESTION_DATE,
        effective_date=issued_date if issued_date is not None else date(2020, 1, 1),
        effective_date_source=DateSource.EXTRACTED if issued_date is not None else DateSource.DEFAULT_INGESTION_DATE,
        ingested_at=datetime(2026, 9, 22, 9, 0),
        source_format="docx",
        content_fingerprint=f"fp-{document_id}",
        extracted_text=extracted_text,
        version_chain_id=f"chain-{document_id}",
        version_ordinal=1,
    )
