# Kiến trúc runtime — hồ sơ thay đổi v0.1.0

Các mục lịch sử được chuyển từ tài liệu thay đổi chung khi chuẩn bị #17.
Số đo giữ revision và điều kiện gốc; không phải phép đo lại artifact 0.1.0.

### #17 / PR TBD — Nhật ký runtime và startup mặc định an toàn

#### Vấn đề

Log mặc định của worker và startup có thể chứa traceback, stderr nguyên dạng từ tiến trình con,
đường dẫn model/recording và mã task/meeting. Startup không tương tác còn gọi `access show`, nên
token localhost và QR có thể đi vào pipe hoặc log CI.

#### Nguyên nhân đo được

- Runner, diarization runner và worker từng in traceback trực tiếp ra stderr.
- Worker kế thừa stderr của tiến trình con; thư viện có thể làm đầy pipe hoặc ghi nội dung riêng tư
  trực tiếp vào log container.
- CLI và shell startup từng ghép path hoặc exception vào thông báo chuẩn bị model/runtime.

#### Thay đổi thiết kế

- Thêm `safe_logging.emit_safe_log`, chỉ cho phép bộ cố định `event`/`stage`/`code`; exception,
  path, task ID, meeting ID và child output không được nội suy vào log mặc định.
- Worker đọc đồng thời stdout và stderr của child qua pipe, tiếp tục drain stderr để child không bị
  block, rồi chỉ ghi một event `child_stderr_suppressed` an toàn.
- Startup chỉ chạy `access show` trên terminal tương tác. Pipe/redirect/CI không nhận token hoặc QR,
  và nhận lệnh explicit để operator tự gọi khi cần. Access show và task diagnose vẫn là lệnh chủ ý
  in dữ liệu cục bộ.

#### Số đo trước và sau

Trước: 8 điểm traceback trong ba tiến trình và một điểm kế thừa child stderr trong phạm vi log;
startup luôn gọi access show kể cả khi stdout không phải TTY. Sau: 134/134 focused regression tests
đạt; sentinel exception/child-output không xuất hiện ở stderr mặc định, và test startup non-TTY xác
nhận access show không được gọi.

#### Đánh đổi và phương án đã loại

- Log mặc định mất chi tiết vendor để bảo vệ dữ liệu; operator dùng mã/stage cố định, `runtime check
  --verbose`, `access show` hoặc `task diagnose` theo chủ ý.
- Chọn pipe + drain thay vì `DEVNULL` để giữ tín hiệu có child stderr mà không làm nghẽn lifecycle;
  không lưu nội dung stderr.
- Không xây subsystem debug mới và không thay đổi schema lỗi public hoặc semantics hủy task.

#### Follow-up

- Khi phát hành, kiểm tra lại log mặc định và lệnh chẩn đoán explicit.
- Khi phát hành, giữ hướng dẫn access-show explicit trong tài liệu vận hành.

#### Liên kết issue/PR

Issue #17; PR TBD.

#### Tag

Quyền riêng tư; Kiến trúc

#### Tài liệu đích

- `docs/user-guide.md` mục Chạy trên máy local.
- Release notes (#17) cho giới hạn log mặc định và lệnh chẩn đoán explicit.


### #17 — Build media LGPL và nguồn runtime GNU

PyAV 18.1.0 upstream nhúng FFmpeg báo LGPL nhưng đi cùng x264/x265 GPL;
nhãn license của FFmpeg không đổi license codec. Container build PyAV từ source
với FFmpeg 8.1.2 nguyên bản, `--disable-gpl --disable-nonfree --disable-autodetect`.
Không dùng patch đổi nhóm license của codec. FFmpeg CLI hệ thống vẫn là chương
trình riêng dùng cho chuẩn hóa media; nguồn Ubuntu của nó đi cùng release.

Các bản GNU OpenMP, Fortran và quadmath nhúng trong wheel được thay bằng runtime
Ubuntu. Bước build so sánh toàn bộ symbol export có version, dừng nếu thiếu,
và giữ nguyên filename mà wheel tham chiếu. Hash trước/sau và package nguồn
nằm trong `openmp-runtime.json`. Kiểm tra publication đối chiếu actual bytes.

FFmpeg/PyAV source, recipe build và copyright đi cùng bundle; thư viện FFmpeg
ở `/opt/asr-media/lib` có thể thay/rebuild độc lập theo LGPL. Binary runtime không
mang compiler/header của build stage. Đánh đổi: build lâu hơn và bỏ các codec
external khỏi PyAV; không khẳng định hiệu năng bằng các số đo lịch sử.
Quá trình chuẩn hóa input vẫn dùng FFmpeg hệ thống; cần smoke audio/container
và kiểm tra numerical runtime trên chính image trước công bố.

Tag: Kiến trúc; Quyền riêng tư. Hồ sơ phát hành #17; phạm vi image `0.1.0`.
