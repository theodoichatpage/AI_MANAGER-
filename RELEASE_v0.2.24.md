# AI MANAGER 0.2.24 — Chạy dự án mới khi còn mục đang chờ

Lỗi đã tái hiện: đã Dừng tất cả, xóa dự án cũ, tạo dự án mới nhưng bước khởi chạy báo phải dừng các dự án khác. Nguyên nhân là `start_selected` chặn cả các mục `waiting`, không chỉ công việc đang chạy.

- Chỉ mục đang chạy/tạm dừng khác mới chặn; thông báo nêu tên mục đó.
- Chạy đúng dự án vừa chọn, không chạy nhầm mục cũ đứng đầu hàng đợi.
- Những dự án đang chờ được giữ nguyên và không tự chạy tiếp khi dự án được chọn hoàn tất.
- Tạm dừng/tiếp tục vẫn giữ phạm vi một dự án. Chạy tất cả/chạy danh sách chủ động mới đổi phạm vi này.
- Không xóa database, thư mục dự án, bản đã phân cảnh hoặc ảnh. Giữ nguyên thay đổi Aprilynne đã có ở commit nền 1244f62.

## Cập nhật
Dừng tác vụ đang chạy, mở Cài đặt -> Kiểm tra cập nhật -> Cập nhật ngay. Manager cập nhật qua GitHub và khởi động lại. Kiểm tra phiên bản hiển thị 0.2.24.

Nếu lần triển khai đầu đã báo lỗi, liên kết Studio đã được lưu: giữ dự án đó, không tạo/xóa lần nữa. Sau cập nhật, bấm Triển khai toàn bộ trên chính dự án này.

## Kiểm thử
Các hồi quy riêng: mục chờ cũ không chặn/không giành lượt; hoàn tất không chạy mục khác; pause/resume giữ phạm vi; chạy tất cả giải phóng phạm vi; Stop all -> delete -> new project; tác vụ chạy/tạm dừng thật vẫn chặn; thiếu workflow bị từ chối; chạy lại dự án đã lỗi vẫn hoạt động trong phạm vi đã chọn. Chạy cùng bộ kiểm thử hàng đợi/điều phối và project operations. Không chạy phiên Windows/Edge thật trong môi trường Linux này.

Kết quả cuối: 262 bài Python, 260 đạt và 2 bài Windows được bỏ qua đúng điều kiện môi trường; kiểm tra cú pháp Python/JavaScript đạt. Tám bài mới kiểm tra trực tiếp hàng đợi SQLite và handler triển khai dự án (Agent/Studio bên ngoài dùng fixture).
