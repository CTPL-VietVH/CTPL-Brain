"""(c) Đọc một đoạn văn bản theo VỊ TRÍ KÝ TỰ, không lấy cả trường về rồi cắt.

Đây là ca thử nặng ký nhất của T0.1, vì nó bảo vệ **điều cấm số 4**: đếm vị trí
theo byte thì đoạn cắt sai mà *không lỗi nào báo* — chỉ là dẫn nguồn sai chỗ.

Đường hỏng thật trong hệ này có hai đầu:
  * Ingestion tính `span_start`/`span_end` bằng Python (chỉ số KÝ TỰ Unicode).
  * Retrieval cắt lại bằng PostgreSQL `SUBSTRING ... FROM ... FOR ...`.
Hai đầu đó phải cho **cùng một chuỗi**. Ca `test_python_and_postgres_agree`
dưới đây chính là chỗ bắt nếu chúng lệch nhau.

07 Mục 2.1 chốt `extracted_text` là **nguồn chân lý duy nhất của chữ nghĩa** và
mẩu chỉ giữ vị trí — nên năng lực "đọc theo đoạn" không phải tối ưu hoá, nó là
điều kiện để thiết kế đó đứng được.
"""

from __future__ import annotations

import time

PROBE_TABLE = "t0_1_probe.long_text"

# Một đoạn văn bản hành chính VN có dấu — mỗi ký tự có dấu chiếm nhiều byte.
VIETNAMESE_PARAGRAPH = (
    "Điều 7. Trách nhiệm của Thủ trưởng đơn vị\n"
    "1. Thủ trưởng đơn vị chịu trách nhiệm tổ chức triển khai Quy chế này "
    "trong phạm vi đơn vị mình quản lý.\n"
    "2. Định kỳ hằng quý, báo cáo kết quả thực hiện về Văn phòng Tổng công ty "
    "để tổng hợp, theo dõi.\n"
    "3. Trường hợp phát hiện vi phạm, phải đình chỉ ngay và báo cáo bằng văn bản "
    "chậm nhất sau 24 giờ kể từ thời điểm phát hiện.\n"
)


def _build_long_document(target_chars: int = 200_000) -> str:
    """Dựng một tài liệu dài thật — T0.1 đòi (c) phải thử với tài liệu dài."""
    chunks, total = [], 0
    i = 0
    while total < target_chars:
        block = f"\nChương {i // 20 + 1} — Mục {i % 20 + 1}\n{VIETNAMESE_PARAGRAPH}"
        chunks.append(block)
        total += len(block)
        i += 1
    return "".join(chunks)


def test_database_encoding_is_utf8(pg):
    enc = pg.execute(
        "SELECT pg_encoding_to_char(encoding) FROM pg_database "
        "WHERE datname = current_database()").fetchone()[0]
    assert enc == "UTF8", f"Kho phải là UTF8, đang là {enc}"
    print(f"\n[(c)] mã hoá kho: {enc}")


def test_python_and_postgres_agree_on_character_positions(pg):
    """⭐ Ingestion tính vị trí bằng Python, Retrieval cắt bằng Postgres — phải khớp."""
    doc = _build_long_document()
    pg.execute(f"CREATE TABLE IF NOT EXISTS {PROBE_TABLE} "
               f"(probe_id text PRIMARY KEY, body text NOT NULL)")
    pg.execute(f"INSERT INTO {PROBE_TABLE} VALUES (%s,%s) "
               f"ON CONFLICT (probe_id) DO UPDATE SET body=EXCLUDED.body",
               ("agree", doc))

    # Kho phải đếm đúng số KÝ TỰ, không phải số byte
    n_chars_db = pg.execute(
        f"SELECT char_length(body) FROM {PROBE_TABLE} WHERE probe_id='agree'"
    ).fetchone()[0]
    n_bytes_db = pg.execute(
        f"SELECT octet_length(body) FROM {PROBE_TABLE} WHERE probe_id='agree'"
    ).fetchone()[0]

    assert n_chars_db == len(doc), "Postgres và Python phải đếm cùng một số ký tự"
    assert n_bytes_db > n_chars_db, \
        "Phép thử tự hỏng: văn bản phải có dấu để byte nhiều hơn ký tự"
    print(f"[(c)] {n_chars_db:,} ký tự nhưng {n_bytes_db:,} byte "
          f"→ lệch {n_bytes_db - n_chars_db:,}; đếm nhầm là sai ngay")

    # Kiểm ở nhiều chỗ, gồm cả chỗ cắt rơi đúng vào một ký tự có dấu
    for span_start in (0, 1, 41, 1000, 12_345, len(doc) - 500):
        span_end = span_start + 300
        expected = doc[span_start:span_end]           # Ingestion: chỉ số Python
        got = pg.execute(                              # Retrieval: cắt trong kho
            f"SELECT SUBSTRING(body FROM %s FOR %s) FROM {PROBE_TABLE} "
            f"WHERE probe_id='agree'",
            (span_start + 1, span_end - span_start),   # SQL đếm từ 1
        ).fetchone()[0]
        assert got == expected, (
            f"LỆCH tại span_start={span_start}\n"
            f"  Python  : {expected[:60]!r}\n"
            f"  Postgres: {got[:60]!r}"
        )
    print("[(c)] Python slice == Postgres SUBSTRING ở cả 6 mốc, kể cả mốc rơi vào ký tự có dấu")


def test_byte_counting_would_silently_corrupt(pg):
    """Chứng minh cái bẫy là THẬT: cùng con số, đếm theo byte ra đoạn khác hẳn."""
    doc = _build_long_document(target_chars=5_000)
    pg.execute(f"INSERT INTO {PROBE_TABLE} VALUES (%s,%s) "
               f"ON CONFLICT (probe_id) DO UPDATE SET body=EXCLUDED.body",
               ("trap", doc))

    span_start, length = 41, 120
    by_char = pg.execute(
        f"SELECT SUBSTRING(body FROM %s FOR %s) FROM {PROBE_TABLE} WHERE probe_id='trap'",
        (span_start + 1, length)).fetchone()[0]
    by_byte = pg.execute(
        f"SELECT convert_from(SUBSTRING(body::bytea FROM %s FOR %s),'UTF8') "
        f"FROM {PROBE_TABLE} WHERE probe_id='trap'",
        (span_start + 1, length)).fetchone()[0]

    assert by_char == doc[span_start:span_start + length]
    assert by_char != by_byte, "Nếu hai cách cho cùng kết quả thì phép thử vô nghĩa"
    print(f"[(c)] cùng (từ={span_start + 1}, dài={length}):")
    print(f"        theo ký tự: {by_char[:52]!r}")
    print(f"        theo byte  : {by_byte[:52]!r}   ← lệch, KHÔNG có lỗi nào báo")


def test_slice_is_cut_in_the_store_not_fetched_whole(pg):
    """Chỉ đoạn cần đọc đi qua dây, không phải cả trường."""
    doc = _build_long_document()
    pg.execute(f"INSERT INTO {PROBE_TABLE} VALUES (%s,%s) "
               f"ON CONFLICT (probe_id) DO UPDATE SET body=EXCLUDED.body",
               ("slice", doc))

    span_start, length = 100_000, 400
    rounds = 40

    def _median_ms(fn) -> float:
        fn()  # làm ấm cache trước, để phép đo không đo nhầm lần nạp đĩa đầu tiên
        samples = []
        for _ in range(rounds):
            t0 = time.perf_counter()
            fn()
            samples.append((time.perf_counter() - t0) * 1000)
        samples.sort()
        return samples[len(samples) // 2]

    def _slice():
        return pg.execute(
            f"SELECT SUBSTRING(body FROM %s FOR %s) FROM {PROBE_TABLE} "
            f"WHERE probe_id='slice'", (span_start + 1, length)).fetchone()[0]

    def _whole():
        return pg.execute(
            f"SELECT body FROM {PROBE_TABLE} WHERE probe_id='slice'").fetchone()[0]

    sliced, whole = _slice(), _whole()
    t_slice, t_whole = _median_ms(_slice), _median_ms(_whole)

    # Bằng chứng CHỊU LỰC là khối lượng: chỉ đoạn cần đọc đi qua dây.
    assert len(sliced) == length
    assert sliced == whole[span_start:span_start + length]
    assert len(sliced) < len(whole) / 100, "Đoạn cắt phải nhỏ hơn cả trường rất nhiều"

    print(f"[(c)] cắt trong kho : {len(sliced):>7,} ký tự về, {t_slice:6.2f} ms (trung vị/{rounds})")
    print(f"[(c)] lấy cả trường : {len(whole):>7,} ký tự về, {t_whole:6.2f} ms (trung vị/{rounds})")
    print(f"[(c)] → đúng {len(sliced) / len(whole) * 100:.2f}% khối lượng đi qua dây")
    if t_slice > t_whole:
        print(f"[(c)] ⚠️  GHI NHẬN: cắt trong kho CHẬM HƠN {t_slice / t_whole:.1f}x về độ trễ. "
              f"SUBSTRING theo vị trí KÝ TỰ trên văn bản đa byte không nhảy thẳng tới "
              f"vị trí được — Postgres phải giải mã UTF-8 từ đầu, chi phí tỉ lệ với ĐỘ "
              f"LỆCH. Đã thử cả STORAGE EXTENDED và EXTERNAL: không đổi. Yêu cầu (c) vẫn "
              f"ĐẠT (đúng ký tự + không lấy cả trường), nhưng lý lẽ 'lãng phí ở mọi lượt "
              f"trả lời' ở 07 Mục 7 yêu cầu 2 chỉ đúng cho BĂNG THÔNG và BỘ NHỚ, không "
              f"đúng cho ĐỘ TRỄ khi kho nằm cùng máy. Việc của PO, không tự đổi thiết kế.")
