# AGENTS.md — HƯỚNG DẪN BẮT BUỘC CHO CODING AGENT

Trước khi sửa bất kỳ mã nguồn WinControl/MAN/Studio/Extension, đọc [WINCONTROL_ARCHITECTURE.md](WINCONTROL_ARCHITECTURE.md) và tuân thủ toàn bộ quy tắc trong đó.

Thứ tự ưu tiên: (1) Giữ WinControl là hệ thống điều hành trung tâm với ChatGPT là bộ não; (2) tái sử dụng Windows UIA/pywinauto và Chrome DevTools MCP; (3) tái sử dụng MAN → Studio → Extension; (4) hoàn thiện vòng nhận nhiệm vụ → quyết định → thực thi → quan sát → sửa lỗi → tiếp tục → kiểm chứng.

CẤM tự ý: tạo AI/Agent/hàng đợi/CDP song song; thay đổi kiến trúc; hardcode dự án Thái Sư Trần Thủ Độ; đổi nhánh Studio phase3-manager-presence; coi thao tác click hoặc test đơn lẻ là receipt/hoàn thành; yêu cầu người dùng chạy Codex thủ công cho từng bước.

Mọi PR phải ghi: thành phần hiện có đã tái sử dụng, lỗi cụ thể có bằng chứng, thay đổi tối thiểu, kiểm thử thực tế, giới hạn chưa xác minh. Nếu xung đột kiến trúc, dừng thay đổi đó và báo rõ, không âm thầm xây hệ thống mới.
