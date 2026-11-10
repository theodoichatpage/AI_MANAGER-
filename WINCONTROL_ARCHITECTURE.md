# WINCONTROL — KIẾN TRÚC CHUẨN BẤT BIẾN

Trạng thái: Quy định kiến trúc do chủ dự án yêu cầu. Áp dụng cho mọi thay đổi tiếp theo trên WinControl, MAN, Studio và Extension.

## Mục tiêu sản phẩm
Người dùng nhập một nhiệm vụ bằng tiếng Việt vào WinControl (ví dụ: "Tạo phần mềm dựng video cơ bản"). WinControl sử dụng ChatGPT làm bộ não để phân tích, lập kế hoạch, chọn hành động, gọi công cụ, quan sát kết quả, tự xử lý lỗi có thể khôi phục, tiếp tục từ checkpoint, kiểm thử sản phẩm và báo cáo. Không yêu cầu người dùng đưa từng lệnh Codex.

## Phân cấp bắt buộc
Người dùng → WinControl (điều hành trung tâm, giao diện nhận lệnh, điều phối vòng lặp) ↔ ChatGPT (suy luận/quyết định).
WinControl → Windows UI Automation/pywinauto (Windows) và Chrome DevTools MCP qua chrome_mcp_bridge.mjs (Chrome).
WinControl → MAN (quản lý công việc, hàng đợi, checkpoint) → Studio (sản xuất nội dung) → Extension (gửi/nhận công việc ChatGPT).
Kết quả/lỗi từ công cụ và MAN/Studio quay về WinControl → ChatGPT để quyết định tiếp.
WinControl KHÔNG ngang hàng với Chrome MCP hoặc pywinauto. ChatGPT không thay thế WinControl. Codex là công cụ phát triển, không phải giao diện vận hành hàng ngày.

## Tái sử dụng, không phát sinh hệ thống
- Tái sử dụng ActionExecutor, TaskStore, Agent Server, Chrome DevTools MCP chính thức, chrome_mcp_bridge.mjs, Windows UIA/pywinauto và MAN/Studio/Extension hiện có.
- Không tạo AI thứ hai, Agent thứ hai, kết nối CDP song song, hàng đợi trùng, hoặc cơ chế ChatGPT gửi trùng với Extension.
- Không hardcode một dự án cụ thể. Không tự ý đổi nhánh Studio phase3-manager-presence.
- Không yêu cầu thêm Full Access khi quyền đã được cấp; nếu quyền của phiên/môi trường khác nhau, nêu chính xác điểm chặn và bằng chứng.
- Không tự ý xây lại hoặc thay thế thành phần hoạt động; mọi ngoại lệ phải có bằng chứng kỹ thuật, lý do và được người dùng đồng ý.

## Vòng điều hành cần triển khai
1. Nhận nhiệm vụ text và lưu task/checkpoint.
2. Đưa mục tiêu và trạng thái cho ChatGPT qua cơ chế được hỗ trợ.
3. Đọc phản hồi, xác định hành động có cấu trúc, validate công cụ và tham số.
4. Thực thi bằng công cụ sẵn có; ghi receipt, log, lỗi, ảnh màn hình khi cần.
5. Gửi kết quả cho ChatGPT, quyết định bước kế tiếp; lặp đến khi có kết quả kiểm chứng hoặc báo chặn rõ ràng.
6. Chống gửi trùng, giữ checkpoint, giới hạn retry, tránh vòng lặp vô hạn và hành động nguy hiểm không được phép.
7. Kiểm thử thực tế đầu-cuối bằng nhiệm vụ người dùng giao; chỉ báo hoàn thành sau khi xác minh đầu ra.

## Quy tắc triển khai
Trước mỗi thay đổi: đọc tài liệu này, kiểm tra mã hiện có, nêu rõ phần tái sử dụng và khoảng trống thực tế. Ưu tiên sửa tối thiểu, kiểm thử hồi quy, không đổi kiến trúc. Phân biệt: mã có trong repo / kiểm thử PASS / đã triển khai PC / vận hành thực tế. Không suy đoán nguyên nhân lỗi; truy vết bằng log và receipt. Không tự nhận có quyền điều khiển PC chỉ vì truy cập được GitHub.

## Tiêu chí chấp nhận
Một câu lệnh từ WinControl kích hoạt chuỗi ChatGPT → công cụ → quan sát → ChatGPT → tiếp tục; có thể tạo file, chạy thử, xử lý lỗi, bàn giao sản phẩm mà không cần người dùng nhập lệnh từng bước. Không coi test riêng Chrome hoặc Windows là bằng chứng hoàn thành toàn hệ thống.
