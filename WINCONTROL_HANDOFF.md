# WinControl — Bàn giao

**Phiên giữ quyền viết:** phiên Claude "WinControl tiếp quản từ Codex (fork)" (`local_8fdb951a`), người dùng xác nhận ngày 2026-11-11. Các phiên khác chỉ đọc. Codex: chỉ làm trên worktree riêng, mở PR, không triển khai vào MAN.
**Nhánh:** `wincontrol/takeover-20261111` (worktree `C:\Users\PC\Projects\AI_MANAGER_WINCONTROL`), đã push.
**Kết luận:** `WINCONTROL_READY` cho **vòng điều hành cơ bản** (2026-11-11 13:19 giờ máy). Chưa có nghĩa các khả năng mở rộng (Chặng 2–4) đã xong.

## 1. Bằng chứng READY (kiểm thử thực tế từ giao diện)

Task `9213574d-0699-47c3-910d-1e875b8b6c2d`, gửi từ ô nhập WinControl: *"Mở Notepad, ghi dòng "WinControl sẵn sàng 11/11", lưu thành tệp wc_ready_1111.txt trong thư mục tạm WinControl rồi xác minh nội dung tệp."*

| Vòng | ChatGPT quyết định | Agent thực thi | Kết quả |
|---|---|---|---|
| 1 | ENSURE_TEMP_DIR | worker | `%TEMP%\WinControl` |
| 2 | OPEN_APP notepad | UIA, cửa sổ mới pid 31212 | OK |
| 3 | FOCUS_WINDOW notepad | UIA | OK |
| 4 | TYPE_TEXT `{"class_name":"Edit"}` | UIA, đọc lại Value | 25 ký tự, verified |
| 5 | SAVE_AS `wc_ready_1111.txt` | UIA hộp thoại Save As | 28 byte |
| 6 | VERIFY_FILE | worker | khớp |
| 7 | `complete` + tóm tắt tiếng Việt | — | task `completed` |

- File thật: `C:\Users\PC\AppData\Local\Temp\WinControl\wc_ready_1111.txt` = "WinControl sẵn sàng 11/11" (UTF-8).
- Biên nhận: mỗi lượt gửi có `exchange_id` ở đầu prompt và receipt `submission: received`; kết quả mỗi bước ghi kèm chỉ số hành động trong TaskStore; nhật ký `~\.ai_manager\automation\automation.jsonl`.
- Chống gửi trùng: đọc lại hội thoại ChatGPT, mỗi exchange id còn hiển thị xuất hiện đúng 1 lần.
- Khôi phục sau gián đoạn: task `93cdbfe3` dừng 4 lần (bridge từ chối, lỗi định tuyến, mất focus) và qua 3 lần khởi động lại MAN/Agent; mỗi lần bấm **Tiếp tục** trên giao diện, nó đi tiếp từ checkpoint, gửi prompt đầu đúng 1 lần dù bản nháp cũ còn trong ô soạn tin, và chạy MAN_STATUS → ENSURE_TEMP_DIR → OPEN_APP với ChatGPT quyết định từng bước.
- Khôi phục kết nối: sau khi khởi động lại MAN, ghép nối Studio tự nạp lại (Studio `connected`), Extension trở lại `responding`.
- Chưa tự tạo được một lần rớt kết nối Chrome MCP thật để quan sát; đường đọc lại (3 lần, mở bridge mới mỗi lần) chỉ được chứng minh bằng test.

## 2. Ba lỗi cấu trúc (Chặng 1)

| Lỗi | Đã sửa mã | Triển khai | Kiểm thử thực tế |
|---|---|---|---|
| Mất ghép nối Studio khi khởi động lại MAN | `6ef5d73`: mã lưu mã hóa DPAPI `~\.ai_manager\studio_pairing.bin`, nạp lại khi khởi động, xóa khi Ngắt | Có | Có — 4 lần khởi động lại, Studio tự `connected` |
| Test chạm DB sản xuất | `6ef5d73`: `test_guard.py` — dưới unittest/pytest tự dùng home tạm, thư mục dự án mặc định theo home tạm, `QueueManager` từ chối thư mục thật | Có | Full suite chạy không đặt `AI_MANAGER_HOME`: nhật ký hàng đợi thật không đổi |
| WinControl bị chặn khi sản xuất chạy | `5271017`: làn WinControl riêng trong cùng Agent (executor, cờ hủy, task hiện tại riêng; Dừng WinControl không dừng sản xuất; Tạm dừng sản xuất không chạm WinControl) | Có | Có (task chạy khi Agent có task sản xuất ở trạng thái failed; chưa chạy song song với sản xuất đang chạy thật) |

## 3. Lỗi tìm thấy khi chạy thật và đã sửa (đều đã triển khai)

- `9d30f31`/`d56a7bf`: prompt nhiều dòng; `2b4cbaa`: snapshot in giá trị nguyên văn (không thoát `"`) → bridge cắt prompt JSON, mọi lượt gửi bị từ chối; `parse_snapshot` cũng sẽ cắt câu trả lời JSON.
- `2b4cbaa`: kết quả "đang chờ" bị coi là trả lời sai → chèn vòng sửa thừa; hành động đã kiểm tra bị kiểm tra lại (trường `retries`).
- `96dceb5`: ô soạn tin ChatGPT chèn xuống dòng quanh liên kết → giá trị nhiều dòng; kết quả là nhật ký nên lệch chỉ số → prompt phản hồi gửi nhầm dữ liệu.
- `71beef4`: sau OPEN_APP notepad, bước ChatGPT bị định tuyến sang Notepad.
- `d304182`: gõ phím bị chặn vì mất focus → nay tự đưa cửa sổ của WinControl lên trước; từ chối trước khi có thao tác (`NOT_EXECUTED`) được báo lại cho ChatGPT.
- `0caa3a0`: lối vào WinControl bị ẩn trong MAN v0.2.25; Notepad riêng; `SAVE_AS`; đọc UIA Value.
- `257b84f`: hành động phải ghi rõ ứng dụng; cấm gõ/bấm trong Chrome/Edge (tab ChatGPT, Studio).

Test: 80 test WinControl/automation đạt; full suite (cô lập) chỉ còn 3 lỗi có sẵn từ `80a0890` (`test_startup_port`, 2 test `test_work_orchestration`) + `test_neon_browser.cjs` thiếu `playwright`.

Triển khai: `integration_reports\takeover_20261111\deploy_wincontrol.ps1` (sao lưu `predeploy_*`, chặn khi có task running/waiting, so checkpoint trước/sau, tự rollback, xác minh MAN phục vụ đúng thư mục bằng `wincontrol.js`). Lần cuối 06:15:06Z: MAN pid 35384, Agent pid 32280.

## 4. MAN, Studio, Extension

- MAN chạy `C:\Users\PC\Projects\AI_MANAGER` (`main` @ `2994818` + 17 tệp triển khai từ nhánh này, chưa commit trên `main`).
- **Sản xuất Thái Sư — nguyên nhân đã xác định:** tài khoản ChatGPT tạo ảnh hết hạn mức gói Plus. Tab ChatGPT trong Edge (hồ sơ "ChatGPT 3", chụp bằng PrintWindow, chỉ đọc) hiện: *"You've hit the Plus plan limit for image generations requests. You can create more images when the limit resets in 5 hours."* Studio chỉ báo "ChatGPT không phản hồi sau 2 lần tự tải lại tab", nên MAN không nhận ra là hết lượt và cứ gửi lại.
  - Diễn biến: 94/384 ảnh xong; ~11:00 ngừng; 11:40 watchdog → `failed`. 13:42 người dùng chọn chạy lại với 1 tab: `IMAGE_LANES` 2→1 (commit `ff10145` trên `main` máy này, **chưa push** vì `main` máy đã lệch xa `origin/main` với nhiều commit của phiên khác), Chạy lại lỗi + Chạy → vẫn cùng lỗi trên cả hai hồ sơ.
  - Ba cửa sổ Edge đang thu nhỏ; đã thử khôi phục (không lấy focus) — không đổi kết quả; đã thu nhỏ lại như cũ.
  - 13:5x: **đã Tạm dừng** sản xuất (task `paused` ở bước 5, không in-flight, không lệnh `intent`, 94 ảnh giữ nguyên). Chạy tiếp sau khi hạn mức đặt lại (khoảng 5 giờ kể từ ~14:02) hoặc đổi sang tài khoản ChatGPT khác.
  - Cần sửa ở Studio/Extension (repo VIDEO_IMAGE_STUDIO): nhận ra thông báo hết hạn mức ảnh và báo lỗi giới hạn để MAN nghỉ (`LIMIT_COOLDOWN`) thay vì gửi lại.
- Phiên "AI MANAGER v0.2.20 takeover" (`local_e8068fff`) commit thẳng vào `main` và tự khởi động lại MAN lúc 09:05 — ngoài nhóm phối hợp này. Cần thống nhất chỉ một phiên triển khai MAN.
- 01:30:47Z: full suite chạy không có home tạm (phiên gốc) đã tạm dừng dự án Thái Sư; nay bị chặn bởi `test_guard`.
- Studio: `connected`; Extension v0.5.19 = mới nhất, `responding`.

## 5. Xưởng Nội Dung (repo riêng)

`main` = `origin/main` (`8a8be58`); web Vercel trùng `main`; 252/253 test đạt (1 bỏ qua); trang không lỗi console. Chưa kiểm tra kết nối Extension trong Chrome người dùng. Không sửa gì.

## 6. Bước tiếp theo

1. Chạy tiếp Thái Sư khi hạn mức ảnh ChatGPT đặt lại (Tiếp tục trong MAN); sửa Studio/Extension để nhận ra hết hạn mức.
2. Chạy thử WinControl song song khi sản xuất đang chạy thật.
3. Chặng 2: công cụ file/thư mục, PowerShell có kiểm soát, Chrome qua MCP, Git, build/test — thêm vào `wincontrol_chat_loop.FIELDS` + `action_worker`, có giới hạn và test.
4. Chặng 3: hành động sửa chữa cho MAN/Studio/Extension dựa trên `MAN_STATUS` (hiện chỉ đọc).
5. Commit 17 tệp đã triển khai vào `main` (hoặc merge nhánh này) để thư mục chạy hết "chưa commit".
