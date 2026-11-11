# WinControl — Bàn giao

**Phiên giữ quyền viết:** phiên Claude "WinControl tiếp quản từ Codex (fork)" (`local_8fdb951a`), người dùng xác nhận ngày 2026-11-11. Các phiên "WinControl tiếp quản từ Codex" và "Cấu trúc - quy trình wincontrol" chỉ đọc.
**Nhánh:** `wincontrol/takeover-20261111` (worktree `C:\Users\PC\Projects\AI_MANAGER_WINCONTROL`), đã push.
**Kết luận hiện tại:** `WINCONTROL_NOT_READY` — xem "Vì sao chưa READY".

## 1. WinControl

| Mức | Trạng thái |
|---|---|
| Đã sửa mã | `d823045` UI Codex · `4a06f42` gia cố vòng lặp · `257b84f` an toàn target_app · `0caa3a0` lối vào UI v0.2.25, Notepad riêng, `SAVE_AS`, kiểm tra UIA Value · `9d30f31` prompt một dòng · `d56a7bf` làm phẳng prompt trong `chatgpt_mcp.send` |
| Test tự động | 38 test Python WinControl + 2 test Node UI đạt |
| Đã triển khai trên PC | Có. Script `integration_reports\takeover_20261111\deploy_wincontrol.ps1` (sao lưu, chặn khi có việc chạy, so checkpoint trước/sau, tự rollback). Lần cuối 2026-11-11 01:42:54Z: MAN pid 13660, Agent pid 26780, checkpoint không đổi. Sau đó chép nóng `wincontrol.js`, `wincontrol_chat_loop.py`, `chatgpt_mcp.py`. |
| Kiểm thử thực tế | Một phần (xem dưới) |

Đã chứng minh thực tế trên PC:
- Giao diện: nút **WinControl** ở thanh trên MAN v0.2.25 → trang Trò chuyện/Công việc; gõ lệnh tiếng Việt, chữ giữ nguyên qua các lần làm mới 2 giây, nút Gửi tạo task thật (`69156ea8`).
- Windows UIA: `OPEN_APP notepad` (cửa sổ mới, gắn theo pid) → `TYPE_TEXT` tiếng Việt → `SAVE_AS` vào `%TEMP%\WinControl` → `VERIFY_FILE` đạt.
- Chrome DevTools MCP: đọc hội thoại ChatGPT (snapshot ~7 giây/lần).
- An toàn: lần gửi đầu bị bridge từ chối (`COMPOSER_VALUE_UNVERIFIED_NO_SEND`) và **không gửi gì** — đúng thiết kế; task dừng `needs_review`.

Chưa chứng minh thực tế: ChatGPT trả JSON → Agent thực thi → kết quả về ChatGPT → bước tiếp theo. Nguyên nhân lần thử thất bại (prompt nhiều dòng) đã sửa nhưng **chưa chạy lại** vì Agent đang bận sản xuất (WinControl cố ý từ chối khi Agent có task chạy).

Lỗi đã tìm và sửa trong đợt này:
- Lối vào WinControl bị ẩn: `manager_ui.js` ẩn header cũ.
- `OPEN_APP notepad` dùng lại Notepad người dùng đang mở (có thể gõ vào file của họ).
- `TYPE_TEXT` báo sai vì đọc UIA Name ("Text Editor") thay vì Value.
- Hành động thiếu `target_app` rơi về `chrome` (tab ChatGPT); nay bắt buộc ghi rõ, cấm gõ/bấm trong Chrome/Edge.
- Prompt nhiều dòng không bao giờ qua được bước xác minh của bridge.

## 2. MAN (AI Manager)

- Đang chạy: `C:\Users\PC\Projects\AI_MANAGER`, cổng 8765, phiên bản trạng thái 0.2.23 (giao diện v0.2.25). Agent online.
- Thư mục chạy vẫn là `main` + thay đổi chưa commit (nay bằng nội dung nhánh này cho 13 tệp đã triển khai). Sao lưu: `integration_reports\takeover_20261111\` (`main_uncommitted.patch`, `predeploy_*`).
- **Sự cố cần điều tra:** 01:30:47Z có tiến trình *không phải* MAN đang chạy đã mở DB hàng đợi thật và chạy khởi tạo `QueueManager` ("Khôi phục sau khi đóng: tạm dừng"), làm dự án Thái Sư đang chạy chuyển sang tạm dừng. Nghi do chạy bộ test không đặt `AI_MANAGER_HOME` (quy tắc 6 của `AGENTS.md`). Chưa xác định chắc chắn.
- Phiên "WinControl tiếp quản từ Codex" xác nhận đã chạy `unittest discover` toàn bộ (không đặt `AI_MANAGER_HOME`) khoảng 01:29–01:31Z — khớp thời điểm trên; test cụ thể chưa xác định. Từ nay chỉ chạy full suite với `AI_MANAGER_HOME` tạm.
- **Khởi động lại MAN làm mất ghép nối Studio:** mã kết nối Studio chỉ nằm trong bộ nhớ MAN. Sau lần triển khai 01:37Z, Studio về `unconfigured` và Extension `extension_lost` cho tới khi được ghép nối lại (lúc 01:50Z đã kết nối lại). Mỗi lần triển khai cần ghép nối lại Studio; nên lưu bền mã này hoặc tránh khởi động lại khi đang sản xuất.
- Lỗi `cannot import name 'StudioReviewRequired'` của task `f3454b7a` là từ 2026-11-01, không do đợt triển khai này.
- 01:26:40Z và 01:43:34Z có lệnh "Tiếp tục" dự án Thái Sư từ một trình duyệt khác (không phải tab của phiên này — đã đối chiếu nhật ký mạng).

## 3. Studio (VIDEO IMAGE STUDIO)

- Kết nối: Studio "connected", tab Studio mở, ChatGPT kết nối; origin nhánh `phase3-manager-presence` (không sửa).
- Lỗi 402 (vượt hạn mức egress Supabase) trong báo cáo Codex 10/11: hiện **không tái hiện** — MAN đọc được dữ liệu phiên.
- Sản xuất Thái Sư: 24/24 phần, 384 cảnh có prompt, 6/384 ảnh xong. Mục `image:part_cecarmg:6` (Cảnh 7) gửi lúc 01:27:49Z, chưa có kết quả; Đã quan sát MAN tự khôi phục, không can thiệp tay: 01:57:59Z thu hồi job treo ("Quá thời gian chờ"), 01:58:04Z gửi lại (lần 2), 01:58:49Z Cảnh 7 hoàn tất, Cảnh 8 bắt đầu.

## 4. Extension

- v0.5.19 = bản mới nhất trong thư mục cập nhật; đang phản hồi (heartbeat vài giây). Không cần cập nhật.

## 5. Xưởng Nội Dung (repo riêng `theodoichatpage/XUONG_NOI_DUNG`)

- `main` sạch, khớp `origin/main` (`8a8be58`). Web tĩnh trên Vercel `xuong-noi-dung-khaki.vercel.app`; mọi tệp `dist/` trên web trùng `main`. Extension v0.4.14.
- `node --test tests/*.test.cjs`: 252 đạt, 1 bỏ qua, 0 lỗi. Trang mở không lỗi console.
- Chưa kiểm tra kết nối Extension/Adapter/Sudowrite trong Chrome của người dùng (dữ liệu nằm trong localStorage trình duyệt đó). Không sửa gì.

## Vì sao chưa READY

1. Vòng ChatGPT → hành động → ChatGPT chưa chạy hết một lần thật sau bản sửa prompt.
2. Agent chỉ chạy một task một lúc; khi sản xuất Studio chạy (hàng giờ), WinControl không nhận lệnh. Cần người dùng chọn thời điểm tạm dừng sản xuất để chạy thử, hoặc chờ sản xuất xong.
3. Tự khôi phục MAN/Studio/Extension mới ở mức đọc tình trạng (`MAN_STATUS`); chưa có hành động sửa tự động.

## Bước tiếp theo

1. Khi Agent rảnh: gửi lại lệnh thử từ giao diện WinControl, theo dõi đủ vòng tới `complete`.
2. Triển khai lại (script trên) để MAN nạp `wincontrol_chat_loop.py` mới cho prompt đầu (đã có lớp làm phẳng trong `chatgpt_mcp.send` nên không bắt buộc).
3. Tìm tiến trình đã khởi tạo DB hàng đợi thật lúc 01:30:47Z.
