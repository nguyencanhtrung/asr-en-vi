# ASR EN VI Meeting Notes

Ứng dụng web chạy trên máy tự quản để lưu bản ghi cuộc họp và tạo transcript bằng faster-whisper
cùng speaker diarization Community-1 trên máy local. Bản ghi, transcript và catalog người nói được
lưu trong workspace; meeting notes chưa được triển khai.

## Chạy trên máy local

Cần Docker Engine và Docker Compose 2.30 trở lên. Máy có NVIDIA GPU cần thêm NVIDIA driver và
NVIDIA Container Toolkit; máy không có GPU tự dùng CPU. Mặc định ứng dụng mở tại
`http://127.0.0.1:8765`; Compose chỉ publish cổng trên loopback của máy chạy Docker.
Hãy mở đúng URL được in trong terminal; host khác (kể cả `localhost` khi cấu hình dùng
`127.0.0.1`) bị từ chối để bảo vệ khỏi DNS rebinding.

```sh
cp .env.example .env
./scripts/start.sh
```

Script build image, chờ app và worker healthy, rồi in access link cùng QR trong terminal.
Link chứa token trong URL fragment. Trang truy cập xóa fragment trước khi gửi token trong
JSON body để đổi lấy phiên trình duyệt.

Script tự dò compute backend bằng chính image runtime. Nếu Docker nhìn thấy NVIDIA GPU, worker
dùng CUDA, `float16` và `whisper-large-v3`; nếu máy không có GPU, worker dùng CPU, `int8` và
`whisper-small` để giảm tài nguyên với độ chính xác thấp hơn. Nếu host có GPU nhưng Docker không
truy cập được GPU, setup dừng và báo lỗi NVIDIA Container Toolkit thay vì âm thầm rơi về CPU.
Model chép lời được tải một lần khi còn thiếu, sau đó script kiểm tra model, CUDA/cuDNN và compute
type trước khi khởi động service. Community-1 phải được chuẩn bị riêng trên host trước khi chạy
script.

Compose tạo hai volume riêng:

- `data` giữ SQLite và trạng thái liveness tối thiểu của worker; app và worker cùng gắn volume này.
- `auth` giữ token và khóa ký cookie với quyền file hạn chế; chỉ app gắn volume này.
- Thư mục model trên host được gắn chỉ đọc vào app và worker; không nằm trong image ứng dụng.

Restart hoặc recreate container vẫn giữ hai volume. Một Compose project/volume mới sinh token
riêng. Đổi cổng bằng `ASR_PORT` trong `.env`; link mặc định tự theo cổng đó. Có thể đặt
`ASR_PUBLIC_URL` nếu cần một URL loopback cụ thể. `ASR_COOKIE_SECURE` mặc định là `false` cho
HTTP localhost; bật khi đặt một TLS terminator local phía trước app.

Workspace nhận `wav`, `mp3`, `m4a`, `mp4`, `mov`, `webm`, `ogg`, `opus` và `flac`. Backend
kiểm tra codec/thời lượng bằng FFmpeg, rồi lưu một bản M4A/AAC do ứng dụng quản lý; file nguồn
không còn cần thiết sau khi upload hoàn tất. Mặc định mỗi file tối đa 4 GiB và 4 giờ. Có thể đổi
hai giới hạn bằng `ASR_MAX_UPLOAD_BYTES` và `ASR_MAX_RECORDING_SECONDS` trong `.env`.

## Model chép lời local

`faster-whisper` 1.2.1 nằm trong dependencies của dự án và được khóa cùng runtime bằng `uv.lock`.
PyAV được giữ dưới phiên bản 19 để tương thích với API giải mã của bản faster-whisper này.
Để cài dependencies phát triển, chạy `uv sync --all-groups --locked`; runtime-only dùng
`uv sync --locked --no-dev`.

Mặc định `./scripts/start.sh` tải model CTranslate2 còn thiếu từ bộ model công khai của Systran:
`faster-whisper-large-v3` cho GPU hoặc `faster-whisper-small` cho CPU. Các lần chạy sau dùng bản
local trong `./models`; app và worker gắn thư mục này chỉ đọc khi phục vụ. Có thể chuẩn bị model
thủ công trước khi chạy nếu máy cần setup offline:

```sh
mkdir -p ./models
cp -a /path/to/prepared-whisper-model ./models/whisper-large-v3
cp -a /path/to/prepared-whisper-small ./models/whisper-small
```

Mỗi model phải có `model.bin`, `config.json`, `tokenizer.json` và `preprocessor_config.json` hợp
lệ. `ASR_MODEL_HOST_PATH` chọn thư mục model trên host; `ASR_GPU_MODEL_PATH` và
`ASR_CPU_MODEL_PATH` chọn hai thư mục trong container. `ASR_DEVICE=auto` là mặc định; có thể đặt
`cpu` hoặc `cuda` để chủ động khóa backend. `ASR_MODEL_PATH` và `ASR_COMPUTE_TYPE` vẫn là override
tường minh cho kiểm thử chuyên biệt. Image chứa CUDA 12.8 và cuDNN 9. Sau bước tải model, runtime
chỉ mở model từ đường dẫn local, bật chế độ offline và tắt telemetry; audio không được gửi ra
ngoài. UI hiển thị compute backend, compute type và model worker đang dùng.

Import cuộc họp chỉ lưu bản ghi. Mở cuộc họp rồi bấm **Bắt đầu chép lời** để chiếm slot xử lý.
Sau khi có transcript, nút **Chạy lại bản ghi** tạo một thế hệ transcript riêng; thế hệ cũ còn
được giữ nếu lần chạy mới lỗi hoặc bị hủy. Chỉ thế hệ hoàn chỉnh được công bố. Giao diện hiển thị
giai đoạn, thời gian đã chạy, số đoạn và mốc timestamp cuối cùng nhận được, không tạo phần trăm
hoặc ETA.

Lựa chọn English hoặc Tiếng Việt khi import chỉ là gợi ý metadata. Runner luôn dùng tác vụ
`transcribe`, tự phát hiện ngôn ngữ theo từng đoạn và không ép transcript sang ngôn ngữ đã chọn.

## Model speaker diarization local

Runtime dùng `pyannote.audio` 4.x và chỉ mở Community-1 từ thư mục local
`/models/speaker-diarization-community-1`. Trước khi tải, hãy chấp nhận điều kiện của
[Community-1 trên Hugging Face](https://huggingface.co/pyannote/speaker-diarization-community-1).
Trên host, tải toàn bộ pipeline vào thư mục được mount bởi Compose. Khi `git clone` hỏi mật khẩu,
nhập Hugging Face access token trong prompt tương tác:

```sh
git lfs install
mkdir -p ./models
git clone https://hf.co/pyannote/speaker-diarization-community-1 \
  ./models/speaker-diarization-community-1
```

Nếu `ASR_MODEL_HOST_PATH` trỏ tới thư mục model khác `./models`, đổi đích của lệnh `git clone`
thành `$ASR_MODEL_HOST_PATH/speaker-diarization-community-1`. Nếu đổi
`ASR_DIARIZATION_MODEL_PATH`, đường dẫn trong container phải nằm dưới `/models`; tải model vào
đường dẫn tương ứng dưới `ASR_MODEL_HOST_PATH`. `scripts/start.sh` kiểm tra các file Community-1
bắt buộc trước khi khởi động; worker còn từ chối file Git LFS chưa được tải hoặc symlink thoát khỏi
thư mục model. Token Hugging Face chỉ dùng cho bước đăng nhập/tải trên host; không đặt token hoặc
ID model trong `.env` và không truyền chúng vào Compose. Worker dùng đường dẫn local, chế độ
offline, `token=False` và tắt telemetry. ASR và diarization chạy lần lượt trong hai child process;
mỗi process thoát trước khi phase tiếp theo bắt đầu, giải phóng bộ nhớ model.

Community-1 trả về regular turns để phát hiện chồng lấn và exclusive turns để gán mỗi đoạn ASR cho
người nói có thời lượng giao nhau lớn nhất. Văn bản và timestamp ASR không bị chia hoặc dịch chuyển.
Đoạn có nhiều người nói, overlap, speaker dominance thấp, không có speaker match hoặc tín hiệu ASR
không chắc được giữ và đánh dấu để rà soát. Khi phát lại, mọi đoạn transcript chứa thời gian phát
được tô sáng; nút timestamp tua cùng nguồn audio đã lưu. Có thể đổi người nói hiển thị trong catalog
của thế hệ hiện tại; gán ban đầu của model và timestamp vẫn được lưu riêng.

Nếu diarization hoặc alignment lỗi hay bị hủy, task không công bố thế hệ mới và thế hệ hiện tại vẫn
được giữ. Không có bước gửi audio hoặc inference cloud. Thư mục model đã tải có thể được dùng offline
sau đó.

Mỗi segment lưu ID ổn định, timestamp bắt đầu/kết thúc, văn bản và các chỉ số model có sẵn:
`avg_logprob`, `no_speech_prob` và `compression_ratio`. Một segment được đánh dấu **Nên nghe lại**
nếu `avg_logprob < -1.0`, `no_speech_prob >= 0.6` hoặc `compression_ratio > 2.4`. Đây là các dấu
hiệu rà soát theo ngưỡng decode của Whisper, không phải xác suất transcript đúng; văn bản vẫn được
giữ nguyên. Các lý do rà soát từ nhận dạng và diarization được lưu riêng để người dùng nghe lại và
điều chỉnh speaker assignment khi cần.

Để thay token và vô hiệu link/session cũ:

```sh
./scripts/rotate-token.sh
```

Lệnh in link và QR mới. Việc này chỉ thay auth state; SQLite và worker tiếp tục dùng volume cũ.
`docker compose down` giữ volume. `docker compose down -v` xóa volume dữ liệu và auth của project.

## Phát triển và kiểm tra

Cài Python 3.12, uv, Node.js và Docker Compose rồi chạy toàn bộ quality gate bằng một lệnh:

```sh
./scripts/check.sh
```

Để chạy transcription video thật bên ngoài Docker, cài dependencies bằng lệnh `uv sync` ở trên.
Bài kiểm tra video vẫn cần `ASR_TEST_VIDEO` và `ASR_MODEL_PATH` trỏ tới file/model local đã chuẩn
bị.

Một kiểm thử Chromium thực chạy HTTP server và xác nhận fragment được loại khỏi URL, token chỉ
được gửi trong body, và cookie không đọc được từ JavaScript. Để chạy, cài Chromium cho Playwright
và đặt `ASR_RUN_BROWSER_TESTS=1`:

```sh
uv run playwright install chromium
ASR_RUN_BROWSER_TESTS=1 uv run pytest -m browser
```

Bài kiểm tra video xuyên suốt mặc định được bỏ qua. Để chạy, cung cấp đường dẫn video thật và một
model local đã chuẩn bị; bài kiểm tra import video qua API, tạo cuộc họp, khởi động worker, chờ
transcription và đọc transcript đã lưu:

```sh
ASR_TEST_VIDEO=/absolute/path/to/meeting.mp4 \
ASR_MODEL_PATH=/absolute/path/to/prepared-whisper-model \
ASR_EXPECTED_TEXT='expected phrase in the recording' \
uv run pytest tests/test_transcription_video_e2e.py -q
```

`ASR_EXPECTED_TEXT` là tùy chọn; khi có, bài kiểm tra còn xác nhận transcript đã lưu chứa câu
mong đợi sau khi chuẩn hóa chữ hoa/thường và khoảng trắng.

## CI/CD

GitHub Actions chạy cùng `./scripts/check.sh` cho mọi pull request và mọi push lên `main`, đồng
thời build Docker image để chặn lỗi đóng gói. Pipeline chỉ phát hành sau khi cả quality gate và
container build thành công:

- Push lên `main` phát hành image `ghcr.io/nguyencanhtrung/asr-en-vi` với tag `edge` và tag SHA.
- Push tag dạng `v1.2.3` phát hành các tag version, `latest` và SHA.
- Image phát hành cho `linux/amd64` và `linux/arm64`, kèm SBOM, provenance và attestation.

Workflow chỉ dùng `GITHUB_TOKEN`; không cần secret registry riêng. Các action được pin bằng commit
SHA bất biến, còn Dependabot kiểm tra cập nhật hằng tuần cho uv, GitHub Actions và Docker base image.

Trong production image, Docker build context chỉ chứa `pyproject.toml`, `README.md`, `uv.lock` và
`src/asr_en_vi`. Hướng dẫn, tài liệu thiết kế và prototype không được đưa vào image.

## Tài liệu dự án

- [Đặc tả v1](docs/specification-v1.md)
- [Thiết kế frontend v1 đã chốt](docs/frontend-design-v1.md)
- [Thiết kế backend v1 đã thống nhất Q1–Q27](docs/backend-design-v1.md)
- [Backend contract v1: schema, API và tác vụ](docs/backend-contract-v1.md)
- [Ứng viên model và căn cứ chọn bộ thử nghiệm](docs/model-candidates-v1.md)
- [Khảo sát tận dụng subscription cho notes](docs/subscription-notes-options-v1.md)
- [Khảo sát OMP/Pi và đăng nhập provider từ UI](docs/harness-notes-v1.md)
- [Quyết định kiến trúc web và Docker](docs/adr/0001-browser-ui-container-backend.md)
- [Truy cập localhost bằng token](docs/adr/0002-localhost-reusable-token.md)
- [Chính sách phân phối non-commercial](docs/adr/0003-public-source-noncommercial.md)
- [Hai service app/worker và SQLite](docs/adr/0004-app-worker-sqlite.md)
- [Markdown là nội dung chính của notes](docs/adr/0005-markdown-notes.md)
- [Giữ các thế hệ transcript khi chạy lại](docs/adr/0006-transcript-generations.md)
- [Tạo notes bằng ChatGPT hoặc OMP + Google Antigravity](docs/adr/0007-cloud-notes-providers.md)
- [Giữ bản chụp nguồn bất biến của notes](docs/adr/0008-notes-source-snapshots.md)
- [Từ vựng dự án](CONTEXT.md)
- [Nghiên cứu ban đầu](docs/ASR-initial-deep-research-vi.pdf)
