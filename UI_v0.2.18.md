# v0.2.18 — sửa tương tác và bố cục compact

Nguyên nhân: details của thiết lập Studio được tái tạo ở mỗi lần render với open dựa trên việc đã liên kết, nên người dùng mở lại thì lần polling tiếp theo đóng lại. Bản sửa giữ open theo lựa chọn người dùng trước khi dựng lại DOM; tách cập nhật header khỏi render nội dung trung gian; giữ scroll của danh sách/nhật ký, cũng giữ trạng thái công cụ kỹ thuật. Đổi profile và nhập ID/URL có onchange blur/render để cập nhật điều kiện nút.

Nút chạy dựa vào trạng thái Queue và workflow đã lưu; không bỏ guard Agent/profile. Dự án lỗi có nút chạy lại lỗi; backend vẫn từ chối thao tác chưa rõ kết quả. Tiếp tục chỉ dùng với paused, tạm dừng chỉ dùng khi đang chạy. Lỗi cũ trong checkpoint không tự bị xóa hoặc coi đã sửa.

Bố cục compact: nút khoảng 23–27px, giảm padding, khung vừa viewport desktop. Dự án có bảng và chi tiết; Điều phối có danh sách trái, thiết lập thu gọn theo ý người dùng, thẻ công đoạn, tiến trình và nhật ký; Điều khiển ứng dụng có sidebar, ba cột Chrome/Edge/CapCut, ảnh screenshot thật nếu Agent đã trả kết quả, nhật ký dưới; Cài đặt có năm nhóm. Không thêm nút dựng video/xuất file giả từ ảnh mẫu.

Kiểm thử: Python 107 tests, 105 PASS và 2 SKIP Windows-only. Node regression app controls/Studio UI PASS. Browser local/server thật: chọn/lọc 3 dự án test, dialog, 8 trang, toast/STOP, mobile không tràn ngang. Fixture UI riêng cho kết nối/linked-project: chọn dự án không đóng thiết lập sau 6.2 giây; đóng/mở giữ qua polling; Lưu/Chạy gửi mỗi nút một lệnh (request bị mock, không chạy Windows); cửa sổ desktop 1920x1080 và 1366x768 không scroll document; nút test ứng dụng nằm trong thẻ; công cụ kỹ thuật giữ trạng thái qua polling. Không có lỗi JavaScript.

Chưa test bản mới trên Windows/Edge/Studio/ChatGPT thật. Ảnh QA có dữ liệu kiểm thử, không phải bằng chứng công việc Studio thật. Không đóng gói database hoặc dữ liệu test. Không đổi Extension, Studio, Queue core hoặc worker trong thay đổi từ v0.2.17.
