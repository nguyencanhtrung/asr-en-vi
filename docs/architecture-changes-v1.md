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

### #119 (pha 0 của #118) — ADR và khung reducer/store cho frontend

#### Vấn đề

Frontend (`src/asr_en_vi/web/`) là JS thuần với state sửa trực tiếp ở khoảng 250 chỗ, chống response cũ bằng các bộ đếm rải rác và không có unit test JS (CI chưa cài Node). Issue #118 chuyển dần sang core thuần; pha 0 dựng nền, chưa chuyển module UI nào.

#### Nguyên nhân đo được

Khoảng 250 lệnh gán state trực tiếp (`history.js` 145, `shell.js` 78, `notes.js` 29), các bộ đếm `loadSeq`/`searchSeq`/`saveSeq`, giao tiếp bằng `CustomEvent` và hàm global; test chỉ có Playwright.

Nguồn: issue #118.

#### Thay đổi thiết kế

`docs/adr/0010-frontend-reducer-core.md` chốt kiến trúc; `src/asr_en_vi/web/store.js` là ES module không chạm DOM gồm `createStore`, `combine`, `createRunner` (effect `fetch`, `schedule`, `cancel`, latest-wins theo `key`, kết quả mang `meta` để reducer bỏ response cũ). `tests/web/*.test.mjs` chạy bằng `node --test`, nằm trong `scripts/check.sh` và job quality của CI (Node 24, action ghim SHA). File UI hiện có, CSP và hành vi người dùng không đổi; không thêm dependency hay build step.

#### Số đo trước và sau

Điều kiện đo: Node 24.13.0, `node --test 'tests/web/*.test.mjs'`, thời gian wall của các test một lần chạy cục bộ; thời gian chạy trên CI nằm trong log job quality.

| | Trước | Sau |
| --- | --- | --- |
| Unit test JS | 0 | 19 test, dưới 0,1 s |
| Node trong CI | không | Node 24 |

Nguồn: `tests/web/store.test.mjs`, `.github/workflows/pipeline.yml`.

#### Đánh đổi và phương án đã loại

- Store tự viết dưới 150 dòng: không middleware hay devtools, đổi lại không phụ thuộc thư viện.
- Framework hoặc bundler: loại theo phạm vi #118.
- `node --test` nhận glob `tests/web/*.test.mjs`: Node 24 coi đối số thư mục là đường dẫn module nên không dùng `tests/web/`.

#### Follow-up

- Pha 1–5 của #118 chuyển từng module; #117 cần thống nhất thứ tự với pha 1.

#### Liên kết issue/PR

Issue #119; thuộc #118.

#### Tag

Kiến trúc

#### Tài liệu đích

- `docs/release/runtime-v0.1.0.md` — kiến trúc frontend.

### #121 (pha 1 của #118) — dialog tạo cuộc họp chuyển sang reducer

#### Vấn đề

`shell.js` (dialog chọn file, upload, tạo cuộc họp) giữ một object `appState` sửa trực tiếp ở 75 chỗ, trộn logic với DOM, và chống response cũ bằng `runId`/`policyRunId` cùng cờ `startingUpload`. Logic upload, hủy, dọn upload dở và tạo cuộc họp không có unit test, chỉ có Playwright.

#### Nguyên nhân đo được

Đếm lệnh gán `appState.<trường>` (`=`, `+=`, `++`) trong `shell.js` trước pha 1 bằng `grep -cE`: 75 dòng. Số 78 ở #118 là ước lượng gộp thêm hai lệnh `.add`/`.delete` trên `appState.pendingCleanup` và khai báo `appState`; 75 là số dùng cho cột "Lệnh gán state" bên dưới. Các nhánh hủy giữa chừng, lỗi mạng, bấm lặp và thử lại chỉ kiểm được qua trình duyệt thật.

Nguồn: `git show 10162b3:src/asr_en_vi/web/shell.js`; issue #118.

#### Thay đổi thiết kế

- `shell-core.js`: core thuần (`initialState`, `reduce`, `selectView`, chính sách file, kiểm form, thông điệp lỗi). `shell.js` là ES module chỉ render và dispatch (`<script type="module">`, nạp trước các script `defer` chưa chuyển). Mọi id chống response cũ nằm trong state.
- `createRunner` thêm effect `upload` (XHR có tiến độ, hủy, cùng ngữ nghĩa `ok`/`error`/`meta`/latest-wins như `fetch`), `storage` và `navigate`. Upload là effect riêng để #117 chèn bước tách audio trước nó.
- `ApiError`, `requestJson`, `meetingIdFromPath`, `formatMeetingDate`, `sameOriginAudioSource` vẫn công bố trên `window` cho `history.js` tới pha 5.
- Route `/assets/store.js` và `/assets/shell-core.js` có bảo vệ truy cập như asset khác, kèm test.
- Test `tests/web/shell-view.test.mjs` chặn gán vào state, `let`/`var` cấp module và truy cập storage ngoài `readStored` trong view đã chuyển; chạy trong `check.sh` và CI.
- Gộp góp ý pha 0: quy tắc tiền tố `key`, ngữ nghĩa lỗi giữa lượt drain và trong callback `schedule` (ADR 0010, mục 11.2), test hàng đợi bị bỏ khi lỗi, contract test yêu cầu có file `tests/web/*.test.mjs`, Node 24 trong `docs/user-guide.md`.

#### Số đo trước và sau

Điều kiện đo: Node 24.13.0, `node --test 'tests/web/*.test.mjs'`, thời gian wall của các test một lần chạy cục bộ.

| | Trước | Sau |
| --- | --- | --- |
| Lệnh gán state trong `shell.js` | 75 | 0 |
| Unit test JS | 19 | 70, dưới 0,1 s |

Nguồn: `tests/web/shell-core.test.mjs`, `tests/web/store.test.mjs`, `tests/web/shell-view.test.mjs`.

#### Đánh đổi và phương án đã loại

- Đóng dialog gửi DELETE upload dở rồi đóng ngay thay vì chờ DELETE trả lời; DELETE lỗi vẫn được nhớ và thử lại.
- Giá trị đã nhớ (ngôn ngữ, chép lời ngay) được đọc mỗi lần mở dialog, không chỉ lúc tải trang, để giữ hành vi cũ khi storage đổi giữa hai lần mở.
- Hủy rồi đóng khi DELETE treo: id nằm ở `pendingCleanup` từ lúc hủy nên không mất; dialog không bị khóa. Dialog bị trình duyệt tự đóng (Esc lần hai) được state theo kịp qua action `dialog-closed`.
- Render chỉ ghi DOM khi giá trị đổi, để vùng `aria-live` không bị đọc lại.
- Không dùng `combine`: dialog là tính năng duy nhất trên store này tới khi pha sau thêm tính năng thứ hai.

#### Follow-up

- #117 thêm effect tách audio trước `shell/upload`.
- Pha 2–5 của #118.

#### Liên kết issue/PR

Issue #121; thuộc #118.

#### Tag

Kiến trúc

#### Tài liệu đích

- `docs/release/runtime-v0.1.0.md` — kiến trúc frontend.

### #123 (pha 2 của #118) — kết nối ChatGPT và Google dùng chung một core provider

#### Vấn đề

`connections.js` (ChatGPT, nút launcher, hộp thoại) và `antigravity.js` (Google Antigravity) mỗi file giữ một object state sửa trực tiếp, nhân đôi cùng một luồng (tải trạng thái, danh sách model, đăng nhập, poll, hủy, lưu, kiểm tra, ngắt kết nối) và chống response cũ bằng bộ đếm `pollGeneration`, `loadGeneration`, `pollTimer` và cờ `savingModel`, `verifying`, `disconnecting`, `busy`. Luồng đăng nhập, hết hạn, hủy giữa chừng và khôi phục sau tải lại chỉ kiểm được bằng Playwright.

#### Nguyên nhân đo được

Đếm dòng gán `connectionState.<trường>` trong `connections.js` và `antigravityState.<trường>` trong `antigravity.js` (`=`, `+=`, `++`) tại 67b8f13 bằng `git show 67b8f13:<file> | grep -cE '<tên state>\.[A-Za-z]+\s*(=[^=]|[-+*/]=|\+\+|--)'`: 31 + 25 = 56. Hai file dài 912 + 461 dòng; chín cặp luồng lặp (tải, bắt đầu đăng nhập, poll, hủy, kết thúc đăng nhập, lưu, kiểm tra, ngắt kết nối, dựng danh sách model).

Nguồn: `git show 67b8f13:src/asr_en_vi/web/connections.js`, `git show 67b8f13:src/asr_en_vi/web/antigravity.js`; issue #118.

#### Thay đổi thiết kế

- `provider-core.js`: core thuần với một reducer cho mọi provider; mô tả provider là dữ liệu (endpoint, kiểu đăng nhập `popup`/`code`, độ trễ poll, hỗ trợ effort, khóa sessionStorage, bảng lỗi, văn bản). Hai provider dùng một store qua `combine`, tạo trong `connections.js` và `antigravity.js` import lại. Cả hai file là ES module chỉ render và dispatch (`<script type="module">`, giữ thứ tự cũ trong `shell.html`).
- `createRunner` thêm effect `open-window` (giữ chỗ cửa sổ rồi chuyển tới URL hoặc đóng), effect `event` (phát `asr:provider-choice-changed` cho `notes.js` đúng các thời điểm cũ) và tham số `now` đóng dấu đồng hồ lên action runner dispatch (hạn hết phiên đăng nhập đi vào reducer dưới dạng dữ liệu).
- Poll qua effect `schedule`; sessionStorage qua effect `storage`; khôi phục đăng nhập dở qua action `provider/boot-restored` mang chuỗi đã lưu.
- Route `/assets/provider-core.js` có bảo vệ truy cập và test asset; `connections.js`, `antigravity.js` thêm vào test asset.
- Gate `tests/web/shell-view.test.mjs` thêm hai view và core mới, mở rộng quy tắc theo góp ý pha 1 (bí danh `store.getState()`, lệnh đổi như `state.list.push`, object cấp module bị sửa), mỗi quy tắc có một ví dụ xấu trong test.
- Bảng trạng thái và chuyển trạng thái của core provider: `frontend-design-v1.md` mục 11.6.

Khác biệt hành vi so với bản cũ (đều nhỏ, ghi để review): Google bỏ qua poll trả lời muộn sau hủy hoặc kết thúc (bản cũ có thể dựng lại phiên đã hủy) và tải trạng thái có id; bấm đăng nhập lặp trong lúc đang khởi động bị bỏ; khi hủy, Google ngừng poll trong lúc chờ DELETE và poll lại nếu hủy lỗi; nút Hủy của ChatGPT khóa tới khi DELETE trả lời; lỗi có câu riêng (cửa sổ đã đóng, URL không an toàn) hiện câu đó ở cả tiếng Anh; dòng chữ giống hệt không ghi lại vào vùng `aria-live`; cuộn tới mục Google không bị hủy bởi lượt tải mới hơn; Google với URL đăng nhập sai hoặc không an toàn giữ login và hiện bảng đăng nhập cùng nút Hủy (bản cũ giữ bảng ẩn, nút Hủy không với tới); ChatGPT bị chặn popup giữ focus ở nút đăng nhập (bản cũ về `body`); sau khi ngắt ChatGPT, ô effort ẩn chỉ còn `default`; nút Hủy ẩn bị `disabled` trước lần đọc đầu của hộp thoại; cuộn tới mục Google lệch khoảng 51 px khi đọc trạng thái lỗi hoặc cần đăng nhập lại (đích vẫn là mục Google).

#### Số đo trước và sau

Điều kiện đo: Node 24.13.0, `node --test 'tests/web/*.test.mjs'`, một lần chạy cục bộ; dòng gán đếm như mục "Nguyên nhân đo được".

| | Trước | Sau |
| --- | --- | --- |
| Lệnh gán state trong `connections.js` + `antigravity.js` | 56 | 0 |
| Bộ đếm và cờ chống response cũ trong view | 8 (`pollGeneration`, `loadGeneration`, `pollTimer` x2, `savingModel`, `verifying`, `disconnecting`, `busy`) | 0 (id trong state của core) |
| Unit test JS | 70 | 133, dưới 0,2 s |
| `connections.js` + `antigravity.js` (dòng) | 1373 | 1358: view 279 + core 1079 (`wc -l`) |

Nguồn: `tests/web/provider-core.test.mjs`, `tests/web/store.test.mjs`, `tests/web/shell-view.test.mjs`.

#### Đánh đổi và phương án đã loại

- Một core cho hai provider thay vì hai core: khác biệt là trường của mô tả (khoảng 20 trường) cộng vài nhánh nhỏ; đổi lại mỗi sửa luồng (badge, lưu, kiểm tra, ngắt kết nối) làm một lần. Phương án loại: một hàm reducer có `if (id === "chatgpt")` rải rác.
- Không thêm file store riêng: store chung nằm ở `connections.js` (module nạp trước) để tránh một route và test asset thừa.
- Đồng hồ vào reducer qua `now` do runner đóng dấu, thay vì `Date.now()` trong reducer hoặc view tự thêm vào từng action.
- Lỗi "trình duyệt tự đóng dialog lúc đang lưu" của pha 1 không sửa ở PR này (không thuộc luồng provider; vẫn mở ở #118).

#### Follow-up

- Pha 3–5 của #118.
- `tr`, `setProp` hiện lặp giữa `shell.js` và `connections.js`; gom khi bỏ global ở pha 5.

#### Liên kết issue/PR

Issue #123; thuộc #118.

#### Tag

Kiến trúc

#### Tài liệu đích

- `docs/release/runtime-v0.1.0.md` — kiến trúc frontend.

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
