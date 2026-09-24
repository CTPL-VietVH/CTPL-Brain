"""Shared fixtures for the T2.7 promote tests — inserts `packages/` into
`sys.path`, same as the other Nhóm 2 test folders.

No live PostgreSQL and no live Qdrant: `InMemorySharedProfileStore` enforces
every constraint `schema/store_schema.py` declares, and
`InMemoryVectorStoreWriter` stands in for the collection. The BGE-M3 model is
faked too — GĐ6's real behaviour is T2.5's subject and is tested there; what
matters here is that GĐ6 ran and produced vectors before anything was
written.
"""

from __future__ import annotations

import pathlib
import sys
from datetime import date, datetime

import numpy as np

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages"))

from ingestion.relations_scan import InMemorySpace, InMemorySpaceScanScope  # noqa: E402
from ingestion.space_registry import InMemorySpaceRegistry  # noqa: E402
from schema.document import DateSource, Document  # noqa: E402

CHUNK_LENGTH_CAP = 5000
INGESTED_AT = datetime(2026, 9, 22, 15, 0)

# The four GĐ7 scan parameters. Real values live in `config/ingestion.yaml`;
# these are the test's own, passed explicitly because neither the scan nor
# the promote has a default for them.
SATURATION_EPSILON = 0.01
SATURATION_ROUNDS = 3
SCAN_PAIR_BUDGET = 100
SCAN_TIME_BUDGET = 10.0

# Fake embedding width. Deliberately NOT 1024: nothing in this module checks
# the contract dimension — that check lives in `ghi_vao_qdrant` behind the
# `VectorStoreWriter` Protocol (T1.3/T2.5), and a lookalike number here would
# suggest otherwise.
FAKE_EMBEDDING_DIM = 4


class FakeBgeM3:
    """Satisfies `vectorization.BgeM3Like` without loading 2.5GB.

    `encode` returns a numpy array because `sinh_vector` calls `.tolist()` on
    each row — the same shape a real `SentenceTransformer` returns.
    """

    def __init__(self, *, max_seq_length: int = 8192) -> None:
        self.max_seq_length = max_seq_length
        self.tokenizer = self
        self.encode_calls = 0

    # Used as `model.tokenizer.encode(...)` by `dem_token`.
    def encode(self, sentences, *, normalize_embeddings=None, batch_size=None):
        if isinstance(sentences, str):
            return sentences.split()
        self.encode_calls += 1
        return np.array(
            [
                [float(len(text) % 7 + index), 0.5, 0.25, 0.125]
                for index, text in enumerate(sentences)
            ],
            dtype=float,
        )


def make_scope(*spaces: InMemorySpace) -> InMemorySpaceScanScope:
    """A scope over the given Space tree; with a single space it is already at
    its fixed point, so the relation scan ends after one idle round."""
    return InMemorySpaceScanScope(list(spaces) or [InMemorySpace(space_id="space-private")])


def make_stored_document(
    *,
    document_id: str,
    version_chain_id: str,
    version_ordinal: int,
    content_fingerprint: str,
    space_id: str = "space-private",
    doc_number: str = "01/2019/QĐ-UBND",
    removed_as_wrong: bool = False,
) -> Document:
    """A document already living in the official store — the state a promote
    has to reckon with, not produce."""
    return Document(
        document_id=document_id,
        space_id=space_id,
        tenant_id="tenant-1",
        title="Bản đã có trong kho",
        doc_number=doc_number,
        issued_date=date(2019, 1, 1),
        issued_date_source=DateSource.EXTRACTED,
        effective_date=date(2019, 1, 1),
        effective_date_source=DateSource.EXTRACTED,
        ingested_at=INGESTED_AT,
        source_format="txt",
        content_fingerprint=content_fingerprint,
        extracted_text="Nội dung bản cũ.",
        version_chain_id=version_chain_id,
        version_ordinal=version_ordinal,
        removed_as_wrong=removed_as_wrong,
    )


# A document carrying every signal the promote path needs downstream: a
# `doc_number` other documents can cite, a subject line for K3, real dates.
SAMPLE_DOCUMENT = """BỘ NỘI VỤ
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: 15/2021/QĐ-BNV
Hà Nội, ngày 15 tháng 3 năm 2021

QUYẾT ĐỊNH
Về việc ban hành Quy chế quản lý tài liệu nội bộ

CHƯƠNG I
QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
1. Quyết định này quy định về công tác quản lý tài liệu nội bộ của cơ quan.
2. Mọi cán bộ, công chức phải chịu trách nhiệm bảo quản tài liệu được giao.

Điều 2. Đối tượng áp dụng
Quyết định này áp dụng đối với toàn thể cán bộ, công chức của Bộ Nội vụ.

CHƯƠNG II
ĐIỀU KHOẢN THI HÀNH

Điều 3. Hiệu lực thi hành
Quyết định này có hiệu lực thi hành kể từ ngày 01 tháng 5 năm 2021.
"""


def buffer_a_document(
    tmp_path: pathlib.Path,
    *,
    buffer,
    fingerprint_index,
    document_id: str = "doc-promote-1",
    space_id: str = "space-private",
    text: str = SAMPLE_DOCUMENT,
    name: str = "quyet-dinh-15.txt",
):
    """Run the real pre-approval chain to produce a real `BufferedIngestion`.

    Building one by hand would let these tests pass on an entry the actual
    pipeline could never produce — the promote is only interesting on what
    `pre_approval_runner` really parks.
    """
    from ingestion.pre_approval_runner import PreApprovalRequest, run_pre_approval_ingestion

    path = tmp_path / name
    path.write_text(text, encoding="utf-8")

    # T2.11 (docs/10 §4.0): the pre-approval chain refuses a Space that is not
    # registered and in use. These cases are about the promote, so the Space
    # they park into exists — the gate itself is tested in
    # `tests/t2_11_space_registry/`.
    space_registry = InMemorySpaceRegistry()
    space_registry.register(space_id)

    result = run_pre_approval_ingestion(
        PreApprovalRequest(
            path=path,
            document_id=document_id,
            space_id=space_id,
            tenant_id="tenant-1",
            title="Quyết định ban hành Quy chế quản lý tài liệu nội bộ",
            doc_number="15/2021/QĐ-BNV",
            ingested_at=INGESTED_AT,
        ),
        fingerprint_index=fingerprint_index,
        buffer=buffer,
        space_registry=space_registry,
        chunk_length_cap=CHUNK_LENGTH_CAP,
    )
    assert result.buffered is not None, "the pre-approval chain must have buffered it"
    return result.buffered
