---
status: accepted
---

# Lưu trích dẫn mốc thời gian tách khỏi Markdown

Người đọc cần đối chiếu từng mục notes với audio, nhưng liên kết timestamp chèn thẳng vào Markdown làm bản lưu, bản sao chép và file tải về khó đọc nên đã bị bỏ khỏi Markdown. Chọn lưu trích dẫn thành dữ liệu riêng của từng bản notes (cột `notes_revisions.citations_json`, schema v10): mỗi mục ghi tiêu đề phần, văn bản mục đúng như đã render và các đoạn nguồn (`id`, `start_seconds`). Cùng một đoạn mã dựng dòng Markdown và trích dẫn để hai bên không lệch nhau. UI chỉ vẽ trích dẫn thành chip ở chế độ Xem; Markdown, chế độ Viết, sao chép và tải về vẫn sạch.

Vì Markdown được sửa tự do (xem [ADR 0005](0005-markdown-notes.md)), chip chỉ gắn vào mục còn đúng tiêu đề phần và nội dung như lúc tạo; mục đã sửa mất chip thay vì bị gắn nhầm nguồn. Đánh đổi là một mục vừa sửa lại giống hệt nội dung cũ sẽ lấy lại chip, và mục sửa nhẹ cũng mất chip dù ý không đổi; đây là chọn lọc có chủ ý, vì chip sai nguy hiểm hơn chip thiếu. Các mục trùng tiêu đề phần và nội dung không phân biệt được trong Markdown, nên cả nhóm mất chip khi số mục của nhóm khác lúc tạo (một mục bị sửa hoặc xoá, hoặc có thêm bản sao, kể cả khi sửa mục khác thành bản sao), kể cả mục chưa đụng tới. Bản notes tạo trước schema v10 có cột NULL và không hiện chip; migration chỉ thêm cột nên không viết lại dữ liệu cũ.

Bấm chip mở bản chụp nguồn bất biến theo [ADR 0008](0008-notes-source-snapshots.md) trong tab Transcript, không dùng transcript đang sửa.
