# Frontend design v1 — ASR EN VI

> **Cập nhật ngày 18/10/2026.** Tài liệu này tiếp tục là chuẩn cho kiến trúc thông tin và hành vi vận hành của phương án **A — Bàn biên tập**. Ngôn ngữ thị giác dark/teal cũ đã được thay thế bởi hệ editorial-engineering light/dark trong [`DESIGN.md`](../DESIGN.md); khi có xung đột về màu, font, bề mặt, radius, theme hoặc responsive, `DESIGN.md` là nguồn chuẩn.

Tài liệu này là chuẩn thiết kế frontend v1 để triển khai. [Đặc tả sản phẩm](specification-v1.md) quy định hành vi, dữ liệu, xác thực và phạm vi nghiệm thu; tài liệu này cụ thể hóa cách trình bày và tương tác. Việc duyệt thiết kế không có nghĩa backend, model, lưu trữ hoặc xác thực đã được triển khai.

## 1. Bản thiết kế được chọn

- Ứng dụng web dùng trên trình duyệt laptop/desktop; v1 truy cập qua localhost bằng token.
- Giao diện điều khiển bằng tiếng Việt, giữ các nhãn quen thuộc như **Transcript**, **Meeting notes**, **Speaker 1** và **English**. Nội dung notes viết bằng ngôn ngữ đầu ra đã chọn (English hoặc Tiếng Việt); transcript giữ ngôn ngữ đã nói.
- Bố cục chính gồm sidebar bên trái và vùng làm việc. Trang cuộc họp chia hai tab, **Meeting notes** và **Transcript & bản ghi**; trình phát là thanh dính ở mép trên tab Transcript & bản ghi, luôn trong tầm nhìn khi cuộn transcript.
- Light/dark theme áp dụng thống nhất cho màn hình duyệt, lịch, trang truy cập, các hộp thoại và thông báo. Mặc định theo hệ điều hành; lựa chọn thủ công được ghi nhớ trên trình duyệt.
- Phương án B/C chỉ là các phương án so sánh trong prototype. Frontend v1 triển khai phương án A; không có bộ chuyển bố cục A/B/C.
- Chưa chọn framework frontend, thư viện component hoặc cách tổ chức API trong tài liệu này.

### 1.1. Nguồn tham chiếu

- [Hướng dẫn chạy prototype](../prototype/ui/README.md).
- [Markup và tương tác](../prototype/ui/app.js), [stylesheet](../prototype/ui/styles.css).
- URL khi chạy server prototype: `http://localhost:8765/prototype/meeting-notes/?variant=A`.
- Hai ảnh dưới đây lưu trạng thái thiết kế đã duyệt ở viewport 1440 × 1000. Nội dung cuộc họp là dữ liệu mẫu. Thanh **PROTOTYPE** ở đáy ảnh là công cụ thử thiết kế, không thuộc frontend sản phẩm.

**Màn hình duyệt transcript và notes** (prototype ban đầu: transcript và notes ở hai vùng cạnh nhau; sản phẩm tách thành hai tab, xem mục 6.0):

![Phương án A: sidebar, transcript, notes và trình phát trên dark theme](assets/frontend-v1/meeting-review.png)

**Màn hình lịch sử theo tháng:**

![Lịch tháng lớn, lịch nhỏ trong sidebar và danh sách cuộc họp của ngày được chọn](assets/frontend-v1/meeting-calendar.png)

## 2. Bố cục và điều hướng

| Vùng | Nội dung và hành vi |
| --- | --- |
| Sidebar | Logo và tên phần mềm, chuyển theme, tìm kiếm, danh sách gần đây, lịch nhỏ, footer; cố định cao bằng viewport |
| Đầu vùng duyệt | Tiêu đề chung **Cuộc họp**, trạng thái kết nối **OpenAI** và **Google** (hai nút riêng), nút **Lịch** ở màn hình hẹp và điểm vào tạo cuộc họp toàn cục |
| Đầu trang cuộc họp | Tên cuộc họp (chỉ hiện một lần, không lặp ở tiêu đề chung), nút **Sửa tên và ngày**, ngày họp, gợi ý ngôn ngữ và dải trạng thái ngắn **Bản ghi · Transcript · Notes** |
| Hai tab | Danh sách tab **Meeting notes** và **Transcript & bản ghi** ngay dưới phần đầu trang (mục 6.0); mỗi lúc chỉ một tab hiện |
| Tab Transcript & bản ghi: transcript | Khối chép lời (nút chép lời/hủy, tiến độ, lỗi), danh sách đoạn ở chế độ đọc (timestamp, người nói, nội dung, dấu cần kiểm tra), danh sách người nói dạng chip và nút **Sửa** mở ô sửa của từng đoạn |
| Tab Meeting notes | Notes theo ngôn ngữ đầu ra đã chọn, nút tạo notes nêu lựa chọn đã lưu cùng **Đổi…**, lời nhắc đặt tên người nói, tiến độ và lỗi tạo notes, chọn bản notes, **Xem \| Viết**, **Tạo lại notes**, copy và xuất Markdown; khi chưa có transcript chỉ có trạng thái trống **Cần transcript trước** |
| Trình phát | Phát/tạm dừng, vị trí hiện tại, tổng thời lượng và thanh tua; nằm trong tab Transcript & bản ghi. Thanh dính ở mép trên vùng nội dung khi cuộn, cao tối đa 72 px, chỉ gồm trình phát; tiêu đề và dòng hướng dẫn của khối bản ghi cuộn đi như bình thường |
| Lịch lớn | Thay vùng duyệt khi mở lịch; sidebar vẫn giữ nguyên để điều hướng |

Ở desktop, sidebar có chiều rộng tham chiếu **228 px** và cố định: cao đúng bằng viewport, đứng yên khi trang cuộn dù transcript dài, tự cuộn bên trong khi nội dung cao hơn viewport, với thanh cuộn mảnh và không bao giờ cuộn ngang; khi quá hẹp, lịch nhỏ đưa **Hôm nay** xuống hàng riêng để tên tháng luôn đọc đủ. Từ 680 px trở xuống nó là thanh trên cùng và cuộn cùng trang. Phần còn lại là vùng làm việc co giãn; trong màn hình duyệt, tab đang chọn dùng toàn bề rộng vùng nội dung. Tab cuộn cùng trang; trong tab Transcript & bản ghi, trình phát dính ở mép trên vùng nội dung (cao tối đa **72 px**, kể cả từ 680 px trở xuống) nên luôn nằm trong tầm nhìn và dùng được.

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

### 6.0. Trang cuộc họp hai tab

Trang cuộc họp có hai tab theo mẫu WAI-ARIA Tabs (`role` tablist/tab/tabpanel, `aria-selected`, `aria-controls`) ngay dưới phần đầu trang: **Meeting notes** (kết quả chính) và **Transcript & bản ghi** (trình phát và transcript đi cùng nhau để đối chiếu).

- **Điều khiển:** chỉ tab đang chọn nằm trong thứ tự Tab; mũi tên trái/phải đổi tab (vòng qua đầu/cuối), Home và End nhảy tới tab đầu/cuối, và tab được chọn ngay khi nhận focus.
- **Nội dung:** tab Transcript & bản ghi chứa khối bản ghi (trình phát dính), khối chép lời, người nói và các đoạn; khi đã có transcript, nhãn tab ghi số đoạn và số đoạn cần kiểm tra (đoạn hiện dấu **Cần kiểm tra** hoặc **Nên nghe lại**) của thế hệ transcript đang hiển thị. Tab Meeting notes chứa toàn bộ phần notes (tạo, tiến độ, lỗi, phiên bản, **Xem | Viết**, sao chép, tải về) cùng khung nguồn đã lưu.
- **Tab mở sẵn:** không có hash thì chọn Meeting notes nếu cuộc họp có ít nhất một bản notes đã lưu hoặc đang tạo notes, ngược lại chọn Transcript & bản ghi. Link nguồn `?notes_source=…&segment=…` không kèm hash mở Meeting notes. Hash luôn thắng. Trước khi biết cuộc họp có notes hay không (tối đa bốn giây), chưa tab nào được chọn: khung notes ẩn còn khung transcript đã có đủ control nhưng trong suốt, để không khung nào bị nháy; cái giá là trong khoảng chờ ngắn đó các control trong suốt ấy vẫn nhận được focus bàn phím mà không có viền focus nhìn thấy.
- **Địa chỉ:** `#notes` và `#transcript` chọn tab tương ứng. Đổi tab là một mục lịch sử mới (`pushState`, giữ đường dẫn và query), nên Back quay lại tab trước, Forward đi tiếp và tải lại trang giữ tab. Mục lịch sử bị rời đi nhớ tab đang hiện, nên Back đúng tab kể cả khi quy tắc mặc định đã đổi. Route `/meetings/{id}` và API không đổi.
- **Chưa có transcript:** tab Meeting notes chỉ hiện **Cần transcript trước**, một dòng nói transcript đang được tạo hay chưa chạy, và nút chuyển sang tab Transcript & bản ghi; không có ô chọn hay nút tạo notes bị tắt.
- **Tạo notes:** bấm tạo notes ở bất kỳ đâu đều chọn tab Meeting notes để theo dõi tiến độ. Nút **Tua bản ghi tới mốc này** của khung nguồn tua rồi mở tab Transcript & bản ghi (focus ở tab) vì trình phát nằm ở đó; mở nguồn từ link hoặc từ notes không đổi tab.
- **Đầu trang:** tên cuộc họp chỉ hiện một lần; dải trạng thái ngắn **Bản ghi · Transcript · Notes** nằm trong phần đầu trang. Từ 680 px trở xuống, danh sách tab nằm ngay dưới phần đầu trang và hai nút trạng thái **OpenAI** và **Google** giữ nguyên.

### 6.1. Transcript và trình phát

Transcript mặc định ở chế độ đọc để nghe và đọc nhanh. Mỗi đoạn gồm timestamp có thể bấm, tên người nói, nội dung (từ 13 px) và nút **Sửa** luôn hiện, không phụ thuộc hover; chưa có ô nhập, select hay nút lưu nào. Đoạn chưa rõ được đánh dấu bằng amber, nhãn **Cần kiểm tra** kèm lý do và chỉ dẫn nghe lại. Đoạn nguồn đang được đối chiếu phải nổi bật để người dùng định vị được trong danh sách. Mỗi đoạn ở chế độ đọc có tối đa hai điểm dừng Tab: timestamp và **Sửa**.

Bấm timestamp trong transcript tua trình phát tới đoạn đó và phát; mở nguồn từ notes chỉ tua tới mốc nguồn, không tự phát. Trình phát là thanh dính ở mép trên vùng nội dung của tab Transcript & bản ghi, có phát/tạm dừng, thanh tua, thời gian hiện tại và tổng thời lượng. Chọn tab Meeting notes ẩn thanh này nhưng không tạm dừng audio, để vừa nghe vừa đọc notes; muốn dừng thì quay lại tab Transcript & bản ghi. Trong sản phẩm, phát âm thanh từ bản sao đã lưu tại backend; dạng sóng và chuyển động trong prototype không chứng minh đã có phát âm thanh thật.

Khi audio đang phát và đoạn đang phát (`aria-current`) đổi, nếu còn thấy một phần danh sách đoạn trong vùng nhìn thấy bên dưới thanh trình phát thì đoạn đó được đưa vào tầm nhìn bằng cuộn gần nhất (`block: "nearest"`), dưới thanh trình phát; khi người dùng bật giảm chuyển động, cuộn tức thì. Không tự cuộn khi audio tạm dừng, trong 2 giây sau khi người dùng cuộn tay (con lăn, chạm, phím cuộn hoặc kéo thanh cuộn), khi focus đang nằm trong một ô sửa của transcript, hay khi cả danh sách đoạn nằm ngoài vùng nhìn thấy đó, kể cả khi danh sách đang ẩn vì tab Meeting notes đang mở. Nhờ vậy người đang đọc notes không bị kéo về transcript, và mở nguồn từ notes giữ nguyên chỗ đang đọc: chỉ tua tới mốc nguồn và đánh dấu đoạn tương ứng. Mọi đích cuộn trong tab Transcript & bản ghi (đoạn transcript) đều dừng dưới thanh trình phát, không nằm dưới nó; tab Meeting notes không ghim thanh nào nên không để dành chỗ. Trình duyệt cũng cuộn control nhận focus bàn phím xuống dưới thanh; riêng ô nhập văn bản có thể chỉ lộ dòng chứa con trỏ, nên một phần của ô vẫn có thể nằm dưới thanh trình phát.

Bấm **Sửa** mở ô sửa tại đoạn đó, gồm ô nội dung, select người nói, **Lưu đoạn** và **Hủy**; chỉ một ô sửa mở tại một lúc. Esc là hủy, Ctrl/⌘+Enter (từ bất kỳ control nào trong ô) là lưu; sau khi lưu hoặc hủy, focus quay lại nút **Sửa** của đoạn đó. Mở đoạn khác đóng ô đang mở nhưng giữ văn bản chưa lưu trong cơ chế bản nháp của transcript; đoạn có bản nháp hiện dấu **Bản nháp chưa lưu** (chữ cùng viền nét đứt, không chỉ màu). Mục **Chi tiết** trong ô sửa chứa **Gán ban đầu** và các chỉ số model (`avg_logprob`, `no_speech_prob`, `compression_ratio`); ở chế độ đọc chúng không hiện (thế hệ cũ chỉ đọc, không có ô sửa, nên giữ mục này đóng sẵn ở mỗi đoạn). Thông báo **Đã lưu** của mọi đoạn đi qua một vùng `aria-live` chung, không có vùng riêng cho từng đoạn. Sau khi lưu, notes hiện có được đánh dấu cần cập nhật; không tự thay nội dung notes.

Q24 bổ sung chọn lại người nói cho từng đoạn (select trong ô sửa, lưu ngay khi đổi) và thêm nhãn nếu thiếu; giữ nhãn model gán ban đầu để đối chiếu trong mục **Chi tiết**. Chỉ chỉnh ở thế hệ hiện tại, cùng khóa nguồn/kiểm tra phiên bản như sửa text. Timestamp và ranh giới đoạn giữ nguyên trong v1; đổi người nói một đoạn không đổi tên cả nhóm hoặc các đoạn khác.

Q20 yêu cầu lưu theo phiên bản đã đọc. Khi tab khác đã cập nhật cùng dữ liệu, giữ phần đang soạn và báo xung đột để người dùng đối chiếu với bản mới; không tự ghi đè hoặc trộn. Quy tắc cũng áp dụng cho tên người nói và nội dung cùng một bản notes. Esc và **Hủy** vẫn giữ bản nháp đã bị đánh dấu xung đột (nội dung đoạn hoặc tên người nói): ô đóng lại, đoạn (hoặc chip) vẫn mang dấu bản nháp, và mở lại sẽ khôi phục bản nháp cùng khung đối chiếu. Nút **Tải lại bản mới nhất** nằm trong ô sửa khi ô đang mở và chuyển lên khung báo xung đột phía trên transcript khi ô đã đóng, cho đến khi người dùng tải bản mới.

Q21 yêu cầu có cách chọn thế hệ transcript: mặc định thế hệ mới nhất đã hoàn tất và lưu đầy đủ, các thế hệ trước chỉ đọc. Lần chạy mới chưa hoàn tất không thay mặc định; notes lỗi sau khi transcript đã lưu không làm mất bản mới. Cách trình bày bộ chọn này bổ sung sau prototype, chưa có UI được nghiệm thu.

Theo quyết định backend được chốt sau khi duyệt prototype, khi đang tạo notes cho cuộc họp này, UI khóa sửa transcript và tên người nói (nút **Sửa** và chip người nói bị tắt, kèm lý do gắn vào từng nút), vẫn cho đọc nguồn; ở ô sửa đang mở, nội dung, select và **Lưu đoạn** bị tắt, còn **Hủy** vẫn dùng được. Backend phải thực thi cùng điều kiện ở API; chỉ mở lại chỉnh sửa sau khi tác vụ đã kết thúc, không ngay khi vừa gửi yêu cầu hủy. Các bản notes đã có và các cuộc họp khác vẫn sửa được. Xem [backend design v1](backend-design-v1.md).

### 6.2. Tên người nói

- Mặc định dùng **Speaker 1**, **Speaker 2**, … theo từng cuộc họp.
- Mục **Người nói trong phiên bản này** ở đầu transcript hiện mỗi người nói thành một chip; chip còn tên mặc định do hệ thống đặt (**Speaker N**) có dấu **đặt tên**. Bấm chip mở ô đổi tên ngay tại chỗ, không phải hộp thoại: Enter lưu, Esc hủy. Chỉ một ô đổi tên mở tại một lúc; tên đang gõ ở ô vừa rời đi được giữ làm bản nháp (chip hiện dấu **bản nháp**).
- Cho phép thêm người nói, sửa tên và **Khôi phục tên mặc định**; để trống thì dùng nhãn mặc định. Ô đổi tên hiện nhãn gốc để đối chiếu. Ở thế hệ cũ, chip chỉ để đọc.
- Tên chỉ áp dụng cho thế hệ transcript đang sửa của cuộc họp hiện tại. Lưu tên cập nhật transcript và đánh dấu notes cần cập nhật; thế hệ mới sau chạy lại dùng nhãn Speaker để đặt tên lại, không tự ghép tên với thế hệ cũ.
- Khi chủ động tạo lại notes, bản mới sử dụng tên đã đặt; các bản cũ và chỉnh sửa thủ công giữ nguyên.
- Vì notes dùng tên người nói tại thời điểm tạo, khi transcript hiện tại còn người nói mang tên mặc định, khu vực tạo notes hiện **Notes sẽ dùng tên người nói hiện tại: …** (liệt kê các tên mặc định) kèm link **Đặt tên trước**. Link chuyển sang tab **Transcript & bản ghi** ở thế hệ hiện tại (nếu đang mở thế hệ cũ thì quay về thế hệ hiện tại) và đưa focus tới tiêu đề **Người nói trong phiên bản này**. Lời nhắc không chặn việc tạo notes; nó ẩn đi trong lúc tác vụ giữ nguồn, khi tên không đổi được.
- Tự học/nhận diện và điền tên từ dữ liệu training là **advanced feature ở phase sau**. V1 không có giao diện huấn luyện hoặc tự nhận diện danh tính.

### 6.3. Meeting notes

Panel **Meeting notes** có hành động tạo notes, chọn bản notes, chỉnh sửa, copy và xuất Markdown. Nội dung có thứ bậc đọc rõ và các nhóm theo đặc tả: **Overview**, **Key Topics and Rationale**, **Decisions**, **Open Questions**, **Confirmed Action Items**, **Items Requiring Confirmation**.

Quyết định/action item có liên kết timestamp để đối chiếu. Các mục cần xác nhận được trình bày riêng với mức nhấn amber; không trộn với công việc đã thống nhất. Không tự đặt người phụ trách hoặc deadline còn thiếu.

Theo Q19, liên kết nguồn của một bản notes mở đúng bản chụp đã dùng lúc tạo, gồm văn bản, tên người nói và ngày họp trước các chỉnh sửa về sau. UI phải phân biệt đang xem nguồn cũ với transcript hiện tại; bản chụp chỉ đọc, vẫn nghe được mốc âm thanh tương ứng. Không đổi ngầm nguồn chỉ để khớp với transcript đang mở.

**Hành động tạo notes.** Dưới tiêu đề panel có đúng một nút chính, tên nút nêu lựa chọn đã lưu: **Tạo notes · English · ChatGPT GPT 6.1 Sol** (ngôn ngữ đầu ra, rồi nhà cung cấp và model). Khi đã có notes, nút đọc **Tạo lại notes · …**, là nút phụ và nằm trong thanh công cụ notes (hàng cuối), cùng nút **Đổi…**; cả nhóm chuyển chỗ như một khối và focus bàn phím đi cùng. **Đổi…** (`aria-expanded`, `aria-controls`) mở vùng chứa ba ô chọn ngôn ngữ đầu ra, nhà cung cấp và model hiện có, dòng nói lần chạy tiếp theo dùng gì, thông báo lưu lựa chọn và đoạn mô tả dữ liệu gửi đi; vùng này đóng sẵn ở mỗi cuộc họp, đóng/mở không gọi API và không có chuyển động. Cách lưu lựa chọn và quy tắc không tự đổi nhà cung cấp hay model giữ nguyên. Khi nhà cung cấp đã chọn chưa kết nối (hoặc cần kết nối lại) hay model chưa sẵn sàng, chính nút đó đọc **Kết nối ChatGPT để tạo notes** hoặc **Kết nối Google Antigravity để tạo notes** và mở hộp thoại kết nối ở đúng phần của nhà cung cấp, dòng giải thích lý do hiện ngay không cần mở **Đổi…**; khi tác vụ đang chạy, nút giữ nguyên chỗ và bị tắt cạnh **Hủy tạo notes**. Từ 520 px trở xuống nút chiếm cả hàng, tên dài xuống dòng trong nút, **Đổi…** nằm dưới.

Notes đã lưu nằm trong một khung toàn bề rộng của panel. Một thanh công cụ dùng chung cho hai chế độ gồm chọn phiên bản, nút chuyển **Xem | Viết**, **Lưu bản nháp**, **Sao chép bản đã lưu**, **Tải Markdown đã lưu** và, ở hàng cuối, hành động tạo notes nói trên. **Xem** là mặc định, được nhớ theo lựa chọn cuối cùng trong trình duyệt, và render Markdown của bản nháp hiện tại với chữ 14 px, heading nằm dưới cấp heading của panel. **Viết** là ô soạn thảo Markdown toàn bề rộng, chữ 13 px, cao tối thiểu 420 px trên desktop. Đổi chế độ không đổi bản nháp, không gọi API và giữ vị trí con trỏ. Khi có thay đổi chưa lưu, nút **Viết** có chấm báo và tên truy cập nói rõ, còn **Xem** hiện dòng “Đang xem bản nháp chưa lưu”. Khối xung đột cùng hai hành động của nó hiện ở cả hai chế độ; Ctrl/⌘+Enter trong ô soạn thảo lưu bản nháp; trình duyệt cảnh báo trước khi đóng hoặc tải lại trang còn bản nháp notes hoặc transcript chưa lưu. UI phân biệt bản đang xem, bản mới nhất, bản đã sửa thủ công và bản chưa phản ánh transcript/tên người nói mới. **Tạo lại notes** tạo bản mới; bản trước vẫn mở, copy và xuất được. Copy/xuất luôn dùng đúng bản đang chọn, kể cả chỉnh sửa của bản đó.

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
| Đang chép lời | Thanh tiến độ (`<progress>`, tên truy cập là nhãn giai đoạn tiếng Việt) kèm phần trăm bằng mốc transcript chia cho thời lượng bản ghi; không vượt 100 % và không hiện 100 % trước khi chép hết. Thiếu thời lượng thì thanh không xác định (viền đứt, nhấp nháy nhẹ, tắt khi giảm chuyển động) và không có phần trăm. Nút hủy ghi **Hủy chép lời**, đổi thành **Đang dừng…** khi đã gửi yêu cầu; khi đã có transcript, **Chạy lại bản ghi** là nút phụ. Compute backend và model tự chọn nằm trong phần **Chi tiết xử lý** (`<details>`, mặc định đóng); giai đoạn, thời gian đã chạy, số đoạn và mốc transcript vẫn ở bảng số đo. Không có ETA, và tiến độ không thêm request ngoài lần poll tác vụ |
| Đang tạo/tạo lại notes | Danh sách bước có thứ tự **Nhận yêu cầu**, **Khởi chạy**, **Tạo notes**, **Lưu notes**, mỗi bước có chữ **Đã xong**, **Đang chạy** hoặc **Chưa tới** (không chỉ dùng màu), kèm thời gian đã chạy và một dòng phụ nhà cung cấp · model · mức suy nghĩ. Bước làm tác vụ thất bại, bị hủy hoặc gián đoạn ghi **Thất bại**, **Đã hủy** hoặc **Bị gián đoạn**. Backend ghi đè giai đoạn khi tác vụ kết thúc nên trang nhớ bước cuối đã thấy trong phiên; mở trang sau khi tác vụ đã kết thúc thì không bước nào được ghi là đã xong, chỉ có một dòng nêu cách tác vụ kết thúc. Nút hủy ghi **Hủy tạo notes**, đổi thành **Đang dừng…**; chỉ một tác vụ tại một thời điểm |
| Backend đang bận | Giải thích vì sao chưa bắt đầu được tác vụ mới; vẫn cho xem/sửa cuộc họp đã hoàn tất, không tạo hàng đợi ẩn. Nếu lần tự chép lời sau khi tạo gặp máy bận hoặc worker/model chưa sẵn sàng, cuộc họp vẫn được lưu, trang nêu lý do cùng nút **Bắt đầu chép lời** và không tự thử lại |
| Đã sẵn sàng | Mở transcript và notes để duyệt; không diễn đạt bản nháp là nội dung chắc chắn đúng |
| Đã có transcript, chưa có notes | Cho đọc/sửa/nghe lại transcript và chủ động tạo notes sau; tác vụ đã kết thúc, không giữ trạng thái đang xử lý để chờ đăng nhập/quota |
| Provider cần kết nối lại hoặc hết quota | Nêu bên được chọn và nguyên nhân; khi bên được chọn chưa kết nối, nút tạo notes thành **Kết nối {provider} để tạo notes** và mở hộp thoại kết nối ở phần của bên đó. Người dùng kết nối lại hoặc chọn bên khác trong **Đổi…** rồi chủ động tạo notes; không tự chuyển provider |
| Lỗi mạng khi tạo notes | Báo lỗi và cho chủ động thử lại; giữ transcript/notes cũ, không thể hiện hệ thống đang tự gửi lại request hoặc tự đổi provider/model |
| Lỗi/đã hủy/bị gián đoạn | Phân biệt trạng thái, nêu vấn đề và đường thử lại phù hợp; không hiển thị là đã hoàn tất hoặc tự chạy lại |
| Mất kết nối trình duyệt | Thông báo mất kết nối; khi kết nối lại, lấy trạng thái hiện tại từ backend. Đóng tab không hủy tác vụ đã được nhận |
| Xóa cuộc họp | Hộp thoại nêu tên cuộc họp, nút giữ lại/xóa; cuộc họp đang có tác vụ phải hủy và chờ backend xác nhận đã dừng trước khi xóa. Xóa dữ liệu ứng dụng quản lý theo đặc tả, không xóa file nguồn bên ngoài |
| Lưu/copy/xuất | Phản hồi thành công hoặc lỗi rõ ràng; không báo đã lưu thành công trước khi backend xác nhận |

Giữ lời nhắc trong form nhập: **Transcript giữ nguyên ngôn ngữ đã nói. Meeting notes viết bằng ngôn ngữ đầu ra đã chọn (English hoặc Tiếng Việt).** Định dạng và giới hạn file phải phản ánh khả năng backend đã công bố; không lấy `audio/*,video/*` trong prototype làm cam kết hỗ trợ mọi codec.

QR/link truy cập được cung cấp từ terminal. Không hiển thị token dùng chung hoặc cơ chế tự cấp quyền ở trang chưa xác thực. Chi tiết theo [ADR về token](adr/0002-localhost-reusable-token.md); không bổ sung tài khoản/mật khẩu hoặc quản lý nhiều người dùng trong v1.

### 7.1. Kết nối provider notes — phạm vi bổ sung sau prototype

Q12 bổ sung lựa chọn **ChatGPT** hoặc **Google Antigravity qua OMP** cho mỗi lần xử lý có tạo notes và mỗi lần tạo lại notes. Người dùng chọn một bên, dùng lại phiên đã lưu hoặc kết nối tài khoản bên đó từ UI. Tạo lại có thể chọn provider khác, vẫn tạo bản notes mới và giữ bản cũ. Không cố định Google làm mặc định toàn hệ thống.

Q27 bổ sung chọn model, nhớ provider gần nhất và model riêng mỗi bên; UI hiển thị rõ lựa chọn trước khi bắt đầu, ngay trong tên nút tạo notes, còn ba ô chọn nằm sau **Đổi…**. Khi đổi preference trong lúc một tác vụ chạy, ghi rõ áp dụng cho lần sau, không đổi cấu hình của tác vụ hiện tại. Model đã nhớ mất quyền/quota phải báo để người dùng chọn lại; không âm thầm thay model.

Đây là kết nối dịch vụ AI sau khi đã vào ứng dụng bằng token localhost, không thay màn hình truy cập ứng dụng. Trạng thái từng provider hiện ở hai nút **OpenAI** (ChatGPT) và **Google** (Antigravity) trên đầu vùng làm việc; cả hai mở hộp thoại kết nối. UI cần thể hiện rõ transcript và thông tin nguồn cần thiết sẽ gửi tới bên được chọn; đoạn mô tả này nằm trong vùng **Đổi…** (không luôn hiển thị) và mở được bất cứ lúc nào trước khi bấm tạo notes; âm thanh và ASR vẫn local. Notes mới cần Internet, trong khi dữ liệu đã lưu vẫn đọc/sửa/nghe lại/copy/xuất được khi mất mạng.

Q13–Q15 đã chốt: lưu một tài khoản/phiên mỗi provider trên bản cài, có nút ngắt kết nối, chỉ đăng nhập lại khi cần. Provider chưa sẵn sàng vẫn cho chép lời local, lưu transcript rồi kết thúc tác vụ. Khi notes lỗi/quota, giữ dữ liệu và cho người dùng chủ động chọn bên khác rồi chạy lại; không tự chuyển provider hay bật API billing. Đăng nhập lại không tự tạo notes từ transcript đang chờ.

Q22 chặn ngắt/đổi tài khoản của provider đã chọn cho tác vụ đang hoạt động, kể cả trước bước notes; hướng dẫn hủy rồi chờ backend xác nhận dừng. Provider không thuộc tác vụ vẫn có thể ngắt. Backend phải thực thi cùng điều kiện, không chỉ vô hiệu nút trên UI.

Vị trí/nội dung hộp thoại kết nối chưa có trong prototype đã duyệt; không coi hình thức UI mới là đã được nghiệm thu. Ràng buộc Antigravity được ghi tại [ADR 0007](adr/0007-cloud-notes-providers.md).

## 8. Khả năng sử dụng và kích thước màn hình

- Nghiệm thu trên Chrome và Firefox bản ổn định ở laptop/desktop. Các mốc tham chiếu đã xem trong prototype là **1440 × 1000**, **1280 × 800** và **1024 × 768**.
- Ở các kích thước đó, không tràn ngang toàn trang; sidebar và công cụ chính vẫn truy cập được. Nội dung dài cuộn cùng trang và không bị trình phát hoặc thanh cố định che mất: đoạn được cuộn tới luôn nằm dưới thanh trình phát, còn control nhận focus bàn phím được cuộn xuống dưới thanh (ô nhập văn bản có thể chỉ lộ dòng chứa con trỏ).
- Trang cuộc họp giữ hai tab ở mọi chiều rộng; nhãn tab xuống dòng thay vì tràn, và từ 680 px trở xuống danh sách tab nằm ngay dưới phần đầu trang. Giữ đầy đủ control/trạng thái; mobile là viewport được nghiệm thu, không được tạo tràn ngang.
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
| FE-01 | Bố cục A và hệ editorial-engineering light/dark thống nhất, có sidebar, trang cuộc họp hai tab (Meeting notes, Transcript & bản ghi) và trình phát; đối chiếu AC-29 |
| FE-02 | Brand là ASR EN VI; footer chỉ có icon GitHub và dòng Version ngắn, đúng metadata bản chạy |
| FE-03 | Danh sách gần đây gọn, tìm kiếm toàn lịch sử, lịch nhỏ ngay dưới danh sách và mở được lịch lớn |
| FE-04 | Lịch nhỏ/lớn đồng bộ; xử lý tháng/năm cũ, tháng 12 sang tháng 1, năm nhuận, tháng trống, nhiều cuộc họp cùng ngày và thiếu ngày; đối chiếu AC-30 |
| FE-05 | Mở đúng cuộc họp từ lịch, dấu ngày cập nhật sau nhập/xóa; điều hướng giữ nguyên metadata và chỉnh sửa đã lưu |
| FE-06 | Đặt/sửa/xóa tên người nói riêng từng cuộc họp; giữ nhãn gốc và không ghi đè notes cũ; đối chiếu AC-28 |
| FE-07 | Timestamp dẫn tới nguồn, chỉnh sửa làm notes cần cập nhật, tạo lại có bản mới, copy/xuất đúng bản chọn; đối chiếu AC-05/07/11 |
| FE-08 | Upload, xử lý (thanh tiến độ khi chép lời, danh sách bước khi tạo notes), bận, hủy (nút nói rõ hủy chép lời hay hủy tạo notes), lỗi và gián đoạn được thể hiện đúng; đóng tab không làm frontend suy diễn tác vụ đã hủy; đối chiếu AC-12/16/19/20/21 |
| FE-09 | Dùng được bằng bàn phím và ở ba viewport tham chiếu; không để nội dung/công cụ bị che hoặc tràn ngang, kể cả khi trình phát dính ở mép trên |
| FE-10 | Không có UI dành riêng cho demo; hoạt động với backend và lưu trữ thật, kiểm soát token và đóng gói sẵn tài nguyên UI; kết nối provider notes theo lựa chọn của người dùng, đối chiếu AC-10/15/22/23 |
| FE-11 | Chọn và kết nối riêng ChatGPT hoặc Google Antigravity qua OMP từ UI, không buộc đăng nhập cả hai; phân biệt kết nối provider với token localhost, đối chiếu AC-35 |
| FE-12 | Dùng lại phiên provider; thể hiện đúng đã có transcript/chưa có notes và lỗi/quota; đổi bên rồi chạy lại là thao tác chủ động, đối chiếu AC-36/37/38 |
| FE-13 | Notes cũ mở đúng bản chụp nguồn, có phân biệt với transcript hiện tại; xung đột ghi giữ bản nháp chưa lưu, đối chiếu AC-41/42 |
| FE-14 | Chọn đúng thế hệ transcript, bản cũ chỉ đọc và không tự ghép tên người nói; chặn ngắt/đổi provider đang dùng, đối chiếu AC-43/44 |
| FE-15 | Sửa tên/ngày và gán speaker từng đoạn theo version/khóa nguồn; bảo toàn snapshot, original assignment và lịch sử ngôn ngữ, đối chiếu AC-45/46 |
| FE-16 | Báo lỗi mạng không tự retry, cho lưu link chỉnh tay hỏng có cảnh báo và chọn/nhớ model rõ ràng, đối chiếu AC-47/48/49 |
| FE-17 | Trang cuộc họp hai tab theo WAI-ARIA: mũi tên, Home, End đổi tab và chỉ tab đang chọn nằm trong thứ tự Tab; tab mở sẵn theo trạng thái cuộc họp, `#notes`/`#transcript` với `pushState`, Back và tải lại giữ tab; trạng thái trống **Cần transcript trước**; tên cuộc họp một lần và dải trạng thái Bản ghi · Transcript · Notes; không tràn ngang ở 360 px, đúng ở theme sáng/tối, focus nhìn thấy và tôn trọng giảm chuyển động |

Việc chốt tài liệu này xác nhận hướng thiết kế. Các tiêu chí trên là điều kiện kiểm tra frontend khi triển khai, không phải báo cáo nghiệm thu sản phẩm đã hoàn thành.
