# AI MANAGER v0.2.23 — Giảm lưu lượng Supabase

Nền: v0.2.22. Đi cùng Studio `phase3-manager-presence` commit fdf74a2 và Extension 0.5.1.

## Vấn đề
Supabase (gói miễn phí, 5 GB/tháng) vượt hạn mức (14,58 GB): mỗi tab Studio mở tải lại toàn bộ dự án mỗi 4 giây suốt ngày (~2,5 GB/ngày/tab); máy chủ đọc toàn bộ bản ghi mỗi lần; Extension và Manager cũng tải cả dự án.

## Thay đổi
- Máy chủ Studio lưu kèm "mốc phiên bản" nhỏ trong bản ghi. Kiểm tra định kỳ chỉ đọc mốc này (vài trăm byte); toàn bộ dự án chỉ tải khi thật sự thay đổi.
- Web Studio: 4 giây/lần chỉ khi đang có việc; rảnh 15 giây; tab ẩn 60 giây.
- Phản hồi bỏ JSON gốc của từng phần và prompt ảnh dài của từng cảnh (vẫn lưu trong cơ sở dữ liệu); nén gzip.
- Lấy lệnh ChatGPT khi không có việc: trả lời từ mốc phiên bản, không đọc dự án.
- Extension 0.5.1 và Manager (đọc Studio, giám sát Studio) dùng mốc phiên bản + bộ nhớ đệm; Manager nhận dữ liệu nén.
- Sửa: bộ chuyển tiếp Supabase làm rơi tham số tab (`worker`), nên chế độ nhiều tab trước đây không thể chạy; Manager đọc đúng lệnh trả về khi giao việc theo tab.

## Cần làm một lần
- Cập nhật hàm `studio-api` lên Supabase (cần đăng nhập Supabase). Chưa cập nhật thì web/Extension/Manager vẫn chạy như cũ (tự quay về cách tải cũ nhưng web đã giãn nhịp).
