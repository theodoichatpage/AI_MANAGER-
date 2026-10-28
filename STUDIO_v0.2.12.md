# AI MANAGER v0.2.12 — Điều phối một dự án Studio thật

1. Đóng Manager/server cũ. Chạy MO_AI_MANAGER.bat trong AI_MANAGER_v0.2.12.
2. Mở Studio Preview trong đúng profile Edge đã đăng nhập, chọn dự án thật, kết nối Extension/ChatGPT cho dự án đó. Không cần cài lại Extension.
3. Manager → Điều phối Studio → chọn dự án Manager thật, chọn Studio ID (hoặc dán mã), chọn Edge/profile đúng. Lưu liên kết và đưa vào Queue.
4. Chạy tất cả theo thứ tự Queue. Manager mở link đúng dự án; chờ tối đa 120 giây để xác nhận tab/Extension/ChatGPT; phân tích cấu trúc nếu chưa có phần; phân cảnh lần lượt các phần chưa hoàn tất. Không bấm phân tích thủ công đồng thời.
5. Theo dõi phần/cảnh thật và nhật ký. Dữ liệu lưu trong analysis/studio_structure.json, analysis/studio_progress.json, scenes/<part-id>.json; journal lệnh và checkpoint Agent nằm local.

Preview: https://video-image-studio-git-phase3-manager-presence-image-studio1.vercel.app/
Studio source commit: 88e57ca5b0bab0ecc4b978dfbee9b83a848dea07
Studio chỉ sửa App.tsx, thêm managerLaunch.mjs và type declaration/test. Không sửa handler server, prompt, Extension hoặc workflow phân tích. Chưa đẩy lên main/production.

Liên kết bằng ID duy nhất, không theo tên. Không mở dự án không có trong metadata profile; không tạo dự án hay profile thay thế. Nonce của phiên chạy + Studio ID + origin trong presence phải khớp trước khi gửi lệnh. Edge xác minh profile qua Windows Agent. Chrome dùng cửa sổ bạn chọn và chưa có cơ chế xác minh tên profile tương đương Edge; ưu tiên nghiệm thu với Edge.

Pause/STOP ngừng worker và không gửi phần tiếp theo. Tác vụ đã gửi sang ChatGPT có thể tiếp tục trả kết quả và Studio vẫn lưu kết quả đó. Resume đọc lại trạng thái, bỏ qua phần hoàn tất. Restart không tự chạy task đã dừng. Nếu POST có kết quả chưa rõ, đánh dấu cần kiểm tra và không tự gửi trùng. Tác vụ lỗi không tự reset toàn dự án. Không tự F5 ChatGPT trong bản này.

Lưu ý: dùng một dự án thật để nghiệm thu trước. Extension hiện tại gắn với một session; bản này không tự ghép ChatGPT sang dự án tiếp theo hoặc đổi hội thoại. Một dự án tiếp theo chưa ghép đúng sẽ chờ rồi báo lỗi, không gửi prompt sai phiên.

Kiểm thử: Manager suite 101 tests (99 PASS, 2 Windows-only SKIP trên Linux); test mới gồm tuần tự hai phần, journal chống POST trùng, skip phần đã hoàn tất, lệch presence, tác vụ ngoài Manager, watchdog, checkpoint restart, mapping ID duy nhất, HTTP trả sai ID. Node UI regression PASS. Studio production build PASS, 4 manager-launch tests PASS.

Studio broad existing suites: node tests/*.test.mjs có 36/73 FAIL ở test cũ (chủ yếu mock chrome.tabs.onUpdated thiếu); Vitest src có 1/14 FAIL tại transcriptWorkspace > starts with an empty workspace do localStorage không tồn tại trong test environment. Các file Extension/transcript production và test này không bị sửa trong thay đổi. Không tuyên bố toàn suite Studio PASS.

Chưa test end-to-end trên Windows với Studio/Extension/ChatGPT thật, chưa coi simulation/transport giả là nghiệm thu. Chưa tạo ảnh, tải ảnh, dựng CapCut hay upload YouTube.
