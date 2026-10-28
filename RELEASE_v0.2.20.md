# AI MANAGER v0.2.20 — bản kiểm tra mở rộng điều phối

**Chưa PASS nghiệm thu toàn bộ mục 27.** Đã triển khai chức năng bên dưới và kiểm thử local/mock, nhưng chưa chạy Edge/Studio/ChatGPT thật trên Windows trong môi trường này.

## Đã triển khai

- Dự án chọn nhiều bằng checkbox; đưa sang Điều phối. Lựa chọn UI không kích hoạt worker. Batch được lưu SQLite khi chạy; thứ tự kéo thả hoặc ↑/↓, không thay đổi khi đang chạy/tạm dừng. Dự án không được chọn không tự chạy cùng batch.
- Bảng công việc riêng từng project, đọc Studio trước khi cấu hình và đọc lại trước khi chuẩn bị workflow. Cấu hình tasks/scopes/error policy/retry/rerun lưu project.json và context Agent. Chỉ highlight Task được chọn.
- Các task đã có worker: phân tích cấu trúc, phân cảnh phần, tạo ảnh, tạo lại ảnh lỗi, đồng bộ/lưu tệp Studio. Phân cảnh và ảnh có phạm vi all/range/selected; ảnh có missing/errors. Phạm vi dùng số thứ tự 1-based, được kiểm tra rồi chốt ID trong journal để Resume không chạy lệch.
- Skip kết quả đã hoàn tất. Rerun ảnh là lựa chọn rõ ràng, backup scene metadata và lưu ảnh mới vào images/reruns/<workflow_id>/; không ghi đè file cũ. Đổi prompt sau checkpoint bị chặn để rà soát lại.
- Project → stage Task → Part/Scene Subtask → result/ledger/checkpoint. Ledger JSON atomic/fsync trong analysis/workflow_<id>.json; operation ID, project/task/subtask, retry, kết quả/lỗi được ghi. Phần xong lưu JSON; ảnh SAVE/VERIFY/CHECKPOINT trước khi gửi scene tiếp theo. Pipeline ảnh/lưu thực thi theo từng scene, cùng nhóm Task images và trạng thái SYNCING, không chờ cả project mới lưu.
- Resource lock SQLite giao dịch liên tiến trình cho Studio/ChatGPT (toàn cục, nghiêm ngặt hơn khóa từng profile); một Agent worker và một project Queue chạy. Khóa giữ qua gián đoạn nếu còn active job/intent. STOP có đối soát read-only nền để giải phóng chỉ khi chứng minh không còn công việc chưa rõ. Không release mù hoặc resend prompt chưa rõ.
- Retry có backoff 5/10/20/30s và giới hạn cho server job đã xác nhận lỗi; lỗi tải/lưu cũng retry giới hạn. Mặc định ghi scene lỗi rồi chạy scene sau; đến cuối báo project lỗi, không báo completed giả. Policy stop dừng project tại lỗi. Retry thủ công chỉ đưa unit ERROR về READY; kết quả đã hoàn tất không reset.
- Reconcile API Studio và file/checksum khi tiếp tục, không tin hoàn toàn checkpoint. File thiếu/hỏng được đưa ERROR để xác minh. Không gửi lại một POST đã có intent chưa xác nhận. Không có backend idempotency key mới: operation_id gửi kèm nhưng chống trùng chủ yếu dựa journal/receipt và khóa local hiện có.
- Mất presence/ChatGPT: không gửi lệnh, chờ tối đa 120 giây rồi pause/review. Wrong profile/session hoặc tác vụ ngoài workflow: pause, giữ checkpoint. Browser/window mất có phục hồi tối đa 2 lần bằng đúng browser/profile và URL/nonce cũ, không gửi lại prompt. Native input không rõ tác động vẫn cần kiểm tra, không ép Resume.
- Pause và Stop tách endpoint/state. PAUSED/STOPPED và các unit giữ đúng checkpoint. Khởi động lại không tự chạy, kể cả trước đó running (khôi phục paused/review theo cơ chế cũ).
- Khi một workflow hoàn tất/lỗi đã xác định và không còn remote job, Queue chuyển project tiếp theo. Lỗi nghiêm trọng/unknown outcome pause cả luồng, không chuyển mù.
- Điều phối không còn nhập đường dẫn/Studio URL/profile kỹ thuật; hiển thị gán hiện tại. Các gán và profile nguồn đồng bộ nằm ở Cài đặt/Điều khiển ứng dụng. Sử dụng cửa sổ đã xác minh nếu đã chọn trong Điều khiển ứng dụng.

## Giới hạn chưa nghiệm thu / chưa hỗ trợ

- Transcript, viết lại, dựng video, xuất chưa có worker và bị khóa có chú thích; không tạo task giả.
- Studio API chỉ có phân tích cấu trúc toàn kịch bản. Không phân tích cấu trúc riêng Part 6–10; dùng scope ở Phân cảnh. Rerun phân tích/phân cảnh bị từ chối vì chưa có cơ chế thay thế kết quả an toàn; chỉ rerun ảnh có backup.
- Extension vẫn chỉ một pairCode/session mỗi browser profile. Chưa tự đổi hội thoại giữa nhiều dự án cùng profile. Chạy không can thiệp chỉ có thể thử với các profile đã ghép đúng từng dự án; nếu chưa đúng Manager chờ/pause. Không có bằng chứng Windows thật chứng minh chuỗi này đã PASS.
- Reconnect là quan sát lại presence/API và phục hồi browser có giới hạn, không tự đăng nhập, không F5 vô hạn, không tự chọn ChatGPT tab đầu tiên. Không có worker tự sửa mọi lỗi ChatGPT.
- Sync/Lưu dùng ảnh Studio đã nhận. Chưa tự kích hoạt quy trình capture một ảnh chỉ tồn tại trong hội thoại nhưng chưa về Studio; trường hợp đó chờ/ERROR để đối soát, không tạo bừa ảnh mới ở task chỉ Lưu.
- Lỗi timeout/unknown POST không tự retry; giữ khóa và pause để tránh duplicate. Không tự gỡ khóa một công việc đang chưa rõ.
- Profile nguồn đồng bộ do người dùng xác nhận; Agent xác minh profile/cửa sổ lúc điều khiển. Không copy cookie, không tạo profile mới.
- Kết quả thử trình duyệt là UI/local HTTP với fixture, không phải test Windows/ChatGPT.

## Kiểm thử

- Python suite cuối: xem WINDOWS_TEST_RESULTS.txt (Windows-only skipped ở Linux).
- Unit/integration giả: ba cấu hình khác nhau A → B → C, không POST chồng; scope phần/cảnh, skip, save file, checksum, retry hữu hạn/continue, unknown POST, thay prompt, missing file, lock persist/release đúng owner, Pause khác Stop, Queue restart, critical review không chuyển project, phục hồi browser giữ project/profile/nonce.
- Node regression app controls/Studio UI; browser local tạo 3 project thật trong thư mục tạm, UI fixture chọn 3 công việc khác nhau và đúng batch payload; menu/dialog/toast, desktop/mobile. Không dùng fixture làm số liệu production.
- Một lần chạy trước có test STOP race timeout khi đợi thread 2s. Không đổi timeout test cũ; chạy riêng 22 test automation PASS và full suite sau PASS. Chưa xác định nguyên nhân timing của lần đó.
- Windows thực: chưa chạy mới các test đóng browser, mất Studio, đổi hội thoại, dừng Scene 50, 3 dự án ChatGPT thật. Do đó không công bố đầy đủ PASS.

## Tệp chính

work_board.js; ui_shell.js; theme.css; index.html; server.py; queue_manager.py; automation_agent/work_config.py; work_ledger.py; resource_lock.py; scoped_images.py; studio_workflow.py; studio_images.py; runtime.py; agent_server.py; action_worker.py; manager_service.py; queue_bridge.py; automation_log.py; build_identity.py; tests/test_work_orchestration.py; test_neon_browser.cjs; test_studio_presence.py.

Studio và Extension không sửa trong bản v0.2.20. Không thay đổi main/production, không làm CapCut workflow.
