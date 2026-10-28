# AI MANAGER v0.2.10

Thay cơ chế xác minh profile trên luồng Mở Edge. Không chờ DOM/trang edge://version hoặc selector UIA để quyết định cửa sổ thuộc profile nào. Đọc Windows Shell property store theo HWND: RelaunchCommand và RelaunchIconResource; đối chiếu thư mục profile chính xác, process Edge và user-data-root. Không đoán Default nếu Windows không trả profile rõ ràng. Không đọc cookie/token/mật khẩu. Nếu không có bằng chứng, trả lỗi và dừng.

Giữ UIA cho focus, nhập URL, chờ trang và chụp ảnh sau khi profile đã được xác minh. Giữ nguyên Chrome/CapCut, STOP, queue và checkpoint.

Mở/xác minh tối đa 25 giây mỗi action, không chờ UIA vô hạn; chỉ mở thêm một cửa sổ/profile mỗi 60 giây khi chưa có cửa sổ đã xác minh. Chống gửi nhiều task Mở Edge trùng nhau. Khi có nhiều cửa sổ đúng profile, hiển thị để người dùng chọn thay vì từ chối tất cả.

Trạng thái phân biệt Chưa mở / Chưa xác minh / Sẵn sàng. Thông báo góc dưới bên phải tự ẩn sau 4 giây.

Kiểm tra Windows: đóng Manager/server cũ; chạy MO_AI_MANAGER.bat; chọn profile → Mở Edge → chọn cửa sổ → Chạy kiểm tra Edge → Xem ảnh. Không cần mở edge://version thủ công. Nếu Windows không cung cấp thông tin profile, lỗi kết thúc rõ và có file edge_last_verification.json trong thư mục dữ liệu automation; không được bỏ guard để báo PASS.

Kiểm thử tự động không chứng minh Edge trên Windows thực tế. Cần người dùng xác nhận đúng tài khoản, screenshot và STOP.

Tài liệu nền tảng:
- https://learn.microsoft.com/windows/win32/properties/props-system-appusermodel-relaunchcommand
- https://learn.microsoft.com/windows/win32/properties/props-system-appusermodel-relaunchiconresource
- https://mhammond.github.io/pywin32/propsys__SHGetPropertyStoreForWindow_meth.html
- https://github.com/chromium/chromium/blob/main/docs/windows_shortcut_and_taskbar_handling.md
