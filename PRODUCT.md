# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Người vận hành làm việc một mình trên máy tự quản. Họ nhập bản ghi cuộc họp, theo dõi xử lý local, nghe lại nguồn và duyệt kết quả có thể đối chiếu.

## Product Purpose

ASR EN VI biến bản ghi cuộc họp tiếng Anh hoặc tiếng Việt thành transcript có timestamp và người nói để người vận hành rà soát. Thành công là kết quả vẫn rõ nguồn, bền qua restart và dùng được khi phần xử lý local không có Internet.

## Positioning

Ứng dụng kết hợp một workspace cuộc họp local-first với ASR, phân biệt người nói, lịch sử thế hệ và chỉnh sửa an toàn; mỗi kết quả vận hành vẫn truy ngược được về bản ghi thay vì chỉ xuất một khối văn bản dùng một lần.

## Operating Context

- Ứng dụng chạy bằng Docker Compose trên localhost và được mở bằng link token từ terminal.
- Người vận hành nhập audio/video, đặt tên và ngày, chọn gợi ý ngôn ngữ, theo dõi tác vụ rồi duyệt transcript trong cùng workspace.
- Lịch tháng, danh sách gần đây và màn hình chi tiết cuộc họp là các đường truy cập chính tới dữ liệu đã lưu.
- Trạng thái worker, model, tác vụ, lỗi và dữ liệu cần nghe lại phải quét nhanh được trong phiên làm việc dài.
- Meeting notes mở ở chế độ **Xem** để đọc toàn bề rộng; **Viết** dùng để sửa Markdown. Bản nháp chưa lưu luôn được báo rõ và trình duyệt cảnh báo trước khi đóng hoặc tải lại trang.

## Capabilities and Constraints

- Giữ nguyên domain language, route, API, focus management, task semantics và dữ liệu hiện có.
- Audio, ASR, diarization, lưu trữ và frontend assets chạy local; UI không tải font, script, CSS, telemetry hoặc visual asset từ bên thứ ba.
- Transcript giữ ngôn ngữ đã nói; nhãn điều khiển dùng tiếng Việt và một số thuật ngữ đã chốt như Transcript, Meeting notes, Speaker và English.
- V1 là single-operator, không có tài khoản nhiều người dùng và không mở truy cập LAN/Internet.
- Thiết kế phải hoạt động trên desktop và mobile mà không che control, mất trạng thái hoặc tạo horizontal overflow.

## Brand Commitments

- Tên sản phẩm giữ nguyên là **ASR EN VI**; biểu tượng sóng âm nét đơn tiếp tục là dấu nhận diện của ứng dụng.
- `https://bibo.id.vn/` là visual authority cho ngôn ngữ nhận diện dùng chung. ASR vẫn là công cụ vận hành, không sao chép bố cục portfolio hoặc biến thành landing page.
- Giọng giao diện ngắn gọn, chính xác, bình tĩnh và thiên về kỹ thuật; không đổi product copy hoặc tạo claim mới ngoài phạm vi đã xác nhận.

## Evidence on Hand

- Product terminology: `CONTEXT.md`.
- Product and workflow constraints: `docs/specification-v1.md`, `docs/backend-design-v1.md` and `docs/backend-contract-v1.md`.
- Existing implemented surfaces and states: `src/asr_en_vi/web/`.
- Existing real-browser behavior coverage: `tests/test_browser_access.py`, `tests/test_browser_workspace.py` and `tests/test_browser_history.py`.
- The repository contains no customer claims, testimonials or marketing proof; future UI must not fabricate them.

## Product Principles

1. Nguồn và trạng thái phải rõ trước khi giao diện tạo cảm giác trau chuốt.
2. Xử lý local và quyền riêng tư là hành vi có thể kiểm chứng, không phải khẩu hiệu trang trí.
3. Mọi chỉnh sửa giữ được lịch sử và ngữ cảnh để người vận hành đối chiếu.
4. Một hệ thống nhận diện chung không được làm giảm mật độ thông tin hoặc tốc độ thao tác.

## Accessibility & Inclusion

- Hỗ trợ đầy đủ tiếng Việt và tiếng Anh bằng font đóng gói local.
- Tất cả control phải dùng được bằng bàn phím, có focus indicator rõ và không truyền trạng thái chỉ bằng màu.
- Light/dark theme, contrast và reduced motion phải theo semantic state và sở thích hệ điều hành/người dùng.
