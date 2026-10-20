# ASR EN VI Meeting Notes

Ứng dụng web chạy trên máy tự quản để lưu bản ghi cuộc họp và tạo transcript bằng faster-whisper
cùng speaker diarization Community-1 trên máy local. Bản ghi, transcript và catalog người nói được
lưu trong workspace; ChatGPT tạo meeting notes tiếng Anh hoặc tiếng Việt theo lựa chọn khi tạo notes.

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

Script build image, khởi động cả app và worker, chờ hai service healthy, rồi kiểm tra từ trong app
rằng worker đang chạy và cả model chép lời lẫn Community-1 đều đọc được qua mount chỉ đọc.
Chỉ sau khi kiểm tra này đạt, script mới in access link cùng QR trong terminal. Một container app
chạy riêng bằng `docker run` không tự khởi động worker hoặc gắn model; dùng `./scripts/start.sh`
cho bản cài mới. Có thể kiểm tra lại bản cài đang chạy bằng:

```sh
docker compose exec -T app python -m asr_en_vi.cli installation check
```

Nếu lệnh báo worker chưa sẵn sàng, kiểm tra service `worker` và volume `data` dùng chung. Nếu
báo không đọc được model, kiểm tra `ASR_MODEL_HOST_PATH` và mount `/models` của cả hai service.
Link chứa token trong URL fragment. Trang truy cập xóa fragment trước khi gửi token trong
JSON body để đổi lấy phiên trình duyệt.

Script tự dò compute backend bằng chính image runtime. Nếu Docker nhìn thấy NVIDIA GPU, worker
dùng CUDA, `float16` và `whisper-large-v3`; nếu máy không có GPU, worker dùng CPU, `int8` và
`whisper-small` để giảm tài nguyên với độ chính xác thấp hơn. Nếu host có GPU nhưng Docker không
truy cập được GPU, setup dừng và báo lỗi NVIDIA Container Toolkit thay vì âm thầm rơi về CPU.
Model chép lời được tải một lần khi còn thiếu, sau đó script kiểm tra model, CUDA/cuDNN và compute
type trước khi khởi động service. Community-1 phải được chuẩn bị riêng trên host trước khi chạy
script.

Compose tạo các volume riêng:

- `data` giữ SQLite và trạng thái liveness tối thiểu của worker; app và worker cùng gắn volume này.
- `auth` giữ token và khóa ký cookie với quyền file hạn chế; chỉ app gắn volume này.
- `provider` giữ đăng ký và credential ChatGPT riêng của bản cài; app và worker cùng gắn volume
  này để đăng nhập, gọi notes và refresh phiên. Worker không gắn volume `auth`.
- Thư mục model trên host được gắn chỉ đọc vào app và worker; không nằm trong image ứng dụng.

Restart hoặc recreate container vẫn giữ các volume. Một Compose project/volume mới sinh token
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

Để in lại access link và QR hiện tại mà không đổi token (token nằm sau dấu `#` của link):

```sh
docker compose exec -T app python -m asr_en_vi.cli access show
```

Để thay token và vô hiệu link/session cũ:

```sh
./scripts/rotate-token.sh
```

Lệnh in link và QR mới. Việc này chỉ thay auth state; SQLite và worker tiếp tục dùng volume cũ.
`docker compose down` giữ volume. `docker compose down -v` xóa volume dữ liệu và auth của project.

## Kết nối ChatGPT

Mở **ChatGPT** trong thanh đầu workspace, rồi chọn **Continue with ChatGPT** để đăng nhập
và cấp quyền dùng gói. Kết nối này độc lập với token truy cập localhost. Ứng dụng lưu phiên trong
volume `provider` với quyền truy cập hạn chế để dùng lại sau restart; không đọc credential từ
Codex hoặc công cụ cá nhân khác. Khi phiên mất hiệu lực, UI yêu cầu kết nối ChatGPT lại.

Sau khi kết nối, chọn và lưu model từ danh sách tài khoản cung cấp. Model đã nhớ không còn khả
dụng cần được chọn lại; ứng dụng không tự chuyển model. Danh sách model không bảo đảm còn quota
hoặc tài khoản gọi được inference. Nút **Chạy kiểm tra bằng dữ liệu tổng hợp** gửi một yêu cầu nhỏ
để kiểm chứng đầu ra JSON; yêu cầu có thể dùng hạn mức ChatGPT, không gửi dữ liệu cuộc họp và
không tự gửi lại nếu lỗi. Sau đó có thể chủ động tạo notes từ transcript hoàn chỉnh.

Với GPT-5.6 Luna và GPT-6 Luna/Sol, có thể chọn `none`, `low`, `medium`, `high`, `xhigh` hoặc `max` cho
`reasoning.effort`, rồi lưu cùng model. Chọn **Mặc định của mô hình** để ứng dụng không gửi tham số
khi kiểm tra; GPT-5.6 Luna mặc định dùng `medium`. GPT-6.1 Sol và GPT-6 Astra hỗ trợ từ `low`
đến `max`. Lần kiểm tra tổng hợp sử dụng effort đang hiển thị,
kể cả khi thay đổi chưa được lưu. Mức effort cao hơn có thể làm yêu cầu lâu hơn và dùng thêm hạn
mức. Mỗi tác vụ notes cố định model và effort đã lưu khi nhận yêu cầu.

Callback dùng HTTP `127.0.0.1` trên cổng app đã publish, tại `/auth/chatgpt/callback`. Mở trình
duyệt trên cùng máy chạy Docker. Không chuyển callback sang `localhost`. Compose và lệnh mặc
định của image tắt access log để tránh ghi authorization code trong query string. Khi tự chạy
Uvicorn, thêm `--no-access-log`; proxy phía trước cũng phải bỏ hoặc che query callback.
Nếu workspace dùng HTTPS qua TLS terminator, ASR vẫn hoạt động; để đăng nhập ChatGPT, đặt
`ASR_CHATGPT_CALLBACK_URL` thành một URL HTTP `127.0.0.1` được route về app tại đường dẫn trên.
Không gửi HTTP vào cổng chỉ nhận TLS. Khi chưa cấu hình đường HTTP riêng, chỉ bước đăng nhập
ChatGPT bị chặn với lỗi cấu hình callback.

**Ngắt kết nối** xóa token ChatGPT đang lưu và thử thu hồi phiên ở OpenAI, không xóa cuộc họp.
Nếu chưa xác nhận được thu hồi từ xa, UI hướng dẫn kiểm tra quyền ứng dụng trong
[ChatGPT Settings → Usage](https://chatgpt.com/settings/usage). Đăng ký và định danh host vẫn
được giữ để dùng lại khi đăng nhập; quay vòng token localhost không ngắt kết nối ChatGPT.

Xem [quy trình kiểm chứng ChatGPT thật](docs/chatgpt-integration-check.md) để ghi nhận quyền tài
khoản, model và kết quả. Kiểm thử giả lập không xác nhận entitlement hoặc quota của tài khoản thật.

## Kết nối Google Antigravity qua OMP

Mở **AI** trên thanh đầu workspace, tới phần **Google Antigravity**, rồi chọn **Kết nối Google
Antigravity**. UI hiển thị URL đăng nhập do OMP cung cấp và, khi provider yêu cầu, ô nhập mã hoặc
URL chuyển hướng. Phiên đăng nhập hết hạn sau 10 phút và có thể hủy rõ ràng. Sau khi kết nối, chọn
model từ catalog, lưu lựa chọn và chạy yêu cầu kiểm tra tổng hợp để xác nhận model thực sự tạo được
đầu ra. Catalog không tự chứng minh quyền inference hoặc quota.

Image pin OMP `18.5.0` bằng checksum riêng cho `amd64` và `arm64`. Runner dùng home, agent store,
XDG directories và working directory riêng dưới volume `provider`; không đọc cấu hình Claude,
Codex hay OMP cá nhân trên host. Mỗi tiến trình RPC chạy với `--no-session`, `--no-tools`,
`--no-extensions`, `--no-skills`, `--no-rules`, `--no-lsp`, `--no-pty` và `--no-ui`; cấu hình còn
tắt MCP, memory, auto-compaction, retry và model fallback. Backend kiểm tra lại rằng RPC không công
bố tool trước khi gửi yêu cầu. Credential OMP được giữ trong volume riêng để dùng lại qua restart.

Yêu cầu kiểm tra chỉ gửi chỉ dẫn tổng hợp cố định và phải trả đúng JSON `{\"ok\":true}`. Event JSON
của OMP chỉ là transport; ứng dụng không coi event hay text assistant là Notes đã hợp lệ. Khi tích
hợp tạo notes, transcript phải tiếp tục được đóng khung là dữ liệu không tin cậy và đi qua cùng
pipeline kiểm tra schema/source ID trước khi lưu. Lỗi revoke, quota, model access và mạng được báo
theo nhóm có thể hành động; nội dung lỗi thô và credential không được trả về UI, và inference không
tự gửi lại.

**Ngắt kết nối Antigravity** yêu cầu OMP vô hiệu hóa credential `google-antigravity` trong store
riêng. OMP không xác nhận thu hồi quyền truy cập ở phía Google; nếu cần thu hồi quyền từ xa, hãy
kiểm tra [quyền truy cập tài khoản Google](https://myaccount.google.com/permissions). Việc ngắt
kết nối không ảnh hưởng ChatGPT, token truy cập localhost, transcript hoặc notes đã lưu.

## Tạo và đối chiếu notes

Mở cuộc họp đã có transcript hoàn chỉnh, lưu lựa chọn ChatGPT/model trong phần kết nối, rồi bấm
**Tạo notes**. Worker gửi transcript cùng ID, timestamp, tên người nói và ngày họp cần thiết;
không gửi audio. Nguồn dài được chia tại ranh giới đoạn, tạo các tóm tắt có trích dẫn đã kiểm tra
riêng theo từng phần, rồi tổng hợp theo thứ tự transcript để xử lý quyết định hoặc đề xuất thay
đổi về sau. Nguồn vượt giới hạn tổng, số phần hoặc có đoạn đơn lẻ quá lớn sẽ bị từ chối trước khi
lưu task và snapshot; transcript không bị cắt hoặc âm thầm bỏ đoạn. Tóm tắt trung gian vẫn có thể
bỏ sót chi tiết, vì vậy hãy đối chiếu nội dung cuối với nguồn.

Mỗi lượt gọi dành tối đa 25.000 token cho reasoning và đầu ra; phần nguồn được chia nhỏ để vẫn
giữ ngân sách context an toàn. Toàn tác vụ có giới hạn 60 phút, không tự đổi model/effort hoặc
tự gửi lại inference nếu hết ngân sách, lỗi hay bị hủy.

Chọn **Tiếng Anh** hoặc **Tiếng Việt** trước khi bấm tạo notes; mặc định là tiếng Anh.
Ngôn ngữ được giữ cố định cho từng tác vụ và bản notes, độc lập với ngôn ngữ transcript.
Notes gồm tổng quan, chủ đề chính và lập luận, quyết định, câu hỏi còn mở, công việc đã xác nhận
và các mục cần xác nhận; tiêu đề và nội dung theo ngôn ngữ đã chọn. Backend kiểm tra cấu trúc và
ID nguồn trước khi lưu. Người phụ trách hoặc thời hạn thiếu giữ là **Undetermined** hoặc
**Chưa xác định**. Chỉ quy đổi deadline tương đối khi ngày họp và cách diễn đạt đủ rõ; luôn giữ
cách nói gốc để rà soát. Kiểm tra schema không thay thế việc người dùng đối chiếu nội dung.

Khi nhận tác vụ, ứng dụng chụp nguồn bất biến và khóa transcript, người nói cùng ngày họp của
cuộc họp đó. Tài khoản/model ChatGPT được giữ cố định; không đổi hoặc ngắt kết nối khi tác vụ còn
hoạt động. Vẫn xem nguồn, sửa notes cũ và làm việc với cuộc họp khác được. Bấm hủy chuyển tác vụ
sang đang dừng; chỉ khi tiến trình gọi provider đã kết thúc mới mở khóa và nhường slot. Lỗi,
hủy hoặc restart giữ transcript và các notes đã lưu; không công bố đầu ra dở hoặc tự gửi lại
inference. Đầu ra đã nhận đầy đủ nhưng không hợp lệ được phép sửa tối đa một lượt.

Chọn phiên bản notes để xem hoặc sửa Markdown. Lưu dùng kiểm tra phiên bản; xung đột giữ bản
nháp để đối chiếu. Sao chép và tải Markdown lấy cùng nội dung đã lưu của phiên bản đang chọn;
cần lưu hoặc giải quyết bản nháp trước. Notes hiển thị, copy và export chỉ chứa nội dung tóm tắt,
không kèm liên kết timestamp. Bản chụp nguồn vẫn được giữ để kiểm tra nội bộ và lưu lịch sử.
Notes cũ hiển thị nguồn lịch sử hoặc cần cập nhật khi nguồn thay đổi; đổi riêng tên cuộc họp
không làm notes cần cập nhật.

## Phát triển và kiểm tra

Cài Python 3.12, uv, Node.js, Docker Compose và actionlint v1.7.11 rồi chạy toàn bộ quality gate
bằng một lệnh (xem [hướng dẫn môi trường và workflow](docs/agents/development.md)):

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
thời build và smoke-test Docker image để chặn lỗi đóng gói. Bước kiểm tra chỉ đọc cache BuildKit;
không xuất lại cache image CUDA/PyTorch nhiều GB sau mỗi lần chạy. Pipeline chỉ phát hành sau khi
cả quality gate và container build thành công:

- Push lên `main` chỉ chạy kiểm tra; không phát hành image.
- Push tag dạng `v1.2.3` phát hành image `ghcr.io/nguyencanhtrung/asr-en-vi` với các tag version,
  `latest` và SHA.
- Image phát hành cho `linux/amd64` và `linux/arm64` trên runner native song song, sau đó ghép
  manifest đa kiến trúc kèm SBOM, provenance và attestation.

Workflow chỉ dùng `GITHUB_TOKEN`; không cần secret registry riêng. Các action được pin bằng commit
SHA bất biến, còn Dependabot kiểm tra cập nhật hằng tuần cho uv, GitHub Actions và Docker base image.

Trong production image, Docker build context chỉ chứa `pyproject.toml`, `README.md`, `uv.lock` và
`src/asr_en_vi`. Hướng dẫn, tài liệu thiết kế và prototype không được đưa vào image.

## Tài liệu dự án

- [Bối cảnh sản phẩm](PRODUCT.md)
- [Hệ thống thiết kế editorial-engineering](DESIGN.md)
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
