# AI MANAGER v0.2.22 — Dự án mới và chạy nhiều tab ChatGPT

Nền: v0.2.21. Cần Studio nhánh `phase3-manager-presence` (commit 2240fcd) và Extension 0.5.0.

## Dự án mới → Triển khai (Studio Automation)
- Dán **link YouTube** hoặc **kịch bản**, bấm **Triển khai**. Manager tạo dự án trong Manager và trên máy chủ Studio, mở Studio, chạy đến hết.
- Có link YouTube: Studio (tab Get Transcript) tự lấy transcript → chia phần → **viết lại theo phong cách** (ô phong cách trong Manager, hoặc phong cách đã lưu trong Studio) → đưa kịch bản sang Phân tích. Manager theo dõi tiến độ (ví dụ "Đang viết lại 3/8"); lỗi được báo rõ, Chạy lại lỗi gửi yêu cầu mới.
- Không có link: kịch bản trong Manager được lưu lên Studio rồi phân tích.
- Tuỳ chọn tạo ảnh sau phân cảnh (cần phong cách ảnh đã lưu trong Studio).

## Nhiều tab ChatGPT (1 hoặc nhiều tài khoản Plus)
- Mỗi tab là một **hồ sơ trình duyệt** riêng (Edge Default, Edge Profile 1, Chrome…) có ChatGPT đăng nhập và Extension 0.5.0. Tối đa 4 tab.
- Manager tự mở ChatGPT + Studio ở các hồ sơ phụ; Extension ở đó tự kết nối với dự án.
- Phân bổ: tab rảnh nhận phần phân cảnh tiếp theo (thực tế xen kẽ 1-3-5 / 2-4-6). Từ 3 tab: 1 tab tạo ảnh ngay khi có phần đã phân cảnh. Xong phân cảnh: mọi tab tạo ảnh.
- Tab mất kết nối > 3 phút hoặc 1 việc quá 30 phút: Manager lấy lại việc và giao tab khác (không bao giờ 2 tab làm cùng 1 việc).
- ChatGPT báo hết lượt ảnh: tab đó nghỉ tạo ảnh 15 phút, Manager báo "Cần bạn xử lý".
- Cảnh báo: nhiều tab dùng chung 1 tài khoản (chung hạn mức ảnh), tài khoản không phải Plus, 2 tab ChatGPT/Studio trong cùng 1 hồ sơ (chỉ 1 tab được dùng), Extension cũ.
- 1 tab: giữ nguyên quy trình tuần tự đã kiểm chứng.

## Cần làm một lần
- Cập nhật hàm máy chủ Studio (Supabase `studio-api`) để có giao việc theo tab. Chưa cập nhật thì Dự án mới vẫn chạy với 1 tab; chế độ nhiều tab sẽ báo lỗi khi giao việc.

## Chưa kiểm chứng thực tế
- Toàn bộ phần trên mới qua kiểm tra tự động; chưa chạy thật trên Windows với nhiều hồ sơ trình duyệt.
