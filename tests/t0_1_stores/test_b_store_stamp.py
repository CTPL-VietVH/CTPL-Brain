"""(b) Đóng dấu siêu dữ liệu lên chính kho vector, để service kiểm lúc khởi động.

Phạm vi của T0.1 là CHỨNG MINH KHO LÀM ĐƯỢC, không phải chọn cách làm.
docs/08 B2 điểm 2 và T1.3 nói rõ: `embedding_model` phải có nhà riêng — *một
điểm dữ liệu dành riêng trong collection*, HOẶC *một bảng Postgres khoá theo
tên collection* — và **"chọn cách nào cũng được, nhưng phải chọn, và ghi vào
T1.3"**. Vậy ở đây chứng minh CẢ HAI đường đều chạy được, và **không chọn**.

Ca thử quan trọng nhất là ca cuối: **đổi mô hình mà giữ nguyên số chiều**. Đó
là thứ hỏng ngầm mà cấu hình collection của Qdrant một mình không bắt được.
"""

from __future__ import annotations

import json

from qdrant_client import models

PROBE_MODEL_A = "BAAI/bge-m3"
PROBE_MODEL_B = "intfloat/multilingual-e5-large"  # CŨNG 1024 chiều — đó là cái bẫy
PROBE_DIM = 1024

STAMP_POINT_ID = 0
STAMP_TABLE = "t0_1_probe.collection_stamp"


def test_qdrant_config_carries_dim_and_metric(qdrant, probe_collection):
    """Số chiều và thước đo thì Qdrant tự mang — đọc được lúc khởi động."""
    name = probe_collection("stamp", size=PROBE_DIM, distance=models.Distance.COSINE)

    info = qdrant.get_collection(collection_name=name)
    params = info.config.params.vectors

    assert params.size == PROBE_DIM
    assert params.distance == models.Distance.COSINE
    print(f"\n[(b)] Qdrant tự mang: size={params.size} distance={params.distance.value}")


def test_qdrant_config_does_NOT_carry_model_name(qdrant, probe_collection):
    """Chứng minh lỗ hổng là THẬT, không phải suy đoán.

    Nếu một ngày Qdrant thêm tên mô hình vào cấu hình collection thì ca này đỏ,
    và đó là tin tốt — lúc đó T1.3 được đơn giản đi.
    """
    name = probe_collection("nomodel", size=PROBE_DIM)
    info = qdrant.get_collection(collection_name=name)
    blob = json.dumps(info.model_dump(mode="json"), ensure_ascii=False).lower()

    assert "bge" not in blob and "embedding_model" not in blob, \
        "Bất ngờ: cấu hình collection có mang tên mô hình — xem lại giả định của T1.3"
    print("[(b)] Qdrant KHÔNG mang tên mô hình → `embedding_model` phải có nhà riêng")


def test_home_candidate_1_dedicated_point_in_collection(qdrant, probe_collection):
    """Nhà ứng viên 1: một điểm dữ liệu dành riêng nằm trong chính collection."""
    name = probe_collection("home1", size=PROBE_DIM)

    qdrant.upsert(
        collection_name=name,
        points=[models.PointStruct(
            id=STAMP_POINT_ID,
            vector=[0.0] * PROBE_DIM,
            payload={"__stamp__": True, "embedding_model": PROBE_MODEL_A,
                     "embedding_dim": PROBE_DIM, "distance_metric": "cosine"},
        )],
        wait=True,
    )

    stamp = qdrant.retrieve(collection_name=name, ids=[STAMP_POINT_ID],
                            with_payload=True)[0].payload
    assert stamp["embedding_model"] == PROBE_MODEL_A
    print(f"[(b)] Nhà 1 (điểm dành riêng) đọc được: {stamp['embedding_model']}")


def test_home_candidate_2_postgres_table_keyed_by_collection(pg, qdrant, probe_collection):
    """Nhà ứng viên 2: một bảng Postgres khoá theo tên collection."""
    name = probe_collection("home2", size=PROBE_DIM)

    pg.execute(f"""
        CREATE TABLE IF NOT EXISTS {STAMP_TABLE} (
            collection_name text PRIMARY KEY,
            embedding_model text NOT NULL,
            embedding_dim   int  NOT NULL,
            distance_metric text NOT NULL
        )""")
    pg.execute(
        f"INSERT INTO {STAMP_TABLE} VALUES (%s,%s,%s,%s) "
        f"ON CONFLICT (collection_name) DO UPDATE SET embedding_model=EXCLUDED.embedding_model",
        (name, PROBE_MODEL_A, PROBE_DIM, "cosine"),
    )
    row = pg.execute(
        f"SELECT embedding_model, embedding_dim, distance_metric FROM {STAMP_TABLE} "
        f"WHERE collection_name=%s", (name,)).fetchone()

    assert row == (PROBE_MODEL_A, PROBE_DIM, "cosine")
    print(f"[(b)] Nhà 2 (bảng Postgres) đọc được: {row[0]}")
    pg.execute(f"DELETE FROM {STAMP_TABLE} WHERE collection_name=%s", (name,))


def test_hardest_case_same_dim_different_model_is_caught(qdrant, probe_collection):
    """⭐ Ca khó nhất: ĐỔI MÔ HÌNH MÀ GIỮ NGUYÊN SỐ CHIỀU.

    Cấu hình collection khớp hoàn hảo (1024 = 1024, cosine = cosine) nên một
    service chỉ so số chiều sẽ khởi động bình thường rồi tìm sai trong im lặng
    (07 Mục 3.1: "rủi ro nặng nhất trong nhóm"). Con dấu mang tên mô hình là
    thứ duy nhất bắt được.
    """
    name = probe_collection("hard", size=PROBE_DIM)
    qdrant.upsert(
        collection_name=name,
        points=[models.PointStruct(
            id=STAMP_POINT_ID, vector=[0.0] * PROBE_DIM,
            payload={"embedding_model": PROBE_MODEL_A, "embedding_dim": PROBE_DIM,
                     "distance_metric": "cosine"},
        )],
        wait=True,
    )

    # Service khởi động với cấu hình của mô hình KHÁC, cùng số chiều
    service_config = {"embedding_model": PROBE_MODEL_B,
                      "embedding_dim": PROBE_DIM, "distance_metric": "cosine"}

    info = qdrant.get_collection(collection_name=name)
    assert info.config.params.vectors.size == service_config["embedding_dim"], \
        "Số chiều KHỚP — đúng vì đó là điều làm ca này nguy hiểm"

    stamp = qdrant.retrieve(collection_name=name, ids=[STAMP_POINT_ID],
                            with_payload=True)[0].payload
    mismatch = stamp["embedding_model"] != service_config["embedding_model"]

    assert mismatch, "Con dấu phải phát hiện được lệch tên mô hình"
    print(f"[(b)] Ca khó nhất: kho='{stamp['embedding_model']}' "
          f"service='{service_config['embedding_model']}' cùng {PROBE_DIM} chiều "
          f"→ BẮT ĐƯỢC, service phải từ chối khởi động")
    print("[(b)] ⚠️  T0.1 chỉ chứng minh cả hai nhà đều chạy được. "
          "CHỌN nhà nào là việc của T1.3 — chưa chọn ở đây.")
