# WinControl — Kiến trúc chuẩn

Tài liệu đối chiếu cho mọi thay đổi WinControl. Thay đổi nào lệch khỏi đây phải sửa tài liệu này trước và được người dùng đồng ý.

## 1. Vai trò

- **WinControl** = giao diện điều hành trong MAN (`wincontrol.js`, tab trong app hiện có). Không phải app, Agent hay Extension mới.
- **ChatGPT** = bộ não. Mọi quyết định bước tiếp theo đến từ ChatGPT, đọc qua Chrome DevTools MCP. Không dùng OpenAI API.
- **Windows Agent** (`automation_agent/agent_server.py` + `runtime.py`) = tay chân. Thực thi từng hành động trong subprocess riêng (`action_worker.py`), lưu checkpoint trong `TaskStore`.

## 2. Luồng một nhiệm vụ

```
Người dùng gõ lệnh (wincontrol.js)
  → POST /api/automation {command:'wincontrol', text, request_id}      (server.py → manager_service.py)
  → Agent /submit: task WinControl, exclusive, 3 bước ban đầu
       OBSERVE_CHATGPT → SEND_CHATGPT(prompt có [exchange_id]) → WINCONTROL_DECIDE
  → runtime.wincontrol_next(): đọc JSON {status, summary, actions}
       continue  → chèn [1 hành động] + SEND_CHATGPT(kết quả) + WINCONTROL_DECIDE
       invalid   → SEND_CHATGPT(yêu cầu sửa JSON), tối đa MAX_CORRECTIONS
       complete  → task xong
       blocked   → needs_review, hiện lý do cho người dùng
  → lặp đến MAX_ROUNDS (12)
UI đọc /api/state mỗi chu kỳ: tab Trò chuyện (hội thoại) và tab Công việc (tiến độ/kết quả).
```

## 3. Thành phần tái sử dụng (không tạo bản thứ hai)

| Việc | Thành phần |
|---|---|
| Đọc/gửi ChatGPT | `chatgpt_mcp.py` → `chrome_mcp_bridge.mjs` → Chrome DevTools MCP chính thức. Một kết nối CDP duy nhất. |
| Hợp đồng JSON, prompt, kiểm tham số | `wincontrol_chat_loop.py` (`validate_actions`, `parse_decision`, `FIELDS`) |
| Windows UIA | `ui_automation.py`, `window_manager.py` (pywinauto) |
| Thực thi, timeout, hủy | `action_executor.py`, `action_worker.py` |
| Checkpoint, hàng đợi | `task_store.py` (SQLite). Không có hàng đợi thứ hai. |
| Giám sát | `watchdog.py`, `extension_monitor.py`, `studio_monitor.py`; WinControl đọc qua `MAN_STATUS` (chỉ đọc `/api/state`). |
| Cập nhật Extension | `extension_updater.py`, mã nguồn Extension ở repo Studio. |

## 4. Bảo đảm an toàn

- **Chống gửi trùng**: `request_id` từ UI (bấm đúp → trả lại task cũ); `exchange_id` nằm trong prompt, nếu đã là lượt user cuối thì coi như đã gửi; `exchange_id` không lặp trong toàn TaskStore; `SEND_CHATGPT` không bao giờ retry (`retries:0`, thuộc `UNSAFE`).
- **Gửi chỉ khi đã xác minh**: fingerprint + turn_count của trang ChatGPT phải khớp lần quan sát trước.
- **Đọc thì được lặp**: snapshot thử lại 3 lần, chờ ChatGPT tới `response_limit` (600 giây) rồi mới `CHATGPT_RESPONSE_TIMEOUT`.
- **Hành động nhập liệu có kết quả mơ hồ** (CLICK, TYPE_TEXT, HOTKEY…) không tự retry.
- **Phạm vi hành động**: chỉ danh sách `WINCONTROL_ACTIONS`, ứng dụng `notepad/chrome/edge/capcut`, tệp chỉ trong `%TEMP%\WinControl`. Không có hành động sản xuất Studio, sửa Extension hay `SEND_CHATGPT` do ChatGPT yêu cầu.
- **Một task WinControl tại một thời điểm**; không chạy khi Agent đang có task khác.

## 5. Ranh giới triển khai

- MAN đang chạy trên PC lấy mã từ thư mục `C:\Users\PC\Projects\AI_MANAGER` (checkout `main`). Mã trên nhánh chưa có hiệu lực cho tới khi được triển khai vào đó và khởi động lại MAN.
- Khởi động lại MAN/Studio là **cổng duyệt riêng**: phải có backup mới, task production đang chạy đã dừng tự nhiên, và người dùng đồng ý.
- Không xóa cờ stopped/in_flight, không phát lại task sản xuất, không dùng dữ liệu Studio đang sản xuất để thử.

## 6. Ba mức trạng thái khi báo cáo

1. **Đã sửa mã** (commit trên nhánh, test tự động đạt).
2. **Đã triển khai trên PC** (MAN chạy đúng commit đó).
3. **Đã kiểm thử thực tế** (vòng đầy đủ từ giao diện WinControl → ChatGPT → Windows → ChatGPT, có log/receipt).

`WINCONTROL_READY` chỉ khi đạt mức 3.
