# AI MANAGER v0.2.7

Ba thẻ Chrome / CapCut / Edge có cùng ba hàng. Edge gộp chọn cửa sổ, URL và nút kiểm tra vào hàng 3, bỏ khối số 4 riêng. Sửa tên profile bị thêm nhầm chrome / Default.

Edge thử nhận dạng nút profile gốc của trình duyệt qua Accessibility với tên chính xác, chỉ khi tên duy nhất trong danh sách profile. Không dùng title hoặc nội dung trang để suy đoán profile. Nếu chưa đọc được, dùng trang edge://version với đường dẫn profile chính xác. Lỗi UIA ở một cửa sổ không ngăn dò cửa sổ khác. Hiện lỗi mở/xác minh ngay trong thẻ Edge thay vì chỉ khóa nút.

Cách thử: đóng Manager/server cũ, chạy MO_AI_MANAGER.bat bản này; chọn profile → Mở Edge. Giữ trang thông tin Edge trong lúc đang xác minh. Khi có cửa sổ, chọn rồi Chạy kiểm tra Edge. Nếu chưa có, lỗi sẽ hiện ngay trong thẻ; gửi ảnh lỗi để đối chiếu Windows thực tế.

Test Python/Node trên Linux không chứng minh hoạt động Edge trên Windows. Không bỏ kiểm tra profile để ép mở khóa nút. Không sửa workflow Chrome/CapCut.
