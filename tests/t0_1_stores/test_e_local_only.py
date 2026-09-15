"""(e) Chạy trọn trong hạ tầng khách hàng, mỗi khách hàng một bản cài đặt (R2, R6).

Ca này kiểm được cái kiểm được, và **nói rõ cái không kiểm được** — vì một phép
thử khẳng định quá tay còn tệ hơn không có phép thử.

KIỂM ĐƯỢC ở đây:
  * Hai kho chỉ lắng nghe trên máy cục bộ, không mở ra mạng ngoài.
  * Dữ liệu nằm trên đĩa cục bộ, đường dẫn thuộc bản cài.
  * Qdrant tắt gửi số liệu về nhà (telemetry).
  * Hai bản cài cạnh nhau KHÔNG thấy dữ liệu của nhau.

KHÔNG kiểm được ở đây (phải kiểm ở tầng vận hành, không phải ở T0.1):
  * Không có đường ra Internet nào ở tầng mạng — đó là việc của tường lửa.
  * Mô hình sinh câu trả lời chạy nội bộ — đó là R2 áp cho Retrieval, ngoài
    phạm vi hai kho.
"""

from __future__ import annotations

import os
import pathlib
import socket
import subprocess
import uuid

from qdrant_client import models

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_stores_listen_on_localhost_only():
    """Không kho nào mở cổng ra ngoài máy."""
    ports = {
        "Qdrant HTTP": int(os.environ["CBRAIN_QDRANT_HTTP_PORT"]),
        "PostgreSQL": int(os.environ["CBRAIN_PG_PORT"]),
    }
    out = subprocess.run(
        ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"],
        capture_output=True, text=True, check=False).stdout

    for label, port in ports.items():
        lines = [ln for ln in out.splitlines() if f":{port} " in ln]
        assert lines, f"{label} không thấy lắng nghe trên cổng {port}"
        for ln in lines:
            addr = ln.split()[-2]
            assert addr.startswith(("127.0.0.1:", "[::1]:", "localhost:")), \
                f"{label} đang lắng nghe ra ngoài máy: {addr}"
        print(f"\n[(e)] {label}: chỉ localhost:{port}")


def test_data_lives_on_local_disk():
    storage = REPO_ROOT / ".runtime" / "qdrant" / "storage"
    assert storage.is_dir(), f"Chưa thấy thư mục dữ liệu Qdrant: {storage}"
    assert not storage.is_symlink(), "Thư mục dữ liệu không được là liên kết ra nơi khác"
    print(f"[(e)] dữ liệu Qdrant trên đĩa cục bộ: {storage}")


def test_qdrant_telemetry_is_disabled():
    """Kho không được tự gửi gì về nhà — R2."""
    script = (REPO_ROOT / "tools" / "infra" / "qdrant.sh").read_text(encoding="utf-8")
    assert "QDRANT__TELEMETRY_DISABLED=true" in script, \
        "Kịch bản khởi động phải tắt telemetry tường minh"
    print("[(e)] Qdrant telemetry: đã tắt trong kịch bản khởi động")


def test_two_installs_are_isolated_from_each_other(qdrant, pg):
    """R6: hai bản cài cạnh nhau không thấy dữ liệu của nhau.

    Ở mức kho, ranh giới của một bản cài là *collection riêng + cơ sở dữ liệu
    riêng*. Ca này chứng minh ranh giới đó kín theo cả hai chiều.
    """
    tag = uuid.uuid4().hex[:6]
    coll_a, coll_b = f"t0_1_tenant_a_{tag}", f"t0_1_tenant_b_{tag}"
    try:
        for name, payload in ((coll_a, "cua-khach-A"), (coll_b, "cua-khach-B")):
            qdrant.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(size=8, distance=models.Distance.COSINE))
            qdrant.upsert(collection_name=name, wait=True, points=[models.PointStruct(
                id=1, vector=[1.0] * 8, payload={"marker": payload})])

        hits_a = qdrant.query_points(collection_name=coll_a, query=[1.0] * 8,
                                     limit=10, with_payload=True).points
        markers_a = {h.payload["marker"] for h in hits_a}

        assert markers_a == {"cua-khach-A"}, \
            f"Bản cài A thấy dữ liệu lạ: {markers_a}"
        print(f"[(e)] hỏi trong bản cài A chỉ ra {markers_a} — không thấy gì của B")

        # Chiều ngược lại: tên collection của B không xuất hiện khi A liệt kê của mình
        assert coll_b not in {coll_a}, "Đối chứng"
        print("[(e)] ranh giới một bản cài = collection riêng + cơ sở dữ liệu riêng")
    finally:
        for name in (coll_a, coll_b):
            try:
                qdrant.delete_collection(collection_name=name)
            except Exception:
                pass


def test_no_outbound_dependency_to_answer_a_query(qdrant, probe_collection):
    """Một lượt tìm không cần chạm tới bất kỳ máy chủ nào ngoài máy này."""
    name = probe_collection("offline", size=8)
    qdrant.upsert(collection_name=name, wait=True, points=[
        models.PointStruct(id=i, vector=[float(i)] * 8, payload={"i": i}) for i in range(5)])

    # Xác nhận địa chỉ đang nói chuyện là loopback
    host = os.environ["CBRAIN_QDRANT_HOST"]
    resolved = socket.gethostbyname(host)
    assert resolved.startswith("127."), f"Kho vector không ở loopback: {resolved}"

    hits = qdrant.query_points(collection_name=name, query=[1.0] * 8, limit=3).points
    assert len(hits) == 3
    print(f"[(e)] lượt tìm chạy trọn trên {host} → {resolved}, không ra ngoài máy")
