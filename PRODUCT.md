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
- Người vận hành nhập audio/video, đặt tên và ngày, chọn gợi ý ngôn ngữ rồi tạo cuộc họp bằng một nút; chép lời tự bắt đầu trừ khi tắt. Sau đó họ theo dõi tác vụ rồi duyệt transcript trong cùng workspace.
- Lịch tháng, danh sách gần đây và màn hình chi tiết cuộc họp là các đường truy cập chính tới dữ liệu đã lưu.
- Khi đối chiếu transcript với audio, trình phát dính ở mép trên màn hình chi tiết cuộc họp và đoạn đang phát tự cuộn vào tầm nhìn; người vận hành không phải cuộn tìm trình phát hay đoạn đang nghe.
- Transcript mở ở chế độ đọc để nghe và đọc nhanh: mỗi đoạn chỉ hiện mốc thời gian, người nói, nội dung và dấu cần kiểm tra. Nút **Sửa** mở ô sửa cho đúng một đoạn tại một lúc; bản nháp chưa lưu của đoạn vừa rời đi được giữ và đánh dấu. Gán người nói ban đầu và chỉ số model nằm trong phần **Chi tiết** của đoạn đang sửa.
- Người nói hiện thành chip; chip còn tên mặc định do hệ thống đặt (Speaker N) có dấu **đặt tên** và đổi tên ngay tại chỗ.
- Trạng thái worker, model, tác vụ, lỗi và dữ liệu cần nghe lại phải quét nhanh được trong phiên làm việc dài.
- Meeting notes mở ở chế độ **Xem** theo mặc định để đọc toàn bề rộng và trình duyệt nhớ lựa chọn cuối cùng; **Viết** dùng để sửa Markdown. Bản nháp chưa lưu luôn được báo rõ và trình duyệt cảnh báo trước khi đóng hoặc tải lại trang.

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
- Mỗi đoạn transcript ở chế độ đọc có tối đa hai điểm dừng Tab (mốc thời gian và **Sửa**). Esc hủy và Ctrl/⌘+Enter lưu trong ô sửa; sau khi lưu hoặc hủy, focus quay lại **Sửa** của đoạn đó. Thông báo lưu của mọi đoạn đi qua một vùng `aria-live` chung. Khi nguồn bị khóa, **Sửa** và chip bị tắt kèm lý do.
- Light/dark theme, contrast và reduced motion phải theo semantic state và sở thích hệ điều hành/người dùng.
- Tự cuộn theo đoạn đang phát chỉ chạy khi còn thấy một phần danh sách đoạn bên dưới thanh trình phát, nên người đang đọc notes không bị kéo về transcript; nó cũng dừng khi audio tạm dừng, khi người dùng vừa cuộn tay hoặc đang sửa, và dùng cuộn tức thì khi người dùng chọn giảm chuyển động; thanh trình phát dính không che đoạn được cuộn tới, còn control nhận focus bàn phím được cuộn xuống dưới thanh (ô nhập văn bản có thể chỉ lộ dòng chứa con trỏ).
