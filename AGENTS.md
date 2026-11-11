# Quy tắc cho tác tử (Claude, Codex) làm việc trên repo này

1. Đọc `WINCONTROL_ARCHITECTURE.md` và `WINCONTROL_HANDOFF.md` trước khi sửa.
2. **Một người viết tại một thời điểm.** Ghi tên phiên đang giữ quyền viết ở đầu `WINCONTROL_HANDOFF.md`. Phiên khác chỉ đọc.
3. Làm trên worktree `C:\Users\PC\Projects\AI_MANAGER_WINCONTROL`, nhánh `wincontrol/takeover-20261111`. Không sửa trực tiếp `C:\Users\PC\Projects\AI_MANAGER` (đó là bản MAN đang chạy) trừ bước triển khai đã được duyệt.
4. Không reset, xóa, ghi đè hoặc `git stash pop`. Cất việc dở bằng commit WIP.
5. Không commit `__pycache__/*.pyc`, `integration_reports/`, `logs/`.
6. Chạy test với `AI_MANAGER_HOME` trỏ sang thư mục tạm. Interpreter: `C:\Users\PC\AppData\Local\AI_MANAGER\runtime-v02\Scripts\python.exe`.
7. Không khởi động lại MAN/Studio, không chạm queue production nếu người dùng chưa duyệt bước triển khai.
8. Báo cáo theo ba mức: đã sửa mã / đã triển khai trên PC / đã kiểm thử thực tế.
