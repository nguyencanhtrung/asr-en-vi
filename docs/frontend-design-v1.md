# Frontend design v1 — ASR EN VI

> **Cập nhật ngày 18/10/2026.** Tài liệu này tiếp tục là chuẩn cho kiến trúc thông tin và hành vi vận hành của phương án **A — Bàn biên tập**. Ngôn ngữ thị giác dark/teal cũ đã được thay thế bởi hệ editorial-engineering light/dark trong [`DESIGN.md`](../DESIGN.md); khi có xung đột về màu, font, bề mặt, radius, theme hoặc responsive, `DESIGN.md` là nguồn chuẩn.

Tài liệu này là chuẩn thiết kế frontend v1 để triển khai. [Đặc tả sản phẩm](specification-v1.md) quy định hành vi, dữ liệu, xác thực và phạm vi nghiệm thu; tài liệu này cụ thể hóa cách trình bày và tương tác. Việc duyệt thiết kế không có nghĩa backend, model, lưu trữ hoặc xác thực đã được triển khai.

## 1. Bản thiết kế được chọn

- Ứng dụng web dùng trên trình duyệt laptop/desktop; v1 truy cập qua localhost bằng token.
- Giao diện điều khiển bằng tiếng Việt, giữ các nhãn quen thuộc như **Transcript**, **Meeting notes**, **Speaker 1** và **English**. Nội dung notes viết bằng ngôn ngữ đầu ra đã chọn (English hoặc Tiếng Việt); transcript giữ ngôn ngữ đã nói.
- Bố cục chính gồm sidebar bên trái, transcript và notes cạnh nhau; trình phát là thanh dính ở mép trên vùng nội dung, luôn trong tầm nhìn khi cuộn.
- Light/dark theme áp dụng thống nhất cho màn hình duyệt, lịch, trang truy cập, các hộp thoại và thông báo. Mặc định theo hệ điều hành; lựa chọn thủ công được ghi nhớ trên trình duyệt.
- Phương án B/C chỉ là các phương án so sánh trong prototype. Frontend v1 triển khai phương án A; không có bộ chuyển bố cục A/B/C.
- Chưa chọn framework frontend, thư viện component hoặc cách tổ chức API trong tài liệu này.

### 1.1. Nguồn tham chiếu

- [Hướng dẫn chạy prototype](../prototype/ui/README.md).
- [Markup và tương tác](../prototype/ui/app.js), [stylesheet](../prototype/ui/styles.css).
- URL khi chạy server prototype: `http://localhost:8765/prototype/meeting-notes/?variant=A`.
- Hai ảnh dưới đây lưu trạng thái thiết kế đã duyệt ở viewport 1440 × 1000. Nội dung cuộc họp là dữ liệu mẫu. Thanh **PROTOTYPE** ở đáy ảnh là công cụ thử thiết kế, không thuộc frontend sản phẩm.

**Màn hình duyệt transcript và notes:**

![Phương án A: sidebar, transcript, notes và trình phát trên dark theme](assets/frontend-v1/meeting-review.png)

**Màn hình lịch sử theo tháng:**

![Lịch tháng lớn, lịch nhỏ trong sidebar và danh sách cuộc họp của ngày được chọn](assets/frontend-v1/meeting-calendar.png)

## 2. Bố cục và điều hướng

| Vùng | Nội dung và hành vi |
| --- | --- |
| Sidebar | Logo và tên phần mềm, chuyển theme, tìm kiếm, danh sách gần đây, lịch nhỏ, footer; cố định cao bằng viewport |
| Đầu vùng duyệt | Tên cuộc họp, trạng thái kết nối **OpenAI** và **Google** (hai nút riêng), nút **Lịch** ở màn hình hẹp và điểm vào tạo cuộc họp toàn cục; khi mở cuộc họp có thêm ngày, ngôn ngữ chính, thời lượng, trạng thái và thao tác xóa |
| Transcript | Danh sách đoạn phát biểu có người nói, timestamp, nội dung và thao tác sửa |
| Meeting notes | Notes theo ngôn ngữ đầu ra đã chọn, chọn bản notes, chỉnh sửa, tạo lại, copy và xuất Markdown |
| Trình phát | Phát/tạm dừng, vị trí hiện tại, tổng thời lượng và thanh tua; dùng chung cho cuộc họp đang mở. Thanh dính ở mép trên vùng nội dung khi cuộn, cao tối đa 72 px, chỉ gồm trình phát; tiêu đề và dòng hướng dẫn của khối bản ghi cuộn đi như bình thường |
| Lịch lớn | Thay vùng duyệt khi mở lịch; sidebar vẫn giữ nguyên để điều hướng |

Ở desktop, sidebar có chiều rộng tham chiếu **228 px** và cố định: cao đúng bằng viewport, đứng yên khi trang cuộn dù transcript dài, tự cuộn bên trong khi nội dung cao hơn viewport, với thanh cuộn mảnh và không bao giờ cuộn ngang; khi quá hẹp, lịch nhỏ đưa **Hôm nay** xuống hàng riêng để tên tháng luôn đọc đủ. Từ 680 px trở xuống nó là thanh trên cùng và cuộn cùng trang. Phần còn lại là vùng làm việc co giãn; trong màn hình duyệt, transcript chiếm khoảng **43%**, notes khoảng **57%** của vùng nội dung. Notes và transcript cuộn cùng trang; trình phát dính ở mép trên vùng nội dung (cao tối đa **72 px**, kể cả từ 680 px trở xuống) nên luôn nằm trong tầm nhìn và dùng được.

Ở màn hình lịch, phần tháng chiếm diện tích chính, danh sách ngày được chọn nằm bên phải với chiều rộng tham chiếu **240 px**. Với viewport từ 1150 px trở xuống, danh sách ngày chuyển xuống dưới lịch. Đây là bố cục đã có trong prototype, không phải một màn hình mới.

Kích thước trên là mốc tham chiếu khi triển khai; ưu tiên giữ thứ bậc, tỷ lệ và khả năng đọc/thao tác. Không sao chép cứng các kích thước chữ quá nhỏ hoặc khoảng trống dành riêng cho thanh công cụ prototype.

## 3. Ngôn ngữ thị giác

### 3.1. Màu sắc

Màu sắc dùng semantic tokens trong [`design-system.css`](../src/asr_en_vi/web/design-system.css) và được mô tả để tái sử dụng trong [`DESIGN.md`](../DESIGN.md). Light theme dùng nền giấy ấm và oxblood; dark theme dùng nền charcoal và dusty rose tương ứng. Success, warning và danger độc lập với màu nhận diện. Mỗi trạng thái cần có nhãn hoặc biểu tượng đi kèm; màu không phải dấu hiệu duy nhất.

### 3.2. Chữ, biểu tượng và bề mặt

- Newsreader Variable dùng cho tiêu đề; Inter Variable dùng cho điều khiển và nội dung chính; JetBrains Mono dùng cho timestamp, version và metadata kỹ thuật. Cả ba được self-host với Vietnamese subset.
- Dùng font có sẵn hoặc đóng gói cùng frontend; không tải font hay icon từ Internet trong runtime.
- Giữ mật độ gọn của prototype: tiêu đề rõ, metadata nhẹ hơn, phân cấp nội dung bằng cỡ chữ, độ đậm và khoảng cách.
- Icon nét đơn, đồng nhất; logo ứng dụng là biểu tượng sóng âm trong ô vuông bo góc. GitHub dùng biểu tượng GitHub riêng.
- Panel có viền hairline, radius 8 px; control dùng 4 px; hộp thoại dùng 12 px. Dùng khoảng trắng và đường phân cách nhẹ để chia nhóm.
- Hover, focus, disabled và selected phải phân biệt được trên nền tối. Hiệu ứng chuyển trạng thái ngắn, tôn trọng tùy chọn giảm chuyển động của trình duyệt.

## 4. Sidebar

Thứ tự từ trên xuống được chốt như sau:

1. Logo sóng âm và tên **ASR EN VI**, đồng thời là đường về workspace; nút chuyển light/dark nằm cùng hàng.
2. Ô **Tìm cuộc họp…**.
3. **Cuộc họp gần đây**: danh sách ngắn, mặc định tối đa ba cuộc họp có ngày, mới nhất trước. Mỗi mục có tên, ngày và thời lượng; mục đang mở có nền/viền lựa chọn.
4. Lịch tháng nhỏ nằm ngay dưới danh sách gần đây.
5. Footer ở đáy sidebar, tách bằng đường kẻ nhẹ.

Nút **Cuộc họp mới** ở đầu vùng duyệt là điểm vào tạo cuộc họp toàn cục. Trạng thái chào mừng trên workspace giữ CTA tạo cuộc họp theo ngữ cảnh, nên home có cả nút header và CTA chào mừng. Trên viewport từ 520 px trở xuống, nút header thu gọn thành biểu tượng nhưng vẫn giữ tên truy cập. Sidebar không lặp lại điểm vào toàn cục và không có mục **Cuộc họp** riêng vì wordmark đã là đường về workspace.

Đầu vùng duyệt có hai nút trạng thái kết nối riêng: **OpenAI** (provider ChatGPT) và **Google** (provider Antigravity). Mỗi nút gồm chấm trạng thái, tên và nhãn **Đã kết nối**, **Chưa kết nối**, **Cần đăng nhập lại** hoặc **Không khả dụng**, có tên truy cập nêu đúng provider của nó. Trạng thái của cả hai được đọc khi mở trang và cập nhật sau khi kết nối, ngắt kết nối, cần kết nối lại hoặc lỗi trong hộp thoại. Cả hai mở cùng một hộp thoại kết nối, bắt đầu từ trên cùng (**Google** cuộn tới phần **Google Antigravity** sau khi dữ liệu tải xong và chuyển focus vào tiêu đề phần đó) và trả focus về nút đã mở khi đóng. Từ 980 px trở xuống, hai nút xuống một hàng riêng dưới tiêu đề để không tràn ngang ở 360 px; nhãn trạng thái quá dài xuống dòng dưới tên thay vì bị cắt, kể cả ở 320 px.

Tìm kiếm theo tên trên toàn bộ lịch sử, không chỉ ba mục gần đây; hiện kết quả hoặc trạng thái không tìm thấy. Lịch là cách chính để duyệt các cuộc họp cũ theo thời gian, tránh buộc người dùng cuộn một danh sách gần đây dài.

Footer căn giữa theo chiều dọc: **chỉ biểu tượng GitHub**, phía dưới là **Version &lt;phiên bản&gt;**, ví dụ `Version 1.0`. Không có dòng “Mã nguồn …”. Icon dẫn tới [repository](https://github.com/nguyencanhtrung/asr-en-vi); dòng version dẫn tới [releases](https://github.com/nguyencanhtrung/asr-en-vi/releases). Cả hai chỉ mở trang bên ngoài khi người dùng chọn.

Icon GitHub phải có tên truy cập và tooltip dù không có text hiển thị. Version phản ánh bản ứng dụng thực tế; dùng **Version dev** khi chưa có version phát hành. `1.0` là ví dụ định dạng, không phải số release đã được công bố. Tên sản phẩm, URL repository và version lấy từ metadata dùng chung.

## 5. Lịch sử bằng lịch tháng

### 5.1. Lịch nhỏ

- Tuần bắt đầu từ thứ Hai, gồm bảy cột **T2–CN**. Ô ngày ngoài tháng hiển thị mờ hơn.
- Tiêu đề tháng/năm có nút trước/sau; cho chọn trực tiếp tháng, nhập/chọn năm và về **Hôm nay**.
- Ngày có cuộc họp được đánh dấu bằng số lượng từ dữ liệu đã lưu. Ngày hiện tại có viền; ngày được chọn có nền nhấn.
- Bấm một ngày hoặc **Chưa đặt ngày** để mở lịch lớn và chọn mục đó. Từ 680 px trở xuống lịch nhỏ ẩn đi; khi đó nút **Lịch** ở đầu vùng làm việc là lối vào duy nhất và mở tháng đang duyệt. Nút này ẩn ở màn hình rộng.
- Mục **Chưa đặt ngày** kèm số lượng luôn cho phép tìm các cuộc họp thiếu ngày.

### 5.2. Lịch lớn

- Tiêu đề **Lịch cuộc họp**, nút **Quay lại notes**, điều khiển tháng/năm và **Hôm nay**.
- Hiển thị tổng số cuộc họp trong tháng; tháng trống có thông báo rõ.
- Lưới tháng hiển thị tên cuộc họp trong từng ngày. Prototype hiển thị tối đa hai mục trong ô và nút `+N khác` để mở danh sách đầy đủ của ngày đó.
- Panel ngày được chọn hiển thị ngày, số lượng và toàn bộ cuộc họp của ngày. Mỗi cuộc họp có tên, thời lượng và trạng thái; chọn mục để mở đúng transcript/notes.
- Ngày trống và nhóm **Chưa đặt ngày** trống đều có thông báo phù hợp.
- **Quay lại notes** trở về cuộc họp đang mở trước khi duyệt lịch. Chọn trực tiếp một cuộc họp trong lịch chuyển sang cuộc họp đó.

### 5.3. Quy tắc dữ liệu và trạng thái

- Lịch nhỏ và lịch lớn dùng chung tháng/ngày đang chọn. Duyệt tháng hoặc năm không thay đổi metadata cuộc họp.
- Xếp lịch theo **ngày họp** người dùng cung cấp, không tự lấy ngày upload/xử lý. Không có ngày thì vào **Chưa đặt ngày**.
- Ngày họp là giá trị ngày, không tự lệch sang ngày khác do chuyển đổi UTC. UI trình bày theo dạng `dd/mm/yyyy` như prototype.
- Nhập/xóa cuộc họp cập nhật dấu ngày, số lượng và danh sách tương ứng. Frontend sản phẩm phải đọc dữ liệu thật từ backend.
- Không hiển thị giờ bắt đầu giả khi chỉ có ngày và thời lượng. Lịch v1 phục vụ duyệt lịch sử; không có đặt lịch tương lai, kéo thả đổi lịch hay đồng bộ Google Calendar.
- Duyệt lịch không làm mất chỉnh sửa đã lưu, tên người nói hoặc các bản notes. Khi có tác vụ đang chạy, vẫn thấy trạng thái và thao tác hủy trong màn hình lịch.

## 6. Duyệt transcript, người nói và notes

### 6.1. Transcript và trình phát

Mỗi đoạn transcript gồm nhãn/tên người nói, timestamp có thể bấm, nội dung và nút sửa. Đoạn chưa rõ được đánh dấu bằng amber và chỉ dẫn nghe lại. Đoạn nguồn đang được đối chiếu phải nổi bật để người dùng định vị được trong danh sách.

Bấm timestamp trong transcript tua trình phát tới đoạn đó và phát; mở nguồn từ notes chỉ tua tới mốc nguồn, không tự phát. Trình phát là thanh dính ở mép trên vùng nội dung, có phát/tạm dừng, thanh tua, thời gian hiện tại và tổng thời lượng. Trong sản phẩm, phát âm thanh từ bản sao đã lưu tại backend; dạng sóng và chuyển động trong prototype không chứng minh đã có phát âm thanh thật.

Khi audio đang phát và đoạn đang phát (`aria-current`) đổi, nếu còn thấy một phần danh sách đoạn trong vùng nhìn thấy bên dưới thanh trình phát thì đoạn đó được đưa vào tầm nhìn bằng cuộn gần nhất (`block: "nearest"`), dưới thanh trình phát; khi người dùng bật giảm chuyển động, cuộn tức thì. Không tự cuộn khi audio tạm dừng, trong 2 giây sau khi người dùng cuộn tay (con lăn, chạm, phím cuộn hoặc kéo thanh cuộn), khi focus đang nằm trong một ô sửa của transcript, hay khi cả danh sách đoạn nằm ngoài vùng nhìn thấy đó. Nhờ vậy người đang đọc notes không bị kéo về transcript, và mở nguồn từ notes giữ nguyên chỗ đang đọc: chỉ tua tới mốc nguồn và đánh dấu đoạn tương ứng. Mọi đích cuộn trong cuộc họp (đoạn transcript, tiêu đề nguồn notes) đều dừng dưới thanh trình phát, không nằm dưới nó. Trình duyệt cũng cuộn control nhận focus bàn phím xuống dưới thanh; riêng ô nhập văn bản có thể chỉ lộ dòng chứa con trỏ, nên một phần của ô vẫn có thể nằm dưới thanh trình phát.

Sửa một đoạn transcript bằng ô nhập tại đoạn đó, có lưu/bỏ qua. Sau khi lưu, notes hiện có được đánh dấu cần cập nhật; không tự thay nội dung notes.

Q24 bổ sung chọn lại người nói cho từng đoạn và thêm nhãn nếu thiếu; giữ nhãn model gán ban đầu để đối chiếu. Chỉ chỉnh ở thế hệ hiện tại, cùng khóa nguồn/kiểm tra phiên bản như sửa text. Timestamp và ranh giới đoạn giữ nguyên trong v1; đổi người nói một đoạn không đổi tên cả nhóm hoặc các đoạn khác.

Q20 yêu cầu lưu theo phiên bản đã đọc. Khi tab khác đã cập nhật cùng dữ liệu, giữ phần đang soạn và báo xung đột để người dùng đối chiếu với bản mới; không tự ghi đè hoặc trộn. Quy tắc cũng áp dụng cho tên người nói và nội dung cùng một bản notes.

Q21 yêu cầu có cách chọn thế hệ transcript: mặc định thế hệ mới nhất đã hoàn tất và lưu đầy đủ, các thế hệ trước chỉ đọc. Lần chạy mới chưa hoàn tất không thay mặc định; notes lỗi sau khi transcript đã lưu không làm mất bản mới. Cách trình bày bộ chọn này bổ sung sau prototype, chưa có UI được nghiệm thu.

Theo quyết định backend được chốt sau khi duyệt prototype, khi đang tạo notes cho cuộc họp này, UI khóa sửa transcript và tên người nói, giải thích lý do và vẫn cho đọc nguồn. Backend phải thực thi cùng điều kiện ở API; chỉ mở lại chỉnh sửa sau khi tác vụ đã kết thúc, không ngay khi vừa gửi yêu cầu hủy. Các bản notes đã có và các cuộc họp khác vẫn sửa được. Xem [backend design v1](backend-design-v1.md).

### 6.2. Tên người nói

- Mặc định dùng **Speaker 1**, **Speaker 2**, … theo từng cuộc họp.
- Nút **Tên người nói** ở đầu transcript hoặc bấm nhãn người nói mở hộp thoại nhập tên cho từng nhãn.
- Cho phép thêm, sửa, xóa tên; để trống thì dùng nhãn mặc định. Giữ nhãn gốc cạnh tên để đối chiếu.
- Tên chỉ áp dụng cho thế hệ transcript đang sửa của cuộc họp hiện tại. Lưu tên cập nhật transcript và đánh dấu notes cần cập nhật; thế hệ mới sau chạy lại dùng nhãn Speaker để đặt tên lại, không tự ghép tên với thế hệ cũ.
- Khi chủ động tạo lại notes, bản mới sử dụng tên đã đặt; các bản cũ và chỉnh sửa thủ công giữ nguyên.
- Tự học/nhận diện và điền tên từ dữ liệu training là **advanced feature ở phase sau**. V1 không có giao diện huấn luyện hoặc tự nhận diện danh tính.

### 6.3. Meeting notes

Panel **Meeting notes** có nhãn **EN**, thao tác **Tạo lại**, chọn bản notes, chỉnh sửa, copy và xuất Markdown. Nội dung có thứ bậc đọc rõ và các nhóm theo đặc tả: **Overview**, **Key Topics and Rationale**, **Decisions**, **Open Questions**, **Confirmed Action Items**, **Items Requiring Confirmation**.

Quyết định/action item có liên kết timestamp để đối chiếu. Các mục cần xác nhận được trình bày riêng với mức nhấn amber; không trộn với công việc đã thống nhất. Không tự đặt người phụ trách hoặc deadline còn thiếu.

Theo Q19, liên kết nguồn của một bản notes mở đúng bản chụp đã dùng lúc tạo, gồm văn bản, tên người nói và ngày họp trước các chỉnh sửa về sau. UI phải phân biệt đang xem nguồn cũ với transcript hiện tại; bản chụp chỉ đọc, vẫn nghe được mốc âm thanh tương ứng. Không đổi ngầm nguồn chỉ để khớp với transcript đang mở.

Chỉnh sửa notes mở hộp thoại rộng có vùng soạn thảo và nút lưu/bỏ qua. UI phân biệt bản đang xem, bản mới nhất, bản đã sửa thủ công và bản chưa phản ánh transcript/tên người nói mới. **Tạo lại** tạo bản mới; bản trước vẫn mở, copy và xuất được. Copy/xuất luôn dùng đúng bản đang chọn, kể cả chỉnh sửa của bản đó.

Nội dung soạn thảo là Markdown tự do theo [ADR 0005](adr/0005-markdown-notes.md). Khi lưu, thao tác luôn nhắm đúng bản notes đã mở trong trình soạn thảo, kể cả nếu một bản mới được tạo xong trong lúc người dùng đang sửa.

Q26 cho lưu nguyên văn Markdown chỉnh tay dù có tham chiếu nguồn hỏng. Hiển thị cảnh báo và vô hiệu thao tác mở nguồn ở link hỏng; không tự sửa hoặc dẫn sang nguồn khác. Copy/xuất vẫn lấy nội dung đã lưu, không thay bằng bản được ứng dụng tự sửa link.

### 6.4. Metadata cuộc họp

Q23 bổ sung sửa tên/ngày họp sau import. Đổi ngày, kể cả thêm/xóa ngày, cập nhật lịch và làm notes cần cập nhật; snapshot/notes cũ giữ ngày trước đó. Khóa thay đổi ngày trong lúc tạo notes; đổi riêng tên không thay nguồn notes. Lưu có kiểm tra phiên bản và giữ bản nháp khi xung đột. Ngôn ngữ gợi ý được chọn cho lần xử lý mới, không sửa lịch sử của thế hệ đã có.

Các thao tác sửa metadata/gán speaker là hành vi bổ sung sau prototype, chưa có UI sản phẩm đã kiểm thử.

## 7. Nhập bản ghi, truy cập và trạng thái tác vụ

| Luồng/trạng thái | Thiết kế và hành vi cần giữ khi triển khai |
| --- | --- |
| Chưa xác thực | Trang tối với logo/tên sản phẩm, hướng dẫn mở link từ terminal và ô nhập token; lỗi token có thông báo, không lộ dữ liệu cuộc họp |
| Link có token hợp lệ | Vào ứng dụng, giữ phiên bằng cookie và loại token khỏi thanh địa chỉ theo đặc tả |
| Chưa có cuộc họp | Trạng thái trống có hành động tạo cuộc họp; lịch không có dấu ngày giả |
| Cuộc họp mới | Hộp thoại có vùng kéo thả/chọn audio hoặc video, tên cuộc họp, ngôn ngữ chính **Tiếng Việt/English**, ngày họp tùy chọn, ô **Chép lời ngay sau khi tạo** và một nút chính **Tạo cuộc họp**; luồng chọn/kết nối provider notes bổ sung theo mục 7.1. Chọn file thì tên được điền sẵn từ tên file (bỏ phần mở rộng, tối đa 200 ký tự) cho tới khi người dùng tự gõ; ngôn ngữ mặc định là lựa chọn lần trước nếu có; ô chép lời bật sẵn và nhớ lựa chọn cuối trong trình duyệt |
| Chọn nơi tạo notes | Có **ChatGPT** và **Google Antigravity qua OMP**; chọn bên nào thì kết nối bên đó, không bắt buộc cả hai |
| Đang upload | Bấm **Tạo cuộc họp** chạy liền tải lên → kiểm tra → tạo theo máy trạng thái hiện có, không có bước tải lên riêng; nếu file đã được kiểm tra thì chỉ tạo. Tiến độ upload riêng; nhãn trạng thái bằng tiếng Việt (**Đang tải lên**, **Đang kiểm tra**, **Sẵn sàng tạo**, …), không hiện mã kỹ thuật như `IDLE`. **Hủy tải lên** dừng lượt đang chạy; upload bị ngắt báo chưa hoàn tất và cho **Tải lại từ đầu** (chạy lại cả luồng với file đã chọn) hoặc chọn file khác. Khi lỗi, form giữ nguyên dữ liệu; lỗi tạo cho **Thử tạo lại**, còn khi chưa biết cuộc họp đã được tạo hay chưa thì nút chính thành **Xác minh và thử lại** để gửi lại đúng yêu cầu |
| Tạo xong, tự chép lời | Khi ô **Chép lời ngay sau khi tạo** đang bật, trang cuộc họp vừa mở gửi yêu cầu chép lời đúng một lần; tải lại trang hoặc Back không gửi lại. Khi tắt, người dùng tự bấm **Bắt đầu chép lời** |
| Đang xử lý/tạo lại notes | Hiển thị giai đoạn, tiến độ do backend cung cấp và nút hủy; chỉ một tác vụ tại một thời điểm |
| Backend đang bận | Giải thích vì sao chưa bắt đầu được tác vụ mới; vẫn cho xem/sửa cuộc họp đã hoàn tất, không tạo hàng đợi ẩn. Nếu lần tự chép lời sau khi tạo gặp máy bận hoặc worker/model chưa sẵn sàng, cuộc họp vẫn được lưu, trang nêu lý do cùng nút **Bắt đầu chép lời** và không tự thử lại |
| Đã sẵn sàng | Mở transcript và notes để duyệt; không diễn đạt bản nháp là nội dung chắc chắn đúng |
| Đã có transcript, chưa có notes | Cho đọc/sửa/nghe lại transcript và chủ động tạo notes sau; tác vụ đã kết thúc, không giữ trạng thái đang xử lý để chờ đăng nhập/quota |
| Provider cần kết nối lại hoặc hết quota | Nêu bên được chọn và nguyên nhân, cho kết nối lại/chọn bên khác rồi chủ động tạo notes; không tự chuyển provider |
| Lỗi mạng khi tạo notes | Báo lỗi và cho chủ động thử lại; giữ transcript/notes cũ, không thể hiện hệ thống đang tự gửi lại request hoặc tự đổi provider/model |
| Lỗi/đã hủy/bị gián đoạn | Phân biệt trạng thái, nêu vấn đề và đường thử lại phù hợp; không hiển thị là đã hoàn tất hoặc tự chạy lại |
| Mất kết nối trình duyệt | Thông báo mất kết nối; khi kết nối lại, lấy trạng thái hiện tại từ backend. Đóng tab không hủy tác vụ đã được nhận |
| Xóa cuộc họp | Hộp thoại nêu tên cuộc họp, nút giữ lại/xóa; cuộc họp đang có tác vụ phải hủy và chờ backend xác nhận đã dừng trước khi xóa. Xóa dữ liệu ứng dụng quản lý theo đặc tả, không xóa file nguồn bên ngoài |
| Lưu/copy/xuất | Phản hồi thành công hoặc lỗi rõ ràng; không báo đã lưu thành công trước khi backend xác nhận |

Giữ lời nhắc trong form nhập: **Transcript giữ nguyên ngôn ngữ đã nói. Meeting notes viết bằng ngôn ngữ đầu ra đã chọn (English hoặc Tiếng Việt).** Định dạng và giới hạn file phải phản ánh khả năng backend đã công bố; không lấy `audio/*,video/*` trong prototype làm cam kết hỗ trợ mọi codec.

QR/link truy cập được cung cấp từ terminal. Không hiển thị token dùng chung hoặc cơ chế tự cấp quyền ở trang chưa xác thực. Chi tiết theo [ADR về token](adr/0002-localhost-reusable-token.md); không bổ sung tài khoản/mật khẩu hoặc quản lý nhiều người dùng trong v1.

### 7.1. Kết nối provider notes — phạm vi bổ sung sau prototype

Q12 bổ sung lựa chọn **ChatGPT** hoặc **Google Antigravity qua OMP** cho mỗi lần xử lý có tạo notes và mỗi lần tạo lại notes. Người dùng chọn một bên, dùng lại phiên đã lưu hoặc kết nối tài khoản bên đó từ UI. Tạo lại có thể chọn provider khác, vẫn tạo bản notes mới và giữ bản cũ. Không cố định Google làm mặc định toàn hệ thống.

Q27 bổ sung chọn model, nhớ provider gần nhất và model riêng mỗi bên; UI hiển thị rõ lựa chọn trước khi bắt đầu. Khi đổi preference trong lúc một tác vụ chạy, ghi rõ áp dụng cho lần sau, không đổi cấu hình của tác vụ hiện tại. Model đã nhớ mất quyền/quota phải báo để người dùng chọn lại; không âm thầm thay model.

Đây là kết nối dịch vụ AI sau khi đã vào ứng dụng bằng token localhost, không thay màn hình truy cập ứng dụng. Trạng thái từng provider hiện ở hai nút **OpenAI** (ChatGPT) và **Google** (Antigravity) trên đầu vùng làm việc; cả hai mở hộp thoại kết nối. UI cần thể hiện rõ transcript và thông tin nguồn cần thiết sẽ gửi tới bên được chọn; âm thanh và ASR vẫn local. Notes mới cần Internet, trong khi dữ liệu đã lưu vẫn đọc/sửa/nghe lại/copy/xuất được khi mất mạng.

Q13–Q15 đã chốt: lưu một tài khoản/phiên mỗi provider trên bản cài, có nút ngắt kết nối, chỉ đăng nhập lại khi cần. Provider chưa sẵn sàng vẫn cho chép lời local, lưu transcript rồi kết thúc tác vụ. Khi notes lỗi/quota, giữ dữ liệu và cho người dùng chủ động chọn bên khác rồi chạy lại; không tự chuyển provider hay bật API billing. Đăng nhập lại không tự tạo notes từ transcript đang chờ.

Q22 chặn ngắt/đổi tài khoản của provider đã chọn cho tác vụ đang hoạt động, kể cả trước bước notes; hướng dẫn hủy rồi chờ backend xác nhận dừng. Provider không thuộc tác vụ vẫn có thể ngắt. Backend phải thực thi cùng điều kiện, không chỉ vô hiệu nút trên UI.

Vị trí/nội dung hộp thoại kết nối chưa có trong prototype đã duyệt; không coi hình thức UI mới là đã được nghiệm thu. Ràng buộc Antigravity được ghi tại [ADR 0007](adr/0007-cloud-notes-providers.md).

## 8. Khả năng sử dụng và kích thước màn hình

- Nghiệm thu trên Chrome và Firefox bản ổn định ở laptop/desktop. Các mốc tham chiếu đã xem trong prototype là **1440 × 1000**, **1280 × 800** và **1024 × 768**.
- Ở các kích thước đó, không tràn ngang toàn trang; sidebar và công cụ chính vẫn truy cập được. Nội dung dài cuộn cùng trang và không bị trình phát hoặc thanh cố định che mất: đoạn được cuộn tới luôn nằm dưới thanh trình phát, còn control nhận focus bàn phím được cuộn xuống dưới thanh (ô nhập văn bản có thể chỉ lộ dòng chứa con trỏ).
- Giữ hai cột transcript/notes khi đủ chỗ. Với chiều rộng nhỏ hơn, xếp dọc và giữ đầy đủ control/trạng thái; mobile là viewport được nghiệm thu, không được tạo tràn ngang.
- Nút chỉ có icon phải có tên truy cập. Ô nhập/select có label. Focus bàn phím rõ; thứ tự Tab hợp lý, hộp thoại giữ focus và có cách đóng bằng bàn phím.
- Dùng chữ hoặc biểu tượng đi cùng màu để phân biệt ngày có cuộc họp, ngày được chọn, trạng thái tác vụ và cảnh báo.
- Nội dung người dùng nhập phải được hiển thị an toàn. Tên dài, notes dài và nhiều cuộc họp cùng ngày không được làm vỡ bố cục hoặc mất đường truy cập nội dung đầy đủ.

## 9. Ranh giới prototype và frontend sản phẩm

Thiết kế đã chốt; code prototype vẫn là bản thử dùng để đối chiếu, không mặc nhiên trở thành nền tảng production. Các hành vi lưu dữ liệu, upload, phát âm thanh, model, tiến độ và token phải được nối với backend thật và nghiệm thu riêng.

Các thành phần chỉ phục vụ prototype phải được loại khỏi frontend sản phẩm:

- Thanh **PROTOTYPE**, chuyển A/B/C, bảng trạng thái nội bộ, nút reset dữ liệu mẫu và mở phiên demo.
- Dữ liệu cuộc họp mẫu, nhãn **Dữ liệu minh họa**, nút **Dùng bản ghi mẫu để thử** và token `demo-local`.
- Tiến độ theo bộ đếm mô phỏng, playback không có âm thanh và trạng thái chỉ lưu trong bộ nhớ rồi mất khi refresh.
- Khoảng đệm chỉ để tránh thanh công cụ thử thiết kế ở đáy trang.

Prototype hiện có không chứng minh các trạng thái backend trong mục 7 đã hoạt động. Khi triển khai, giữ thiết kế đã duyệt và thay các mô phỏng bằng hành vi thật theo [đặc tả v1](specification-v1.md).

## 10. Tiêu chí đối chiếu frontend

| Mã | Điều kiện đạt |
| --- | --- |
| FE-01 | Bố cục A và hệ editorial-engineering light/dark thống nhất, có sidebar, transcript/notes cạnh nhau và trình phát; đối chiếu AC-29 |
| FE-02 | Brand là ASR EN VI; footer chỉ có icon GitHub và dòng Version ngắn, đúng metadata bản chạy |
| FE-03 | Danh sách gần đây gọn, tìm kiếm toàn lịch sử, lịch nhỏ ngay dưới danh sách và mở được lịch lớn |
| FE-04 | Lịch nhỏ/lớn đồng bộ; xử lý tháng/năm cũ, tháng 12 sang tháng 1, năm nhuận, tháng trống, nhiều cuộc họp cùng ngày và thiếu ngày; đối chiếu AC-30 |
| FE-05 | Mở đúng cuộc họp từ lịch, dấu ngày cập nhật sau nhập/xóa; điều hướng giữ nguyên metadata và chỉnh sửa đã lưu |
| FE-06 | Đặt/sửa/xóa tên người nói riêng từng cuộc họp; giữ nhãn gốc và không ghi đè notes cũ; đối chiếu AC-28 |
| FE-07 | Timestamp dẫn tới nguồn, chỉnh sửa làm notes cần cập nhật, tạo lại có bản mới, copy/xuất đúng bản chọn; đối chiếu AC-05/07/11 |
| FE-08 | Upload, xử lý, bận, hủy, lỗi và gián đoạn được thể hiện đúng; đóng tab không làm frontend suy diễn tác vụ đã hủy; đối chiếu AC-12/16/19/20/21 |
| FE-09 | Dùng được bằng bàn phím và ở ba viewport tham chiếu; không để nội dung/công cụ bị che hoặc tràn ngang, kể cả khi trình phát dính ở mép trên |
| FE-10 | Không có UI dành riêng cho demo; hoạt động với backend và lưu trữ thật, kiểm soát token và đóng gói sẵn tài nguyên UI; kết nối provider notes theo lựa chọn của người dùng, đối chiếu AC-10/15/22/23 |
| FE-11 | Chọn và kết nối riêng ChatGPT hoặc Google Antigravity qua OMP từ UI, không buộc đăng nhập cả hai; phân biệt kết nối provider với token localhost, đối chiếu AC-35 |
| FE-12 | Dùng lại phiên provider; thể hiện đúng đã có transcript/chưa có notes và lỗi/quota; đổi bên rồi chạy lại là thao tác chủ động, đối chiếu AC-36/37/38 |
| FE-13 | Notes cũ mở đúng bản chụp nguồn, có phân biệt với transcript hiện tại; xung đột ghi giữ bản nháp chưa lưu, đối chiếu AC-41/42 |
| FE-14 | Chọn đúng thế hệ transcript, bản cũ chỉ đọc và không tự ghép tên người nói; chặn ngắt/đổi provider đang dùng, đối chiếu AC-43/44 |
| FE-15 | Sửa tên/ngày và gán speaker từng đoạn theo version/khóa nguồn; bảo toàn snapshot, original assignment và lịch sử ngôn ngữ, đối chiếu AC-45/46 |
| FE-16 | Báo lỗi mạng không tự retry, cho lưu link chỉnh tay hỏng có cảnh báo và chọn/nhớ model rõ ràng, đối chiếu AC-47/48/49 |

Việc chốt tài liệu này xác nhận hướng thiết kế. Các tiêu chí trên là điều kiện kiểm tra frontend khi triển khai, không phải báo cáo nghiệm thu sản phẩm đã hoàn thành.
