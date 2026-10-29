# AI MANAGER v0.2.17 — giao diện neon

Nền navy, viền cyan, menu ngang, nút Dừng tất cả dùng chung. Dự án gồm bộ lọc, bảng, thông tin dự án và lịch sử; Điều phối Studio gồm danh sách dự án trái, thiết lập có thể thu gọn, tiến trình và nhật ký; Cài đặt gồm các nhóm đường dẫn, thư mục, Agent, kết nối và profile. Điều khiển Chrome/Edge/CapCut giữ các nút hiện có.

Không dùng ảnh minh họa hoặc số liệu cố định làm kết quả thật. Những chức năng chưa có như dựng video, xuất video, quản lý cookie không được thêm nút giả. Dữ liệu danh sách và tiến độ lấy từ API hiện tại. Hồ sơ có phân loại TEST tiếp tục được nhận diện.

Thay đổi giao diện: ui_shell.js, theme.css, index.html, studio_automation.js. Server phục vụ hai tài nguyên mới và trả các đường dẫn Chrome/CapCut đã lưu để biểu mẫu không vô tình xóa cấu hình. Version Agent tăng đồng bộ để bootstrap phát hiện bản cũ. Không sửa Extension, Studio, prompt, worker hoặc cơ chế Queue/checkpoint trong thay đổi UI từ v0.2.16.

Kiểm chứng: Python 107 tests (105 PASS, 2 SKIP Windows-only); Node regression app controls và Studio UI PASS. Playwright chạy trình duyệt headless với server local thật và thư mục test tạm: tạo 3 dự án, chọn/lọc, hộp thoại thêm dự án/đổi thư mục, 8 menu, STOP và toast 4 giây, kiểm tra không tràn ngang ở 1536x1024 và 390x844, không có lỗi JavaScript.

Các ảnh QA được chụp từ 3 hồ sơ kiểm thử tạo qua API local. Không đóng gói database hoặc hồ sơ test vào bản Windows. Không coi kiểm thử giao diện Linux là bằng chứng automation Windows/Edge/CapCut/ChatGPT đã PASS. Chưa nghiệm thu bản giao diện mới trên máy Windows của người dùng.
