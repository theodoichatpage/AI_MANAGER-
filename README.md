# AI MANAGER ? 0.2.25 source release

This branch reconciles the current MAN production source with GitHub 0.2.24, preserving both histories. It includes the existing Studio workflow, story/review coordination, queue fixes, and single-project deployment fixes. This is a source snapshot, not a claim of a new production end-to-end acceptance run.

Windows: run `MO_AI_MANAGER.bat` (Python 3.10+) or `python server.py`, then open http://127.0.0.1:8765 locally. Studio and browser integration require their existing configuration and authenticated sessions. No credentials, project databases, user media, or browser profiles are distributed here.

Unaccepted Maintenance Mode / Windows Control integration candidates remain outside this release. Publishing this branch does not install a patch, restart services, or activate production automation. The historical notes below describe earlier milestones and are not the current acceptance report.

## Validation

See `RELEASE_v0.2.25.md` for the merge scope and validation results. Live MAN/STUDIO production acceptance was not rerun during source synchronization.

## Phase 2: hàng đợi mô phỏng
Mỗi thư mục gốc có database `.ai_manager_queue.sqlite3` chứa hàng đợi, checkpoint và nhật ký. Chỉ chạy một dự án; mở lại sau gián đoạn sẽ tạm dừng dự án đang chạy. Chọn Hàng đợi để kiểm tra trạng thái và điều khiển. Tiến độ và lỗi trong Phase 2 là mô phỏng, không phải ảnh thật. Các nút Test: hoàn tất/lỗi dùng để kiểm tra chuyển trạng thái. Để cập nhật, dừng chương trình cũ trước khi chạy phiên bản mới.

## Kiểm tra Phase 2
Mở MO_AI_MANAGER.bat và giữ cửa sổ đó mở. Bấm “Tạo / nạp 3 dự án TEST”, sau đó “Chạy tất cả”. Trong Hàng đợi có các nút thử hoàn tất và thử lỗi. Để thử khôi phục, đóng cửa sổ chạy khi tiến độ 30–50%, mở lại file .bat và bấm Tiếp tục. Các dự án TEST được lưu thật; bấm nút tạo lần nữa sẽ nạp lại, không đặt lại tiến độ.

## Đọc phiên Studio (bản kiểm tra)
Mở VIDEO IMAGE STUDIO, chọn Kết nối ChatGPT và sao chép mã kết nối. Trong AI MANAGER chọn Kết nối Studio và dán mã. Dữ liệu được đọc định kỳ, không gửi lệnh tới Studio. Mã phiên được giữ trong bộ nhớ đến khi chương trình đóng; cần nhập lại sau khi khởi động. Đọc được dữ liệu máy chủ không chứng minh tab Studio hay ChatGPT đang mở, do đó hai trạng thái này được ghi là chưa xác định. Chức năng chưa điều khiển phân tích, ảnh hoặc tải xuống.

## Phase 4 — Windows Automation Agent, v0.2.7

Mở `MO_AI_MANAGER.bat` trên Windows 10/11 với Python 3.10+. Lần đầu launcher tự tạo môi trường riêng và cài thư viện miễn phí. Agent chạy riêng, API chỉ bind loopback và dùng token ngẫu nhiên; mọi action UI chạy trong subprocess có timeout.

Vào **Điều khiển ứng dụng** để chạy Chrome/CapCut, liệt kê PID/HWND, screenshot, hoặc thử nhập trong cửa sổ test riêng. Có thể gắn workflow vào dự án rồi dùng **Chạy tất cả**. **Dừng tất cả** dừng cả Queue và Agent; **Dừng Agent** còn đóng tiến trình Agent.

Dữ liệu task, checkpoint và log lưu riêng trong `~/.ai_manager/automation`. Không xóa dữ liệu dự án cũ. Dự án mô phỏng cũ vẫn giữ chế độ mô phỏng; không báo số ảnh giả. Lỗi giữa thao tác nhập/click cần kiểm tra thủ công, không tự phát lại. Browser recovery chỉ phục hồi cửa sổ/URL đã biết; không gửi lại prompt ChatGPT. CapCut chỉ là nền tảng mở/focus/UIA/screenshot/đóng, chưa phục hồi timeline/project editing.

Automated checks: `python -m unittest discover -s tests -v`; JavaScript: `node --check automation.js`. Các bài test Linux và mocked Windows APIs không thay thế nghiệm thu Windows. Xem `docs/WINDOWS_ACCEPTANCE.md`.

## Microsoft Edge v0.2.7

Đọc [EDGE_v0.2.7.md](EDGE_v0.2.7.md) để kiểm tra Edge và profile hiện có. Không tạo profile hoặc đọc cookie. Chrome/CapCut giữ luồng cũ. Chưa nghiệm thu Edge trên Windows thật.

## v0.2.8

Thông báo nổi tự ẩn sau 4 giây. Có Chẩn đoán Edge để đọc bằng chứng UIA trên Windows; chưa xác nhận sửa được lỗi nhận diện profile.

## v0.2.10

Đổi xác minh Edge sang Windows Shell properties, bỏ chờ Accessibility trên luồng mở profile. Xem [EDGE_v0.2.10.md](EDGE_v0.2.10.md). Windows vẫn chờ nghiệm thu, không lấy test mô phỏng làm bằng chứng PASS.

## v0.2.11

Sửa lỗi win32gui.SetProp: Agent không ghi thuộc tính lên cửa sổ. Thêm real-Windows API contract, Agent build identity và nút thử lại khi OPEN_APP lỗi. Xem [EDGE_v0.2.11.md](EDGE_v0.2.11.md). Kiểm thử API Windows và kiểm thử Edge thực tế là hai kết quả riêng.

## v0.2.12 — Điều phối Studio

Menu Điều phối Studio liên kết dự án bằng ID + browser/profile, mở đúng dự án Preview, phân tích cấu trúc và phân cảnh từng phần qua API hiện có. Lưu analysis/scenes/checkpoint, không reset phần hoàn tất, không tự phát lại POST không rõ kết quả. Chưa nghiệm thu chuỗi Studio/Extension/ChatGPT trên Windows. Xem STUDIO_v0.2.12.md.
