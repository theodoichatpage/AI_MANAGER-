# v0.2.0 — nghiệm thu Windows (chưa chạy trong môi trường phát triển)

| Kiểm tra từ giao diện | Kết quả cần thấy | Hiện trạng |
|---|---|---|
| MO_AI_MANAGER.bat | Tự chuẩn bị runtime, Agent và server; mở Dashboard | Chờ Windows |
| Kiểm tra Agent | Online + PID + uptime thật | Chờ Windows |
| Danh sách process / cửa sổ | PID, HWND, title thật | Chờ Windows |
| Workflow Chrome | Mở, chờ window, focus, URL example.com, UIA Document, screenshot | Chờ Windows |
| Workflow CapCut | Phát hiện executable, mở, focus, screenshot | Chờ Windows |
| Test nhập text an toàn | Cửa sổ test riêng, ô Edit đọc lại đúng text, screenshot | Chờ Windows |
| STOP trong WAIT | Không action tiếp theo, không tự chuyển project | Chờ Windows |
| Restart giữa workflow | Queue/task/checkpoint/log còn; paused hoặc needs_review | Chờ Windows |
| Thay vị trí / maximize Chrome | UIA tìm element và HWND, không dùng tọa độ màn hình cố định | Chờ Windows |
| Agent chết | Manager khởi động lại có giới hạn; workflow gián đoạn không tự phát lại thao tác nguy hiểm | Chờ Windows |

Chỉ sau khi các mục trên được kiểm tra trực tiếp mới coi Phase 4 PASS. Windows Agent điều khiển được các action đã cấu hình; chưa có workflow dựng video CapCut hay tự động toàn chuỗi Studio.
