---
status: accepted
---

# Frontend: core reducer thuần, effect là dữ liệu, store tự viết

Frontend (`src/asr_en_vi/web/`) là JS thuần dùng biến global, mỗi module giữ một object `state` sửa trực tiếp ở hàng trăm chỗ, lẫn với code DOM. Không có danh sách action hay hàm chuyển trạng thái; chống response cũ bằng các bộ đếm (`loadSeq`, `searchSeq`, `saveSeq`) và cờ `*InFlight` rải rác; giữa các module báo nhau bằng `CustomEvent` và hàm global. Muốn biết hết trạng thái hợp lệ phải đọc toàn bộ file, và không test được logic ngoài trình duyệt. Chọn kiến trúc dưới đây, áp dụng dần theo từng pha (issue #118); hành vi người dùng thấy không đổi.

**Các lớp.**

- **Core** của mỗi tính năng: `initialState`, `reduce(state, action) -> { state, effects }`, selector. Reducer thuần: không chạm DOM, `fetch`, timer, storage, `Date.now` hay `Math.random`; thời gian và id đi vào qua action. `effects` là tùy chọn (thiếu = rỗng).
- **Effect là dữ liệu**: object `{type, ...}`, reducer chỉ mô tả việc cần làm. Ba loại có sẵn, `key` bắt buộc ở cả ba (thiếu thì runner ném lỗi): `fetch` (`key`, `url`, `init`, `ok`, `error`, `meta`), `schedule` (`key`, `delay`, `action`) và `cancel` (`key`).
- **Runner** (`createRunner`) thực thi effect và dispatch kết quả về dạng action. `fetch`, `setTimeout`, `clearTimeout` được truyền vào nên test Node dùng bản giả.
- **View** chỉ đọc state, render DOM và gắn handler để dispatch action. Không giữ state riêng ngoài trạng thái DOM thuần (focus, scroll).
- **Store** (`createStore`, `combine`) trong `src/asr_en_vi/web/store.js`: `getState`, `dispatch`, `subscribe`. `combine` đưa mọi action tới mọi reducer của tính năng và nối các effect, nên giao tiếp giữa tính năng đi qua action dùng chung, thay cho `CustomEvent` và hàm global.

**Quy tắc.**

- Chỉ reducer tạo state mới. View và runner không gán vào state.
- Một effect mới có cùng `key` với effect đang chạy sẽ hủy effect cũ (hủy request hoặc xóa timer): bản mới nhất thắng. `cancel` hủy theo `key`.
- Chống response cũ nằm trong reducer: effect `fetch` mang `meta` (ví dụ id yêu cầu lưu trong state); runner gắn nguyên `meta` vào action kết quả; reducer bỏ action có id không khớp. Runner cũng không dispatch kết quả của request đã bị hủy hoặc thay thế.
- Kết quả `fetch`: mã 2xx thành `{type: ok, response: {status, body}, meta}`; mã lỗi HTTP hoặc lỗi mạng thành `{type: error, error: {message, status?, body?}, meta}`. Body được parse JSON, không phải JSON thì giữ nguyên text (không kiểm tra content-type). Request bị hủy **không** sinh action nào: hủy là chủ ý của reducer nên không cần báo lại.
- Dispatch khi đang xử lý (từ effect hoặc subscriber) được xếp hàng FIFO, không gọi lồng reducer. Subscriber được gọi một lần sau khi hàng đợi cạn, chỉ khi state đổi (so sánh identity).
- Lỗi trong reducer, effect hoặc subscriber: state giữ tới action cuối chạy thành công, hàng đợi bị bỏ, lỗi ném cho nơi gọi `dispatch`; với kết quả `fetch` nó hiện thành `unhandledRejection`.
- Loại effect mới (upload XHR có tiến độ, ghi storage...) thêm thành nhánh trong `createRunner`; reducer không đọc storage, giá trị đọc được vào state qua một action khởi động (boot).
- Đặt tên action theo sự kiện đã xảy ra (`meeting-opened`, `notes-loaded`, `notes-load-failed`), không theo lệnh gọi hàm.

**Lựa chọn nền.** ES modules (`<script type="module">`) để Node import được core; không framework, không build step, không dependency runtime, giữ CSP `script-src 'self'`. Test bằng `node --test` (`tests/web/`), chạy trong `scripts/check.sh` và CI. Store cố ý nhỏ: không middleware, devtools hay thư viện selector.

**Đánh đổi và phương án đã loại.**

- React/framework hoặc TypeScript/bundler: loại vì thêm build step và dependency; có thể đề xuất sau bằng ADR riêng.
- Giữ bộ đếm `*Seq`: loại vì quy tắc nằm rải rác và không test được độc lập.
- Dùng event bus chung thay cho action: loại vì không có state trung tâm để kiểm tra.
- Chi phí: viết thêm reducer và bảng chuyển trạng thái cho mỗi tính năng; chuyển từng pha để mỗi PR đủ nhỏ.
