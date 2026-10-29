# AI MANAGER v0.2.21 — Đối soát Studio trước khi chạy lại

Nền: v0.2.20 (bản Windows đang chạy, trước đó chưa có trên GitHub — đã đưa lên ở commit riêng).

## Lỗi đã xử lý: "Dự án chưa có kịch bản" (1 Đời Nguyễn Du)

Nguyên nhân thật:
1. Studio giữ kịch bản gõ tay chỉ trong trình duyệt (`vis-script-draft`), không lưu lên máy chủ Studio cho đến khi bấm Phân tích. Manager đọc máy chủ → rỗng.
2. "Chạy lại lỗi" đưa task về hàng đợi nhưng Queue đọc ảnh chụp trạng thái Agent cũ (task vẫn `failed` + lỗi cũ) nên fail lại ngay trong cùng mili-giây (LOAD OLD ERROR → RETRY).

## Thay đổi

- Mọi "Chạy lại lỗi" Studio: REFRESH (đọc Studio API + tab Studio) → RECONCILE (`analysis/studio_reconcile.json`) → VALIDATE → RESUME. Lỗi cũ không còn là nguồn sự thật.
  - Studio còn tác vụ → giữ nguyên checkpoint.
  - Tab Studio của lượt chạy còn mở → tiếp tục từ STUDIO_READY.
  - Tab đã đóng → mở lại đúng URL/nonce cũ (không tạo run mới).
  - Tab Studio chứng minh không có kịch bản/transcript → từ chối chạy lại với mã `SCRIPT_MISSING` và hướng dẫn, không lặp lỗi.
- Queue bỏ qua trạng thái Agent cũ hơn lượt chạy hiện tại; Manager làm mới trạng thái Agent ngay sau requeue.
- `SCRIPT_MISSING` không còn là lỗi cứng ở lần đọc đầu: STUDIO_ANALYZE đọc lại Studio mỗi vòng, chờ tối đa 10 phút (`SCRIPT_NOT_SYNCED` khi Studio có bản nháp chưa lưu), rồi mới báo `SCRIPT_MISSING`. Khi `script_content_exists=true`, `script_character_count>0` trên máy chủ Studio thì tiếp tục.
- Kịch bản trước khi gửi phân tích: SAVE `analysis/studio_script.txt` → VERIFY sha256 → CHECKPOINT (journal + ledger).
- Bước mới `STUDIO_TRANSCRIPT` (GET_TRANSCRIPT) trước Phân tích, theo trạng thái thật: đã phân tích / đã có transcript / đã có kịch bản → bỏ qua có lý do; không có gì → chờ người dùng lấy transcript trong Studio.
- Mỗi lần retry có watchdog mới (không bị hết giờ do thời điểm của lần chạy trước).
- Hết giờ STUDIO_READY nói rõ: thiếu ChatGPT/Extension hay thiếu tab Studio.
- Presence nhận `projectState` từ Studio (chỉ số ký tự, không nhận nội dung kịch bản).
- Thao tác thủ công trong Studio (Phân tích cấu trúc, Phân cảnh một phần, Phân cảnh toàn bộ) được Manager theo dõi chỉ đọc (`external_jobs`), không gửi lệnh chen vào; xong thì tiếp tục từ trạng thái thật.
- Tiếp tục / Chạy (dự án paused, stopped, failed) cũng REFRESH → RECONCILE → VALIDATE như Chạy lại lỗi. Tiếp tục không tăng retry epoch (không gửi lại phần lỗi); thời gian tạm dừng không làm hết giờ watchdog.

- Task Studio ở `needs_review` (ví dụ mất kết nối Studio/ChatGPT khi Studio còn job) được Tiếp tục/Chạy lại sau đối soát nếu nhật ký chứng minh mọi lệnh đã được Studio xác nhận (không có lệnh `intent` chưa rõ kết quả). Tab Studio đã đóng thì mở lại đúng URL/nonce cũ trước, không gửi lệnh nào.

## Cần bản Studio preview mới

`VIDEO_IMAGE_STUDIO` nhánh `phase3-manager-presence` commit f2d1d41 (chưa merge main):
báo trạng thái kịch bản/transcript; tab do Manager mở tự lưu kịch bản gõ trong đúng dự án; bản nháp dùng chung chưa rõ dự án → hiện nút "Lưu kịch bản này cho AI MANAGER", không tự lưu.

## Giới hạn

- Manager chưa tự lấy transcript YouTube (Studio chưa có kênh lệnh từ Manager); bước Transcript chờ người dùng thao tác trong Studio.
- Task cũ tạo từ v0.2.20 không có bước STUDIO_TRANSCRIPT; gắn lại workflow để có bước này.
