# AI MANAGER — Phase 1 (bản thử nghiệm cục bộ)

Yêu cầu Python 3.10 trở lên. Trên Windows chạy `MO_AI_MANAGER.bat`, hoặc `python server.py`. Truy cập http://127.0.0.1:8765 trên chính máy đó. Chọn thư mục gốc, tạo dự án bằng tên hoặc dòng đầu của kịch bản. Mỗi dự án có project.json và các thư mục analysis, scenes, prompts, images, logs. Đổi thư mục gốc sẽ hiển thị các dự án trong thư mục mới; dữ liệu cũ vẫn ở chỗ cũ.

Các nút điều phối đang khóa: chưa triển khai hàng đợi, Studio, ChatGPT, checkpoint, tạo ảnh và retry. Không sử dụng OpenAI API. Chỉ chạy trên localhost; không chuyển tiếp cổng ra Internet.

## Phase 2: hàng đợi mô phỏng
Mỗi thư mục gốc có database `.ai_manager_queue.sqlite3` chứa hàng đợi, checkpoint và nhật ký. Chỉ chạy một dự án; mở lại sau gián đoạn sẽ tạm dừng dự án đang chạy. Chọn Hàng đợi để kiểm tra trạng thái và điều khiển. Tiến độ và lỗi trong Phase 2 là mô phỏng, không phải ảnh thật. Các nút Test: hoàn tất/lỗi dùng để kiểm tra chuyển trạng thái. Để cập nhật, dừng chương trình cũ trước khi chạy phiên bản mới.

## Kiểm tra Phase 2
Mở MO_AI_MANAGER.bat và giữ cửa sổ đó mở. Bấm “Tạo / nạp 3 dự án TEST”, sau đó “Chạy tất cả”. Trong Hàng đợi có các nút thử hoàn tất và thử lỗi. Để thử khôi phục, đóng cửa sổ chạy khi tiến độ 30–50%, mở lại file .bat và bấm Tiếp tục. Các dự án TEST được lưu thật; bấm nút tạo lần nữa sẽ nạp lại, không đặt lại tiến độ.

## Đọc phiên Studio (bản kiểm tra)
Mở VIDEO IMAGE STUDIO, chọn Kết nối ChatGPT và sao chép mã kết nối. Trong AI MANAGER chọn Kết nối Studio và dán mã. Dữ liệu được đọc định kỳ, không gửi lệnh tới Studio. Mã phiên được giữ trong bộ nhớ đến khi chương trình đóng; cần nhập lại sau khi khởi động. Đọc được dữ liệu máy chủ không chứng minh tab Studio hay ChatGPT đang mở, do đó hai trạng thái này được ghi là chưa xác định. Chức năng chưa điều khiển phân tích, ảnh hoặc tải xuống.
