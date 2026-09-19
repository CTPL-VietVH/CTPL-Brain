"""`embedding_registry` — đọc/ghi CON DẤU THẬT trên kho, và điểm vào khởi động
duy nhất mà cả hai service PHẢI gọi trước khi phục vụ bất kỳ truy vấn nào
(07 Mục 3.1 ràng buộc 2, docs/08 T1.3).

T1.2 (`schema.config`) đã xây phần QUYẾT ĐỊNH thuần logic: `StoreStamp`,
`ContractConfig`, và `assert_contract_matches_store_stamp` so ba trường của
chúng. T1.2 cố ý CHƯA chọn `embedding_model` sống ở đâu trên kho thật — đó là
việc của module này.

──────────────────────────────────────────────────────────────────────────
CHỌN NHÀ (quyết định đã được PO duyệt trước, vòng phản biện N6, Phương án 3)
──────────────────────────────────────────────────────────────────────────

T0.1 (b) đã CHỨNG MINH (không chọn) hai nhà ứng viên cho `embedding_model`:
một điểm dữ liệu dành riêng trong chính collection Qdrant, hoặc một bảng
PostgreSQL khoá theo tên collection. Module này CHỌN nhà 2 — PostgreSQL —
bằng hai bảng:

- `embedding_models` — CATALOG: `(model_name, model_version)` làm khoá chính,
  cộng `embedding_dim`. Đây là danh mục MỌI bản model từng được biết tới —
  một bản ghi LỊCH SỬ, không phải một hàng cấu hình được ghi đè.
- `embedding_model_collections` — bản ghi model nào đang ACTIVE cho MỘT
  collection Qdrant cụ thể, khoá chính là `collection_name`, khoá ngoại trỏ
  về `embedding_models (model_name, model_version)`.

`model_version` là cột PHỤ trong catalog — mục đích DUY NHẤT là lưu lịch sử/
audit (biết chính xác bản nào từng dùng cho collection nào, tại sao cần hai
bảng thay vì một). Nó KHÔNG được đưa vào `StoreStamp` hay `ContractConfig`:
hai class đó đã CHỐT đúng ba trường theo docs/07 Mục 3.1, module này không có
thẩm quyền tự thêm trường thứ tư. So khớp mismatch (`assert_contract_matches_
store_stamp`, import nguyên từ `schema.config`, KHÔNG viết lại logic so khớp
ở đây) vẫn chỉ dựa trên `embedding_model` (tên).

Vì sao CHỈ `embedding_model` lấy từ Postgres, còn `embedding_dim` và
`distance_metric` lấy THẲNG từ chính Qdrant: T0.1 (b) đã đo thật — cấu hình
collection của Qdrant mang `size` và `distance` một cách ĐÁNG TIN (đọc từ
chính kho, không ai gõ tay lại được), nhưng KHÔNG mang tên mô hình. Đọc lại
`embedding_dim`/`distance_metric` từ một bảng Postgres riêng là tạo thêm một
ô phải khớp với ô mà Qdrant đã tự đảm bảo đúng — đúng y hệt lý do
`DistanceMetric` không tách `l2_normalize` thành khoá riêng trong `config.py`.

Tên/nhãn collection Qdrant là KHOÁ NỐI (join key) giữa hai kho — bảng active-
record khoá theo `collection_name`, KHÔNG nhét fingerprint vào payload của
từng điểm dữ liệu (point) trong collection: cạnh mẩu (`Chunk`, xem `chunk.py`)
chỉ được chứa whitelist đã chốt ở 07 Mục 5, `embedding_model` không có trong
whitelist đó và không có lý do gì phải lặp lại ở mọi point khi một collection
chỉ có MỘT model.

──────────────────────────────────────────────────────────────────────────
⛔ NỢ KỸ THUẬT CỐ Ý — KHÔNG xây ở đây
──────────────────────────────────────────────────────────────────────────

Module này KHÔNG có, và CỐ Ý KHÔNG xây, bất kỳ logic "đổi model rồi tự động
re-point traffic" hay orchestration nạp lại toàn kho nào. `set_active_
embedding_model_for_collection` chỉ là MỘT câu UPSERT đơn giản: gọi lại nó với
model khác cho cùng `collection_name` là hành vi HỢP LỆ — đúng bước "đóng dấu
lại" thủ công sau khi nạp lại toàn kho theo quy trình v1 đã chốt (docs/07
Mục 3.1: dừng dịch vụ → nạp lại toàn kho bằng mô hình mới → đóng dấu lại →
bật lại cùng lúc). Đây KHÔNG phải một luồng đổi model không gián đoạn.

docs/07 Mục 3.1 đã ghi rõ: "cách viết ràng buộc 2 đã mở sẵn đường cho phương
án không gián đoạn về sau ... vì con dấu nằm trên kho chứ không phải giữa hai
service, nên hai kho có hai con dấu khác nhau vẫn cùng tồn tại được". Vì
`collection_name` là khoá chính của bảng active-record (không phải một hàng
"cấu hình toàn cục" duy nhất), một bản cài có nhiều collection với nhiều con
dấu khác nhau ĐÃ chạy được ngay bây giờ mà không cần sửa gì thêm — cái CHƯA
xây là công cụ tự động chuyển đổi traffic giữa chúng (đó là việc của T1.5,
công cụ nạp lại toàn kho, và vẫn là một quy trình THỦ CÔNG có kế hoạch trước
ở v1, không phải migration tự động).

──────────────────────────────────────────────────────────────────────────
Vì sao KHÔNG import `psycopg` trực tiếp
──────────────────────────────────────────────────────────────────────────

Mọi hàm trong module nhận một đối tượng kết nối Postgres kiểu "duck-typed":
chỉ cần có `.execute(sql, params)` trả về một cursor có `.fetchone()` — giống
hệt cách `tests/t0_1_stores/conftest.py` dùng `pg.execute(...)`. `packages/
schema/` là module DÙNG CHUNG cho cả hai service; ép một driver Postgres cụ
thể vào đây là ép một lựa chọn triển khai (R6: mỗi bản cài độc lập) vào tầng
hợp đồng dùng chung.

`qdrant_client.QdrantClient` thì KHÔNG duck-type: Qdrant là công nghệ đã CHỐT
(CLAUDE.md Mục 5), và việc map `qdrant_client.models.Distance` sang
`DistanceMetric` nội bộ là chính việc mà module này phải làm.
"""

from __future__ import annotations

from typing import Any, Protocol

from qdrant_client import QdrantClient
from qdrant_client.models import Distance as QdrantDistance

from .config import (
    ContractConfig,
    DistanceMetric,
    StoreStamp,
    assert_contract_matches_store_stamp,
)

__all__ = [
    "EmbeddingRegistryError",
    "CollectionNotFoundOnQdrantError",
    "UnsupportedQdrantDistanceError",
    "CollectionNotStampedError",
    "CatalogDimensionConflictError",
    "CatalogEntryConflictError",
    "UnknownCatalogEntryError",
    "PgConnectionLike",
    "EMBEDDING_MODELS_TABLE",
    "EMBEDDING_MODEL_COLLECTIONS_TABLE",
    "EMBEDDING_MODELS_TABLE_DDL",
    "EMBEDDING_MODEL_COLLECTIONS_TABLE_DDL",
    "read_store_stamp",
    "assert_collection_ready_for_contract",
    "register_embedding_model",
    "set_active_embedding_model_for_collection",
]


# --------------------------------------------------------------------------- #
# Lỗi — mỗi loại một tên riêng, để nơi gọi bắt được đúng thứ nó muốn bắt
# (cùng phong cách `schema.config`)
# --------------------------------------------------------------------------- #


class EmbeddingRegistryError(Exception):
    """Gốc cho mọi lỗi khi đọc/ghi con dấu embedding trên kho thật."""


class CollectionNotFoundOnQdrantError(EmbeddingRegistryError):
    """Collection nêu tên không tồn tại trên Qdrant.

    Không suy đoán số chiều hay thước đo từ đâu khác khi collection vắng mặt —
    con dấu chỉ đọc được từ một kho ĐÃ TỒN TẠI.
    """


class UnsupportedQdrantDistanceError(EmbeddingRegistryError):
    """Thước đo Qdrant không map được sang `DistanceMetric` nội bộ.

    v1 CHỐT `DistanceMetric` chỉ có COSINE/DOT/EUCLID (07 Mục 3.1,
    `schema.config.DistanceMetric`). Qdrant còn có `MANHATTAN` — không có ánh
    xạ tương ứng, và một collection dùng `Manhattan` coi như đã sai ngay từ
    lúc tạo, không phải một ca "lệch cấu hình" bình thường.
    """


class CollectionNotStampedError(EmbeddingRegistryError):
    """Collection CHƯA TỪNG có bản ghi active nào trong Postgres.

    Đây là tình huống collection MỚI TOANH mà chưa ai gán model — KHÔNG suy
    đoán ngầm bằng cách "dùng tạm model trong `ContractConfig` của bên gọi",
    vì đó đúng là điều làm mất tác dụng của con dấu: bên gọi luôn có sẵn một
    `ContractConfig`, dùng nó để lấp chỗ trống là tự xác nhận chính mình.
    """


class CatalogDimensionConflictError(EmbeddingRegistryError):
    """`embedding_dim` ghi trong catalog Postgres LỆCH với dim thật của Qdrant.

    Đây là dấu hiệu CATALOG HỎNG (ai đó từng ghi sai tay, hoặc model đổi dim
    mà quên đăng ký bản `model_version` mới) — TỪ CHỐI CHẠY thay vì lặng lẽ
    tin dim thật của Qdrant và bỏ qua catalog.
    """


class CatalogEntryConflictError(EmbeddingRegistryError):
    """Đăng ký lại `(model_name, model_version)` với `embedding_dim` KHÁC.

    Catalog là bản ghi LỊCH SỬ (`embedding_models`), không phải một hàng cấu
    hình được ghi đè. Model thật sự đổi dim thì đó phải là một
    `model_version` khác, không phải ghi đè lặng lẽ lên bản cũ.
    """


class UnknownCatalogEntryError(EmbeddingRegistryError):
    """Gán active cho `(model_name, model_version)` chưa từng có trong catalog.

    Bọc lại lỗi vi phạm khoá ngoại (FK) của Postgres thành một lỗi có tên
    riêng, thông báo rõ ràng bằng tiếng Việt — không để lộ
    `psycopg.errors.ForeignKeyViolation` thô ra ngoài mà không giải thích.
    """


# --------------------------------------------------------------------------- #
# Kiểu kết nối Postgres — duck-typed, không ép driver cụ thể
# --------------------------------------------------------------------------- #


class PgConnectionLike(Protocol):
    """Mọi đối tượng có `.execute(sql, params)` trả về cursor có `.fetchone()`.

    Đúng hình dạng `psycopg.Connection.execute(...)` mà
    `tests/t0_1_stores/conftest.py` đã dùng — module này không import
    `psycopg` để không ép một driver cụ thể vào tầng dùng chung.
    """

    def execute(self, query: str, params: Any = None) -> Any: ...


# --------------------------------------------------------------------------- #
# Hai bảng — tên và DDL export dưới dạng hằng số, dùng chung cho cả code THẬT
# lẫn test (test không được hard-code lại SQL của mình)
# --------------------------------------------------------------------------- #

#: Catalog — MỌI bản model từng được biết tới. Bản ghi LỊCH SỬ, không ghi đè.
EMBEDDING_MODELS_TABLE = "embedding_models"

#: Model nào đang ACTIVE cho MỘT collection Qdrant cụ thể — khoá theo tên
#: collection. Đổi active model cho một collection là một UPSERT thủ công,
#: KHÔNG phải migration tự động (xem "NỢ KỸ THUẬT CỐ Ý" ở đầu file).
EMBEDDING_MODEL_COLLECTIONS_TABLE = "embedding_model_collections"

EMBEDDING_MODELS_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {EMBEDDING_MODELS_TABLE} (
    model_name    text    NOT NULL,
    model_version text    NOT NULL,
    embedding_dim integer NOT NULL,
    PRIMARY KEY (model_name, model_version)
)
"""

EMBEDDING_MODEL_COLLECTIONS_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {EMBEDDING_MODEL_COLLECTIONS_TABLE} (
    collection_name text NOT NULL PRIMARY KEY,
    model_name      text NOT NULL,
    model_version   text NOT NULL,
    FOREIGN KEY (model_name, model_version)
        REFERENCES {EMBEDDING_MODELS_TABLE} (model_name, model_version)
)
"""


# --------------------------------------------------------------------------- #
# Ánh xạ thước đo Qdrant → DistanceMetric nội bộ
# --------------------------------------------------------------------------- #

# Giá trị THẬT của `qdrant_client.models.Distance` viết hoa chữ đầu
# ("Cosine"/"Dot"/"Euclid"/"Manhattan") — khác `DistanceMetric` nội bộ viết
# thường. `MANHATTAN` cố ý KHÔNG có mặt: `DistanceMetric` không có giá trị
# tương ứng (07 Mục 3.1 chỉ cân nhắc cosine/dot/euclid).
_QDRANT_DISTANCE_TO_METRIC: dict[str, DistanceMetric] = {
    QdrantDistance.COSINE.value: DistanceMetric.COSINE,
    QdrantDistance.DOT.value: DistanceMetric.DOT,
    QdrantDistance.EUCLID.value: DistanceMetric.EUCLID,
}


def _map_qdrant_distance(distance: QdrantDistance, *, collection_name: str) -> DistanceMetric:
    raw = distance.value if hasattr(distance, "value") else str(distance)
    try:
        return _QDRANT_DISTANCE_TO_METRIC[raw]
    except KeyError:
        raise UnsupportedQdrantDistanceError(
            f"Collection '{collection_name}' trên Qdrant dùng thước đo {raw!r} mà "
            "`DistanceMetric` nội bộ (schema.config) không có ánh xạ tương ứng. "
            f"Giá trị map được: {', '.join(sorted(_QDRANT_DISTANCE_TO_METRIC))}. "
            "07 Mục 3.1 CHỐT v1 chỉ nhận `cosine` — collection dùng thước đo "
            "khác coi như đã sai ngay từ lúc tạo, không phải một ca lệch cấu "
            "hình bình thường."
        ) from None


# --------------------------------------------------------------------------- #
# FK violation của Postgres — nhận diện bằng duck-typing, không import psycopg
# --------------------------------------------------------------------------- #

# SQLSTATE chuẩn của Postgres cho "foreign_key_violation" — cùng một mã này
# dùng được ở mọi driver Postgres (psycopg 2 lẫn 3), không riêng gì psycopg.
_FOREIGN_KEY_VIOLATION_SQLSTATE = "23503"


def _looks_like_foreign_key_violation(exc: BaseException) -> bool:
    """Nhận diện lỗi vi phạm khoá ngoại mà KHÔNG import lớp lỗi cụ thể.

    psycopg 3 gắn `.sqlstate` lên chính exception; psycopg 2 gắn `.pgcode`.
    Kiểm cả hai, cộng tên lớp, để không phụ thuộc vào đúng MỘT driver.
    """
    sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
    if sqlstate == _FOREIGN_KEY_VIOLATION_SQLSTATE:
        return True
    return "ForeignKeyViolation" in type(exc).__name__


# --------------------------------------------------------------------------- #
# Đọc con dấu THẬT
# --------------------------------------------------------------------------- #


def read_store_stamp(
    *,
    qdrant_client: QdrantClient,
    pg_connection: PgConnectionLike,
    collection_name: str,
) -> StoreStamp:
    """Đọc CON DẤU THẬT của một collection Qdrant cụ thể.

    `embedding_dim` và `distance_metric` lấy THẲNG từ cấu hình collection của
    Qdrant (T0.1 (b) đã chứng minh đáng tin). `embedding_model` lấy từ
    PostgreSQL bằng cách JOIN `embedding_model_collections` với
    `embedding_models` theo `collection_name` — đúng phần mà Qdrant KHÔNG
    mang.

    Thứ tự kiểm, và vì sao theo thứ tự đó:
    1. Collection không tồn tại trên Qdrant → `CollectionNotFoundOnQdrantError`
       ngay lập tức — không có gì để đối chiếu tiếp.
    2. Thước đo Qdrant không map được → `UnsupportedQdrantDistanceError`.
    3. Collection chưa từng active trong Postgres →
       `CollectionNotStampedError` — KHÔNG suy đoán.
    4. `embedding_dim` catalog lệch dim thật của Qdrant →
       `CatalogDimensionConflictError` — catalog tự mâu thuẫn với kho nó
       mô tả.

    Trả về `StoreStamp` chỉ khi cả bốn bước trên đều sạch.
    """
    try:
        info = qdrant_client.get_collection(collection_name=collection_name)
    except Exception as exc:
        raise CollectionNotFoundOnQdrantError(
            f"Không đọc được collection '{collection_name}' từ Qdrant: {exc}. "
            "Con dấu chỉ đọc được từ một collection ĐÃ TỒN TẠI — TỪ CHỐI CHẠY, "
            "không suy đoán số chiều hay thước đo."
        ) from exc

    vectors_config = info.config.params.vectors
    real_dim = vectors_config.size
    real_metric = _map_qdrant_distance(vectors_config.distance, collection_name=collection_name)

    row = pg_connection.execute(
        f"""
        SELECT m.model_name, m.embedding_dim
        FROM {EMBEDDING_MODEL_COLLECTIONS_TABLE} AS c
        JOIN {EMBEDDING_MODELS_TABLE} AS m
          ON m.model_name = c.model_name AND m.model_version = c.model_version
        WHERE c.collection_name = %s
        """,
        (collection_name,),
    ).fetchone()

    if row is None:
        raise CollectionNotStampedError(
            f"Collection '{collection_name}' CHƯA TỪNG được đóng dấu active trong "
            f"Postgres (bảng {EMBEDDING_MODEL_COLLECTIONS_TABLE}) — chưa ai gán "
            "model nào cho collection này. TỪ CHỐI CHẠY, không suy đoán "
            "`embedding_model` là gì (07 Mục 3.1). Gọi `register_embedding_model` "
            "rồi `set_active_embedding_model_for_collection` trước."
        )

    model_name, catalog_dim = row

    if catalog_dim != real_dim:
        raise CatalogDimensionConflictError(
            f"Catalog Postgres (bảng {EMBEDDING_MODELS_TABLE}) ghi "
            f"embedding_dim={catalog_dim!r} cho model {model_name!r}, nhưng "
            f"collection '{collection_name}' trên Qdrant thực tế có "
            f"dim={real_dim!r}. Catalog TỰ MÂU THUẪN với chính kho nó mô tả — "
            "TỪ CHỐI CHẠY thay vì lặng lẽ dùng dim thật của Qdrant."
        )

    return StoreStamp(
        embedding_model=model_name,
        embedding_dim=real_dim,
        distance_metric=real_metric,
    )


def assert_collection_ready_for_contract(
    *,
    config: ContractConfig,
    qdrant_client: QdrantClient,
    pg_connection: PgConnectionLike,
    collection_name: str,
) -> None:
    """ĐIỂM VÀO DUY NHẤT lúc khởi động — cả Ingestion và Retrieval (Nhóm 2/3,
    chưa xây) PHẢI gọi hàm này trước khi phục vụ bất kỳ truy vấn nào, đúng chỗ
    service dựng kết nối tới collection Qdrant của mình.

    Đặt ở `packages/schema/` (Nhóm 1), không phải Nhóm 2/3: docs/07 Mục 3.1
    nói rõ cấu hình mô hình biểu diễn "gộp vào chính module schema dùng
    chung", và docs/08 xếp T1.3 vào Nhóm 1.

    Chỉ gọi `read_store_stamp` rồi gọi `assert_contract_matches_store_stamp`
    (import nguyên từ `schema.config`, KHÔNG viết lại logic so khớp ở đây) —
    hàm này không có logic quyết định riêng, nó là dây nối giữa "đọc thật" và
    "so khớp thật" đã có sẵn.
    """
    stamp = read_store_stamp(
        qdrant_client=qdrant_client,
        pg_connection=pg_connection,
        collection_name=collection_name,
    )
    assert_contract_matches_store_stamp(config, stamp, store_name=collection_name)


# --------------------------------------------------------------------------- #
# Hai hàm ghi tối thiểu — cho T1.3 tự seed test, và cho T1.5 (nạp lại toàn
# kho, CHƯA XÂY) dùng sau này
# --------------------------------------------------------------------------- #


def register_embedding_model(
    *,
    pg_connection: PgConnectionLike,
    model_name: str,
    model_version: str,
    embedding_dim: int,
) -> None:
    """Đăng ký một dòng catalog `(model_name, model_version, embedding_dim)`.

    Idempotent nếu ghi lại ĐÚNG Y HỆT giá trị cũ. Nếu `(model_name,
    model_version)` đã tồn tại với `embedding_dim` KHÁC → raise
    `CatalogEntryConflictError`: catalog là bản ghi LỊCH SỬ, không lặng lẽ
    ghi đè lên chính nó.
    """
    existing = pg_connection.execute(
        f"SELECT embedding_dim FROM {EMBEDDING_MODELS_TABLE} "
        "WHERE model_name = %s AND model_version = %s",
        (model_name, model_version),
    ).fetchone()

    if existing is not None:
        (existing_dim,) = existing
        if existing_dim != embedding_dim:
            raise CatalogEntryConflictError(
                f"('{model_name}', '{model_version}') đã có trong catalog "
                f"({EMBEDDING_MODELS_TABLE}) với embedding_dim={existing_dim!r}, "
                f"không thể đăng ký lại với embedding_dim={embedding_dim!r} khác "
                "đi. Nếu model thật sự đổi số chiều thì đó phải là một "
                "`model_version` khác, không phải ghi đè bản cũ."
            )
        return  # y hệt giá trị cũ — idempotent, không làm gì thêm

    pg_connection.execute(
        f"INSERT INTO {EMBEDDING_MODELS_TABLE} "
        "(model_name, model_version, embedding_dim) VALUES (%s, %s, %s)",
        (model_name, model_version, embedding_dim),
    )


def set_active_embedding_model_for_collection(
    *,
    pg_connection: PgConnectionLike,
    collection_name: str,
    model_name: str,
    model_version: str,
) -> None:
    """Gán một catalog entry ĐÃ CÓ SẴN làm active cho một collection (upsert).

    ⛔ Đây là MỘT câu UPSERT đơn giản, KHÔNG phải migration tự động — gọi lại
    hàm này với model khác cho cùng `collection_name` là hành vi HỢP LỆ (bước
    "đóng dấu lại" thủ công sau khi nạp lại toàn kho — xem "NỢ KỸ THUẬT CỐ Ý"
    ở đầu file). Hàm này KHÔNG đụng gì tới Qdrant: chỉ ghi Postgres.

    `(model_name, model_version)` phải đã tồn tại trong catalog trước (khoá
    ngoại) — nếu chưa, Postgres raise lỗi vi phạm FK và hàm này bọc lại thành
    `UnknownCatalogEntryError` với thông báo tiếng Việt rõ ràng.
    """
    try:
        pg_connection.execute(
            f"""
            INSERT INTO {EMBEDDING_MODEL_COLLECTIONS_TABLE}
                (collection_name, model_name, model_version)
            VALUES (%s, %s, %s)
            ON CONFLICT (collection_name) DO UPDATE SET
                model_name = EXCLUDED.model_name,
                model_version = EXCLUDED.model_version
            """,
            (collection_name, model_name, model_version),
        )
    except Exception as exc:
        if _looks_like_foreign_key_violation(exc):
            raise UnknownCatalogEntryError(
                f"Không thể gán model ('{model_name}', '{model_version}') làm "
                f"active cho collection '{collection_name}': cặp (model_name, "
                f"model_version) này CHƯA TỪNG được đăng ký trong catalog "
                f"({EMBEDDING_MODELS_TABLE}). Gọi `register_embedding_model(...)` "
                "trước."
            ) from exc
        raise
