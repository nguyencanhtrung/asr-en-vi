# Ứng viên model cho backend v1

> Trạng thái: người dùng đã đồng ý bộ thử nghiệm Q7 rồi **hoãn Qwen theo Q12**, chuyển notes sang ChatGPT hoặc OMP + Google Antigravity. Chưa benchmark hoặc chốt cấu hình phát hành. Đọc nguồn ngày 2026-10-15. Phạm vi, phần cứng và tiêu chí nghiệm thu theo [spec v1](specification-v1.md), đặc biệt AC-01–06, AC-10 và AC-13–14.

## Bộ model đã chốt để thử trước

Chọn **Whisper large-v3 để chuyển âm thanh thành transcript** và **pyannote Community-1 để phân biệt người nói** chạy local. Tạo notes (English hoặc Tiếng Việt) qua **ChatGPT** hoặc **OMP + Google Antigravity**, ưu tiên khảo sát Gemini ở nhánh Antigravity; Q27 cho người dùng chọn model phù hợp từ catalog của kết nối. Model ID cụ thể còn cần kiểm chứng. Qwen3-14B Q4_K_M từng được chọn thử nhưng không còn thuộc pipeline v1 đã chọn, nhằm dành VRAM cho xử lý âm thanh. Kết quả trên bản ghi của nhóm mới quyết định cấu hình phát hành.

| Vai trò | Model / tài nguyên | Runtime đề xuất và căn cứ |
| --- | --- | --- |
| Âm thanh → văn bản | `openai/whisper-large-v3` | `faster-whisper` dùng CTranslate2; hỗ trợ FP16, INT8 và timestamp theo đoạn. Model đa ngôn ngữ, có chế độ chép lời giữ ngôn ngữ nguồn. [Model card](https://huggingface.co/openai/whisper-large-v3), [runtime](https://github.com/SYSTRAN/faster-whisper) |
| Ai nói, lúc nào | `pyannote/speaker-diarization-community-1` | `pyannote.audio`; trả đoạn thời gian theo nhãn người nói, có đầu ra exclusive giúp ghép với transcript. Chạy local được sau tải model. [Model card](https://huggingface.co/pyannote/speaker-diarization-community-1) |
| Transcript → notes | Model được tài khoản ChatGPT hoặc Antigravity cho phép dùng; nhánh Antigravity ưu tiên khảo sát Gemini | Cloud qua adapter đã chọn; không nạp LLM local. Xem [subscription](subscription-notes-options-v1.md), [harness](harness-notes-v1.md) và ràng buộc provider tại [ADR 0007](adr/0007-cloud-notes-providers.md) |

`faster-whisper`, `llama.cpp` và `vLLM` là phần mềm chạy model. WhisperX là bộ ghép ASR, căn chỉnh thời gian và diarization; không phải một model thay thế Whisper. V1 chỉ cần timestamp theo đoạn, nên chưa cần buộc thêm model căn chỉnh từng từ. [WhisperX](https://github.com/m-bain/whisperX)

## Ứng viên đối chiếu

| Model | Lý do giữ trong danh sách | Điều phải kiểm chứng |
| --- | --- | --- |
| `vinai/PhoWhisper-large` | VinAI tinh chỉnh Whisper trên 844 giờ tiếng Việt với nhiều giọng vùng miền; bản large có 1,55 tỷ tham số. [Nguồn VinAI](https://github.com/VinAIResearch/PhoWhisper) | So với Whisper trên câu Việt xen thuật ngữ Anh và cuộc họp đổi ngôn ngữ. Benchmark tiếng Việt không chứng minh chất lượng tiếng Anh; chưa đề xuất tự chuyển sang PhoWhisper chỉ vì người dùng chọn Vietnamese. |
| `Qwen/Qwen3-ASR-1.7B` | Có hỗ trợ chính thức English và Vietnamese; runtime `qwen-asr` dùng Transformers hoặc vLLM. [Model card](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) | Chất lượng, tốc độ và cách giữ timestamp tiếng Việt. `Qwen3-ForcedAligner-0.6B` đi kèm chỉ liệt kê 11 ngôn ngữ, không có Vietnamese; không được suy ra ASR hỗ trợ tiếng Việt thì aligner cũng hỗ trợ. [Danh sách hỗ trợ](https://huggingface.co/Qwen/Qwen3-ASR-1.7B#released-models-description-and-download) |
| `Qwen/Qwen3.5-9B` — hoãn | Đã phát hành; nhận văn bản, có chế độ tắt thinking. Qwen xác nhận llama.cpp hỗ trợ dòng 3.5. [Model card](https://huggingface.co/Qwen/Qwen3.5-9B), [repo Qwen](https://github.com/QwenLM/Qwen3.8#local-use) | Chỉ giữ làm tham khảo nếu mở lại nhánh LLM local; không đánh giá trong v1 hiện tại. Chưa xác minh GGUF 9B do chính Qwen phát hành. |

Qwen3-14B từng được chọn làm mốc vì có artifact GGUF chính thức đã xác minh, không phải kết luận nó mới nhất hoặc tốt hơn Qwen3.5-9B. Chưa có phép đo nào trong repo chứng minh model tạo notes, local hoặc cloud, đáp ứng dữ liệu cuộc họp này. Việc hoãn Qwen tạo notes không tự loại ứng viên ASR cùng thương hiệu khỏi nghiên cứu âm thanh.

## Bộ nhớ và cách chạy

Pipeline hiện tại chạy lần lượt ASR và diarization local, giải phóng GPU giữa các model; sau đó gọi provider cloud cho notes. Cách dùng tiến trình con và thu hồi tài nguyên còn cần kiểm chứng. Huấn luyện nhận diện danh tính là phase sau, không bổ sung model training vào v1.

**Nghiên cứu LLM local bên dưới được giữ để tham khảo, đã hoãn theo Q12.**

File Qwen3-14B Q4_K_M chính thức khoảng **9 GB trên đĩa**. Đây không phải tổng VRAM: runtime còn cần bộ nhớ ngữ cảnh, buffer tính toán và tài nguyên CUDA. [Danh sách file](https://huggingface.co/Qwen/Qwen3-14B-GGUF/tree/main)

Với model cỡ 32 tỷ tham số, ước tính riêng trọng số ở đúng 4 bit là `32 × 10^9 × 4 / 8 = 16 GB`, khoảng **14,9 GiB**, chưa gồm overhead lượng tử hóa và bộ nhớ chạy. Vì vậy Qwen2.5-32B-Instruct trong nghiên cứu ban đầu không nên là cấu hình mặc định trên GPU 16 GB. CPU offload có thể là phương án thử sau; chưa biết có đạt thời gian mục tiêu. [Model được tham chiếu](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct)

Q7 ban đầu dự kiến chạy lần lượt ASR, diarization và LLM local. Q12 bỏ giai đoạn LLM local khỏi cấu hình cần thử, không yêu cầu tải Qwen/llama.cpp để khởi động v1.

Đo trên RTX 5080 thực tế với revision cố định, batch size và giới hạn context cụ thể. Benchmark faster-whisper công bố dùng GPU và dữ liệu khác; không suy ra toàn bộ cuộc họp hai giờ sẽ hoàn thành trong 30 phút. [Điều kiện benchmark upstream](https://github.com/SYSTRAN/faster-whisper#benchmark)

## Transcript dài và bằng chứng

Đề xuất chép lời bằng tác vụ `transcribe`; không dùng `translate` để biến transcript thành tiếng Anh. Whisper hỗ trợ hai chế độ này riêng biệt. Khả năng giữ code-switch phải đo trên dữ liệu của nhóm. [Whisper](https://huggingface.co/openai/whisper-large-v3)

Đầu vào LLM gồm văn bản, ID đoạn, mốc thời gian, nhãn/tên người nói và ngày họp đã nhập. Khi tạo notes, nguồn của cuộc họp bị khóa chỉnh sửa theo quyết định Q3 đã chốt.

Q17 đã chốt xử lý theo ngân sách model/provider: nguồn vừa ngân sách thì xử lý một lượt; nguồn dài thì trích xuất theo đoạn phát biểu có phần chồng, giữ ID bằng chứng, rồi hợp nhất bằng cùng provider/model. Mọi bước, gồm hợp nhất, phải nằm trong ngân sách. Không cắt phần cuối hoặc để harness tự rút gọn mất nguồn. Q18 cho tối đa một lượt yêu cầu sửa lỗi cấu trúc/tham chiếu trong cả tác vụ, không phải mỗi chunk; quá giới hạn thì báo lỗi và không công bố notes không hợp lệ. Phép kiểm tra ID không tự bảo đảm nội dung đúng. Context, giới hạn đầu ra và số lượt gọi thực tế cần đo riêng cho mỗi provider.

## Thiết lập ASR offline và bước xác minh

Tải trước trọng số, tokenizer, cấu hình và các tài nguyên phụ của ASR/diarization; runtime nạp bằng đường dẫn local. faster-whisper có thể tự tải tokenizer nếu thiếu file khi chuyển đổi, nên bước setup phải kiểm tra đủ artifact. Tạo notes cloud cần Internet và kết nối tài khoản provider, không thuộc cam kết offline. [Hướng dẫn chuyển đổi](https://github.com/SYSTRAN/faster-whisper#model-conversion)

Community-1 yêu cầu người dùng chấp nhận điều kiện truy cập và tạo token Hugging Face khi thiết lập; model card hướng dẫn chạy offline. Đặt `PYANNOTE_METRICS_ENABLED=0` để tắt telemetry, rồi nghiệm thu cả khi mất mạng và khi có mạng theo AC-10. [Điều kiện và offline](https://huggingface.co/pyannote/speaker-diarization-community-1), [cấu hình telemetry](https://github.com/pyannote/pyannote-audio#configuring-telemetry)

Bước tiếp theo là so sánh trên ba loại bản ghi của spec, đo riêng lỗi nội dung, người nói, timestamp, notes, thời gian từng giai đoạn và VRAM đỉnh. Phải có bản ghi hai giờ để kiểm chứng mục tiêu 30 phút. Tài liệu này chưa tải/cài model, chấp nhận điều khoản truy cập hoặc thực hiện benchmark.
