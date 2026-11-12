# WinControl — Bàn giao

**Phiên giữ quyền viết và triển khai:** phiên Claude "Cấu trúc - quy trình wincontrol" (người dùng giao lúc ~22:00 ngày 2026-11-11). Chủ triển khai MAN ghi trong `%LOCALAPPDATA%\AI_MANAGER\DEPLOY_OWNER.json` = `cau-truc-quy-trinh-wincontrol`; chỉ triển khai qua `tools\deploy_man.ps1`. Các phiên khác chỉ đọc. Codex: chỉ làm trên worktree riêng, mở PR, không triển khai vào MAN.
**Nhánh:** `wincontrol/takeover-20261111` (worktree `C:\Users\PC\Projects\AI_MANAGER_WINCONTROL`), đã push.
**Kết luận:** `WINCONTROL_READY` cho **vòng điều hành cơ bản** (2026-11-11 13:19 giờ máy). Chưa có nghĩa các khả năng mở rộng (Chặng 2–4) đã xong.

## 0. Đợt 2026-11-11 tối (phiên "Cấu trúc - quy trình wincontrol")

| Việc | Đã sửa mã | Đã triển khai | Kiểm thử thực tế |
|---|---|---|---|
| (1) Mã đang chạy được commit | `b6fae8b` + merge `ecb9578` trên `main` của `C:\Users\PC\Projects\AI_MANAGER`; sao lưu `origin/pc-main/20261111` (không đè `origin/main`, vốn có 3 commit máy chưa có) | — | `main` = nhánh, không còn mã chạy chưa commit |
| (2) Một chủ triển khai MAN | `360b100`, `76735ec`: `tools/deploy_man.ps1` (kiểm `DEPLOY_OWNER.json`, chặn khi có task running/waiting, ff-merge, so checkpoint, tự hoàn lại); `AGENTS.md` quy tắc 7; bộ nhớ dự án | Tệp khóa đã tạo; phiên "AI MANAGER v0.2.20 takeover" xác nhận không khởi động lại MAN | Gọi sai chủ → bị từ chối |
| (6) Nhận ra hết lượt ảnh ChatGPT | Studio `b5acdab` (nhánh `phase3-manager-presence`): Extension 0.5.20 đọc thông báo giới hạn sau lượt user cuối, báo lỗi một lần kèm lời ChatGPT, không tải lại tab. MAN `3ca2f78`: tab nghỉ đúng thời gian ChatGPT nói (15 phút–6 giờ) | Extension 0.5.20 đã tự cập nhật (2/3 tab đang chạy 0.5.20). Phần MAN **chưa** (cần khởi động lại) | Chưa gặp lại thông báo giới hạn thật |
| (7) Điều khiển sản xuất | `7e5c9b5`: hành động `MAN_QUEUE` (chỉ pause/resume qua `/api/queue`; resume chỉ dự án người dùng nêu tên; trùng tên → từ chối; lặp lại không gửi lần hai; xác nhận từ trạng thái MAN). `MAN_STATUS` có id + tiến độ | **Chưa** (cần khởi động lại) | Chưa |
| (3) Chạy song song với sản xuất | — | — | Chưa: cần triển khai (7) rồi tiếp tục Thái Sư |

Test: 320 test Python (cô lập) — chỉ 3 lỗi có sẵn (`test_startup_port`, 2 `test_work_orchestration`); 4 test UI Node đạt; Extension: test_watchdog/test_ping đạt, 2 test lỗi có sẵn (`test_image_instead`, `test_manager_heartbeat`); test Studio liên quan Extension: 53 đạt / 2 lỗi có sẵn (giống hệt trước khi sửa).

Triển khai bị dừng: lần chạy đầu `deploy_man.ps1` từ chối vì task `b359d508` (stopped từ đầu tháng 11, còn cờ `in_flight` cũ — một trong 3 cờ Codex dặn không xóa). Đã sửa script để chỉ chặn task running/waiting; lần chạy lại bị bộ kiểm tra an toàn chặn, chờ người dùng duyệt khởi động lại MAN.

### Cập nhật sau khi người dùng cho phép (~22:30–22:50)

- Triển khai `deploy_man.ps1` (sửa thêm 2 lỗi của script: hàm `Git` tự gọi chính nó; cảnh báo stderr của git bị coi là lỗi): 15:35:25Z `ecb9578→400bb4c`, rồi 15:40:58Z `→993c8d5`. Checkpoint không đổi cả hai lần; Studio tự ghép nối lại sau ~3 giây; Extension `responding` 0.5.20. Biên nhận: `AI_MANAGER\integration_reports\deploys\`.
- **Kiểm thử thực tế (7) từ giao diện WinControl:**
  - Lần 1 (`673f157e`): ChatGPT → MAN_STATUS → MAN_QUEUE resume → MAN từ chối 400 "Nguồn truy cập không hợp lệ" (Agent thiếu header `Origin`). Không có gì thay đổi; task dừng `needs_review` đúng thiết kế. Sửa `993c8d5` (gửi Origin của MAN, báo lý do MAN từ chối; MAN giả trong test kiểm Origin).
  - Lần 2 (`a5884c05`): ChatGPT nhớ lỗi cũ, kiểm tra lại rồi tự `blocked` — không thử lại khi chưa rõ nguyên nhân.
  - Lần 3 (`ea327664`, lệnh nêu rõ lỗi đã sửa): MAN_STATUS → **MAN_QUEUE resume: `paused → running`** → MAN_STATUS xác nhận → `complete`. Dự án Thái Sư chạy lại; 10 ảnh mới trong 30 phút sau đó.
- **Kiểm thử thực tế (3):** task `046c161a` (lệnh chỉ đọc) chạy trọn vòng trong lúc Agent đang chạy sản xuất `f433e842`; sản xuất không bị gián đoạn.
- Phát hiện khi chạy thật và đã sửa mã (`dcb7f0b`, **chưa triển khai** — sản xuất đang chạy nên script từ chối khởi động lại, đúng thiết kế): kết quả MAN_STATUS bị cắt 1500 ký tự nên ChatGPT không thấy Studio/Extension; nay phần tình trạng đứng trước danh sách dự án. Triển khai ở lần sản xuất tạm dừng tiếp theo.
- (6) phía MAN đã triển khai; chưa gặp lại thông báo hết lượt ảnh thật để quan sát tab nghỉ.
- Còn sót: task WinControl `673f157e`, `a5884c05` ở `needs_review` (vô hại, từ lần thử 1–2).

### Đêm 11→12/11 và triển khai sáng 12/11

- Sản xuất Thái Sư chạy từ 22:45 đến 02:17 (688 tệp ảnh mới; nhật ký luồng: 180 ảnh hoàn tất trong lượt này).
- **(6) đã chứng minh thực tế:** 02:27 Extension 0.5.20 báo "ChatGPT báo hết lượt tạo ảnh (giới hạn tài khoản): You've hit the Plus plan limit…"; MAN cho 3 tab nghỉ tới 08:24–08:29, không gửi lại; cảnh bị lỗi không tính là đã thử.
- **Lỗi mới tìm thấy:** khi mọi tab đều nghỉ, ~37 phút không tiến độ → bộ canh giữ tiến độ báo "Studio quá thời gian tại lanes:24:180" và đánh dấu task `failed` (02:54). Ngoài ra, ngay sau khi hết nghỉ, bộ canh giữ vẫn tính từ trước lúc nghỉ. Sửa `6e35ea7`: khi mọi tab đang nghỉ và không có việc đang gửi, MAN chờ tới hết nghỉ (`lanes:rest:*`, thông báo giờ chạy tiếp); hết nghỉ thì đồng hồ tiến độ tính lại. Test tái hiện đúng lỗi thật.
- Gộp nhánh Aprilynne `aprilynne/review-depth-20261111` (`2bf54db`, `0141b39`: đọc trọn thân bài, sửa mọi phần yếu, tối đa 6 vòng khi điểm còn tăng) — `0712df6`.
- Test: 328 Python (cô lập), chỉ 3 lỗi có sẵn; 4 test UI đạt.
- Triển khai 01:08:35Z `993c8d5→6e35ea7` (gồm `dcb7f0b`, Aprilynne, `6e35ea7`): checkpoint không đổi; Studio `connected`, Extension 0.5.20 `responding` sau ~3 giây. MAN pid 33360, Agent pid 8792.
- Dự án Thái Sư đang `failed` (task `f433e842`, bước 5, checkpoint giữ nguyên). `MAN_QUEUE` chỉ cho tiếp tục dự án `paused`, nên chạy lại dự án `failed` cần người dùng quyết.
- 08:12 người dùng duyệt chạy lại: `/api/queue` `retry` (đối soát, giữ checkpoint) rồi `start_selected`. **`6e35ea7` chứng minh thực tế:** MAN hiện "Tất cả tab ChatGPT đang nghỉ vì hết lượt tạo ảnh; Manager chạy tiếp lúc 08:24" và chờ, không báo lỗi; sau 08:24 các tab nhận việc lại.
- Tài khoản ChatGPT (cả 3 tab dùng chung h***6@gmail.com) **vẫn bị giới hạn**: 08:31 và 08:34 hai tab gặp lại thông báo và nghỉ tới 14:31/14:34; task vẫn `running`, không lỗi. Ảnh chạy tiếp khi tài khoản hết giới hạn (hoặc thêm tài khoản ChatGPT khác cho một hồ sơ Edge).
- `50848c9` (chưa triển khai): xóa thông báo "đang nghỉ" cũ khi các tab đã làm việc lại (thấy lúc 08:32).
- **Studio Aprilynne** (bàn giao từ phiên Aprilynne, người dùng duyệt trực tiếp): đẩy `442cac9` lên `phase3-manager-presence` (fast-forward từ `41a6e7e`, chỉ `AnalysisTab.tsx`); Vercel `success`. Bản triển khai được Vercel bảo vệ đăng nhập nên chưa đọc được bundle; tab Phân tích trong Edge cần F5 để nạp bản mới (chưa kiểm tra trên tab — không mở dự án ở trình duyệt thứ hai để tránh tranh quyền điều phối).
- **Kiểm tra bằng WinControl** (task `2d9ebeee`, chỉ đọc, chạy song song sản xuất): MAN 0.2.23, Agent bật, Studio kết nối + tab mở, Extension 0.5.20 = mới nhất, Thái Sư `running`. Bản `MAN_STATUS` mới cho ChatGPT thấy đủ Studio/Extension.

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

### Sáng 12/11 (tiếp): tài khoản ChatGPT thứ hai, Aprilynne một tuyến, ngưỡng mất kết nối

- Ảnh người dùng gửi cho thấy kiểu thông báo thứ hai: "You're out of images… Try again at 10:46 PM". Extension **0.5.21** (Studio `0d8255a`) nhận kiểu này; MAN `6127fc3` đọc giờ "Try again at" (tin tới 24 giờ) và **cho nghỉ theo tài khoản** (mọi tab cùng tài khoản nghỉ cùng nhau; tab đã đổi sang tài khoản khác làm việc ngay). Lần nghỉ cũ ghi trước bản này không có tài khoản: đã tạm dừng qua WinControl, sao lưu `manager_639058….json.before_clear_rest_20261112T085054`, xóa 2 dòng nghỉ của `edge_Profile_1`/`edge_Default` (đã đổi sang tài khoản s***e), rồi chạy tiếp qua WinControl.
- **Tài khoản thứ hai chứng minh thực tế:** `edge_Default` (s***e) tạo xong cảnh 23 lúc 09:23 (ảnh 181), 182 lúc ~09:40.
- **WinControl tạm dừng/tiếp tục thật** nhiều lần (pause `54ab13cb`, `6ca42b52`; resume `df6bc08f`, `d70b5769`, …): mỗi lần ChatGPT đọc MAN_STATUS → MAN_QUEUE → đọc lại để xác nhận.
- **Aprilynne một tuyến** (phiên Aprilynne làm; người dùng duyệt trực tiếp ở phiên này): MAN `567d981`+`2b6d520` (duyệt khi ≥8/12; presence gửi `storyReview`; bỏ `aprilynne_gate`) triển khai 02:33:17Z; Studio `b48c5a0` fast-forward lên `phase3-manager-presence`, Vercel success. (Trước đó `4c30aa6` đã có trên origin.)
- **Lỗi mới, đã sửa:** lúc 09:27 và 09:42 dự án tự `needs_review` "Mất Studio/ChatGPT quá thời gian" — tab Studio tự tải lại theo bản Vercel mới và Extension tự lên 0.5.21 làm ChatGPT rời >120 giây. `b74b818`: chờ 10 phút (không gửi gì khi mất kết nối). Triển khai 06:03:48Z, rồi chạy tiếp qua WinControl.
- Đề xuất từ phiên Aprilynne: phát hành theo đợt bằng `tools/release.ps1` (nhánh `aprilynne/release-script-20261112`, **chưa xem/chưa đưa vào**; cần thêm bước tạm dừng/tiếp tục sản xuất).
- Đã đề xuất, chờ người dùng đồng ý: **Telegram** (nhận lệnh từ đúng tài khoản người dùng, chuyển vào WinControl, báo tình trạng; token do người dùng tự dán).
- 13:05–13:30: sau `b74b818` dự án chạy ổn định 25 phút, ảnh 182 → 191, không tạm dừng. Task WinControl `5afab052` cho chạy tiếp thành công nhưng dừng `needs_review` ở bước gửi kết quả cho ChatGPT: "element did not become interactive" (ô soạn tin tạm khóa; chưa gửi gì). Sửa `chatgpt_mcp.send`: thử lại tối đa 3 lần cho đúng lỗi này, kiểm tra trùng trước mỗi lần — **đã commit, chưa triển khai** (chờ lần sản xuất tạm dừng tới).
- **Telegram** (`telegram_bridge.py`, commit sau `decf95b`): dùng lại thiết kế gateway cũ của Codex (`Documents\AI_MAN_TELEGRAM_TEST`, đang dừng từ 8/11 — **không chạy song song gateway cũ với cùng bot**, Telegram chỉ cho một nơi nhận tin). Token dán ở tab Công việc của WinControl, lưu DPAPI `~\.ai_manager\telegram_token.bin`; ghép nối bằng `/pair <mã 6 số>` trong 15 phút; chỉ nhận lệnh từ đúng người dùng trong chat riêng; mỗi tin xử lý một lần (`request_id` `tg-<update_id>`). Báo cáo: WinControl xong/dừng, dự án đổi trạng thái, thông báo Studio (hết lượt…), mất/kết nối lại. 7 test; **chưa triển khai**.

### Chiều 12/11: triển khai Telegram và sự cố hệ thống

- WinControl tạm dừng 2 lần thất bại (14:08, 14:13): gửi cho ChatGPT quá 18 giây → `needs_review` (an toàn). Sửa `b561a1f`: điền/gửi được 45 giây. Đã tạm dừng trực tiếp qua `/api/queue` (giống nút Tạm dừng) để triển khai.
- Triển khai 07:14:08Z `b74b818→b561a1f` (Telegram `b90680b`, thử gửi lại khi ô soạn tin tạm khóa `aaa6c60`, 45 giây).
- **Sự cố ~14:16–14:19**: Windows ghi `LiveKernelEvent` (tầng hệ điều hành); MAN, Edge và Chrome "bộ não" của WinControl đều tắt; không có lỗi Python trong `logs/manager.log`. Đã khởi động lại MAN (14:20) và Chrome WinControl (`--remote-debugging-port=63635`, đúng hồ sơ trong `settings.json`). Nguyên nhân gốc chưa xác định chắc.
- Sửa `49d883c` (triển khai 07:38:05Z): WinControl tự mở lại **Chrome của chính nó** (hồ sơ + cổng đã cấu hình) khi không kết nối được; bản nháp chưa gửi bắt đầu bằng `[wincontrol-` được thay, chữ người dùng gõ vẫn bị chặn. Test `tests/test_bridge_draft.cjs`.
- 14:41–14:59: WinControl `c35ef8fa` cho chạy tiếp **thành công**; MAN tự mở lại tab Studio trong Edge; ảnh 199 → 202.
- **Telegram đã triển khai, chưa cấu hình:** người dùng dán token XuongAIbot ở tab Công việc → nhắn `/pair <mã>` cho bot.
