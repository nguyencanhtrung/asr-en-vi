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
| Thẻ nguồn đã lưu | Chỉ hiện khi mở một nguồn từ notes: nằm ngay dưới trình phát trong tab Transcript & bản ghi, tiêu đề **Nguồn đã lưu lúc tạo notes**, văn bản/người nói/mốc của bản chụp, ghi chú khi transcript hiện tại đã khác, nút **Tua bản ghi tới mốc này** và **Đóng nguồn** (mục 6.3) |
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
- **Nội dung:** tab Transcript & bản ghi chứa khối bản ghi (trình phát dính), khối chép lời, người nói và các đoạn; khi đã có transcript, nhãn tab ghi số đoạn và số đoạn cần kiểm tra (đoạn hiện dấu **Cần kiểm tra** hoặc **Nên nghe lại**) của thế hệ transcript đang hiển thị. Tab Meeting notes chứa toàn bộ phần notes (tạo, tiến độ, lỗi, phiên bản, **Xem | Viết**, sao chép, tải về). Thẻ nguồn đã lưu nằm ở tab Transcript & bản ghi, ngay dưới trình phát.
- **Tab mở sẵn:** không có hash thì chọn Meeting notes nếu cuộc họp có ít nhất một bản notes đã lưu hoặc đang tạo notes, ngược lại chọn Transcript & bản ghi. Link nguồn `?notes_source=…&segment=…` không kèm hash mở Transcript & bản ghi, nơi có thẻ nguồn. Hash luôn thắng (`#notes` hiện tab notes và giữ nguồn đã nạp cho lần chuyển tab sau). Trước khi biết cuộc họp có notes hay không (tối đa bốn giây), chưa tab nào được chọn: khung notes ẩn còn khung transcript đã có đủ control nhưng trong suốt, để không khung nào bị nháy; cái giá là trong khoảng chờ ngắn đó các control trong suốt ấy vẫn nhận được focus bàn phím mà không có viền focus nhìn thấy.
- **Địa chỉ:** `#notes` và `#transcript` chọn tab tương ứng. Đổi tab là một mục lịch sử mới (`pushState`, giữ đường dẫn và query), nên Back quay lại tab trước, Forward đi tiếp và tải lại trang giữ tab. Mục lịch sử bị rời đi nhớ tab đang hiện, nên Back đúng tab kể cả khi quy tắc mặc định đã đổi. Route `/meetings/{id}` và API không đổi.
- **Chưa có transcript:** tab Meeting notes chỉ hiện **Cần transcript trước**, một dòng nói transcript đang được tạo hay chưa chạy, và nút chuyển sang tab Transcript & bản ghi; không có ô chọn hay nút tạo notes bị tắt.
- **Tạo notes:** bấm tạo notes ở bất kỳ đâu đều chọn tab Meeting notes để theo dõi tiến độ. Thẻ nguồn và trình phát cùng nằm ở tab Transcript & bản ghi nên nút **Tua bản ghi tới mốc này** của thẻ chỉ tua, không đổi tab. Bấm chip mốc thời gian của notes chọn tab Transcript & bản ghi bằng một mục lịch sử mới (xem 6.3), nên Back quay lại Meeting notes.
- **Đầu trang:** tên cuộc họp chỉ hiện một lần; dải trạng thái ngắn **Bản ghi · Transcript · Notes** nằm trong phần đầu trang. Từ 680 px trở xuống, danh sách tab nằm ngay dưới phần đầu trang và hai nút trạng thái **OpenAI** và **Google** giữ nguyên.

### 6.1. Transcript và trình phát

Transcript mặc định ở chế độ đọc để nghe và đọc nhanh. Mỗi đoạn gồm timestamp có thể bấm, tên người nói, nội dung (từ 13 px) và nút **Sửa** luôn hiện, không phụ thuộc hover; chưa có ô nhập, select hay nút lưu nào. Đoạn chưa rõ được đánh dấu bằng amber, nhãn **Cần kiểm tra** kèm lý do và chỉ dẫn nghe lại. Đoạn nguồn đang được đối chiếu phải nổi bật để người dùng định vị được trong danh sách. Mỗi đoạn ở chế độ đọc có tối đa hai điểm dừng Tab: timestamp và **Sửa**.

Bấm timestamp trong transcript tua trình phát tới đoạn đó và phát; bấm chip mốc thời gian của notes tua tới mốc nguồn rồi phát (trình duyệt có thể chặn phát khi link vừa được dán; khi đó thẻ nguồn nhắc bấm phát), còn nút **Tua bản ghi tới mốc này** của thẻ nguồn chỉ tua. Trình phát là thanh dính ở mép trên vùng nội dung của tab Transcript & bản ghi, có phát/tạm dừng, thanh tua, thời gian hiện tại và tổng thời lượng. Chọn tab Meeting notes ẩn thanh này nhưng không tạm dừng audio, để vừa nghe vừa đọc notes; muốn dừng thì quay lại tab Transcript & bản ghi. Trong sản phẩm, phát âm thanh từ bản sao đã lưu tại backend; dạng sóng và chuyển động trong prototype không chứng minh đã có phát âm thanh thật.

Khi audio đang phát và đoạn đang phát (`aria-current`) đổi, nếu còn thấy một phần danh sách đoạn trong vùng nhìn thấy bên dưới thanh trình phát thì đoạn đó được đưa vào tầm nhìn bằng cuộn gần nhất (`block: "nearest"`), dưới thanh trình phát; khi người dùng bật giảm chuyển động, cuộn tức thì. Không tự cuộn khi audio tạm dừng, trong 2 giây sau khi người dùng cuộn tay (con lăn, chạm, phím cuộn hoặc kéo thanh cuộn), khi focus đang nằm trong một ô sửa của transcript, hay khi cả danh sách đoạn nằm ngoài vùng nhìn thấy đó, kể cả khi danh sách đang ẩn vì tab Meeting notes đang mở. Nhờ vậy người đang đọc notes không bị kéo về transcript. Mở nguồn từ notes là một thao tác chủ động khác: đoạn nguồn được đánh dấu bằng nhãn **Nguồn của mục notes** và đưa vào tầm nhìn bằng cuộn gần nhất (cuộn tức thì khi bật giảm chuyển động), chỉ khi chưa thấy được dưới thanh trình phát. Mọi đích cuộn trong tab Transcript & bản ghi (đoạn transcript) đều dừng dưới thanh trình phát, không nằm dưới nó; tab Meeting notes không ghim thanh nào nên không để dành chỗ. Trình duyệt cũng cuộn control nhận focus bàn phím xuống dưới thanh; riêng ô nhập văn bản có thể chỉ lộ dòng chứa con trỏ, nên một phần của ô vẫn có thể nằm dưới thanh trình phát.

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

Mục có nguồn hiện chip mốc thời gian để đối chiếu, chỉ ở chế độ **Xem** và không nằm trong Markdown (xem bên dưới). Các mục cần xác nhận được trình bày riêng với mức nhấn amber; không trộn với công việc đã thống nhất. Không tự đặt người phụ trách hoặc deadline còn thiếu.

Theo Q19, chip mốc thời gian của một bản notes mở đúng bản chụp đã dùng lúc tạo, gồm văn bản, tên người nói và ngày họp trước các chỉnh sửa về sau. UI phân biệt đang xem nguồn cũ với transcript hiện tại: thẻ **Nguồn đã lưu lúc tạo notes** luôn nói đây là bản chụp bất biến, hiện mốc thời gian, người nói và ngày họp của bản chụp (**Chưa đặt ngày** khi lúc đó cuộc họp chưa có ngày) và, khi nguồn hiện tại đã khác (văn bản hoặc người nói của đoạn đổi, là lần chép lời khác, hoặc ngày họp đã được thêm, đổi hay xóa), thêm ghi chú nói rõ khác ở đâu; bản chụp chỉ đọc, vẫn nghe được mốc âm thanh tương ứng. Không đổi ngầm nguồn chỉ để khớp với transcript đang mở.

Trích dẫn là dữ liệu riêng của bản notes, không phải link trong Markdown: mỗi mục lưu tiêu đề phần, văn bản đúng như đã render và các đoạn nguồn (ID, mốc bắt đầu). Ở chế độ **Xem**, mục có nguồn hiện sau nội dung một chip cho mỗi đoạn nguồn, nhãn `mm:ss` (`h:mm:ss` từ một giờ), là link `<a>` tới `/meetings/{id}?notes_source={snapshot}&segment={segment}#transcript` với tên truy cập “Nghe lại đoạn nguồn lúc …”. Chip chỉ gắn vào mục còn đúng tiêu đề phần và nội dung như lúc tạo; mục đã sửa hoặc chuyển phần không có chip, và sửa một mục không làm mất chip mục khác, trừ các mục trùng tiêu đề phần và nội dung: Markdown không cho biết mục nào trong nhóm là bản gốc, nên nhóm chỉ giữ chip (mỗi mục đúng chip của mình, theo thứ tự) khi số mục của nhóm bằng lúc tạo; sửa hay xoá một mục trong nhóm, hoặc thêm bản sao của chúng (kể cả sửa mục khác thành bản sao), làm cả nhóm mất chip. Markdown đã lưu, **Viết**, sao chép và tải về không chứa link. Bản notes tạo trước khi có trích dẫn không hiện chip và không báo lỗi.

Bấm chip (hoặc mở link của chip) chọn tab Transcript & bản ghi bằng một mục lịch sử mới, nên Back quay lại tab Meeting notes; hiện thẻ nguồn ngay dưới trình phát (focus chuyển tới tiêu đề thẻ mà không cuộn, kể cả khi mở bằng link dán hoặc Back/Forward), tua và phát audio, đánh dấu đoạn tương ứng trong transcript và đưa nó vào tầm nhìn. Một thao tác duy nhất phục vụ cả bấm chip lẫn link dán từ ngoài. Xem [ADR 0009](adr/0009-notes-citations-apart-from-markdown.md).

**Hành động tạo notes.** Dưới tiêu đề panel có đúng một nút chính, tên nút nêu lựa chọn đã lưu: **Tạo notes · English · ChatGPT GPT 6.1 Sol** (ngôn ngữ đầu ra, rồi nhà cung cấp và model). Khi đã có notes, nút đọc **Tạo lại notes · …**, là nút phụ và nằm trong thanh công cụ notes (hàng cuối), cùng nút **Đổi…**; cả nhóm chuyển chỗ như một khối và focus bàn phím đi cùng. **Đổi…** (`aria-expanded`, `aria-controls`) mở vùng chứa ba ô chọn ngôn ngữ đầu ra, nhà cung cấp và model hiện có, dòng nói lần chạy tiếp theo dùng gì, thông báo lưu lựa chọn và đoạn mô tả dữ liệu gửi đi; vùng này đóng sẵn ở mỗi cuộc họp, đóng/mở không gọi API và không có chuyển động. Cách lưu lựa chọn và quy tắc không tự đổi nhà cung cấp hay model giữ nguyên. Khi nhà cung cấp đã chọn chưa kết nối (hoặc cần kết nối lại) hay model chưa sẵn sàng, chính nút đó đọc **Kết nối ChatGPT để tạo notes** hoặc **Kết nối Google Antigravity để tạo notes** và mở hộp thoại kết nối ở đúng phần của nhà cung cấp, dòng giải thích lý do hiện ngay không cần mở **Đổi…**; khi tác vụ đang chạy, nút giữ nguyên chỗ và bị tắt cạnh **Hủy tạo notes**. Từ 520 px trở xuống nút chiếm cả hàng, tên dài xuống dòng trong nút, **Đổi…** nằm dưới.

Notes đã lưu nằm trong một khung toàn bề rộng của panel. Một thanh công cụ dùng chung cho hai chế độ gồm chọn phiên bản, nút chuyển **Xem | Viết**, **Lưu bản nháp**, **Sao chép bản đã lưu**, **Tải Markdown đã lưu** và, ở hàng cuối, hành động tạo notes nói trên. **Xem** là mặc định, được nhớ theo lựa chọn cuối cùng trong trình duyệt, và render Markdown của bản nháp hiện tại với chữ 14 px, heading nằm dưới cấp heading của panel. **Viết** là ô soạn thảo Markdown toàn bề rộng, chữ 13 px, cao tối thiểu 420 px trên desktop. Đổi chế độ không đổi bản nháp, không gọi API và giữ vị trí con trỏ. Khi có thay đổi chưa lưu, nút **Viết** có chấm báo và tên truy cập nói rõ, còn **Xem** hiện dòng “Đang xem bản nháp chưa lưu”. Khối xung đột cùng hai hành động của nó hiện ở cả hai chế độ; Ctrl/⌘+Enter trong ô soạn thảo lưu bản nháp; trình duyệt cảnh báo trước khi đóng hoặc tải lại trang còn bản nháp notes hoặc transcript chưa lưu. UI phân biệt bản đang xem, bản mới nhất, bản đã sửa thủ công và bản chưa phản ánh transcript/tên người nói mới. **Tạo lại notes** tạo bản mới; bản trước vẫn mở, copy và xuất được. Copy/xuất luôn dùng đúng bản đang chọn, kể cả chỉnh sửa của bản đó.

Nội dung soạn thảo là Markdown tự do theo [ADR 0005](adr/0005-markdown-notes.md). Khi lưu, thao tác luôn nhắm đúng bản notes đã mở trong trình soạn thảo, kể cả nếu một bản mới được tạo xong trong lúc người dùng đang sửa.

Q26 cho lưu nguyên văn Markdown chỉnh tay dù có tham chiếu nguồn hỏng. Backend trả `warnings` cho bản đã lưu (xem backend contract, mục 4); UI hiển thị cảnh báo và vô hiệu thao tác mở nguồn ở link hỏng: ở chế độ **Xem** link đó là chữ thường gạch chân đứt nét màu cảnh báo, không phải `<a>` nên không có đường mở nguồn (tên truy cập thêm “liên kết nguồn không hợp lệ”), và dòng `#notes-link-warning` phía trên khung nêu số link hỏng cùng link đầu tiên. Không tự sửa hoặc dẫn sang nguồn khác. Copy/xuất vẫn lấy nội dung đã lưu, không thay bằng bản được ứng dụng tự sửa link.

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
| FE-18 | Trích dẫn mốc thời gian của notes: chip `mm:ss`/`h:mm:ss` sau mục có nguồn, chỉ ở **Xem**, Markdown/Viết/sao chép/tải về không có link; chip chỉ gắn vào mục còn nguyên nội dung; bấm chip hoặc dán link chọn tab Transcript, hiện thẻ **Nguồn đã lưu lúc tạo notes** dưới trình phát, tua và phát, đánh dấu và cuộn tới đoạn, Back về Meeting notes; notes cũ không chip; không tràn ngang ở 360 px, đúng ở theme sáng/tối, focus nhìn thấy và tôn trọng giảm chuyển động |

Việc chốt tài liệu này xác nhận hướng thiết kế. Các tiêu chí trên là điều kiện kiểm tra frontend khi triển khai, không phải báo cáo nghiệm thu sản phẩm đã hoàn thành.

## 11. Kiến trúc mã frontend: reducer, effect và store

Quyết định và lý do nằm ở [ADR 0010](adr/0010-frontend-reducer-core.md). Mục này là quy ước cho code; từ pha 1 `shell.js`, từ pha 2 `connections.js` và `antigravity.js`, từ pha 3 `notes.js` đã theo kiến trúc này, các file UI còn lại chuyển dần theo 11.4. Hành vi người dùng thấy không đổi.

### 11.1. Các lớp

| Lớp | Việc | Không được |
| --- | --- | --- |
| Core | `initialState`, `reduce(state, action) -> { state, effects }`, selector | chạm DOM, `fetch`, timer, storage, `Date.now`, `Math.random` |
| Effect | object `{type, ...}`: `fetch`, `schedule`, `cancel`, `upload`, `storage`, `navigate`, `open-window`, `event`, `call` | chứa hàm hoặc logic |
| Runner | `createRunner({ fetch, setTimeout, clearTimeout, XMLHttpRequest, storage, navigate, open, emit, calls, now })` chạy effect, dispatch kết quả | quyết định nghiệp vụ |
| View | đọc state, render DOM, handler chỉ dispatch action | giữ state riêng ngoài focus/scroll |
| Store | `createStore`, `combine`, `subscribe` (`src/asr_en_vi/web/store.js`) | biết về tính năng cụ thể |

### 11.2. Quy ước action và effect

- Action là `{type, ...payload}`, đặt tên theo sự kiện đã xảy ra (`notes-loaded`, `notes-load-failed`), không theo lệnh.
- Effect `fetch` khai báo `ok` và `error` là tên action của kết quả; mã 2xx gửi `ok`, lỗi HTTP hoặc mạng gửi `error`; request bị hủy không gửi gì.
- `key` bắt buộc ở mọi effect (thiếu thì runner ném lỗi). Effect cùng `key` thay thế effect cũ; `cancel` hủy theo `key`.
- `key` và `type` của action dùng chung một namespace: luôn đặt tiền tố tính năng (`shell/upload`, `shell/upload-sent`, `notes/load`). Với `storage`, `key` là khóa storage.
- `upload` giống `fetch` (2xx là `ok`; lỗi HTTP là `error` có `status`, `body`; lỗi truyền là `error` có `kind` là `network` hoặc `timeout`) và gửi thêm action `progress` `{loaded, total, lengthComputable, meta}`; hủy không sinh action. `storage` ghi hoặc xóa (`area` là `local` hoặc `session`) và nuốt lỗi storage bị chặn. `navigate` gọi `navigate(url)` được truyền vào. `open-window` (`op`: `reserve` mở `about:blank` qua `open`, đặt `opener = null`, tiêu đề và chữ, rồi gửi `ok` hoặc `error` nếu bị chặn; `navigate` gửi cửa sổ tới `url` hoặc gửi action `closed` nếu người dùng đã đóng; `close`) giữ cửa sổ ngoài bảng hủy/thay thế theo `key`. `event` gọi `emit(name)`. `call` (`name`, `args`, `ok`, `error`, `meta`) gọi `calls[name](...args)`: thiếu `ok` và `error` thì chạy ngay; có thì giá trị hoặc promise trả về thành action `ok` (`value`) hoặc `error` (`{message}`), hủy/thay thế theo `key` như `fetch`; tên lạ thì ném lỗi. `now` (tùy chọn) đóng dấu `now` lên action runner dispatch.
- Body của `fetch` được parse JSON, không phải JSON thì giữ text (không kiểm tra content-type).
- Loại effect mới thêm thành nhánh trong `createRunner`. Reducer không đọc storage: view đọc giá trị đã nhớ và đưa vào state qua action mở (shell: `shell/dialog-opened`; provider: `provider/boot-restored`), ghi qua effect `storage`.
- Lỗi trong reducer, effect hoặc subscriber: state giữ tới action cuối chạy thành công, hàng đợi bị bỏ, lỗi ném cho nơi gọi `dispatch` (với kết quả `fetch` là `unhandledRejection`). Giữa lượt drain, state đã đổi nhưng subscriber không được báo và effect còn lại của action đó bị bỏ; lỗi trong callback `schedule` là exception chưa bắt của timer, không đi qua `dispatch` của nơi gọi.
- Module đã chuyển vẫn công bố trên `window` mọi hàm mà script chưa chuyển gọi tới pha 5 (từ pha 1: `ApiError`, `requestJson`, `meetingIdFromPath`, `formatMeetingDate`, `sameOriginAudioSource`). Mỗi file module mới có route `/assets/<tên>.js` và test asset.
- Tính năng nói chuyện với nhau bằng action dùng chung đi qua `combine`, không dùng `CustomEvent` hay hàm global.

### 11.3. Quy tắc response cũ và quy tắc gán state

- Reducer lưu id yêu cầu mới nhất trong state, đặt id vào `meta` của effect `fetch`; action kết quả mang lại `meta` và reducer bỏ action có id không khớp.
- Chỉ reducer tạo state mới. Từ pha 1, `tests/web/shell-view.test.mjs` quét các file view đã chuyển (danh sách `VIEWS`) và core (`CORES`) trong `check.sh`/CI: view không gán vào state, không có `let`/`var` cấp module, chỉ đọc storage trong `readStored`; core không chạm DOM, mạng, timer, storage, đồng hồ hay ngẫu nhiên. Quét này là grep heuristic (có bắt thêm bí danh `const s = state` hoặc `store.getState()`, destructure, `Object.assign(state, …)`, `delete state.x`, lệnh đổi như `state.list.push(…)` và object/collection cấp module, kể cả `export const`, bị gán hoặc đổi; cấm tên kiểu `*Seq`, `*InFlight`, `*Timer`), không thay review: cách viết lạ vẫn lọt (bí danh của một lát cắt như `const s = state.x; s.y = 1` đã bị bắt từ pha 3; phần trong `${…}` của template literal được quét như mã; còn mù với một dấu backtick nằm trong regex literal, làm lệch chỗ bắt đầu/kết thúc template phía sau, và với `}` lồng trong `${…}` (quét dừng ở `}` đầu tiên)). Mỗi quy tắc có một ví dụ xấu trong cùng test để biết nó còn bắt được. Khi chuyển file mới, thêm nó vào danh sách.

### 11.4. Thứ tự chuyển

Mỗi pha thêm vào tài liệu này bảng state và chuyển trạng thái của core vừa chuyển, gồm cả trạng thái lỗi, hủy và response cũ.

| Pha | Phạm vi |
| --- | --- |
| 0 | ADR, `store.js`, `node --test` cho `tests/web/`, Node trong CI (mục này) |
| 1 | `shell.js` (xong, #121): dialog tạo cuộc họp và upload, xem 11.5; #117 thêm bước tách audio thành effect đứng trước effect `shell/upload` |
| 2 | `connections.js` và `antigravity.js` dùng chung một core provider (xong, #123), xem 11.6 |
| 3 | `notes.js` + `notes-core.js` (xong, #126): chế độ xem/soạn, chọn provider/model, task notes, lưu revision, nguồn trích dẫn, xem 11.7 |
| 4 | `history.js` tách thành core điều hướng/meeting, transcript và generation, calendar, search, polling task, khóa nguồn notes |
| 5 | bỏ global và `CustomEvent` còn sót, xóa code chết, cập nhật tài liệu |

### 11.5. Shell: dialog tạo cuộc họp

Core `shell-core.js` (`initialState`, `reduce`, `selectView`), view `shell.js`. Văn bản trong core là `{text, params}`, view dịch bằng `t()`.

**Id chống response cũ** (trong state): `policyRequest` (tải chính sách), `runId` (một lượt upload: tạo slot, truyền, kiểm tra), `createRequest` (lưu cuộc họp). Mỗi effect `fetch`/`upload` mang id trong `meta`; action có id khác bị bỏ. Mở và đóng dialog tăng `policyRequest` và `runId`.

**Trạng thái `phase`** (nhãn hiện ở `#state-label`, `data-state` của dialog):

| `phase` | Nghĩa | Vào bằng | Nút/trường |
| --- | --- | --- | --- |
| `idle` | chưa chọn file, chính sách đã tải | `policy-loaded` | chọn file được |
| `selected` | file hợp lệ đã chọn, hoặc đang chuẩn bị slot upload | `file-selected`, bắt đầu lượt mới | tạo được nếu form hợp lệ |
| `uploading` | đang truyền byte, có tiến độ | `upload-created` | khóa form; hiện nút hủy |
| `checking` | server kiểm tra file | `upload-sent` | khóa form; hiện nút hủy |
| `ready` | server xác nhận `ready`, chưa lưu | `upload-completed`, `form-edited` sau lỗi tạo | tạo được |
| `creating` | đang lưu cuộc họp | `submit-requested`, `upload-completed` | khóa form và nút đóng |
| `saved` | đã lưu, đang chuyển trang | `meeting-created` | khóa |
| `error` | lỗi (chính sách, file, upload, tạo) | các action lỗi | tùy cờ bên dưới |
| `aborted` | người dùng hủy upload | `shell/upload-cancel-requested` | thử lại được |

Cờ bổ sung: `starting` (đang dọn upload cũ và tạo slot; khóa form), `cancelling` (đã hủy, chờ dọn), `failure` (lỗi upload chờ dọn xong để báo), `serverReady`, `retryable`, `fileRefused` (server từ chối nội dung file: không thử lại cùng file), `createAttemptFailed`, `createUncertain` + `createRetryPayload` (tạo không rõ kết quả: gửi lại đúng payload để server khử trùng), `pendingCleanup` (upload dở chưa xóa được, thử lại ở lần chọn file hoặc lượt sau).

**Chuyển trạng thái** (`shell/` bỏ tiền tố trong cột sự kiện):

| Từ | Sự kiện | Tới | Effect |
| --- | --- | --- | --- |
| đóng | `dialog-opened` (đọc storage) | `idle`, chờ chính sách | `fetch shell/policy` |
| mở | `policy-loaded` hợp lệ / sai định dạng | `idle` / `error` | |
| mở | `policy-load-failed` | `error`, `policyFailed` | |
| mở | `policy-*` với id cũ | không đổi | |
| không bận | `file-selected` hợp lệ | `selected` | `fetch` DELETE upload cũ và các upload chờ dọn |
| không bận | `file-selected` sai đuôi, quá lớn, chưa có chính sách | `error` | như trên |
| đang bận hoặc tạo không rõ | `file-selected` | không đổi | |
| có thể tạo | `submit-requested` khi chưa `serverReady` | `selected`, `starting` | DELETE upload cũ, rồi `fetch shell/upload-create` |
| `starting` | `upload-created` | `uploading` | `upload shell/upload` |
| `starting` | `upload-create-failed` hoặc thiếu mã | `error` | |
| `uploading` | `upload-progressed` | `uploading` | |
| `uploading` | `upload-sent` | `checking` | `fetch shell/upload-complete` |
| `uploading` | `upload-failed` (mạng, hết giờ, HTTP) | `uploading` rồi `error` sau khi dọn | DELETE upload |
| `checking` | `upload-completed` ready | `ready` rồi `creating` ngay | `fetch shell/create` |
| `checking` | `upload-completed` khác ready, `upload-completion-failed` | `error` sau khi dọn | DELETE upload |
| `uploading`, `checking` | `upload-cancel-requested` hoặc đóng dialog | `aborted` sau khi dọn | `cancel shell/upload`, `cancel shell/upload-complete`, DELETE upload (id vào `pendingCleanup` ngay, xóa khi DELETE được xác nhận) |
| `uploading`, `checking` đang chờ DELETE của lỗi upload | `upload-cancel-requested` hoặc đóng dialog | `aborted` ngay; bỏ `failure`, kết quả hủy giữ nguyên khi DELETE cũ trả lời | |
| `aborted` đang chờ DELETE (`cancelling`) | `upload-cancel-requested` | không đổi | |
| `cancelling` | `dialog-close-requested` | đóng, state về ban đầu; DELETE đang chờ để id ở `pendingCleanup` | |
| mở | `dialog-closed` (trình duyệt tự đóng dialog) | đóng, state về ban đầu | `cancel` mọi effect đang bay, DELETE upload (trừ khi tạo không rõ); đang `creating` thì chỉ hạ cờ `open`, lượt lưu vẫn chạy tiếp |
| đóng | `dialog-closed` | không đổi | |
| không bận | `multiple-files-dropped` | `error` (lỗi file) | |
| bất kỳ | kết quả lượt cũ (`runId` khác) | không đổi | |
| `ready`, tạo lại | `submit-requested` | `creating` | `fetch shell/create` |
| `creating` | `meeting-created` | `saved` | `storage` ngôn ngữ; `storage` cờ chép lời (nếu bật); `navigate` |
| `creating` | `meeting-create-failed` 4xx | `error`, `createAttemptFailed`, giữ `serverReady` | |
| `creating` | `meeting-create-failed` 4xx `upload_not_ready` | `error`, `retryable` | |
| `creating` | lỗi mạng hoặc 5xx hoặc thiếu mã cuộc họp | `error`, `createUncertain` | |
| `creating` | kết quả với `createRequest` cũ | không đổi | |
| `error` sau lỗi tạo | `form-edited` | `ready` | |
| `creating`, `starting` | `dialog-close-requested` | không đổi | |
| khác | `dialog-close-requested` | đóng, state về ban đầu | DELETE upload (trừ khi tạo không rõ) |
| bất kỳ | `auto-transcribe-toggled` | không đổi phase | `storage` cờ chép lời |

Thay đổi nhỏ so với bản trước pha 1: đóng dialog gửi DELETE upload dở rồi đóng ngay, không chờ DELETE trả lời; DELETE lỗi vẫn vào `pendingCleanup`. DELETE treo không khóa dialog: Hủy rồi Đóng/Esc vẫn đóng được.

### 11.6. Provider: kết nối ChatGPT và Google Antigravity

Core `provider-core.js` (`reduceProvider`, `reduce`, `initialState`, `selectView`, `selectLauncher`), view `connections.js` (header, hộp thoại, ChatGPT; tạo store chung) và `antigravity.js` (mục Google). Văn bản trong core là `{text, params}`; thời gian định dạng là marker `timestamp(value)`, view dịch bằng `t()` và `Intl`.

**Mô tả provider** (`CHATGPT`, `ANTIGRAVITY`, dữ liệu thuần): `endpoints`, `catalog` (`preferences`: lựa chọn lưu ở `/api/notes-preferences`; `self`: catalog mang model và effort đã lưu), `storageKey` (sessionStorage), `login` (`kind`: `popup` hoặc `code`; `firstPoll`, `poll`, `pollError`; `clientExpiry`; `restoreExpired`; `pollErrors`; `cancelStrict`), `strictStatus`, `loadFailure`, `exclusive` (một thao tác một lúc), `confirmDisconnect`, `effort` (`per-model` hoặc `fixed`), `reconnect` (mã lỗi cần đăng nhập lại), `errors`, `copy`. Luồng viết một lần; khác biệt là nhánh nhỏ theo trường này.

Store: `combine({ chatgpt, antigravity, launcher })`; mọi reducer thấy mọi action. Action `provider/<sự kiện>` mang `provider` (hoặc `meta.provider`); reducer của provider khác bỏ qua. Kết quả mọi `fetch` là `provider/response` hoặc `provider/request-failed` với `meta.op`.

**Id chống response cũ** (trong state mỗi provider): `loadId` (một lượt tải: trạng thái, preferences, catalog; mọi bước mang id), `loginGen` (một lượt đăng nhập/poll/hủy; tăng khi ChatGPT bắt đầu, khi hủy và khi kết thúc; Google không tăng lúc bắt đầu), `headerGen` (giá trị `loadId` lúc đọc trạng thái khi tải trang). Action mang id khác bị bỏ. Key effect: `<provider>/load`, `/poll`, `/poll-wait` (schedule), `/login-start`, `/login-cancel`, `/login-input`, `/login-window`, `/save`, `/verify`, `/disconnect`, `/refresh-load|save|verify`; `provider/header`.

**Tải trạng thái** (`dialog-opened` từ nút launcher, hoặc sau đăng nhập `connected`):

| Từ | Sự kiện (`meta.op`) | Tới | Effect |
| --- | --- | --- | --- |
| bất kỳ | `dialog-opened` | `loading`, `loadId + 1`; ChatGPT: badge và nút `loading`, xóa thông báo | `fetch providers` |
| `loading` | `providers` hợp lệ | trạng thái mới (badge, launcher, tóm tắt kiểm tra) | ChatGPT: `fetch preferences`; Google: `fetch models` nếu `connected`, không thì xóa danh sách model và xong |
| `loading` | `providers` thiếu hoặc trạng thái lạ (ChatGPT) | lỗi `INVALID_PROVIDER_STATUS` | xem dòng lỗi |
| `loading` | `preferences` (ChatGPT) | lưu preferences | `fetch models` nếu `connected`, không thì placeholder "kết nối để tải" và xong |
| `loading` | `models` | danh sách model, lựa chọn đã lưu, effort; model đã lưu không còn thì hiện mục vô hiệu và báo | xong |
| `loading` | lỗi mạng/HTTP, body không phải object | lỗi hiện ra; ChatGPT giữ trạng thái cuối nếu có, không thì badge `error`; Google badge `error` trừ khi cần đăng nhập lại | xong |
| bất kỳ | kết quả với `loadId` cũ | không đổi | |
| trang vừa tải | `header-requested` rồi kết quả | ChatGPT: đặt trạng thái chỉ khi `headerGen = loadId` (chưa có lượt tải mới hơn), sai thì nút `error`; Google: đặt nút chỉ khi chưa có trạng thái | `fetch provider/header` |

Cuộn tới mục Google (`launcher.scroll`): đặt khi mở từ nút Google; view cuộn khi cả hai provider hết `loading`, rồi dispatch `scroll-handled`. Một lượt tải mới hơn trong lúc chờ không hủy cuộn (khác bản cũ, chỉ cuộn khi lượt tải của ChatGPT không đổi).

**Lỗi cần đăng nhập lại** (tải, lưu, kiểm tra): mã `*reconnect_required` và các mã hết quyền (ChatGPT, trừ HTTP 401 là phiên workspace) hoặc `reconnect_required`/`provider_disconnected` (Google).

| Từ | Sự kiện | Tới | Effect |
| --- | --- | --- | --- |
| tải/lưu/kiểm tra | lỗi cần đăng nhập lại | Google: ngay `reconnect_required` hoặc `disconnected`, xóa model; vẫn bận | `fetch refresh-<tác vụ>` (đọc lại trạng thái) |
| chờ refresh | `refresh` ok có provider hợp lệ | áp trạng thái mới (Google không `connected`: xóa model) | |
| chờ refresh | `refresh` lỗi | giữ state | |
| chờ refresh | `refresh` xong | tác vụ kết thúc, hết bận, lỗi hiện ra; thao tác không được gửi lại | |
| tải | `refresh` của `loadId` cũ | không đổi | |

**Lưu, kiểm tra, ngắt kết nối**:

| Từ | Sự kiện | Tới | Effect |
| --- | --- | --- | --- |
| `connected`, có model chọn được | `save-requested` | bận; ChatGPT: trạng thái "Đang lưu" | `fetch save` (PUT) |
| bận | `save-requested`, `verify-requested` (Google, `exclusive`), `disconnect-requested` lặp | không đổi, không gửi thêm | |
| bận lưu | `save` ok | model/effort đã lưu cập nhật, thông báo "Đã lưu" | `event asr:provider-choice-changed` |
| bận lưu | `save` lỗi | lỗi hiện ra; ChatGPT: "Chưa lưu được"; hết bận | refresh nếu cần đăng nhập lại |
| `connected` | `verify-requested` | bận kiểm tra, "Đang chạy…" | `fetch verify` (POST) |
| bận kiểm tra | `verify` ok | kết quả `success`, cập nhật `verification` của provider | |
| bận kiểm tra | `verify` lỗi | kết quả `error`; hết bận | refresh nếu cần đăng nhập lại |
| ChatGPT `connected` | `disconnect-confirm-toggled` | mở hoặc đóng câu hỏi xác nhận; yêu cầu focus | |
| ChatGPT | `disconnect-requested` | bận ngắt | `fetch disconnect` (DELETE) |
| ChatGPT bận ngắt | trả lời `disconnected` | `disconnected`, xóa model, đóng xác nhận, thông báo thu hồi từ xa, focus nút đăng nhập | `event` |
| ChatGPT bận ngắt | trả lời khác hoặc lỗi | `DISCONNECT_NOT_CONFIRMED` hoặc lỗi; giữ kết nối; xác nhận vẫn mở | |
| Google | `disconnect-requested` | bận ngắt | `fetch disconnect` |
| Google bận ngắt | trả lời ok | thông báo; vẫn bận | `fetch providers` (tải lại), `afterLoad` |
| Google chờ tải lại | tải xong (thành công hay lỗi) | hết bận | `event` |
| bất kỳ | `choice-edited` | model/effort chọn đổi; ChatGPT đổi model thì effort về mặc định hoặc đã lưu; báo "chưa được lưu" nếu khác đã lưu | |

**Đăng nhập**:

| Từ | Sự kiện | Tới | Effect |
| --- | --- | --- | --- |
| không đăng nhập | `login-requested` | nút đăng nhập khóa, xóa lỗi (ChatGPT: cả thông báo); lặp khi đang khởi động hoặc đã có login thì bị bỏ | ChatGPT: `open-window reserve`; Google: `fetch login-start` |
| ChatGPT chờ cửa sổ | `window-blocked` | lỗi `POPUP_BLOCKED`, nút mở lại | |
| ChatGPT chờ cửa sổ | `window-reserved` | | `fetch login-start` |
| khởi động | `login-start` hợp lệ | ChatGPT: có login, `loginGen + 1`; Google: có login, link, ô nhập mã | lưu sessionStorage; ChatGPT: `open-window navigate`, `schedule poll-wait` 500; Google: `fetch poll` ngay |
| khởi động | `login-start` sai phiên, URL không an toàn, lỗi (ChatGPT) | lỗi hiện ra, nút mở lại, không có login | `open-window close` |
| khởi động | `login-start` Google: phiên không phải object | lỗi `INVALID_LOGIN_SESSION`, nút mở lại, không có login | |
| khởi động | `login-start` Google: URL sai hoặc không an toàn | lỗi hiện ra, login vẫn giữ và đã lưu: hiện bảng đăng nhập và nút Hủy (người dùng hủy được), không poll | |
| khởi động (ChatGPT) | phiên đã hết hạn lúc trả lời | `expired` ngay | đóng cửa sổ |
| ChatGPT | `window-closed` (người dùng đã đóng) | lỗi "cửa sổ đã đóng"; vẫn poll | |
| có login | `poll-due` (đúng `loginGen`) | ChatGPT: hết hạn thì `expired` | `fetch poll` |
| có login | `poll` pending | ChatGPT: kiểm hết hạn, chép lại; Google: áp lại link/ô nhập | `schedule poll-wait` 1000 |
| có login | `poll` kết thúc (`connected`, `cancelled`, `expired`, `failed`) | không login; thông báo hoặc lỗi theo trạng thái; ChatGPT xóa lỗi | xóa sessionStorage; `connected`: tải lại + `event` |
| có login | `poll` trạng thái lạ (ChatGPT) | lỗi `INVALID_LOGIN_STATUS` kèm "kiểm tra lại" | |
| có login | `poll` lỗi | ChatGPT: lỗi kèm "kiểm tra lại", không poll tự động; Google: phiên không còn (`404`) thì `expired`, lỗi khác thì báo | Google: `schedule` 2000 |
| ChatGPT lỗi poll | `poll-retry-requested` | xóa lỗi | `schedule poll-wait` 0 |
| có login | `login-cancel-requested` | `loginGen + 1`, nút hủy khóa (ChatGPT) | hủy poll, `fetch login-cancel` (DELETE) |
| hủy | trả lời trạng thái kết thúc | như poll kết thúc | |
| hủy | trả lời khác (ChatGPT) hoặc lỗi | lỗi (`CANCEL_NOT_CONFIRMED`), nút hủy mở lại, login giữ; Google: phiên không còn thì `expired`; trả lời nào cũng kết thúc | `schedule` poll 1000 |
| Google có login | `login-input-submitted` (đã cắt khoảng trắng, không rỗng) | | `fetch login-input` |
| Google | `login-input` ok | ô nhập xóa và đóng, áp phiên mới | |
| Google | `login-input` lỗi | lỗi hiện ra, ô nhập giữ | |
| bất kỳ | kết quả poll, hủy với `loginGen` cũ | không đổi (gồm poll bay trước khi hủy) | |

**Khôi phục sau tải lại** (`boot-restored` mang chuỗi sessionStorage thô):

| Từ | Sự kiện | Tới | Effect |
| --- | --- | --- | --- |
| không login | chuỗi `null` hoặc sai hình dạng | không đổi | |
| không login | JSON hỏng | không đổi | xóa sessionStorage |
| không login | ChatGPT hợp lệ | có login | ghi lại sessionStorage; `schedule poll-wait` 0 (poll một lần, poll thấy hết hạn thì kết thúc) |
| không login | Google còn hạn | có login | `fetch poll` ngay |
| không login | Google hết hạn | không đổi | xóa sessionStorage, không gọi mạng |

Khác bản trước pha 2 (đầy đủ trong mục #123 của `architecture-changes-v1.md`): Google cũng bỏ poll trả lời muộn sau hủy hoặc kết thúc (có `loginGen`) và tải trạng thái có `loadId`; bấm đăng nhập lặp bị bỏ; lỗi có câu riêng của nó (cửa sổ đã đóng, URL không an toàn) hiện câu đó ở cả hai ngôn ngữ; một dòng chữ giống hệt không ghi lại vào vùng `aria-live`; cuộn tới mục Google không bị hủy bởi lượt tải mới hơn.

### 11.7. Notes: tab Meeting notes

Core `notes-core.js` (`initialState`, `reduce`, `selectView`, `selectSummary`, `hasUnsavedDraft` và các hàm thuần: nhãn, thông báo lỗi, chuẩn hóa revision/trích dẫn/request, `markdownBlocks`, `sourceReference`, `sourceFromHref`), view `notes.js` (store riêng; render, handler chỉ dispatch). `notes.js` là `<script type="module">` đứng sau `history.js` (script `defer`) và trước `connections.js`, nên chạy đúng thứ tự cũ và thấy `window.ASRMeetingHistory`. Văn bản trong core là `{text, params}`; view dịch bằng `t()`; chuỗi trần là lời của máy chủ.

**State** (`state`): `mode` (`view`/`write`), `hidden` (trang ở nền), `origin`, `view`, `meetingId`, `meeting` (object của `history.js`), `transcribing`, `speakerNames` (tên người nói mặc định, đi cùng context), `choice` (lựa chọn provider: `loaded`, `loadedFor`, `loading`, `loadId`, `load` {pha tải}, `localProvider`, `preferences`, `status`, `catalogs`, `catalogErrors`, `saving`, `saveId`, `message`, `open`), `notes[meetingId]` (`revisions`, `task`, `sourceLocked`, `sourceLockKnown`, `known`, `selectedNoteId`, `starting`, `canceling`, `saving[revisionId]`, `readError`, `runError`, `runErrorUncertain`, `actionMessage`), `drafts[revisionId]` (`value`, `baselineMarkdown`, `expectedEditVersion`, `conflict`), `outputLanguages`, `pending[meetingId]` (request chờ trả lời), `taskSteps[taskId]`, `snapshots`, `readId`, `authoritativeId`, `poll` {`token`, `scheduled`}, `source` {`id`, `key`, `current`, `visible`, `status`, `focus`}.

**Id chống response cũ**: `readId` (lần đọc notes mới nhất; meta `{id, meetingId, poll}`), `poll.token` (tăng khi dừng poll, đổi meeting; poll cũ bị bỏ), `choice.loadId` (một lượt tải lựa chọn: providers, preferences, catalog), `choice.saveId`, `source.id` (một lần mở nguồn; tăng khi đóng), `authoritativeId` (số duy nhất làm hậu tố key `notes/authoritative/<n>`, không so với response). Key effect: `notes/read/<id>`, `notes/poll` (schedule, thay thế nhau), `notes/choice/providers/<loadId>`, `notes/choice/preferences/<loadId>`, `notes/choice/catalog/<provider>/<loadId>`, `notes/choice/save/<saveId>`, `notes/start/<meetingId>`, `notes/cancel/<taskId>`, `notes/save/<revisionId>`, `notes/save-latest/<revisionId>`, `notes/authoritative/<n>`, `notes/source-snapshot/<id>`, `notes/copy`, `notes/source-shown` (schedule 0 trước mark/seek), `notes/source-open-seek`, `notes/source-play`, `notes/source-seek`, `notes/host` (lệnh không có kết quả). Mỗi request có key riêng nên không request nào bị hủy giữa chừng (như bản cũ); response cũ bị bỏ vì id trong `meta` không khớp state.

**Vào trang và đọc notes**:

| Từ | Sự kiện | Tới | Effect |
| --- | --- | --- | --- |
| bất kỳ | `booted` | `mode` từ localStorage, `hidden`, `origin` | |
| bất kỳ | `context` không có meeting | `meetingId = null`, `poll.token + 1` | hủy `notes/poll` |
| bất kỳ | `context` có meeting | `meetingId`, `meeting`; đổi meeting: dừng poll, đóng ô chọn, `sourceLockKnown/known = false`; nhận khóa nguồn từ meeting; nhận request và ngôn ngữ đã lưu nếu chưa có | `call setNotesSourceLock`, `fetch` notes; đổi meeting hoặc chưa tải lựa chọn: tải lựa chọn; xử lý địa chỉ trang (mở/đóng nguồn); `call setNotesSummary` |
| đang đọc | `read` ok hợp lệ, id/meeting/poll khớp | `revisions`, `task`, khóa nguồn, `known`; chọn revision đầu nếu chưa chọn; xóa `pending` nếu task trùng `request_id` hoặc đang chạy; task vừa kết thúc: tải lại lựa chọn | `call setNotesSourceLock`; task đang chạy: `schedule notes/poll` nếu chưa có, không thì hủy poll |
| đang đọc | `read` ok sai hình dạng, hoặc lỗi mạng/HTTP | `known = true`, `readError` | chưa biết khóa: `call setNotesSourceLock false`; poll: `schedule` 3000 |
| bất kỳ | `read` với id/meeting/poll cũ | không đổi | |
| có task đang chạy | `poll-due` (đúng token, meeting, task còn chạy) | | `fetch` notes (poll) |
| có task đang chạy | `visibility-changed` | `hidden` | `schedule` 3000 (ẩn) hoặc 1000 |

**Chọn provider/model** (`choice`): `loadId + 1`, `loading`, `loaded = false`, rồi `providers` và `preferences` song song; cả hai ok thì áp (trạng thái, preferences, `loaded`, `loadedFor`) và tải catalog của provider `connected` (provider khác: `catalogs = null` kèm lý do); catalog xong hết thì `loading = false`. Một trong hai lỗi: `loaded = false`, `loading = false`, `message` (chặn tạo notes tới khi tải lại); catalog lỗi: `provider_in_use` hoặc lỗi chung, model đã lưu vẫn giữ. Mọi kết quả `loadId` cũ bị bỏ. Chọn provider có model đã lưu hoặc chọn model: `saving`, `PUT /api/notes-preferences` (`saveId`); ok: `preferences`, `message` (nói rõ task đang chạy giữ provider cũ), `saving = false`; lỗi: `message`, lựa chọn đã lưu giữ. Chọn provider chưa có model: `localProvider` tới khi chọn model. Ngôn ngữ đầu ra: ghi local+session; bị bỏ khi có `pending`.

**Chạy, hủy**:

| Từ | Sự kiện | Tới | Effect |
| --- | --- | --- | --- |
| sẵn sàng (`canStartNotes`) | `start-clicked {requestId}` | tạo `pending` nếu chưa có và điền phần còn thiếu (generation, version, model, effort); `starting = true`, xóa lỗi | ghi `pending` (local+session); `call selectTab notes`; `fetch POST notes-runs` |
| không sẵn sàng hoặc `starting` | `start-clicked` | không đổi, không gửi thêm | |
| `starting` | `start` ok, task hợp lệ | `task`, khóa nguồn theo trạng thái task, xóa `pending`, thông báo | xóa storage; `call setNotesSourceLock`; task chạy: poll; không: đọc notes |
| `starting` | `start` ok, task sai hình dạng | `runError` không chắc chắn (giữ `pending`) | |
| `starting` | `start` lỗi 4xx | xóa `pending`; `runError` theo `error.code` của provider; có mã: tải lại lựa chọn; 409: đọc notes, làm mới meeting | |
| `starting` | `start` lỗi mạng/5xx | giữ `pending`, `runErrorUncertain`; nút thành "Xác minh yêu cầu notes" gửi lại cùng request id | |
| task đang chạy, không `canceling` | `cancel-clicked` | `canceling = true` | `fetch POST` hủy |
| `canceling` | `cancel` ok | `task` mới, xóa `runError`; còn chạy: poll; không: đọc notes | |
| `canceling` | `cancel` lỗi | `runError`, `canceling = false` | |
| `canceling` | `cancel-clicked` | không đổi | |

**Revision và bản nháp** (reducer tạo/đối chiếu bản nháp của revision đang chọn sau mỗi action: chưa có thì tạo; sạch thì theo bản đã lưu; bẩn và `edit_version` khác thì đặt `conflict`):

| Từ | Sự kiện | Tới | Effect |
| --- | --- | --- | --- |
| có bản nháp | `draft-edited` | `value`; `conflict` nếu khác phiên bản đã lưu | |
| bẩn, không đang lưu | `save-clicked` | `saving[id] = true` | `fetch PATCH` (`expected_edit_version`, `markdown`) |
| đang lưu hoặc sạch | `save-clicked` | không đổi | |
| đang lưu | `save` ok khớp id/meeting | revision thay thế, bản nháp = bản đã lưu, `conflict = null` | |
| đang lưu | `save` ok sai revision/meeting hoặc sai hình dạng | `actionMessage` lỗi, bản nháp giữ | |
| đang lưu | `save` lỗi 409 | không đổi (vẫn đang lưu) | `fetch GET` bản mới nhất |
| đang lưu | `save-latest` ok | revision thay thế, `conflict = {markdown, editVersion}`, bản nháp giữ | |
| đang lưu | `save-latest` lỗi hoặc sai revision | `conflict` tạm `{markdown: "", editVersion: expectedEditVersion}`, hết đang lưu, bản nháp giữ, báo chưa tải được bản mới nhất | |
| đang lưu | `save` lỗi khác | `actionMessage`, bản nháp giữ | |
| `conflict` | `keep-draft-clicked` | nền = bản của người khác, `expectedEditVersion` mới, `conflict = null` | như `save-clicked` |
| `conflict` | `use-latest-clicked` | bản nháp = bản đã lưu mới nhất | |
| sạch, không `conflict`, không đang lưu | `copy-clicked`/`export-clicked` | "Đang đọc…" | `fetch GET` bản đã lưu |
| bẩn, `conflict` hoặc đang lưu | `copy-clicked`/`export-clicked` | báo lưu trước | |
| đang đọc để chép | trả lời; bản nháp đổi trong lúc đọc | `conflict`, không chép | |
| đang đọc để chép | trả lời; revision hoặc meeting đã đổi | báo chọn lại, không chép | |
| đang đọc để chép | trả lời hợp lệ | bản nháp theo bản mới nhất nếu khác | chép: `call copy` rồi `copied`/`copy-failed`; tải: `call download` |
| bất kỳ | `mode-chosen` | `mode` | `storage` ghi localStorage |
| bất kỳ | `revision-picked` | `selectedNoteId`, xóa thông báo | |

**Nguồn trích dẫn** (`source`): `source-opened {reference, fromClick}` (chỉ khi bấm chip) cho cùng meeting; địa chỉ trang qua `context`/`location-changed` đi cùng đường mở nguồn nhưng không qua action này: `source.id + 1`, `key`, "Đang tải…"; click: `call showNotesSourceTab`; snapshot chưa có: `fetch` (`snapshots` giữ bản đã tải). Snapshot sai meeting/id: lỗi (nếu còn là lần mở mới nhất). Snapshot đúng nhưng đã có lần mở mới hơn hoặc đã đổi meeting: bỏ. Không thấy đoạn: lỗi. Đủ: `current`, `visible`, `focus + 1` (view focus tiêu đề), `schedule notes/source-shown` (delay 0, để view vẽ thẻ nguồn trước) → `source-shown {id}`: còn đúng lần mở và còn `current` thì `call markNotesSource`, `call seekNotesSource` → `source-sought`: tua không được thì báo; được thì `call playRecording` → `source-played`: "đang phát" hoặc "bấm phát". Lỗi của hai lệnh = lỗi mở nguồn. `source-closed {href}`: `source.id + 1`, `current = null`, ẩn; `call markNotesSource null`; địa chỉ còn query thì `call replaceUrl`. `location-changed`: địa chỉ không còn nguồn mà đang mở thì đóng (không đổi địa chỉ); cùng nguồn đang hiện thì không làm gì. `source-seek-clicked`: `call seekNotesSource` → báo, đánh dấu dòng transcript nếu tua được.

**Quy ước view**: `render` chỉ chạy khi có meeting (bản cũ còn vẽ lại tab đang ẩn khi một trả lời tới sau lúc rời cuộc họp: tải/lưu lựa chọn, chép/tải xuống; không thấy được vì tab ẩn và context kế tiếp vẽ lại); ô xem trước Markdown chỉ dựng lại khi các khối đổi (khóa JSON), nên focus trên chip trích dẫn được giữ; câu hỏi chỉ đọc tới `history.js` gọi thẳng: `currentContext` lúc boot, `defaultSpeakerNames` lúc nhận `asr:meeting-context` (tên vào action `notes/context`), `hasUnsavedTranscriptDrafts` lúc trang đóng; ghi chú đã copy/tải chỉ cập nhật `#notes-copy-export-status` khi có chữ (như bản cũ).

**Khác bản trước pha 3** (đầy đủ trong mục #126 của `architecture-changes-v1.md`): ô cảnh báo liên kết hỏng không dựng lại khi nội dung không đổi; sau một lần tạo notes mà máy chủ trả task đã kết thúc ngay, nút "Đang gửi yêu cầu…" tắt trước khi lần đọc lại xong; lỗi mở nguồn để lại nút tua bị khóa; không vẽ lại tab ẩn khi trả lời tới sau lúc rời cuộc họp; nhắc tên người nói không thấy người nói mới thêm ở tab Bản ghi tới context kế tiếp; ô xem trước không dựng lại khi khối không đổi, nên ẩn/hiện tab hay một lượt poll không làm mất focus trên chip trích dẫn.
