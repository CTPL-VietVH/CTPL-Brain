"""(d) Đọc quan hệ giữa tài liệu TẠI THỜI ĐIỂM TRUY VẤN, độ trễ thấp, vài nghìn nút.

docs/08 T0.1 chốt: lớp quan hệ nằm trong PostgreSQL bằng truy vấn đệ quy —
**không kho đồ thị riêng**. "Ba kho" trong 06 và 07 là ba kho LOGIC; vật lý chỉ
có hai. Mọi câu "kho đồ thị" đọc là *lớp quan hệ trong PostgreSQL*.

Hai điều phải chứng minh, không chỉ một:
  1. Đi hết CHUỖI SỬA ĐỔI cả hai chiều đủ nhanh (06 Mục 6.2).
  2. Trạng thái duyệt đọc TƯƠI lúc hỏi — Manager duyệt xong là có hiệu lực
     ngay, không nạp lại mẩu nào (06 Mục 6.4, và điều cấm số 10).

Quy ước chiều theo 07 Mục 2.3: **`from` TÁC ĐỘNG LÊN `to`**. Với sửa đổi/thay
thế thì `from` là văn bản ra sau. "Ngược lên để có bối cảnh gốc" = đi theo `to`;
"xuôi xuống để biết còn hiệu lực không" = đi ngược lại theo `from`.
"""

from __future__ import annotations

import time

REL_TABLE = "t0_1_probe.relation_edge"

PROBE_NODES = 4_000       # "đồ thị vài nghìn nút" đúng chữ của T0.1
PROBE_CHAIN_LEN = 12      # một chuỗi sửa đổi dài 12 mắt xích
LATENCY_BUDGET_MS = 50.0  # "độ trễ thấp" — trần của riêng phép thử này


def _seed(pg) -> None:
    pg.execute(f"""
        CREATE TABLE IF NOT EXISTS {REL_TABLE} (
            edge_id          bigserial PRIMARY KEY,
            from_document    text NOT NULL,
            to_document      text NOT NULL,
            relation_kind    text NOT NULL,
            approval_state   text NOT NULL
        )""")
    pg.execute(f"TRUNCATE {REL_TABLE}")

    rows = []
    # Một chuỗi sửa đổi dài: doc-0000 bị sửa bởi doc-0001, bị sửa bởi doc-0002...
    for i in range(PROBE_CHAIN_LEN):
        rows.append((f"doc-{i + 1:04d}", f"doc-{i:04d}", "sua_doi_thay_the", "da_duyet"))
    # Nhiễu nền: vài nghìn cạnh khác để đồ thị không rỗng quanh chuỗi trên
    for i in range(PROBE_CHAIN_LEN, PROBE_NODES):
        rows.append((f"doc-{i:04d}", f"doc-{(i * 7) % PROBE_NODES:04d}", "dan_chieu", "da_duyet"))

    with pg.cursor() as cur:
        cur.executemany(
            f"INSERT INTO {REL_TABLE} (from_document,to_document,relation_kind,approval_state) "
            f"VALUES (%s,%s,%s,%s)", rows)
    pg.execute(f"CREATE INDEX IF NOT EXISTS rel_from_idx ON {REL_TABLE}(from_document)")
    pg.execute(f"CREATE INDEX IF NOT EXISTS rel_to_idx   ON {REL_TABLE}(to_document)")
    pg.execute(f"ANALYZE {REL_TABLE}")


# "Xuôi xuống để biết còn hiệu lực không": từ một tài liệu, đi ngược theo `from`
# để tìm mọi văn bản ra sau đã sửa nó.
SQL_FORWARD = f"""
WITH RECURSIVE nguoc_len_chuoi(document_ref, depth) AS (
    SELECT %s::text, 0
  UNION
    SELECT e.from_document, c.depth + 1
    FROM {REL_TABLE} e
    JOIN nguoc_len_chuoi c ON e.to_document = c.document_ref
    WHERE e.relation_kind = 'sua_doi_thay_the'
      AND e.approval_state = %s
      AND c.depth < %s
)
SELECT document_ref, depth FROM nguoc_len_chuoi WHERE depth > 0 ORDER BY depth
"""


def test_walk_amendment_chain_within_latency_budget(pg):
    _seed(pg)
    started = time.perf_counter()
    rows = pg.execute(SQL_FORWARD, ("doc-0000", "da_duyet", 64)).fetchall()
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert len(rows) == PROBE_CHAIN_LEN, \
        f"Phải đi hết {PROBE_CHAIN_LEN} mắt xích, chỉ thấy {len(rows)}"
    assert [r[1] for r in rows] == list(range(1, PROBE_CHAIN_LEN + 1))
    assert elapsed_ms < LATENCY_BUDGET_MS, \
        f"Độ trễ {elapsed_ms:.1f} ms vượt trần {LATENCY_BUDGET_MS} ms"

    n_edges = pg.execute(f"SELECT count(*) FROM {REL_TABLE}").fetchone()[0]
    print(f"\n[(d)] {n_edges:,} cạnh / {PROBE_NODES:,} nút")
    print(f"[(d)] đi hết chuỗi {PROBE_CHAIN_LEN} mắt xích: {elapsed_ms:.2f} ms "
          f"(trần {LATENCY_BUDGET_MS:.0f} ms) — không cần kho đồ thị riêng")


def test_approval_state_is_read_fresh_at_query_time(pg):
    """⭐ Manager duyệt/gỡ một liên kết → có hiệu lực NGAY, không nạp lại mẩu nào.

    Đây là điều cấm số 10 ở dạng kiểm được: nếu ai đó chép `approval_state`
    xuống payload cạnh mẩu thì hiệu lực tức thì này biến mất.
    """
    _seed(pg)

    before = pg.execute(SQL_FORWARD, ("doc-0000", "da_duyet", 64)).fetchall()
    assert len(before) == PROBE_CHAIN_LEN

    # Manager gỡ duyệt mắt xích thứ 5 — chỉ một thao tác ghi trong kho quan hệ
    pg.execute(f"UPDATE {REL_TABLE} SET approval_state='da_tu_choi' "
               f"WHERE from_document='doc-0005' AND to_document='doc-0004'")

    after = pg.execute(SQL_FORWARD, ("doc-0000", "da_duyet", 64)).fetchall()

    assert len(after) == 4, \
        f"Chuỗi phải đứt tại mắt xích bị gỡ duyệt, còn 4; đang là {len(after)}"
    print(f"[(d)] gỡ duyệt 1 liên kết → chuỗi {PROBE_CHAIN_LEN} tụt còn {len(after)} "
          f"ngay ở lượt hỏi kế tiếp, KHÔNG nạp lại mẩu nào")


def test_cycle_does_not_hang_the_query(pg):
    """Đồ thị thật có vòng. `UNION` khử trùng nên truy vấn phải dừng, không treo."""
    _seed(pg)
    # Tạo một vòng: doc-0000 sửa doc-0011 (trong khi doc-0011 đã sửa ngược lên)
    pg.execute(f"INSERT INTO {REL_TABLE} (from_document,to_document,relation_kind,approval_state) "
               f"VALUES ('doc-0000','doc-0011','sua_doi_thay_the','da_duyet')")

    started = time.perf_counter()
    rows = pg.execute(SQL_FORWARD, ("doc-0000", "da_duyet", 64)).fetchall()
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert elapsed_ms < LATENCY_BUDGET_MS, f"Vòng làm truy vấn chậm bất thường: {elapsed_ms:.1f} ms"
    assert rows, "Vẫn phải trả về được kết quả khi có vòng"
    print(f"[(d)] đồ thị có vòng: dừng sau {elapsed_ms:.2f} ms, không treo")
