"""(a) Lọc loại trừ theo danh sách định danh + lọc theo phạm vi Space.

Đây là hình dạng thật của bước 1 và bước 2 ở 06 Mục 6.2: phạm vi quyền cắt
không gian tìm, danh sách "gỡ vì sai" truyền vào như danh sách loại trừ, cả hai
tính TƯƠI tại thời điểm hỏi (NT3) nên phải truyền theo từng truy vấn chứ không
được đóng băng vào payload.

07 Mục 6 (S7) chốt chi phí tỷ lệ với KÍCH THƯỚC DANH SÁCH, không phải kích
thước kho — phép thử dưới đây thử với vài trăm định danh đúng như T0.1 đòi.
"""

from __future__ import annotations

import random
import time

from qdrant_client import models

# --- Tham số của riêng phép thử này, không phải tham số vận hành ---
PROBE_DOC_COUNT = 400          # số tài liệu
PROBE_CHUNKS_PER_DOC = 10      # → 4.000 mẩu, cỡ kho vài nghìn tài liệu của thiết kế
PROBE_SPACE_COUNT = 12
PROBE_EXCLUDED_DOCS = 300      # "vài trăm định danh" theo đúng chữ của T0.1
PROBE_ALLOWED_SPACES = 4


def test_exclusion_list_combined_with_space_scope(qdrant, probe_collection):
    rng = random.Random(20260914)
    name = probe_collection("excl")

    doc_ids = [f"doc-{i:04d}" for i in range(PROBE_DOC_COUNT)]
    space_ids = [f"space-{i:02d}" for i in range(PROBE_SPACE_COUNT)]
    doc_space = {d: rng.choice(space_ids) for d in doc_ids}

    points = []
    pid = 0
    for doc in doc_ids:
        for _ in range(PROBE_CHUNKS_PER_DOC):
            points.append(
                models.PointStruct(
                    id=pid,
                    vector=[rng.gauss(0, 1) for _ in range(1024)],
                    # Chỉ hai trường cắt không gian tìm — đúng QT2. Không có
                    # danh sách quyền, không có loại Space, không có nhãn.
                    payload={"document_ref": doc, "space_ref": doc_space[doc]},
                )
            )
            pid += 1
    qdrant.upload_points(collection_name=name, points=points, wait=True)
    qdrant.create_payload_index(
        collection_name=name, field_name="space_ref",
        field_schema=models.PayloadSchemaType.KEYWORD, wait=True,
    )
    qdrant.create_payload_index(
        collection_name=name, field_name="document_ref",
        field_schema=models.PayloadSchemaType.KEYWORD, wait=True,
    )

    # Hai danh sách TƯƠI, dựng ngay lúc hỏi
    allowed_spaces = rng.sample(space_ids, PROBE_ALLOWED_SPACES)
    excluded_docs = rng.sample(doc_ids, PROBE_EXCLUDED_DOCS)

    query_filter = models.Filter(
        must=[models.FieldCondition(
            key="space_ref", match=models.MatchAny(any=allowed_spaces))],
        must_not=[models.FieldCondition(
            key="document_ref", match=models.MatchAny(any=excluded_docs))],
    )

    probe_vector = [rng.gauss(0, 1) for _ in range(1024)]
    started = time.perf_counter()
    hits = qdrant.query_points(
        collection_name=name, query=probe_vector,
        query_filter=query_filter, limit=50, with_payload=True,
    ).points
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert hits, "Bộ lọc kết hợp không được trả về rỗng khi vẫn còn tài liệu hợp lệ"

    excluded_set = set(excluded_docs)
    allowed_set = set(allowed_spaces)
    for h in hits:
        assert h.payload["document_ref"] not in excluded_set, \
            f"Tài liệu bị loại trừ vẫn lọt: {h.payload['document_ref']}"
        assert h.payload["space_ref"] in allowed_set, \
            f"Mẩu ngoài phạm vi quyền vẫn lọt: {h.payload['space_ref']}"

    # Đối chứng: đúng những tài liệu lẽ ra còn lại thì còn lại
    survivors = {d for d in doc_ids
                 if doc_space[d] in allowed_set and d not in excluded_set}
    assert survivors, "Phép thử tự hỏng: không còn tài liệu nào để tìm"

    print(f"\n[(a)] {PROBE_DOC_COUNT} tài liệu / {len(points)} mẩu / "
          f"{PROBE_SPACE_COUNT} Space")
    print(f"[(a)] loại trừ {PROBE_EXCLUDED_DOCS} định danh + giới hạn "
          f"{PROBE_ALLOWED_SPACES} Space → {len(survivors)} tài liệu còn lại")
    print(f"[(a)] {len(hits)} kết quả, không ca nào lọt bộ lọc, {elapsed_ms:.1f} ms")


def test_exclusion_list_is_passed_per_query_not_frozen(qdrant, probe_collection):
    """Danh sách loại trừ đổi giữa hai lượt hỏi thì kết quả phải đổi THEO NGAY.

    Đây là NT3 ở dạng kiểm được: nếu có ai đó đóng băng danh sách vào payload
    thì ca này đỏ. Cũng chính là con bug thật ghi ở điều cấm số 9.
    """
    rng = random.Random(7)
    name = probe_collection("fresh")

    points = [
        models.PointStruct(
            id=i,
            vector=[rng.gauss(0, 1) for _ in range(1024)],
            payload={"document_ref": f"doc-{i}", "space_ref": "space-00"},
        )
        for i in range(50)
    ]
    qdrant.upload_points(collection_name=name, points=points, wait=True)
    qdrant.create_payload_index(
        collection_name=name, field_name="document_ref",
        field_schema=models.PayloadSchemaType.KEYWORD, wait=True,
    )

    probe_vector = [rng.gauss(0, 1) for _ in range(1024)]

    before = qdrant.query_points(
        collection_name=name, query=probe_vector, limit=10, with_payload=True,
    ).points
    top_doc = before[0].payload["document_ref"]

    # Lượt sau: Manager vừa đánh dấu tài liệu hạng nhất là "gỡ vì sai"
    after = qdrant.query_points(
        collection_name=name, query=probe_vector, limit=10, with_payload=True,
        query_filter=models.Filter(must_not=[models.FieldCondition(
            key="document_ref", match=models.MatchAny(any=[top_doc]))]),
    ).points

    assert top_doc not in {h.payload["document_ref"] for h in after}, \
        "Quyết định gỡ phải có hiệu lực ngay ở lượt hỏi kế tiếp"
    print(f"\n[(a)] gỡ '{top_doc}' giữa hai lượt → biến mất ngay, không nạp lại gì")
