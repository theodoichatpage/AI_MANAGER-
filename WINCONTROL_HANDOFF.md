# WinControl — Bàn giao

**Phiên giữ quyền viết:** phiên Claude được người dùng chọn ngày 2026-11-11 ("Phiên này"). Các phiên khác — "WinControl tiếp quản từ Codex" và bản fork của nó — chỉ đọc.
**Nhánh:** `wincontrol/takeover-20261111` (worktree `C:\Users\PC\Projects\AI_MANAGER_WINCONTROL`), đã push.

## Trạng thái (2026-11-11)

| Mức | Trạng thái |
|---|---|
| Đã sửa mã | `d823045` (WIP Codex: giao diện Trò chuyện/Công việc), `4a06f42` (WIP phiên fork: MAN_STATUS, chống trùng, đọc lại, vòng sửa JSON). |
| Test tự động | 36/36 test Python WinControl + 2/2 test Node UI đạt. Toàn bộ suite: 293 test, 3 lỗi ngoài WinControl (xem dưới), 2 bỏ qua. |
| Đã triển khai trên PC | **Chưa.** MAN đang chạy (PID 21776, cổng 8765, từ 2026-11-10 22:36) lấy mã từ `C:\Users\PC\Projects\AI_MANAGER` với bản sửa cũ hơn của Codex, chưa commit. |
| Đã kiểm thử thực tế | **Chưa.** |

## Nguồn gốc các bản sửa

- `main` (checkout `C:\Users\PC\Projects\AI_MANAGER`): còn các thay đổi chưa commit của Codex. Khác `d823045` ở 4 tệp (`wincontrol.js`, `automation.css`, `index.html`, `chatgpt_mcp.py`), và các bản này **cũ hơn**. Giữ nguyên, không commit.
- `codex/wincontrol-chatgpt-integration-20261110` (worktree Temp) = `d823045`, đã push để sao lưu.
- `integration_reports/` (8,3 GB, ngoài git): backup và bộ Maintenance Mode của Codex. Không thuộc phạm vi đợt này.

## Lỗi suite không thuộc WinControl (nguyên nhân có thể của các lệnh `Exited (status 1)`)

- `test_work_orchestration` (2 lỗi): SQLite tạm bị khóa lúc dọn dẹp trên Windows (WinError 32).
- `test_startup_port`: `server.py` không thoát trong 5 giây khi cổng 8765 bị MAN thật chiếm.

## Tiến trình khác cần lưu ý

- Vẫn còn tiến trình Codex đang chạy (một tiến trình mở với `-C ...\Temp\wincontrol-pr3-20261110`). Chúng có thể ghi vào worktree Temp.
- `control_readonly_service` gateway/watchdog (từ `integration_reports\...\maintenance_mode_v3`) và `serve_fixture.py` đang chạy.

## Bước tiếp theo

Xem quy trình 7 giai đoạn trong `WINCONTROL_ARCHITECTURE.md` §5–6. Kế tiếp là Giai đoạn 3: rà soát mã P0/P1 đối chiếu kiến trúc, kiểm thử cô lập (Giai đoạn 4), rồi trình kế hoạch triển khai lên PC để người dùng duyệt (Giai đoạn 5).
