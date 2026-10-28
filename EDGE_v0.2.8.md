# AI MANAGER v0.2.8 — Chẩn đoán Edge

Thông báo thao tác là ô nổi góc phải, tự ẩn sau 4 giây, không chiếm hàng trong layout. Lỗi tác vụ vẫn lưu trong nhật ký/checkpoint.

Chưa xác nhận giải quyết được lỗi profile trên máy Windows của người dùng. Các bản trước chỉ xác nhận Edge đã mở, không xác nhận được danh tính profile. Không bỏ guard để mở khóa nút.

Cách lấy dữ liệu thực tế:
1. Chạy MO_AI_MANAGER.bat, chọn profile Edge.
2. Trong đúng cửa sổ Edge đó, mở edge://version và giữ nguyên trang.
3. Trên thẻ Microsoft Edge, bấm Chẩn đoán Edge.
4. Kéo xuống Cài đặt nâng cao → Chẩn đoán Edge → Sao chép chẩn đoán. Dán kết quả vào cuộc trò chuyện hỗ trợ.

Chẩn đoán chỉ đọc: HWND/PID, số control, class/automation ID của thanh địa chỉ, cờ nhận diện trang version/path và loại lỗi UIA. Không gửi hoặc xuất nội dung hội thoại, cookie, token, mật khẩu hay URL hội thoại. Không click/nhập text/nạp lại trang. Nếu UIA treo quá 20 giây worker chẩn đoán bị dừng, Agent chính vẫn hoạt động.
