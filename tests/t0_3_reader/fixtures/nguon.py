"""Nội dung nguồn dùng chung cho tập thử TỰ DỰNG của T0.3.

⚠️ **ĐÂY LÀ VĂN BẢN TỰ DỰNG, KHÔNG PHẢI VĂN BẢN THẬT.**

`docs/08` T0.3 đòi nghiệm thu trên *"ít nhất 20 văn bản hành chính Việt Nam
thật, trong đó ít nhất 5 văn bản soạn tay không dùng Heading style và ít nhất 5
PDF"*. Tập tự dựng ở đây **không thay thế** yêu cầu đó và **không được dùng để
tuyên bố T0.3 xong**.

Nó phục vụ đúng một việc: chứng minh **bốn bộ đọc trả ra CÙNG MỘT hình dạng
cây** từ cùng một nội dung — tức điểm cắm GĐ2 đứng được. Việc phân cấp có dựng
đúng trên văn bản thật hay không thì chỉ văn bản thật mới trả lời được.
"""

# Một Quy chế rút gọn, viết theo đúng quy chuẩn trình bày hành chính VN:
# chữ HOA cho Chương, "Điều N." cho Điều, "1." cho Khoản, "a)" cho Điểm.
QUY_CHE = """QUYẾT ĐỊNH
Về việc ban hành Quy chế quản lý tài sản công

CHƯƠNG I
QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh
1. Quy chế này quy định việc quản lý, sử dụng tài sản công tại các đơn vị trực thuộc Tổng công ty.
2. Đối tượng áp dụng bao gồm:
a) Các đơn vị hạch toán phụ thuộc;
b) Các chi nhánh và văn phòng đại diện;
c) Người lao động được giao quản lý tài sản.

Điều 2. Nguyên tắc quản lý
1. Tài sản công phải được sử dụng đúng mục đích, tiết kiệm và hiệu quả.
2. Mọi trường hợp điều chuyển tài sản giữa các đơn vị phải được Tổng giám đốc phê duyệt bằng văn bản.

CHƯƠNG II
TRÁCH NHIỆM CỦA CÁC ĐƠN VỊ

Điều 3. Trách nhiệm của Thủ trưởng đơn vị
1. Thủ trưởng đơn vị chịu trách nhiệm tổ chức triển khai Quy chế này trong phạm vi đơn vị mình quản lý.
2. Định kỳ hằng quý, báo cáo kết quả thực hiện về Văn phòng Tổng công ty để tổng hợp, theo dõi.
3. Trường hợp phát hiện vi phạm, phải đình chỉ ngay và báo cáo bằng văn bản chậm nhất sau 24 giờ.

Điều 4. Hiệu lực thi hành
1. Quy chế này có hiệu lực kể từ ngày ký ban hành.
2. Các quy định trước đây trái với Quy chế này đều bãi bỏ.
"""

# Tài liệu KHÔNG theo điều khoản — 07 Mục 2.2 nói rõ khi đó đơn vị là chuỗi
# tiêu đề lồng nhau (quy trình, biên bản, báo cáo).
QUY_TRINH = """QUY TRÌNH TIẾP NHẬN VÀ XỬ LÝ HỒ SƠ

1. Mục đích
Quy trình này mô tả các bước tiếp nhận hồ sơ từ khách hàng.

1.1 Phạm vi áp dụng
Áp dụng cho toàn bộ bộ phận một cửa.

1.2 Tài liệu viện dẫn
Căn cứ Quyết định số 115/QĐ-TCT ngày 12 tháng 3 năm 2025.

2. Nội dung quy trình
Các bước thực hiện được mô tả dưới đây.

2.1 Tiếp nhận hồ sơ
Cán bộ một cửa kiểm tra tính đầy đủ của hồ sơ.

2.2 Thẩm định hồ sơ
Chuyên viên thẩm định trong thời hạn ba ngày làm việc.

2.3 Trả kết quả
Kết quả được trả tại quầy hoặc qua đường bưu chính.
"""

# Văn bản KHÔNG có dấu hiệu phân cấp nào — dùng để chứng minh bộ đọc NÓI RA
# rằng nó không dựng được, thay vì lặng lẽ cắt theo độ dài.
KHONG_CAU_TRUC = """Kính gửi các anh chị trong nhóm dự án.

Sau buổi trao đổi sáng nay tôi tổng hợp lại mấy ý chính để mọi người cùng nắm. Trước hết là việc bàn giao hạ tầng, bên đối tác báo sẽ hoàn tất trong tuần này nhưng chưa có mốc cụ thể. Tiếp theo là phần tài liệu hướng dẫn, hiện còn thiếu phần cấu hình cho môi trường thử nghiệm.

Mong mọi người cho ý kiến thêm trước thứ sáu. Cảm ơn cả nhà.
"""
