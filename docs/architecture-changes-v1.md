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

Đếm lần gán vào `connectionState.<trường>` trong `connections.js` và `antigravityState.<trường>` trong `antigravity.js` tại 67b8f13 (bỏ chú thích; `=`, `+=`, `++`, `--` hậu tố và tiền tố, gán lồng): 32 + 3 tiền tố + 26 = 61. Cách đếm đầu tiên bằng `grep -c` trên dòng bỏ sót `++x` tiền tố và gán lồng nên ra 56; số đúng là 61. Hai file dài 912 + 461 dòng; chín cặp luồng lặp (tải, bắt đầu đăng nhập, poll, hủy, kết thúc đăng nhập, lưu, kiểm tra, ngắt kết nối, dựng danh sách model).

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
| Lệnh gán state trong `connections.js` + `antigravity.js` | 61 (bản đầu ghi 56) | 0 |
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

### #126 (pha 3 của #118) — `notes.js` chuyển sang reducer

#### Vấn đề

`notes.js` (2093 dòng) giữ một object `state` sửa trực tiếp ở hàng trăm chỗ, trộn logic với DOM và chống response cũ bằng bộ đếm `loadSeq`, `readSeq`, `pollSeq`, `selectionSeq`, `sourceSeq`, bộ hẹn giờ `pollTimer` và cờ `requestInFlight`, `cancelInFlight`, `saveInFlight`, `transcriptionRequestInFlight`. Những luồng khó nhất của tab (response tới sai thứ tự khi đổi cuộc họp, poll cũ, hủy giữa chừng, tạo hoặc lưu lặp, xung đột revision, khôi phục bản nháp) chỉ kiểm được bằng Playwright. Bản nháp và bước task còn được tạo ngay trong lúc render.

#### Nguyên nhân đo được

Đếm lần gán vào `state`, `choice`, `data`, `draft`, `notes` tại 6f1a609 trong `git show 6f1a609:src/asr_en_vi/web/notes.js`, bỏ chú thích, đếm từng lần xuất hiện (không phải dòng): gán và gán kép `<tên>(.trường|[chỉ số])+ (=|+=|-=|*=|/=|++|--)` 121; `++`/`--` tiền tố 3 (`++choice.loadSeq`, `++state.readSeq`, `++state.sourceSeq`); đổi Map/Set `state.<x>.set|delete|add|clear(`, `data.saveInFlight.add|delete(` 12; tổng 136. Mười tên `*Seq`, `*InFlight`, `*Timer` (`cancelInFlight`, `loadSeq`, `pollSeq`, `pollTimer`, `readSeq`, `requestInFlight`, `saveInFlight`, `selectionSeq`, `sourceSeq`, `transcriptionRequestInFlight`). Bản nháp (`revisionDraft`) và bước task (`renderTaskSteps`) còn được tạo và ghi vào state ngay trong lúc render.

Nguồn: `git show 6f1a609:src/asr_en_vi/web/notes.js`; issue #118.

#### Thay đổi thiết kế

- `notes-core.js`: core thuần (`initialState`, `reduce`, `selectView`, `selectSummary`, `hasUnsavedDraft`) cùng các hàm thuần chuyển từ `notes.js` (nhãn, thông báo lỗi theo mã, chuẩn hóa revision, trích dẫn và request chờ, `markdownBlocks`, `sourceReference`, `sourceFromHref`). Thời gian, id ngẫu nhiên (`requestId`), giá trị đã lưu (`stored`), địa chỉ trang (`href`, `origin`) và trạng thái ẩn của trang vào qua action.
- `notes.js`: ES module khoảng 0,5 nghìn dòng, store riêng, render từ `selectView` bằng `setProp`, handler chỉ dispatch. Vị trí trong `shell.html` giữ nguyên (sau `history.js`, trước `connections.js`); `<script type="module">` thay `defer`.
- Effect mới `call` (`key`, `name`, `args`, `ok`, `error`, `meta`) và tham số `calls` của `createRunner`: một cổng cho lệnh tới `history.js` (`setNotesSourceLock`, `setNotesSummary`, `selectTab`, `markNotesSource`, `showNotesSourceTab`, `focusSpeakerCatalog`, `refreshMeeting`, `seekNotesSource`, `playRecording`) và cho clipboard, tải file, `history.replaceState`. Kết quả bất đồng bộ (tua, phát, chép) về thành action; hủy/thay thế theo `key` như `fetch`.
- Poll bằng `schedule`; `localStorage` (chế độ Xem/Viết) và request chờ, ngôn ngữ đầu ra (local + session) bằng `storage`; id request tạo trong view (`crypto.randomUUID`) và vào bằng action `notes/start-clicked`.
- Route `/assets/notes-core.js` có bảo vệ truy cập; `notes.js` và `notes-core.js` thêm vào hai test asset.
- Gate `tests/web/shell-view.test.mjs`: thêm `notes.js` (view) và `notes-core.js` (core); sửa hai điểm mù từ pha 2: `${…}` trong template literal được quét như mã, bí danh lát cắt (`const s = state.x; s.y = 1`) bị bắt; mỗi điểm có ví dụ xấu trong test.
- Bảng trạng thái và chuyển trạng thái: `frontend-design-v1.md` mục 11.7. ADR 0010 thêm effect `call`.

Khác biệt hành vi so với bản cũ (đều nhỏ, ghi để review): request đọc/tải lựa chọn có key riêng nên không bị hủy giữa chừng, response cũ bị bỏ bằng id (như bản cũ); sau khi tạo notes mà máy chủ trả task đã kết thúc ngay, nút "Đang gửi yêu cầu…" tắt trước khi lần đọc lại xong (bản cũ giữ tới khi đọc xong); ô cảnh báo liên kết hỏng chỉ dựng lại khi nội dung đổi (bản cũ dựng lại mỗi lần render, làm vùng `aria-live` đọc lại); nội dung vẫn giống nhau thì không ghi lại vào DOM; request chờ và ngôn ngữ đã lưu được đọc ở mỗi sự kiện context cho cuộc họp chưa có trong state (bản cũ đọc ngôn ngữ một lần, còn request chờ thì đọc lại ở mỗi lần render tới khi thấy); bản nháp và bước task được đối chiếu sau mỗi action thay vì khi render; tóm tắt gửi cho `history.js` chỉ khi context tới hoặc tóm tắt đổi (bản cũ gửi mỗi lần render); lỗi mở nguồn để nút "Tua bản ghi" bị khóa (bản cũ giữ trạng thái trước); vùng `aria-live` trạng thái notes chỉ ghi giá trị cuối (bản cũ ghi hai lần khi đang chép lời hoặc sau lỗi chưa chắc chắn); `markNotesSource` và `seekNotesSource` chạy sau một tick (`schedule` delay 0, action `source-shown`) để view vẽ thẻ nguồn trước, như bản cũ; gõ vào bản nháp render lại đầy đủ nên hộp xung đột ẩn ngay khi phím gõ làm hết xung đột (bản cũ chờ lần render đầy đủ kế tiếp); lưu bị 409 thì cảnh báo xung đột chỉ hiện khi bản mới nhất đã đọc xong (bản cũ không render giữa 409 và lần đọc đó); ô xem trước chỉ dựng lại khi các khối Markdown đổi (khóa JSON), nên ẩn/hiện tab trình duyệt hay một lượt poll không làm mất focus bàn phím trên chip trích dẫn (bản cũ dựng lại mỗi lần render); tên người nói mặc định đi cùng action context (view hỏi `history.js` khi nhận `asr:meeting-context`) thay vì hỏi lúc render, nên người nói mới thêm ở tab Bản ghi (chưa có đoạn nào) chưa vào câu nhắc tới context kế tiếp; render chỉ chạy khi có meeting (bản cũ còn vẽ lại tab ẩn khi trả lời tải/lưu lựa chọn, chép/tải xuống tới sau lúc rời cuộc họp; không thấy được).

#### Số đo trước và sau

Điều kiện đo: Node 24.13.0, `node --test tests/web/*.test.mjs`, một lần chạy cục bộ; lần gán đếm như mục "Nguyên nhân đo được" (`=`, `+=`, `++`/`--` tiền tố và hậu tố, gán lồng) vào `state` và các bí danh của nó (`state`, `choice`, `data`, `draft`, `notes`; tức `state.choice`, `meetingNotes()`, `revisionDraft()`), cộng lệnh `.set/.delete/.add/.clear` trên Map/Set của state: 121 phép gán + 3 tiền tố + 12 lệnh Map/Set = 136 trên `git show 6f1a609:src/asr_en_vi/web/notes.js` bỏ comment. Dòng này đếm cả thay đổi Map/Set, mà số đo của #123 không đếm. Sau: 0 ở `notes.js`, kiểm bằng gate; `notes-core.js` tạo state mới nên không gán tại chỗ.

| | Trước | Sau |
| --- | --- | --- |
| Lần gán/đổi state trong `notes.js` (gồm thay đổi Map/Set) | 136 | 0 |
| Bộ đếm và cờ chống response cũ trong view | 10 | 0 (id trong state của core; `transcriptionRequestInFlight` chỉ còn là tên trường do `history.js` gửi) |
| Unit test JS | 133 | 237 (98 cho core notes, 4 cho runner `call`, 2 thêm cho gate), 0,1 s |
| `notes.js` (dòng) | 2093 | khoảng 2,5 nghìn: view khoảng 0,5 nghìn + core khoảng 1,9 nghìn (`wc -l`) |

Nguồn: `tests/web/notes-core.test.mjs`, `tests/web/shell-view.test.mjs`.

#### Đánh đổi và phương án đã loại

- `history.js` chưa chuyển nên lệnh tới nó đi qua một effect `call` có tên, thay vì thêm một loại effect cho từng lệnh; câu hỏi chỉ đọc (`hasUnsavedTranscriptDrafts` lúc trang đóng, `currentContext` lúc boot, `defaultSpeakerNames` lúc nhận context) view gọi thẳng vì reducer không chờ giá trị trả về tức thời. Tên người nói vào state qua action context: `history.js` phát `asr:meeting-context` khi đổi tên, gán đoạn hay sửa đoạn; thêm người nói thì không, nên tên mới vào câu nhắc ở context kế tiếp.
- Request đọc không bị hủy khi có request mới hơn (key theo id) để giữ hành vi cũ; test Playwright của #12 chờ response thứ nhất đọc xong.
- Tổng số dòng tăng (khoảng 2,5 nghìn so với 2093) vì reducer tạo state mới thay vì gán tại chỗ: đổi lại mọi chuyển trạng thái nằm ở một nơi và test được ngoài trình duyệt.
- Câu "Revision notes mới nhất không khớp." giữ làm hằng `LATEST_MISMATCH`: bản cũ tạo nó rồi hiển thị câu của lỗi 409; bảng tiếng Anh vẫn cần nó.

#### Follow-up

- Lỗi pha 1 còn mở: dialog tự đóng trong lúc lưu (xem comment #118 ngày 2026-10-28); đọc notes của cuộc họp A trả lời muộn (start/cancel/409) làm rơi lần đọc đầu của cuộc họp B vì `readId` dùng chung (đã có ở bản cũ qua `readSeq`; bỏ qua đọc khi `meetingId` khác meeting hiện tại, hoặc stale theo từng meeting); `LATEST_MISMATCH` là chuỗi chết, xóa cùng bản tiếng Anh khi `i18n.js` mở ở pha 5.
- Pha 4–5 của #118; `tr`, `setProp` lặp giữa `shell.js`, `connections.js` và `notes.js`, gom khi bỏ global ở pha 5.
- Góp ý pha 2 còn mở: cuộn tới mục Google trước khi view Google render xong, `gen` trong meta của `POST …/input`, descriptor còn trường không ai đọc, cờ descriptor thực chất là switch theo provider.

#### Liên kết issue/PR

Issue #126; thuộc #118.

#### Tag

Kiến trúc

#### Tài liệu đích

- `docs/release/runtime-v0.1.0.md` — kiến trúc frontend.

### #128 (pha 4a của #118) — điều hướng và thư viện cuộc họp trong `history.js` chuyển sang reducer

#### Vấn đề

Phần điều hướng và thư viện của `history.js` (danh sách, tìm kiếm, lịch, chọn cuộc họp, tab, sửa tên/ngày, xóa) giữ trong object `state` sửa tại chỗ, chống response cũ bằng `loadSeq`, `searchSeq`, `saveSeq` và hai bộ hẹn giờ `searchTimer`, `tabTimer`. Thứ tự response (đổi cuộc họp giữa chừng, tìm kiếm gõ nhanh, lưu rồi đổi cuộc họp, xóa lỗi rồi tải lại) chỉ kiểm được bằng Playwright.

#### Nguyên nhân đo được

Đếm lần gán vào trường điều hướng/thư viện của `state` trong `git show 2819779:src/asr_en_vi/web/history.js`, bỏ chú thích, đếm từng lần xuất hiện (không phải dòng), cùng cách đếm với #126 (tính cả bí danh của `state`): gán và gán kép `<tên>(.trường|[chỉ số])+ (=|+=|-=|*=|/=|++|--)` vào các trường `calendar`, `deletionRequestMeetingId`, `deletionRequestPending`, `draft`, `editorBusy`, `loadSeq`, `meeting` (gồm `state.meeting.transcription =`), `meetings`, `notesCount`, `notesKnown`, `notesSourceLockKnown`, `notesSourceLocked`, `notesTaskStatus`, `query`, `recent`, `results`, `saveSeq`, `searchFailed`, `tab`, `tabTimer`, `total`, `view` = 54, cộng 3 phép gán qua bí danh `draft` của `state.draft` trong `showConflict` (`draft.original.title`, `draft.original.meeting_date`, `draft.version`) = 57; `++` tiền tố 3 (`++state.searchSeq`, `++state.loadSeq`, `++state.saveSeq`); đổi Map `deletionFailures.set|delete(` 3; tổng 63. Các trường task và transcript của `state` (`selectedGenerationId`, `taskPollId`, `transcriptMutation*`, `editingSegment`, …) và các phép gán vào `draft` của bản nháp transcript không được đếm. Năm bộ đếm và bộ hẹn giờ thuộc phần 4a: `loadSeq`, `saveSeq`, `searchSeq`, `searchTimer`, `tabTimer`. Các tên `*InFlight`/`*Timer` còn lại (`taskPollTimer`, `taskRequestInFlight`, `transcriptMutationInFlight`, `transcriptReloadInFlight`, `transcriptionRequestInFlight`) thuộc 4b/4c, giữ nguyên.

Nguồn: `git show 2819779:src/asr_en_vi/web/history.js`; issue #118.

#### Thay đổi thiết kế

- `history-core.js`: core thuần (`initialState`, `reduce`, các selector `selectHeading/Sidebar/Calendar/LockStatus/Editor/Deletion`) cùng hàm thuần chuyển từ `history.js` (ngày và lưới lịch, `meetingIdFromPathname`, chọn thế hệ transcript, tab mặc định). Địa chỉ trang (`pathname`, `search`, `hash`, tab hiện tại) vào qua trường `at` mà view đóng dấu lên mọi action; ngày hôm nay vào qua `history/booted`.
- `history.js`: ES module, một store `combine({history: reduce})`; `render` so sánh với bản đã vẽ và chỉ vẽ phần đổi; handler chỉ dispatch. Phần task (4b) và transcript (4c) còn mệnh lệnh, giữ trong object `legacy`; chúng báo sửa tại chỗ bằng `history/meeting-updated` và tải lại bằng `history/meeting-fetched`.
- Effect mới ở `history.js`: `history/list`, `/search`, `/search-timer`, `/tab-timer`, `/meeting`, `/save`, `/conflict`, `/delete`, và lệnh `address.push` qua `calls`.
- Route `/assets/history-core.js` có bảo vệ truy cập; thêm vào hai test asset. `shell.html` đổi `history.js` sang `type="module"`.
- Gate `tests/web/shell-view.test.mjs`: `history-core.js` vào CORES; `history.js` vào `PARTIAL` (phải là module, miễn quy tắc view cho tới khi 4c xong).
- Bảng trạng thái và chuyển trạng thái: `frontend-design-v1.md` mục 11.8. ADR 0010 thêm một ý: địa chỉ vào core như dữ liệu `at`.

Khác biệt hành vi so với bản cũ (đều nhỏ, ghi để review): danh sách cuộc họp tải lại nhiều lần thì kết quả mới nhất theo id thắng (bản cũ: cái tới sau cùng); xóa ô tìm kiếm hủy luôn hẹn giờ và tìm kiếm đang chạy; lịch vẽ lại ngay khi danh sách về, còn thanh bên chờ kết quả tìm kiếm; `aria-current` ở thanh bên theo view ngay, `repaintSidebar` của phần cũ chỉ dựng lại khi dữ liệu đổi; tên và ngày đang sửa nằm trong state (sự kiện input), giá trị DOM đi kèm khi gửi; promise của `loadMeeting` trả `false` ngay lúc bị thay thế (bản cũ: khi response cũ tới); hộp thoại xóa hiện lỗi khi tải lại kết thúc hoặc bị thay; cài cuộc họp tạo bản sao đã gộp (bản cũ sửa object nhận về); phản hồi lưu không phải object tính là lỗi; tab chỉ vẽ lại khi đổi; ngày tính bằng số học ngày dân sự (cùng kết quả cho năm 1000–9999); focus bàn phím trên link ở sidebar được giữ khi danh sách dựng lại (bản cũ rơi về `body` khi tải xong hoặc làm mới danh sách); sau khi xóa thất bại, nút xác nhận tắt tới khi tải lại xong kể cả khi gõ lại tên (bản cũ bật lại nếu gõ lại tên); lần lưu metadata cũ của cuộc họp đã rời bị hủy khi lưu cuộc họp khác (khóa `history/save`, bản mới nhất thắng). Giữ như cũ: nút "Xóa ngày" gán `value` trực tiếp để bỏ ngày nhập dở; làm mới cùng cuộc họp vẽ tab trước khi báo `asr:meeting-context` cho `notes.js`, để focus tiêu đề nguồn không rơi vào panel đang ẩn. Số lần `asr:meeting-context` mỗi lần tải giữ 4.

#### Số đo trước và sau

Điều kiện đo: Node 24.13.0, `node --test tests/web/*.test.mjs`, một lần chạy cục bộ; lần gán đếm như mục "Nguyên nhân đo được": 57 phép gán (54 + 3 qua bí danh) + 3 tiền tố + 3 lệnh Map = 63 trên `git show 2819779:src/asr_en_vi/web/history.js` bỏ comment. Sau: 0 trong mã 4a của `history.js` (mọi thay đổi điều hướng/thư viện đi qua `reduce`); còn 1 phép gán ở cầu nối 4b/4c (`editTranscription` ghi `meeting.transcription` vào cuộc họp của store) và các sửa tại chỗ phần tử thế hệ transcript (`generation.source_version`, `item.text`, danh sách người nói), mà số đếm trước không tính; hết khi 4b/4c chuyển. `history-core.js` tạo state mới nên không gán tại chỗ.

| | Trước | Sau |
| --- | --- | --- |
| Lần gán/đổi state điều hướng/thư viện trong `history.js` (gồm Map) | 63 | 0 ở mã 4a; 1 ở cầu nối 4b/4c |
| Bộ đếm và bộ hẹn giờ chống response cũ ở phần 4a | 5 | 0 (id trong state của core) |
| Unit test JS | 237 | 314 (77 cho core history) |
| `history.js` (dòng) | 4295 | khoảng 4,8 nghìn: view và phần cũ 3857 + core 972 (`wc -l`) |

Nguồn: `tests/web/history-core.test.mjs`, `tests/web/shell-view.test.mjs`.

#### Đánh đổi và phương án đã loại

- Phần 4b/4c đọc state qua `legacy` và `nav()` chỉ để đọc; chúng sửa meeting tại chỗ rồi báo `history/meeting-updated` (chỉ nhận nếu đúng object store đang giữ; `editTranscription` truyền chính object nó vừa sửa, nên bản cầm từ trước một `await` bị bỏ qua). Đây là cầu nối tạm tới khi 4b/4c chuyển.
- `history.js` chưa vào gate view (VIEWS) vì còn mã 4b/4c mệnh lệnh; vào ở 4c.
- Chuỗi "Không thể tải dữ liệu cuộc họp." giữ làm giá trị dự phòng: `i18n.js` chưa mở và `test_i18n` đòi mọi mục catalog xuất hiện dạng `t("…")`.
- Tổng số dòng tăng vì reducer tạo state mới thay vì gán tại chỗ: đổi lại mọi chuyển trạng thái nằm ở một nơi và test được ngoài trình duyệt.

#### Follow-up

- 4b (task) và 4c (transcript) của #118, rồi `history.js` vào VIEWS; bỏ `legacy` và `history/meeting-updated`.
- Chuỗi dự phòng chết ở trên xóa cùng bản tiếng Anh khi `i18n.js` mở ở pha 5.

#### Liên kết issue/PR

Issue #128; thuộc #118.

#### Tag

Kiến trúc

#### Tài liệu đích

- `docs/release/runtime-v0.1.0.md` — kiến trúc frontend.

### #130 (pha 4b của #118) — task phiên âm trong `history.js` chuyển sang reducer

#### Vấn đề

Phần task phiên âm của `history.js` (bắt đầu, hủy, poll tiến độ, request id chờ ở sessionStorage, ngôn ngữ, lỗi task, chẩn đoán) chạy mệnh lệnh trên object `legacy`, với hẹn giờ `taskPollTimer`, cờ `taskRequestInFlight` và chống response cũ bằng so sánh `taskPollId` với `nav().meeting`. Thứ tự response (poll tới sau khi rời cuộc họp, bắt đầu hoặc hủy bị lỗi mạng, hủy giữa chừng, bấm lặp, khôi phục request chờ sau tải lại, đổi nhịp khi trang ẩn) chỉ kiểm được bằng Playwright.

#### Nguyên nhân đo được

Đếm trên `git show e9b3e50:src/asr_en_vi/web/history.js` bỏ chú thích, cùng cách đếm với #126 và #128 (từng lần xuất hiện, không phải dòng): 7 trường task của `legacy` (`taskPollTimer`, `taskPollId`, `taskRequestInFlight`, `pendingTaskRequestId`, `transcriptionLanguageMeetingId`, `transcriptionLanguageSelection`, `taskRequestError`) được gán 18 lần (`legacy.<trường> =`: `taskRequestError` 5, `taskPollTimer` 3, mỗi trường còn lại 2) và đọc/gán tổng cộng 42 lần; hai tên `*Timer`/`*InFlight` của phần task (`taskPollTimer` 9 lần xuất hiện, `taskRequestInFlight` 7). `transcriptionRequestInFlight` (2 lần) là tên trường hợp đồng gửi cho `notes.js`, giữ nguyên.

Nguồn: `git show e9b3e50:src/asr_en_vi/web/history.js`; issue #118, #130.

#### Thay đổi thiết kế

- `task-core.js`: core thuần (`initialState`, `reduce`, `selectTask`, `selectRuntime`, `selectRequestBusy`, `displayedLanguage`, `diagnosticCommand`). Id request mới, nhịp ẩn/hiện của trang, chuỗi sessionStorage và khóa tự chạy vào qua action; ghi sessionStorage và xóa khóa tự chạy bằng effect `storage`; poll bằng `schedule` + `fetch`; sao chép lệnh chẩn đoán bằng effect `call`.
- Lát `task` cùng store với `history` (`combine({history, task})`). Đối tượng task ở lại trong cuộc họp của `history-core`; bốn action `task/poll-loaded`, `task/start-succeeded`, `task/cancel-succeeded`, `task/refresh-loaded` do cả hai lát xử lý (`history-core` đặt task vào cuộc họp mới tạo, không sửa tại chỗ). View đóng dấu mọi action bằng `shown` (cuộc họp lát history đang giữ, kể cả ở trang chủ hoặc khi cuộc họp khác đang tải) như `at`, và đổi `legacy.rev`, `readyRev` của `history-core` thành `task/meeting-left`, `task/meeting-ready`.
- `history.js`: bỏ 7 trường task khỏi `legacy`, bỏ `editTranscription`, `startTaskPolling`, `pollTask` và các hàm request id; `renderTranscription` chỉ đọc `selectTask`. `history-core.js` thêm bốn case dùng chung và xuất `failureOf`; cuộc họp nhận task mang khóa nguồn notes như đã báo (`notes-core` chỉ đọc lại `notes_source_locked` khi nhận object cuộc họp mới, mà object nay đổi mỗi lượt poll). Thanh bên chỉ vẽ lại khi id cuộc họp mở đổi; "Tải lại bản mới nhất" bỏ kết quả theo `installRev` thay vì so object cuộc họp (object nay đổi mỗi lượt poll, nên so object sẽ bỏ nhầm khi đang chạy task).
- Route `/assets/task-core.js` có bảo vệ truy cập; thêm vào hai test asset. Gate `shell-view.test.mjs`: `task-core.js` vào CORES.
- Bảng trạng thái và chuyển trạng thái: `frontend-design-v1.md` mục 11.9. ADR 0010 thêm một ý về `shown` và action dùng chung giữa các lát. Không thêm loại effect.

Khác biệt hành vi so với bản cũ (đều nhỏ, ghi để review; đã đối chiếu từng ý với `git show e9b3e50`): chỉ một lần đọc poll chạy cho mỗi task (bản cũ: `visibilitychange` hoặc cuộc họp tải lại giữa lúc đọc đặt thêm timer, hai lần đọc có thể chồng nhau); request poll bị hủy khi rời cuộc họp (bản cũ để chạy rồi bỏ kết quả); nút Hủy giữ tắt tới khi yêu cầu hủy xong (bản cũ: lượt poll kế tiếp vẽ lại và bật nút, bấm được lần hai); câu trả lời bắt đầu hoặc hủy tới sau khi một cuộc họp khác đã tải xong không đổi cuộc họp đang hiện (ở trang chủ hoặc khi cuộc họp khác đang tải thì như bản cũ: câu trả lời áp vào cuộc họp history còn giữ và poll chạy tới khi task kết thúc; bản cũ sửa object cuộc họp cũ, đặt `taskPollId` và timer cho cuộc họp không còn hiện, và với lỗi bắt đầu ghi một dòng lên trạng thái của cuộc họp khác), nhưng request chờ vẫn được rút; lỗi của yêu cầu gắn với cuộc họp của nó (bản cũ: một biến chung hiện ở mọi cuộc họp tới khi có bắt đầu hoặc hủy thành công); ô ngôn ngữ nhớ lựa chọn của người dùng, không nhớ giá trị vừa vẽ (bản cũ ghi lại giá trị đang hiện mỗi lần vẽ); request chờ đọc từ sessionStorage một lần khi cuộc họp tải xong (bản cũ: mỗi lần vẽ khi bộ nhớ chưa có của cuộc họp đó); dòng "mất kết nối", "không tải được transcript mới" và kết quả sao chép giữ tới sự kiện task kế tiếp, khi lần tải lại cuộc họp xong hoặc khi rời cuộc họp (khi mở lại cùng cuộc họp, bản cũ xóa ngay lúc bấm; bản cũ: tới lần vẽ transcript kế tiếp, do bất kỳ nguyên nhân); body 2xx không phải object là lỗi rõ ràng (bản cũ: khi bắt đầu, `TypeError` hiện chữ lỗi của JS ở khối lỗi; khi hủy, task bị gỡ khỏi cuộc họp, nút Bắt đầu hiện và poll dừng, không báo lỗi; khi poll, task rỗng được vẽ rồi dòng "mất kết nối"); khóa tự chạy mà `removeItem` bị chặn thì vẫn chạy đúng một lần (bản cũ: không chạy); nút Hủy vẽ lại khi bấm nên `asr:meeting-context` có thêm một lần (cùng nội dung) lúc bấm hủy và lúc sao chép lệnh; thanh bên không còn dựng lại khi cuộc họp cùng id được thay bằng object mới (người dùng không thấy). Chuỗi `asr:meeting-context` phát cho `notes.js` khác ở số lần, giá trị cuối giống hệt; mỗi lần thêm là một lần `notes.js` đọc lại notes (`GET …/notes`): lúc bắt đầu phát `{inflight true, task trước đó}` rồi `{false, task nhận}` (bản cũ: thêm `{true, task nhận}` ở giữa); poll tới `succeeded` (có đọc lại cuộc họp) phát 3 lần (bản cũ 4), tới `canceled` như cũ; tải cuộc họp khôi phục request chờ từ sessionStorage thêm 1 lần; mở lại cuộc họp đang có dòng "mất kết nối", "không tải được transcript mới" hoặc kết quả sao chép thêm 1 lần; hủy lỗi hoặc thành công thêm 1 đến 2 lần, trước câu trả lời vẫn mang task cũ; bấm sao chép lệnh chẩn đoán phát 1 lần; lần poll hoặc đọc lại thất bại cũng phát, nên khi máy chủ mất kết nối, lần đọc notes kèm theo cũng lỗi và tab Notes hiện lỗi đọc tới lượt poll tốt kế tiếp (bản cũ: không phát, tab Notes không đổi). Tải lại cuộc họp giữa lúc task chạy (không có request chờ) như cũ. Giữ như cũ: nhịp 1000/3000 ms, thử lại 3000 ms, `transcriptionRequestInFlight` giữ `true` tới khi đọc lại cuộc họp xong, `asr:meeting-context` cho `notes.js` giữ hình dạng và thời điểm sau mỗi lần vẽ task.

#### Số đo trước và sau

Điều kiện đo: Node 24.13.0, `node --test tests/web/*.test.mjs`, một lần chạy cục bộ; lần gán đếm như mục "Nguyên nhân đo được". Sau: 0 trường task trong `legacy`, 0 tên `taskPollTimer`/`taskRequestInFlight` trong `history.js` (cùng biểu thức chính quy trên bản hiện tại); `selectRequestBusy` thay cho cờ.

| | Trước | Sau |
| --- | --- | --- |
| Lần gán trường task của `legacy` | 18 | 0 |
| Tên `*Timer`/`*InFlight` của phần task trong `history.js` | 2 (16 lần xuất hiện) | 0 |
| Unit test JS | 314 | 399 (85 cho core task), 0,1 s |
| `history.js` (dòng) | 3857 | 3588 |
| `history-core.js` (dòng) | 972 | 998 (`wc -l`) |
| `task-core.js` (dòng) | 0 | 501 (`wc -l`) |

Nguồn: `tests/web/task-core.test.mjs`, `tests/web/shell-view.test.mjs`.

#### Đánh đổi và phương án đã loại

- `shown` đóng dấu lên mọi action thay vì để lát `task` giữ bản sao của cuộc họp: một bản sao sẽ lệch khỏi `meeting.transcription.task` mà `history-core` giữ và `notes.js` đọc. Đổi lại mỗi action mang thêm một object nhỏ; reducer test dựng nó bằng một hàm cùng hình dạng.
- `legacy.rev` và `readyRev` đổi thành action trong view vì `history-core` không phát được action; phản ứng trực tiếp trên `history/meeting-requested` buộc `task-core` lặp lại phép chọn cuộc họp (địa chỉ, `popped`, `hash-changed`).
- Yêu cầu bắt đầu, hủy và đọc lại cuộc họp không bị hủy khi rời cuộc họp (server đã nhận; hủy giữa đường làm mất câu trả lời, nên request chờ rút chậm); khóa `task/start` dùng chung vì cờ cũ cũng dùng chung.
- Chữ trạng thái theo từng status và bảng nhãn giai đoạn ở lại view (`TASK_STAGES` còn được test tương thích đọc từ `history.js`).

#### Follow-up

- 4c (transcript) của #118, rồi `history.js` vào VIEWS; bỏ `legacy`, `editTranscription` đã bỏ ở 4b, còn `history/meeting-updated` cho transcript.
- Chuỗi "Chưa xác nhận được việc nhận tác vụ…" không còn hiện (dòng trạng thái giữ "Bản ghi đã lưu…" như bản cũ); `history.js` giữ nó làm literal chết để `test_i18n` không báo mục dư: xóa literal và bản tiếng Anh khi `i18n.js` mở ở pha 5.

#### Liên kết issue/PR

Issue #130; thuộc #118.

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
