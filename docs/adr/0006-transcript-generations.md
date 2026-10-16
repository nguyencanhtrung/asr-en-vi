---
status: accepted
---

# Giữ các thế hệ transcript khi chạy lại bản ghi

Chạy lại nhận dạng có thể thay đổi văn bản, segment, timestamp và nhãn người nói, trong khi transcript trước đã được sửa và các bản notes cũ vẫn cần đối chiếu nguồn. Chọn lưu kết quả chạy lại thành một thế hệ transcript mới, giữ nguồn cũ cùng các chỉnh sửa và liên kết của notes cũ, thay vì ghi đè kết quả hiện có. Đánh đổi là thêm dữ liệu văn bản và quản lý phiên bản, nhưng tránh mất công sức duyệt hoặc gắn bằng chứng của một bản notes sang kết quả nhận dạng khác; không trộn các segment hoặc speaker của hai lần xử lý.

Q21 chọn thế hệ mới nhất đã lưu đầy đủ làm mặc định để xem/sửa; các thế hệ trước chỉ đọc, còn notes cũ vẫn sửa/copy/xuất được. Thế hệ mới không kế thừa tên người nói vì nhãn của hai lần nhận dạng có thể khác nghĩa; người dùng đặt tên lại. Lần chạy chưa có transcript hoàn tất không thay thế hệ hiện tại. Q20 yêu cầu kiểm tra phiên bản khi ghi để tránh tab cũ ghi đè chỉnh sửa mới; chi tiết trong [backend design v1](../backend-design-v1.md).

Giữ thế hệ cũ giải quyết việc chạy lại âm thanh. Việc bảo toàn nguồn khi sửa ngay trong cùng thế hệ được quyết định riêng tại [ADR 0008](0008-notes-source-snapshots.md).
