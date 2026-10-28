# AI MANAGER v0.2.6 — Microsoft Edge

Bản Windows để kiểm tra Edge, chưa tuyên bố PASS trên Windows.

1. Đóng Manager/server cũ, giải nén một thư mục AI_MANAGER_v0.2.6, chạy MO_AI_MANAGER.bat.
2. Điều khiển ứng dụng → Microsoft Edge → Làm mới profile → chọn profile đã đăng nhập → Mở Edge.
3. Agent mở trang edge://version để đọc đúng đường dẫn profile. Chỉ cửa sổ xác minh được mới hiện để chọn. Nếu UIA không cung cấp đường dẫn, báo lỗi và không thao tác trang.
4. Chọn cửa sổ → Chạy kiểm tra Edge (https://chatgpt.com) → Xem ảnh. Xác nhận tài khoản đúng profile và phiên đăng nhập còn nguyên. Không gửi prompt.
5. Trong lúc chạy, DỪNG TẤT CẢ. Mở lại Manager: tác vụ đã dừng không tự chạy.
6. Cài đặt nâng cao → chọn dự án + Edge; profile lấy từ thẻ Edge phía trên → Lưu trình duyệt/profile cho dự án. Sau restart lựa chọn dự án vẫn được lưu. Có thể gắn workflow kiểm tra vào hàng đợi; phải khớp cấu hình đã lưu.

Chỉ đọc tên/thư mục từ Local State và kiểm tra Preferences tồn tại. Không đọc mật khẩu/token/cookie, không sao chép phiên đăng nhập, không tạo profile. Phát hiện profile Stable trong %LOCALAPPDATA%/Microsoft/Edge/User Data. Đường dẫn UserDataDir tùy chỉnh qua chính sách doanh nghiệp, Edge Beta/Dev/Canary chưa hỗ trợ trong bản này và không được đoán profile thay thế.

Cửa sổ Edge do Manager đã xác minh được tái sử dụng. Cửa sổ mở sẵn chưa được xác minh sẽ cần một cửa sổ trang thông tin cùng profile cho lần kết nối đầu; các lần sau không mở thêm nếu cửa sổ còn hợp lệ. Agent không đóng cửa sổ Edge khác. Dùng HWND/PID/thời điểm process và thuộc tính nonce của cửa sổ để chặn handle tái sử dụng. Sau khi cửa sổ mất hoặc profile không xác minh được, task thất bại có giới hạn; người dùng chọn/mở lại đúng cửa sổ, không tự chọn cửa sổ thay thế.

URL sẵn sàng = URL đúng và có UIA Document, chưa chứng minh đăng nhập hoặc trang đã network-idle. Chỉ người dùng xác nhận tài khoản ChatGPT bằng ảnh/giao diện Windows. Automation test không thay thế kiểm tra Windows thật.

Tham chiếu profile path: https://learn.microsoft.com/deployedge/edge-learnmore-create-user-directory-vars
