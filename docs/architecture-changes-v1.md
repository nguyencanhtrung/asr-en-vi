# Thay đổi kiến trúc và tối ưu v1 — ASR EN VI

## 1. Mở đầu

**Mục đích.** Tổng kết các tối ưu và thay đổi kiến trúc/thiết kế kể từ đợt nghiệm thu #16 (image build từ revision `151f3e4`, xem [báo cáo nghiệm thu](acceptance-report-v1.md)). Tài liệu sống theo giai đoạn phát triển; các mục đã được tách theo tag vào hồ sơ `docs/release/` cho #17. Số `#NN` là issue hoặc PR của repo trên GitHub.

**Quy tắc.**

1. Mỗi PR có tối ưu hoặc thay đổi thiết kế thêm một mục mới, hoặc cập nhật mục đã có, ngay trong PR đó (giai đoạn documentation của issue), theo mẫu ở mục 6. Việc chưa có PR nằm ở mục 5 và chuyển thành mục đầy đủ trong PR của nó.
2. Mỗi mục tự đủ nghĩa: nêu bối cảnh cần thiết trong một dòng thay vì "xem mục trên"; chỉ liên kết sang mục khác để tra cứu thêm.
3. Mọi số có nguồn công khai (issue, PR hoặc tài liệu trong repo), ghi ngay dưới bảng. Nguồn lệch nhau thì dùng số đo mới nhất và ghi một dòng chênh lệch.
4. Không ghi nội dung cuộc họp, thông tin xác thực, đường dẫn cá nhân, bằng chứng riêng tư hay chi tiết công cụ phát triển.

**Bảng tách khi release (#17).** Mỗi mục có một hoặc nhiều tag. Khi release, mục chuyển nguyên sang tài liệu đích của từng tag của nó. Cần tag mới thì thêm một hàng vào bảng này trong PR đầu tiên dùng tag đó.

| Tag | Nội dung | Tài liệu đích (mục) |
| --- | --- | --- |
| Hiệu năng | thời gian, bộ nhớ, thông lượng; lần đo lại tiêu chí nghiệm thu | `docs/release/performance-v0.1.0.md`; tài liệu thiết kế/contract/nghiệm thu giữ liên kết tới hồ sơ này |
| Kiến trúc | ranh giới module, luồng dữ liệu, vòng đời tác vụ | `docs/release/runtime-v0.1.0.md`; tài liệu thiết kế/contract/nghiệm thu giữ liên kết tới hồ sơ này |
| Quyền riêng tư | dữ liệu hoặc kết nối ra ngoài máy, telemetry | `docs/release/privacy-v0.1.0.md`; tài liệu thiết kế/contract/nghiệm thu giữ liên kết tới hồ sơ này |
| Notes | pipeline tạo notes: chia/hợp nhất, ngân sách, phục hồi, prompt | `docs/release/notes-v0.1.0.md`; tài liệu thiết kế/contract/nghiệm thu giữ liên kết tới hồ sơ này |

Bảng mốc AC-13 đã chuyển vào báo cáo nghiệm thu; việc còn mở đã chuyển vào release notes. Các mục bên dưới giữ liên kết để truy vết.

## 2. Chuỗi xử lý và chỗ mỗi thay đổi tác động

```text
upload
  │
chuẩn hoá — kiểm tra và chuyển audio phía server            (ngoài mốc AC-13)
  │
  ▼ POST /api/tasks: bắt đầu mốc AC-13
ASR — Whisper large-v3, CUDA
  │
diarization — pyannote Community-1, CUDA
  │   nạp model → giải mã đầu vào → diarizing
  │   ◄── [#71] giải mã một lần thành waveform 16 kHz mono; pipeline nhận waveform, không nhận đường dẫn
ghép người nói — căn đoạn ASR với lượt nói
  │
  ▼ transcript sẵn: mốc 1 của AC-13
bấm "Tạo notes" — notes không tự chạy sau transcript (#73)
  │
notes — chia chunk → trích xuất → hợp nhất → kiểm tra → render
  │   ◄── [#72] đầu ra vượt trần → gọi lại với mục tiêu độ dài nhỏ hơn
  ▼ notes sẵn: mốc 2 của AC-13

[#74] bao trùm ASR → notes: ORT_DISABLE_TELEMETRY=1 trong mọi tiến trình con của worker
[#99] đo cả đoạn từ POST /api/tasks tới notes sẵn (không đổi mã)
```

## 3. Các thay đổi đã chuyển vào hồ sơ phát hành

### #74 / PR #91 — Tắt telemetry ONNX Runtime trong tiến trình con của worker

Đã chuyển nguyên mục: [Quyền riêng tư](release/privacy-v0.1.0.md).

### #72 / PR #94 — Phục hồi notes khi đầu ra của provider vượt trần

Đã chuyển nguyên mục: [Pipeline notes](release/notes-v0.1.0.md).

### #71 / PR #98 — Diarization giải mã bản ghi một lần thành waveform 16 kHz

Đã chuyển nguyên mục: [Hiệu năng](release/performance-v0.1.0.md).

### #99 / PR #103 — Đo lại AC-13 trên main sau #71, #72, #74

Đã chuyển nguyên mục: [Hiệu năng](release/performance-v0.1.0.md).

### #104 / PR #109 — Notes một lượt theo context thật của model

Đã chuyển nguyên mục: [Hiệu năng](release/performance-v0.1.0.md), [Pipeline notes](release/notes-v0.1.0.md).

### #17 / PR #112 — Nhật ký runtime và startup mặc định an toàn

Đã chuyển nguyên mục: [Quyền riêng tư](release/privacy-v0.1.0.md), [Kiến trúc runtime](release/runtime-v0.1.0.md).

### #100 / PR #111 — Notes văn phong telegraph, mỗi ý một mục

Đã chuyển nguyên mục: [Pipeline notes](release/notes-v0.1.0.md).

### #115 — Tắt PR Dependabot và xác minh config digest image công khai

#### Vấn đề

Metadata do BuildKit trả về sau khi push image có provenance và SBOM không bảo đảm chứa
`containerimage.config.digest`; gate cũ vì vậy dừng sau khi push thành công. Dependabot cũng
không còn là cơ chế cập nhật dependency được sử dụng trong repository.

#### Nguyên nhân đo được

Gate cũ đọc config digest từ `PUBLISHED_METADATA`, nhưng metadata published thực tế chỉ cung cấp
index/manifest digest và attestations. Việc tra cứu image công khai phải đi qua index rồi child
manifest đúng platform để lấy config descriptor.

Nguồn: `tests/test_published_image_contract.py`, `tests/test_image_config.py` và workflow phát hành.

#### Thay đổi thiết kế

Xóa cấu hình Dependabot để ngăn tạo PR cập nhật version. Helper `scripts/resolve-image-config.py`
dùng token GHCR anonymous, hash-check bytes của index, child manifest và config, bỏ qua descriptor
attestation, rồi yêu cầu đúng một child Linux cho platform. Workflow so sánh config digest công khai
với digest candidate trước các kiểm tra version, schema, revision và smoke; thứ tự publish source
trước image và kiểm tra hai kiến trúc trước khi gắn tag không đổi.

#### Số đo trước và sau

| | Trước | Sau |
| --- | --- | --- |
| Nguồn config digest của gate | metadata published không ổn định | registry index → child manifest → config |
| Số child native được chấp nhận | không xác minh | đúng 1 Linux child |

Nguồn: `tests/test_delivery_contract.py`, `tests/test_image_config.py` và `tests/test_published_image_contract.py`.

#### Đánh đổi và phương án đã loại

- Tra cứu registry anonymous: chịu thêm ba request artifact read-only ngoài token, đổi lại xác minh artifact thực sự đã public.
- Đọc lại metadata BuildKit sau push: loại vì metadata published có thể thiếu config digest khi có SBOM/provenance.
- Giữ Dependabot version updates: loại theo quyết định của issue #115; security alerts không thay đổi.

#### Follow-up

- #115: giữ các test negative cho platform thiếu, trùng, unknown và config sai.

#### Liên kết issue/PR

[Issue #115](https://github.com/nguyencanhtrung/asr-en-vi/issues/115).

#### Tag

Kiến trúc

#### Tài liệu đích

- `docs/release/runtime-v0.1.0.md` — release publication verification.

## 4. Mốc AC-13 (#16 → #99 → #104)

Đã chuyển bảng mốc và điều kiện đo vào [báo cáo nghiệm thu](acceptance-report-v1.md).

## 5. Đang làm / tiếp theo

Các kết quả chưa đạt và follow-up nằm trong [release notes](release/notes-v1.md).

## 6. Mẫu mục mới

Mục mới sao chép mẫu dưới đây và giữ nguyên tên các heading, để việc tách theo tag không phải viết lại.

````markdown
### #<issue> / PR #<pr> — <tiêu đề ngắn: thay đổi gì>

#### Vấn đề

<Bối cảnh cần để hiểu mục này một mình (thuật ngữ, mốc AC) trong một hai dòng; điều gì sai hoặc chậm.>

#### Nguyên nhân đo được

<Nguyên nhân kèm số đo; bảng nếu nhiều số.>

Nguồn: <issue/PR/comment hoặc mục của tài liệu trong repo>.

#### Thay đổi thiết kế

<Thiết kế mới: module, hàm, hằng số, hành vi mới; điều gì không đổi.>

#### Số đo trước và sau

<Điều kiện đo (revision, mẫu, cấu hình), rồi bảng trước/sau.>

| | Trước | Sau |
| --- | --- | --- |
| <chỉ số> | <số> | <số> |

Nguồn: <issue/PR/tài liệu>. <Nếu nguồn lệch nhau: dùng số đo mới nhất, ghi một dòng chênh lệch.>

#### Đánh đổi và phương án đã loại

- <Phương án đã chọn>: <đánh đổi>.
- <Phương án đã loại>: <lý do>.

#### Follow-up

- #<n>: <một dòng>.

#### Liên kết issue/PR

Issue #<n>, PR #<n>; liên quan #<n>.

#### Tag

<một hoặc nhiều tag trong bảng ở mục 1: Hiệu năng | Kiến trúc | Quyền riêng tư | Notes>

#### Tài liệu đích

- <tệp và mục sẽ nhận nội dung khi release>
````
