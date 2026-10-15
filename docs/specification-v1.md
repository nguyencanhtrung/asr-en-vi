# Đặc tả v1 — ASR EN VI Meeting Notes

Ứng dụng desktop chạy trên Ubuntu để biến bản ghi cuộc họp của một nhóm nội bộ cố định thành meeting notes tiếng Anh. Người dùng nhập bản ghi, chọn ngôn ngữ chính, xử lý tại máy, nghe lại và sửa bản nháp, sau đó copy hoặc xuất notes.

Các yêu cầu sản phẩm dưới đây tổng hợp những quyết định đã được người dùng đồng ý trong phiên làm rõ specification. Mục tiêu hiệu năng và chất lượng cần được kiểm chứng bằng bản ghi thực tế trước khi nghiệm thu.

## 1. Người dùng và phạm vi

| Thuộc tính | Yêu cầu v1 |
| --- | --- |
| Người dùng | Một nhóm nội bộ cố định; nội dung chủ yếu từ người dùng và boss |
| Thời điểm xử lý | Sau cuộc họp |
| Nguồn | File audio hoặc video đã thu từ Meet hoặc microphone trong phòng |
| Buổi họp điển hình | Dài 1–2 giờ, có 2–3 người nói; người dùng và boss có thể cùng xuất hiện |
| Ngôn ngữ đầu vào | Toàn tiếng Anh; tiếng Việt xen thuật ngữ Anh; hoặc cả hai ngôn ngữ trong một bản ghi |
| Transcript | Giữ ngôn ngữ đã nói, gồm thuật ngữ Anh trong câu Việt |
| Meeting notes | Tiếng Anh |
| Thiết bị | Máy hiện có với Ryzen 9 và RTX 5080; không mua thêm phần cứng |
| Hệ điều hành đích | Ubuntu 24.04 trên máy hiện tại |
| Hình thức ứng dụng | GUI được đóng gói thành công cụ có biểu tượng mở ứng dụng |
| Phạm vi dữ liệu | Xử lý và lưu trữ hoàn toàn local; vận hành offline sau thiết lập |

Phạm vi nghiệm thu tập trung vào các bản ghi 1–2 giờ. Khả năng xử lý bản ghi dài hơn sẽ được xác định bằng thử nghiệm, không suy ra từ độ dài ngữ cảnh quảng cáo của model.

V1 không bao gồm tự ghi âm, bot tham gia Meet, chép lời thời gian thực, nhận diện danh tính người nói xuyên nhiều cuộc họp, dịch toàn bộ transcript, đồng bộ cloud hoặc tự gửi notes cho người khác. Các định dạng Word/PDF và hỗ trợ Windows chưa thuộc phạm vi đã chốt.

## 2. Luồng sử dụng

1. Mở ứng dụng, vào lịch sử hoặc tạo cuộc họp mới.
2. Kéo thả hoặc chọn file audio/video có sẵn.
3. Đặt tên cuộc họp, chọn ngôn ngữ chính và tùy chọn nhập ngày họp.
4. Bắt đầu xử lý; xem tiến độ hoặc hủy tác vụ.
5. Xem transcript, nhãn người nói và notes tiếng Anh.
6. Bấm mốc thời gian để nghe lại đoạn nguồn; sửa transcript hoặc notes.
7. Khi cần, chủ động tạo lại notes từ transcript đã sửa.
8. Copy notes hoặc xuất Markdown; mở lại cuộc họp từ lịch sử khi cần.

### 2.1. Nhập bản ghi và metadata

- Hỗ trợ file audio và video trong tập định dạng được ứng dụng công bố. Tập định dạng cụ thể phải bao phủ các file mẫu thực tế được chọn để nghiệm thu.
- Lựa chọn ngôn ngữ chính gồm **English** và **Vietnamese**.
- Ngôn ngữ chính là gợi ý nhận dạng. Chọn Vietnamese vẫn phải giữ thuật ngữ Anh; chọn English vẫn phải xử lý được đoạn tiếng Việt trong cùng bản ghi.
- Lựa chọn ngôn ngữ chính không thay đổi ngôn ngữ đầu ra của notes, vốn luôn là tiếng Anh, và không yêu cầu dịch transcript.
- Ngày họp có thể để trống. Không coi ngày xử lý hoặc thời gian sửa file là ngày họp đã được xác nhận.
- Ứng dụng lưu bản sao âm thanh riêng cho cuộc họp. Lịch sử vẫn phải phát lại được sau khi file nguồn bên ngoài bị đổi tên, di chuyển hoặc xóa.

### 2.2. Xử lý và tiến độ

- Chỉ xử lý một cuộc họp mỗi lần trong v1.
- GUI hiển thị giai đoạn đang chạy, trạng thái hoàn tất hoặc lỗi và cung cấp nút hủy.
- Tác vụ bị lỗi hoặc bị hủy không được hiển thị là đã hoàn thành đầy đủ.
- Khi không thể tiếp tục, thông báo phải chỉ rõ vấn đề để người dùng có thể thử lại hoặc thay đầu vào. Không âm thầm bỏ phần còn lại của bản ghi.
- Không có cơ chế tự chuyển sang dịch vụ cloud khi xử lý local thất bại.

Chi tiết kỹ thuật như hàng đợi, checkpoint và cách nạp model được quyết định khi triển khai; không phải tính năng người dùng bắt buộc của v1.

## 3. Transcript, người nói và bằng chứng

### 3.1. Transcript

- Lưu transcript đầy đủ để đọc, chỉnh sửa và đối chiếu với bản ghi.
- Bảo toàn nội dung và ngôn ngữ đã nói; giữ các thuật ngữ tiếng Anh trong câu Việt.
- Mỗi đoạn phát biểu có mốc thời gian trên bản ghi và nhãn người nói khi xác định được.
- Độ phân giải thời gian theo đoạn là đủ cho v1. Không cam kết mọi từ đều có timestamp chính xác.
- Mốc thời gian trên GUI phải mở được đúng đoạn âm thanh liên quan. Trong bản Markdown xuất ra, mốc thời gian vẫn phải đọc và đối chiếu được, dù không có trình phát của ứng dụng.

### 3.2. Người nói

- Phân biệt người nói trong từng cuộc họp bằng các nhãn như `Speaker 1`, `Speaker 2`, `Speaker 3`.
- Nhãn chỉ có ý nghĩa trong cuộc họp đó; không biểu thị cùng một người ở các cuộc họp khác nhau.
- Người dùng không phải gán tên cho các nhãn và ứng dụng không cần tự nhận ra boss hoặc thành viên cố định.
- Tên được nhắc trong nội dung vẫn được giữ khi phù hợp. Ví dụ, “John will send the report” có thể tạo action item với người phụ trách John mà không cần biết John là nhãn người nói nào.

### 3.3. Nội dung chưa rõ

- Đoạn mà hệ thống phát hiện không chắc chắn phải được đánh dấu để người dùng nghe lại, kèm mốc thời gian.
- Bước tạo notes không được tự bổ sung thông tin sự kiện vào phần nội dung còn thiếu hoặc chưa rõ.
- Quyết định hoặc action item dựa trên đoạn chưa rõ phải được đưa vào phần cần xác nhận.
- Nói chồng, tiếng ồn và chuyển ngôn ngữ là các trường hợp phải có trong đánh giá khi xuất hiện trong dữ liệu thực tế.

Đánh dấu không chắc chắn là hỗ trợ cho bước duyệt, không phải bảo đảm rằng hệ thống phát hiện được mọi lỗi nhận dạng. WhisperX công bố các hạn chế với nói chồng và phân biệt người nói; vì vậy chất lượng phải được đo trên dữ liệu của nhóm. [Nguồn WhisperX](https://github.com/m-bain/whisperX#limitations-)

## 4. Meeting notes tiếng Anh

Notes là bản nháp để người dùng duyệt. Cấu trúc nội dung gồm:

| Phần | Nội dung |
| --- | --- |
| Overview | Tổng quan ngắn về cuộc họp |
| Key Topics and Rationale | Vấn đề quan trọng, lập luận và các phương án đã cân nhắc |
| Decisions | Các quyết định đã thống nhất, kèm mốc thời gian nguồn |
| Open Questions | Vấn đề chưa chốt và các điểm còn bất đồng |
| Confirmed Action Items | Các công việc đã được thống nhất |
| Items Requiring Confirmation | Đề xuất chưa thống nhất, nội dung mơ hồ hoặc cần người dùng kiểm tra |

Notes phải giữ được ý nghĩa của phát biểu tiếng Anh lẫn tiếng Việt. Việc diễn đạt lại bằng tiếng Anh không được làm tăng mức chắc chắn của phát biểu hoặc biến một ý tưởng thành quyết định.

### 4.1. Action items

Mỗi action item có nội dung công việc, người phụ trách, thời hạn nếu có, trạng thái đã thống nhất/cần xác nhận và mốc thời gian nguồn.

| Tình huống | Cách ghi nhận |
| --- | --- |
| Công việc đã thống nhất, người phụ trách và thời hạn rõ | Ghi thông tin được phát biểu và dẫn về đoạn nguồn |
| Thiếu người phụ trách | Ghi chưa xác định; không tự giao cho người dùng hoặc boss |
| Thiếu thời hạn | Ghi chưa xác định; không tự đặt deadline |
| `Speaker 2` nói “I'll send the report tomorrow” | Người phụ trách là `Speaker 2`; xử lý “tomorrow” theo quy tắc ngày họp |
| Người nói giao việc rõ ràng cho John | Người phụ trách là John, dù người phát biểu có nhãn khác |
| “We should investigate this next week” nhưng chưa có cam kết rõ | Đưa vào phần cần xác nhận, giữ những thông tin thực sự có trong phát biểu |
| Đề xuất do hệ thống sinh, nếu có | Ghi rõ là đề xuất của hệ thống và tách khỏi công việc đã thống nhất trong cuộc họp |

Người nói và người phụ trách là hai thông tin riêng. Người dùng có thể sửa người phụ trách khi duyệt mà không cần đặt tên cho các nhãn người nói.

### 4.2. Ngày họp và deadline

- Chỉ quy đổi mốc thời gian tương đối khi có ngày họp và đủ cơ sở xác định.
- Nếu không có ngày họp, giữ nguyên cách nói như “tomorrow”; không lấy ngày xử lý làm mốc.
- Các cách nói chưa xác định được một ngày cụ thể như “next week” được giữ nguyên. Không tự chọn một ngày trong tuần.
- Kết quả phải cho phép đối chiếu deadline với phát biểu gốc tại mốc thời gian nguồn.

## 5. Duyệt, sửa và tạo lại notes

- GUI có trình phát âm thanh, transcript và notes để người dùng đối chiếu.
- Người dùng sửa trực tiếp được cả transcript và notes.
- Sau khi transcript thay đổi, ứng dụng báo rằng notes hiện tại chưa phản ánh thay đổi đó.
- Người dùng chủ động kích hoạt tạo lại notes; việc sửa transcript không tự ghi đè notes.
- Mỗi lần tạo lại notes tạo một bản nháp mới. Giữ bản trước để người dùng quay lại, kể cả khi bản đó đã được sửa thủ công.
- Phân biệt được bản notes đang xem, bản được tạo từ transcript trước đó và bản mới nhất. Không trình bày một bản cũ như thể đã phản ánh transcript vừa sửa.
- Bước duyệt tập trung vào quyết định, người phụ trách, thời hạn, số liệu, thuật ngữ quan trọng và các phần cần xác nhận.

Mục tiêu là khoảng **5–10 phút duyệt và sửa cho mỗi giờ họp**. Đây là mục tiêu cần đo với người dùng thực tế, không phải một giới hạn buộc người dùng phải dừng kiểm tra.

## 6. Lưu trữ, xuất kết quả và thiết lập offline

### 6.1. Lịch sử local

- Hiển thị danh sách cuộc họp đã nhập/xử lý để mở lại.
- Lưu local bản sao âm thanh, metadata, transcript, notes và các bản notes trước đó cần để quay lại.
- Giữ dữ liệu đến khi người dùng chủ động xóa; không có lịch tự xóa trong phạm vi đã chốt.
- Khi xóa cuộc họp, xóa bản sao âm thanh và kết quả do ứng dụng quản lý. Giữ nguyên file nguồn bên ngoài.

### 6.2. Copy và xuất

- Có nút **Copy notes** và chức năng xuất **Markdown**.
- Copy/xuất sử dụng bản notes người dùng đang chọn, bao gồm các chỉnh sửa của bản đó.
- Kết quả giữ cấu trúc nội dung, action items, trạng thái cần xác nhận và mốc thời gian nguồn.
- Ứng dụng không tự gửi kết quả tới boss, các thành viên hoặc một dịch vụ bên ngoài.

### 6.3. Thiết lập và runtime

- Cho phép tải model và các tài nguyên cần thiết từ Internet trong lần thiết lập đầu.
- Sau khi thiết lập đủ tài nguyên, toàn bộ thao tác nhập, xử lý, nghe lại, sửa, mở lịch sử và xuất phải hoạt động khi ngắt Internet.
- Không gửi âm thanh, transcript, notes hoặc metadata cuộc họp ra ngoài. Tắt telemetry; runtime xử lý cuộc họp không phát sinh kết nối Internet, kể cả khi máy có mạng. Chuẩn bị đủ tài nguyên ở bước thiết lập để không cần tải động lúc chạy.
- Model, thư viện và cơ chế đóng gói được chọn theo khả năng hoạt động trên máy đã chốt.
- Nếu chọn model có yêu cầu tài khoản, token hoặc chấp thuận điều khoản, bước thiết lập phải thể hiện rõ và để người dùng thực hiện. Việc cho phép tải model không đồng nghĩa với cho phép ứng dụng tự chấp thuận điều khoản thay người dùng.

## 7. Giới hạn phần cứng và lựa chọn kỹ thuật

Ngân sách phần cứng là máy Ryzen 9 và RTX 5080 hiện có. RTX 5080 có **16 GB VRAM** theo thông số NVIDIA. Không đưa việc mua thêm phần cứng thành điều kiện để đạt phạm vi v1. [Nguồn NVIDIA](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5080/)

Khảo sát môi trường hiện tại ghi nhận Ubuntu 24.04.4, Ryzen 9 9950X và khoảng 60,4 GiB RAM tổng mà hệ điều hành nhận. Lần khảo sát chưa đọc được GPU qua `nvidia-smi`; cần xác minh runtime GPU trên máy đích trước khi đo hiệu năng.

[PDF nghiên cứu ban đầu](ASR-initial-deep-research-vi.pdf) là tài liệu tham khảo về giải pháp. Các tên PhoWhisper, WhisperX, pyannote, Qwen2.5 32B và vLLM là ứng viên, không phải các thành phần đã được chốt bắt buộc.

Các quyết định kỹ thuật cần giải quyết bằng thử nghiệm:

- Chọn ASR cho toàn tiếng Anh, tiếng Việt xen thuật ngữ và chuyển ngôn ngữ trong cùng bản ghi. Kết quả benchmark tiếng Việt của PhoWhisper chưa đủ để suy ra chất lượng ở cả ba trường hợp. [Nguồn VinAI](https://github.com/VinAIResearch/PhoWhisper)
- Chọn cách phân biệt người nói và căn chỉnh thời gian đủ tốt để mở đúng đoạn nguồn, kể cả khi chuyển ngôn ngữ.
- Chọn model tạo notes và cách xử lý transcript dài phù hợp RAM/VRAM. Cấu hình mặc định 32.768 token của Qwen2.5-32B-Instruct không tự chứng minh khả năng xử lý toàn bộ cuộc họp trong một lượt; ngữ cảnh dài hơn cần cấu hình bổ sung và đo thực tế. [Model card Qwen](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct#processing-long-texts)
- Kiểm tra khả năng tải và chạy offline toàn bộ tài nguyên. Ví dụ, model Community-1 được WhisperX hiện dùng có điều kiện truy cập trên Hugging Face và hỗ trợ chạy từ bản tải local. [Model card pyannote](https://huggingface.co/pyannote/speaker-diarization-community-1)

Framework GUI, định dạng đóng gói, cấu trúc lưu trữ, precision và cách sắp xếp model trong bộ nhớ là lựa chọn triển khai. Các lựa chọn đó phải phục vụ hành vi và tiêu chí trong đặc tả này.

## 8. Nghiệm thu

### 8.1. Bộ bản ghi thực tế

Khởi đầu bằng ít nhất ba bản ghi đại diện, được xử lý local:

1. Cuộc họp hoàn toàn bằng tiếng Anh.
2. Cuộc họp tiếng Việt xen thuật ngữ Anh.
3. Cuộc họp có cả tiếng Anh và tiếng Việt trong cùng bản ghi.

Người dùng đánh dấu trước các ý quan trọng, quyết định và công việc cần có trong kết quả. Bộ mẫu phản ánh cách thu thực tế, độ dài 1–2 giờ và 2–3 người nói. Cần có mẫu dài 2 giờ để kiểm chứng trực tiếp mục tiêu thời gian cho bản ghi 2 giờ.

### 8.2. Tiêu chí kiểm tra

| Mã | Tiêu chí | Cách kiểm tra |
| --- | --- | --- |
| AC-01 | Nhận đúng nội dung quan trọng ở cả ba trường hợp ngôn ngữ | Đối chiếu từng bản ghi với phần người dùng đã đánh dấu; không dùng kết quả tốt ở một ngôn ngữ để che lỗi ở ngôn ngữ khác |
| AC-02 | Notes tiếng Anh ghi đủ các ý quan trọng đã đánh dấu | So sánh notes với nội dung nguồn và các mục đã xác định trước |
| AC-03 | Không bịa quyết định, người phụ trách hoặc deadline trong bộ mẫu | Đối chiếu từng quyết định/action item; kiểm tra riêng trường hợp thiếu thông tin và phát biểu mơ hồ |
| AC-04 | Dùng đúng nhãn người nói tại các đoạn quan trọng | Kiểm tra đoạn đổi người nói và action item dùng đại từ “tôi”; không yêu cầu nhận diện tên |
| AC-05 | Mốc thời gian tìm được đúng bằng chứng | Bấm mốc của quyết định/action item và nghe đoạn nguồn; timestamp theo đoạn là đủ |
| AC-06 | Xử lý deadline tương đối đúng điều kiện | Kiểm tra có/không có ngày họp, “tomorrow” và “next week” |
| AC-07 | Giữ chỉnh sửa và các bản notes | Sửa transcript, kiểm tra cảnh báo notes cũ; tạo lại, rồi mở lại bản notes đã sửa trước đó |
| AC-08 | Lịch sử không phụ thuộc vị trí file nguồn | Di chuyển file nguồn sau khi nhập; mở lại cuộc họp và phát âm thanh từ bản sao |
| AC-09 | Xóa đúng phạm vi | Xóa cuộc họp; kiểm tra dữ liệu ứng dụng được xóa và file nguồn bên ngoài vẫn còn |
| AC-10 | Offline sau thiết lập và không gửi dữ liệu ra ngoài | Ngắt Internet rồi thực hiện toàn bộ luồng sử dụng; khi máy có mạng, kiểm tra runtime không phát sinh kết nối Internet hoặc gửi telemetry |
| AC-11 | Copy và Markdown phản ánh bản notes được chọn | Đối chiếu kết quả xuất với bản đã sửa, gồm action items và timestamp |
| AC-12 | Tiến độ, hủy và lỗi được thể hiện đúng | Hủy tác vụ, thử đầu vào không hỗ trợ và lỗi xử lý; không báo hoàn thành đầy đủ cho tác vụ thất bại |
| AC-13 | Mục tiêu xử lý bản ghi 2 giờ trong tối đa 30 phút | Đo trên máy đích sau thiết lập; tính từ bắt đầu xử lý đến khi cả transcript và notes sẵn để duyệt, gồm nạp model và tiền xử lý |
| AC-14 | Mục tiêu duyệt/sửa khoảng 5–10 phút mỗi giờ họp | Người dùng đo thời gian thực tế để đưa bản nháp về mức dùng được trên từng bản ghi |

AC-13 và AC-14 là **mục tiêu đã thống nhất nhưng chưa được kiểm chứng**. Báo cáo nghiệm thu phải ghi rõ kết quả đạt/chưa đạt, phần cứng, cấu hình model và bản ghi dùng để đo. Không suy ra đạt mục tiêu chỉ từ tốc độ quảng cáo của một thành phần hoặc một đoạn âm thanh ngắn.

Các kiểm tra chất lượng áp dụng trên bộ mẫu đã duyệt; kết quả đạt trên bộ mẫu không phải cam kết chính xác tuyệt đối cho mọi cuộc họp. Khi kết quả chưa đạt, cần ghi rõ sai lệch và thử điều chỉnh trong giới hạn phần cứng hiện có.
