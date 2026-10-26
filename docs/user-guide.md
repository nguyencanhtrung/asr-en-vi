# Hướng dẫn vận hành chi tiết

Ứng dụng web chạy trên máy tự quản để lưu bản ghi cuộc họp và tạo transcript bằng faster-whisper
cùng speaker diarization Community-1 trên máy local. Bản ghi, transcript và catalog người nói được
lưu trong workspace; ChatGPT hoặc Google Antigravity tạo meeting notes tiếng Anh hoặc tiếng Việt
theo lựa chọn khi tạo notes.

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

Mặc định, script build `ASR_IMAGE` từ source trong checkout. Có thể dùng `--source` để ghi rõ
chế độ này. `--pull` tải ảnh được chỉ định trong `ASR_IMAGE`; ảnh phải có tag version cụ thể như
`ghcr.io/nguyencanhtrung/asr-en-vi:v0.1.0` hoặc digest `@sha256:...`, không dùng `local`,
`latest` hay `edge`. Trước khi chạy service, script so sánh version ứng dụng và schema được hỗ trợ
trong image với source checkout. `--offline` chỉ dùng image đã có trên máy và model đã chuẩn bị;
chế độ này kiểm tra model local, không build, pull hoặc tải model. Mọi chế độ dùng cùng một giá trị
`ASR_IMAGE` cho app và worker.

Chế độ source và pull chạy bước chuẩn bị ASR riêng, chỉ cho phép truy cập model hub trong lệnh
`model prepare` nếu model ASR còn thiếu. Khởi động offline chỉ kiểm tra model. Script chờ cả hai
service healthy, rồi kiểm tra từ trong app rằng worker đang chạy và cả model chép lời lẫn
Community-1 đều đọc được qua mount chỉ đọc.
Chỉ sau khi kiểm tra này đạt, terminal tương tác mới in access link cùng QR. Khi chạy qua pipe,
CI hoặc redirect, script che access token và nhắc lệnh hiển thị rõ ràng:

```sh
docker compose exec -T app python -m asr_en_vi.cli access show
```

Một container app chạy riêng bằng `docker run` không tự khởi động worker hoặc gắn model; dùng
`./scripts/start.sh` cho bản cài mới. Có thể kiểm tra lại bản cài đang chạy bằng:

```sh
docker compose exec -T app python -m asr_en_vi.cli installation check
docker compose exec -T app python -m asr_en_vi.cli version --json
```

### Cài bản phát hành

Các lệnh dưới đây dùng source tag `v0.1.0` và image `ghcr.io/nguyencanhtrung/asr-en-vi:v0.1.0` sau khi bản phát hành được công bố.
Đây là ví dụ cú pháp, không phải xác nhận image có tag đó khớp candidate mới nhất.
Khi cài bản công bố, dùng tag/commit/digest đã xác nhận trong release notes; không ghi đè tag cũ.
Giữ nguyên `COMPOSE_PROJECT_NAME` và `ASR_MODEL_HOST_PATH` khi chạy lại để Compose dùng đúng
volume và thư mục model. Chuẩn bị ASR khi còn online; chỉ tải Community-1 sau khi người vận hành
đã chấp thuận điều kiện ở mục [Model speaker diarization local](#model-speaker-diarization-local).

Tải source checkout đúng tag và build image từ source:

```sh
git clone --branch v0.1.0 --depth 1 https://github.com/nguyencanhtrung/asr-en-vi.git
cd asr-en-vi
export COMPOSE_PROJECT_NAME=asr-source-v1
export ASR_MODEL_HOST_PATH="$PWD/models"
export ASR_IMAGE=asr-en-vi:v0.1.0
./scripts/start.sh --source
```

Để cài từ image công khai, dùng checkout cùng tag và chạy:

```sh
export COMPOSE_PROJECT_NAME=asr-pull-v1
export ASR_PORT=8766
export ASR_MODEL_HOST_PATH="$PWD/models"
export ASR_IMAGE=ghcr.io/nguyencanhtrung/asr-en-vi:v0.1.0
./scripts/start.sh --pull
```

Hai tên project khác nhau tạo volume dữ liệu/token/provider riêng; cổng 8766 tránh
đụng bản source đang chạy. Để cài độc lập trên máy khác, clone cùng source tag trước,
cài Docker/Compose và chuẩn bị Community-1 như trên. Không sao chép `.env`, volume
`auth` hoặc `provider` từ bản cài cũ. Dùng digest đã công bố trong `ASR_IMAGE` khi
cần cố định artifact (`ghcr.io/nguyencanhtrung/asr-en-vi@sha256:...`).

Mở access link của chính bản cài mới, chọn ChatGPT hoặc Google trên thanh workspace
và hoàn tất đăng nhập bằng tài khoản của mình. Xem các mục kết nối provider bên dưới,
đặc biệt ràng buộc Antigravity. Dùng một recording được phép để kiểm tra import,
transcript, notes và export; trạng thái healthy không chứng minh provider dùng được.

Image build từ source dùng tag local `asr-en-vi:v0.1.0`, khác với image công khai trên GHCR, nên
tên image cho biết nó đến từ đâu. Mọi chế độ của `start.sh` so nhãn
`org.opencontainers.image.revision` của image với commit của checkout và dừng nếu hai giá trị khác
nhau; hãy checkout đúng tag hoặc chọn đúng image. Nếu checkout hoặc image không có revision
(`unknown`), script chỉ cảnh báo vì không thể xác minh. Checkout chỉ có revision khi thư mục này là
gốc của một repo git; bản giải nén nằm trong repo khác không mượn commit của repo đó và được coi là
`unknown`.

Sau khi chuẩn bị model và ngắt Internet, giữ các giá trị trên trong cùng checkout rồi chạy:

```sh
./scripts/start.sh --offline
```

Smoke tùy chọn cho máy Linux/NVIDIA dùng một Compose project riêng; cần Docker, Chromium với
Playwright, model đã chuẩn bị và file WAV được phép dùng. Lệnh ghi JSON, log và báo cáo vào thư mục
đầu ra. Thay đường dẫn WAV mẫu bằng file local hai người nói (2–90 giây, tối đa 25 MiB). Nó không
xác nhận public pull hay smoke đã qua trước khi thực sự chạy. Với `--mode pull`, smoke tự pull
image bằng một `DOCKER_CONFIG` rỗng mới và ghi `anonymous_pull` vào evidence, nên đăng nhập registry
có sẵn trên máy không thể che việc image chưa công khai. `DOCKER_CONFIG` rỗng cũng bỏ Docker
context, nên khi chưa đặt `DOCKER_HOST`, smoke đọc endpoint của context đang dùng và đặt nó làm
`DOCKER_HOST` chỉ cho lệnh pull; context cần TLS vẫn phải tự đặt `DOCKER_HOST`, `DOCKER_CERT_PATH`
và `DOCKER_TLS_VERIFY`. Pull lỗi chưa chắc do image riêng tư (cũng có thể do registry hoặc Docker
daemon không truy cập được); stderr đã che thông tin nhạy cảm nằm trong `smoke.log`. Khi có thể, nó
cũng ghi `image_revision_parity`. Ở pha ngắt mạng, smoke giữ phiên ChatGPT đã kết nối, bấm tạo
notes và kiểm tra tác vụ kết thúc `failed` với mã `provider_unavailable`, notes đã lưu không đổi và
không có lời gọi ra ngoài:

```sh
./scripts/offline-smoke.py \
  --image "$ASR_IMAGE" \
  --models "$ASR_MODEL_HOST_PATH" \
  --audio ./authorized-two-voice.wav \
  --output /tmp/asr-offline-smoke-evidence \
  --mode offline
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

| Thành phần | Nguồn và điều kiện | Mạng hoặc chấp thuận |
| --- | --- | --- |
| Runtime | Docker Engine, Docker Compose 2.30+, `faster-whisper` 1.2.1 và `pyannote.audio` 4.0.7; dependency Python được khóa trong `uv.lock` | Người vận hành cài Docker; GPU cần NVIDIA driver và Container Toolkit đã cấu hình trên host. |
| ASR GPU | [Systran faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3), MIT, tải công khai | Chế độ source/pull có thể tải ở bước `model prepare`; không cần chấp thuận điều khoản gated. |
| ASR CPU | [Systran faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small), MIT, tải công khai | Chế độ source/pull có thể tải ở bước `model prepare`; không cần chấp thuận điều khoản gated. |
| Diarization | [pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1), CC-BY-4.0, truy cập gated | Người vận hành phải tự chấp thuận điều kiện và tải model trên host. Ứng dụng không chấp thuận thay, không nhúng token, không tải model này. |
| Giao diện | HTML, CSS, JavaScript và font được đóng gói trong wheel | Được phục vụ local; không tải UI động từ mạng. |

Chế độ source/pull tải model CTranslate2 còn thiếu từ bộ model công khai của Systran:
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
ngoài. UI hiển thị compute backend, compute type và model worker đang dùng trong phần
**Chi tiết xử lý** của khối Transcript; phần này thu gọn mặc định.

Hộp thoại **Cuộc họp mới** có một nút chính **Tạo cuộc họp**: nút này tải file lên, chờ máy chủ
kiểm tra rồi tạo cuộc họp. Tên cuộc họp được điền sẵn từ tên file (bỏ phần mở rộng) cho tới khi
bạn tự gõ, và gợi ý ngôn ngữ mặc định là lựa chọn lần trước. Ô **Chép lời ngay sau khi tạo** được
bật sẵn và nhớ lựa chọn cuối trong trình duyệt này. Khi bật, trang cuộc họp tự gửi yêu cầu chép
lời đúng một lần để chiếm slot xử lý; tải lại trang hoặc Back không gửi lại. Nếu máy đang bận hoặc
worker/model chưa sẵn sàng, trang hiện lý do cùng nút **Bắt đầu chép lời** và không tự thử lại.
Khi tắt ô này, cuộc họp chỉ lưu bản ghi; mở cuộc họp rồi bấm **Bắt đầu chép lời** để chiếm slot.

Sau khi có transcript, nút phụ **Chạy lại bản ghi** tạo một thế hệ transcript riêng; thế hệ cũ
còn được giữ nếu lần chạy mới lỗi hoặc bị hủy. Chỉ thế hệ hoàn chỉnh được công bố. Khi chép lời
đang chạy, thanh tiến độ hiện giai đoạn bằng tiếng Việt và phần trăm bằng mốc transcript chia cho
thời lượng bản ghi (không vượt 100 %); thiếu thời lượng thì thanh không xác định và không có phần
trăm. Nút hủy ghi **Hủy chép lời**. Giao diện còn hiển thị thời gian đã chạy, số đoạn và mốc
timestamp cuối cùng nhận được, không có ETA. Tiến độ đọc từ lần poll tác vụ hiện có, không thêm
request.

Trong trang cuộc họp, **Xóa cuộc họp** yêu cầu nhập đúng tên trước khi gửi yêu cầu xóa. Nếu
transcript hoặc notes đang chạy, giao diện hướng dẫn hủy tác vụ và chờ trạng thái kết thúc rồi thử
lại. Sau khi máy chủ chấp nhận xóa, ứng dụng đánh dấu cuộc họp trong SQLite trước, rồi xóa audio,
upload và file tạm do workspace quản lý; file nguồn bên ngoài không bị thay đổi. Transcript, các
thế hệ và người nói, snapshot nguồn notes cùng mọi phiên bản notes chỉ bị xóa khỏi cơ sở dữ liệu
sau khi dọn file thành công. Nếu dọn dẹp lỗi hoặc tiến trình dừng giữa chừng, giao diện giữ cuộc họp
ở trạng thái chờ/thất bại, cho phép thử lại, và ứng dụng tiếp tục xử lý các dấu xóa còn lại khi khởi
động. Cuộc họp chỉ biến mất khỏi lịch sử, tìm kiếm, lịch và nhóm **Chưa đặt ngày** sau khi bước xóa
cuối cùng được lưu thành công.

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
được tô sáng; nút timestamp tua và phát cùng nguồn audio đã lưu. Chip mốc thời gian của notes cũng
tua, phát và đánh dấu đoạn nguồn trong transcript, còn nút **Tua bản ghi tới mốc này** của thẻ nguồn
chỉ tua. Người nói do model gán ban đầu và timestamp được lưu riêng, nên sửa người nói không làm mất
chúng.

Trang cuộc họp chia thành hai tab theo mẫu WAI-ARIA Tabs, ngay dưới phần đầu trang: **Meeting notes**
và **Transcript & bản ghi**. Phần đầu trang hiện tên cuộc họp đúng một lần (tiêu đề chung phía trên
chỉ ghi **Cuộc họp**), ngày họp, gợi ý ngôn ngữ và một dải trạng thái ngắn **Bản ghi · Transcript ·
Notes**, mỗi mục là chữ trạng thái như **Chưa chép lời**, **Đang chép lời**, **Hoàn tất**,
**Đang tạo** hay **2 bản**. Tab **Transcript & bản ghi** chứa khối bản ghi với trình phát dính, khối
chép lời (nút chép lời và hủy, tiến độ, lỗi), người nói và các đoạn; khi đã có transcript, nhãn tab
ghi số đoạn và số đoạn **cần kiểm tra** (đoạn có dấu rà soát). Tab **Meeting notes** chứa toàn bộ
phần notes: tạo, tiến độ, lỗi, phiên bản, **Xem | Viết**, sao chép và tải về. Khi chưa có transcript
hoàn chỉnh, tab này chỉ hiện trạng thái trống **Cần transcript trước** cùng nút chuyển sang tab
Transcript, không có ô chọn hay nút tạo notes bị tắt.

Mở `/meetings/{id}` không kèm hash chọn **Meeting notes** nếu cuộc họp có ít nhất một bản notes đã
lưu hoặc đang tạo notes, ngược lại chọn **Transcript & bản ghi**. `#notes` và `#transcript` chọn
tab tương ứng và thắng quy tắc mặc định; link nguồn `?notes_source=…&segment=…` không kèm hash mở
tab **Transcript & bản ghi**, nơi có thẻ nguồn đã lưu (`#notes` vẫn hiện tab notes và giữ nguồn đã
nạp cho lần chuyển tab sau). Đổi tab (bấm, hoặc mũi tên trái/phải, Home, End khi focus ở một tab)
thêm một mục lịch sử bằng `pushState` với hash mới và giữ nguyên đường dẫn cùng query, nên Back quay
lại tab trước và tải lại trang giữ tab; chỉ tab đang chọn nằm trong thứ tự Tab. Bấm tạo notes từ bất
kỳ đâu đều chọn tab **Meeting notes** để theo dõi tiến độ. Thẻ nguồn nằm ngay dưới trình phát, cùng
tab với nó, nên nút **Tua bản ghi tới mốc này** của thẻ không đổi tab. Từ 680 px trở xuống, danh
sách tab nằm ngay dưới phần đầu trang; hai nút trạng thái **OpenAI** và **Google** giữ nguyên.

Transcript mở ở chế độ đọc: mỗi đoạn chỉ hiện nút timestamp, tên người nói, nội dung (13 px) và,
nếu có, dấu rà soát (**Cần kiểm tra** kèm lý do, hoặc **Nên nghe lại**); chưa có ô nhập, select hay
nút lưu nào. Nút **Sửa** luôn hiện ở mỗi đoạn của thế hệ hiện tại và mở ô sửa của đoạn đó, gồm nội
dung, select người nói, **Lưu đoạn** và **Hủy**. Chỉ một ô sửa mở tại một lúc. Select lưu ngay khi đổi
người nói; **Lưu đoạn** hoặc Ctrl/⌘+Enter (từ bất kỳ control nào trong ô đang mở) lưu nội dung;
**Hủy** hoặc Esc đóng ô và bỏ phần đã gõ. Sau khi lưu hoặc hủy, focus quay lại nút **Sửa** của đoạn
đó. Mở đoạn khác cũng đóng ô đang mở nhưng giữ văn bản chưa lưu làm bản nháp trong trang này: đoạn có
bản nháp hiện dấu **Bản nháp chưa lưu**, và mở lại sẽ khôi phục văn bản. Bản nháp đã bị đánh dấu xung
đột (transcript đã đổi ở tab khác) còn được giữ cả khi **Hủy** hoặc Esc, để đối chiếu với bản mới.

Mục **Chi tiết** trong ô sửa chứa **Gán ban đầu** (người nói do model gán) và các chỉ số model của
đoạn; ở chế độ đọc chúng không hiện. Thế hệ cũ chỉ đọc: không có **Sửa**, nhưng mỗi đoạn giữ một mục
**Chi tiết** đóng sẵn cho hai thông tin này. Khi nguồn đang bị khóa (đang tạo notes, hoặc đang kiểm
tra trạng thái khóa), **Sửa** và chip người nói bị tắt, lý do hiện ở dòng trạng thái phía trên danh
sách người nói; nếu khóa đến khi ô sửa đang mở, nội dung, select và **Lưu đoạn** bị tắt, còn **Hủy**
vẫn dùng được. Mỗi đoạn ở chế độ đọc có tối đa hai điểm dừng Tab (timestamp và **Sửa**), và thông
báo **Đã lưu** của mọi đoạn dùng chung một vùng trạng thái `aria-live` ở đầu khối transcript.

Mục **Người nói trong phiên bản này** hiện mỗi người nói thành một chip; người nói còn tên mặc định
do hệ thống đặt (**Speaker N**) có dấu **đặt tên**. Bấm chip mở ô đổi tên ngay tại chỗ: Enter lưu,
Esc hoặc **Hủy** đóng, **Khôi phục tên mặc định** xóa tên đã đặt. Chỉ một ô đổi tên mở tại một lúc;
tên đang gõ ở ô vừa rời đi được giữ làm bản nháp (chip hiện dấu **bản nháp**), và bản nháp đã bị
đánh dấu xung đột còn được giữ cả khi Esc hoặc **Hủy**. **Thêm người nói** vẫn nằm dưới danh sách
chip. Ở thế hệ cũ, chip chỉ để đọc.

Trình phát dính ở mép trên vùng nội dung khi cuộn transcript trong tab **Transcript & bản ghi**, ở
cả desktop và màn hình từ 680 px trở xuống; thanh dính chỉ gồm trình phát (cao tối đa 72 px), còn
tiêu đề và dòng hướng dẫn của khối bản ghi cuộn đi như bình thường. Tab **Meeting notes** không
ghim trình phát và không tạm dừng audio, nên bạn vừa nghe vừa đọc notes được; muốn dừng thì quay
lại tab **Transcript & bản ghi**. Khi audio đang phát và đoạn đang phát đổi, danh
sách tự cuộn để đoạn đó nằm gọn trong tầm nhìn, dưới thanh trình phát, miễn là còn thấy một phần
danh sách đoạn; cuộn tức thì khi hệ điều hành bật giảm chuyển động. Danh sách không tự cuộn khi
audio tạm dừng, trong 2 giây sau khi bạn cuộn tay (con lăn, chạm, phím cuộn hoặc kéo thanh cuộn),
khi focus đang nằm trong một ô sửa của transcript, hay khi cả danh sách đoạn nằm ngoài tầm nhìn
dưới thanh trình phát hoặc đang ẩn vì bạn ở tab **Meeting notes** (ví dụ lúc bạn đang đọc notes hoặc
vừa mở một nguồn), nên trang không bị kéo khỏi chỗ đang đọc.

Nếu diarization hoặc alignment lỗi hay bị hủy, task không công bố thế hệ mới và thế hệ hiện tại vẫn
được giữ. Không có bước gửi audio hoặc inference cloud. Thư mục model đã tải có thể được dùng offline
sau đó.

Mỗi segment lưu ID ổn định, timestamp bắt đầu/kết thúc, văn bản và các chỉ số model có sẵn:
`avg_logprob`, `no_speech_prob` và `compression_ratio`. Một segment được đánh dấu **Nên nghe lại**
nếu `avg_logprob < -1.0`, `no_speech_prob >= 0.6` hoặc `compression_ratio > 2.4`. Đây là các dấu
hiệu rà soát theo ngưỡng decode của Whisper, không phải xác suất transcript đúng; văn bản vẫn được
giữ nguyên. Các lý do rà soát từ nhận dạng và diarization được lưu riêng để người dùng nghe lại và
điều chỉnh speaker assignment khi cần. Giao diện chỉ hiện các chỉ số model trong mục **Chi tiết**
của đoạn, không hiện ở chế độ đọc.

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

Thanh đầu workspace có hai nút trạng thái riêng: **OpenAI** (ChatGPT) và **Google**
(Antigravity). Mỗi nút hiện chấm màu cùng chữ **Đã kết nối**, **Chưa kết nối**, **Cần đăng nhập
lại** hoặc **Không khả dụng**, và cả hai mở cùng hộp thoại kết nối. Nút tạo notes trong tab
**Meeting notes** cũng mở hộp thoại này, ở đúng phần của nhà cung cấp đã chọn, khi bên đó chưa
kết nối hoặc chưa có model dùng được.

Mở **OpenAI**, rồi chọn **Continue with ChatGPT** để đăng nhập và cấp quyền dùng gói. Kết nối này
độc lập với token truy cập localhost. Ứng dụng lưu phiên trong volume `provider` với quyền truy
cập hạn chế để dùng lại sau restart; không đọc credential từ Codex hoặc công cụ cá nhân khác. Khi
phiên mất hiệu lực, UI yêu cầu kết nối ChatGPT lại.

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

Xem [quy trình kiểm chứng ChatGPT thật](chatgpt-integration-check.md) để ghi nhận quyền tài
khoản, model và kết quả. Kiểm thử giả lập không xác nhận entitlement hoặc quota của tài khoản thật.

## Kết nối Google Antigravity qua OMP

Mở **Google** trên thanh đầu workspace; hộp thoại mở thẳng phần **Google Antigravity**. Chọn
**Kết nối Google Antigravity**. UI hiển thị URL đăng nhập do OMP cung cấp và, khi provider yêu cầu,
ô nhập mã hoặc URL chuyển hướng. Phiên đăng nhập hết hạn sau 10 phút và có thể hủy rõ ràng. Sau khi
kết nối, chọn model từ catalog, lưu lựa chọn và chạy yêu cầu kiểm tra tổng hợp để xác nhận model
thực sự tạo được đầu ra. Catalog không tự chứng minh quyền inference hoặc quota.

Cùng lúc lưu model, chọn **Mức suy nghĩ**: High (mặc định, đầy đủ hơn nhưng chậm hơn, khoảng 7–10
phút cho cuộc họp 1 giờ) hoặc Medium (nhanh hơn nhưng có thể bỏ sót việc cần làm). Mỗi tác vụ notes
ghim mức này lúc được nhận; đổi sau đó chỉ áp dụng cho lần chạy tiếp theo.

Image pin OMP `18.5.0` bằng checksum riêng cho `amd64` và `arm64`. Runner dùng home, agent store,
XDG directories và working directory riêng dưới volume `provider`; không đọc cấu hình Claude,
Codex hay OMP cá nhân trên host. Mỗi tiến trình RPC chạy với `--no-session`, `--no-tools`,
`--no-extensions`, `--no-skills`, `--no-rules`, `--no-lsp`, `--no-pty` và `--no-ui`, cùng
`--system-prompt` trung tính chỉ cho phép trả lời văn bản (thay prompt trợ lý lập trình mặc định của
OMP, không có tool); cấu hình còn
tắt MCP, memory, auto-compaction, retry và model fallback. Backend kiểm tra lại rằng RPC không công
bố tool trước khi gửi yêu cầu. Credential OMP được giữ trong volume riêng để dùng lại qua restart.

Yêu cầu kiểm tra chỉ gửi chỉ dẫn tổng hợp cố định và phải trả đúng JSON `{\"ok\":true}`. Event JSON
của OMP chỉ là transport; ứng dụng không coi event hay text assistant là Notes đã hợp lệ. Khi tích
hợp tạo notes, transcript phải tiếp tục được đóng khung là dữ liệu không tin cậy và đi qua cùng
pipeline kiểm tra schema/source ID trước khi lưu. Lỗi revoke, quota, model access và mạng được báo
theo nhóm có thể hành động; nội dung lỗi thô và credential không được trả về UI, và inference không
tự gửi lại. Mỗi lệnh gọi tạo notes có thể chạy tối đa 15 phút trong giới hạn 60 phút của tác vụ;
provider dừng với finish reason lỗi (ví dụ `MALFORMED_FUNCTION_CALL`) được báo là phản hồi không
dùng được.

**Ngắt kết nối Antigravity** yêu cầu OMP vô hiệu hóa credential `google-antigravity` trong store
riêng. OMP không xác nhận thu hồi quyền truy cập ở phía Google; nếu cần thu hồi quyền từ xa, hãy
kiểm tra [quyền truy cập tài khoản Google](https://myaccount.google.com/permissions). Việc ngắt
kết nối không ảnh hưởng ChatGPT, token truy cập localhost, transcript hoặc notes đã lưu.

## Tạo và đối chiếu notes

Mở cuộc họp đã có transcript hoàn chỉnh, kết nối nhà cung cấp và lưu model trong phần kết nối, rồi
bấm nút tạo notes trong tab **Meeting notes**. Tab chỉ có một nút chính, tên nút nêu lựa chọn đã
lưu: **Tạo notes · English · ChatGPT GPT 6.1 Sol** (ngôn ngữ đầu ra, nhà cung cấp, model).
**Đổi…** mở vùng chứa ba ô chọn ngôn ngữ đầu ra, nhà cung cấp và model cùng mô tả dữ liệu được
gửi đi; vùng này đóng sẵn, lựa chọn lưu ngay và hệ thống không tự đổi nhà cung cấp hay model. Nếu
nhà cung cấp đã chọn chưa kết nối hoặc model chưa sẵn sàng, nút thành **Kết nối ChatGPT để tạo
notes** (hoặc **Kết nối Google Antigravity để tạo notes**) và mở hộp thoại kết nối ở đúng phần của
nhà cung cấp đó; khi tác vụ đang chạy, nút giữ nguyên chỗ, bị tắt, cạnh **Hủy tạo notes**.

Notes dùng tên người nói tại thời điểm tạo. Nếu transcript hiện tại còn người nói mang tên mặc
định do hệ thống đặt (**Speaker N**), khu vực tạo notes hiện **Notes sẽ dùng tên người nói hiện
tại: Speaker 1, Speaker 2.** kèm link **Đặt tên trước**, chuyển sang tab **Transcript & bản ghi**
và đưa focus tới danh mục người nói. Lời nhắc không chặn việc tạo notes, và ẩn đi khi tác vụ đang
giữ nguồn vì tên không đổi được.

Worker gửi transcript cùng ID, timestamp, tên người nói và ngày họp cần thiết; không gửi audio.
Nguồn dài được chia tại ranh giới đoạn, tạo các tóm tắt có trích dẫn đã kiểm tra
riêng theo từng phần, rồi tổng hợp theo thứ tự transcript để xử lý quyết định hoặc đề xuất thay
đổi về sau. Mỗi phần sau chỉ mở đầu bằng các đoạn cuối nguyên vẹn của phần trước (tối đa 2.000
byte) làm ngữ cảnh khi chúng vừa; đoạn đầu của phần mới được ưu tiên chỗ, còn phần trước kết thúc
bằng một mảnh của đoạn bị cắt thì không có. Một đoạn đơn lẻ quá lớn cho một lượt gọi được cắt
thành các mảnh văn bản; mỗi mảnh giữ ID và thời điểm bắt đầu/kết thúc của đoạn gốc, hai mảnh liền
nhau lặp lại tối đa 300 ký tự, và transcript đã lưu không đổi. Khi các tóm tắt trung gian quá dài
để ghép cặp, tóm tắt lớn hơn được rút gọn riêng thay vì bị bỏ hoặc cắt; tác vụ chỉ lỗi khi hết
giới hạn số lượt gọi hoặc 8 tầng rút gọn, khi một tóm tắt không thể nhỏ thêm hoặc không vừa một
yêu cầu rút gọn dù đứng riêng. Trước khi gọi provider, backend kiểm tra mọi đoạn đều nằm trong ít
nhất một lượt gọi; manifest độ phủ ghi mỗi lượt gọi xử lý đoạn nào được lưu cùng bản notes (UI và
API không hiển thị). Nguồn vượt 1.000.000 byte hoặc cần hơn 24 phần sẽ bị từ chối trước khi lưu
task và snapshot; transcript không bị cắt hoặc âm thầm bỏ đoạn. Tóm tắt trung gian vẫn có thể bỏ
sót chi tiết, vì vậy hãy đối chiếu nội dung cuối với nguồn.

Mỗi lượt gọi dành tối đa 25.000 token cho reasoning và đầu ra; phần nguồn được chia nhỏ để vẫn
giữ ngân sách context an toàn. Toàn tác vụ có giới hạn 60 phút, không tự đổi model/effort hoặc
tự gửi lại inference nếu hết ngân sách, lỗi hay bị hủy.

Chọn **English** hoặc **Tiếng Việt** trong **Đổi…** trước khi bấm tạo notes; mặc định là English
và tên nút luôn nêu ngôn ngữ đang chọn.
Ngôn ngữ được giữ cố định cho từng tác vụ và bản notes, độc lập với ngôn ngữ transcript.
Notes gồm tổng quan, chủ đề chính và lập luận, quyết định, câu hỏi còn mở, công việc đã xác nhận
và các mục cần xác nhận; tiêu đề và nội dung theo ngôn ngữ đã chọn. Backend kiểm tra cấu trúc và
ID nguồn trước khi lưu. Người phụ trách hoặc thời hạn thiếu giữ là **Undetermined** hoặc
**Chưa xác định**. Chỉ quy đổi deadline tương đối khi ngày họp và cách diễn đạt đủ rõ; luôn giữ
cách nói gốc để rà soát. Kiểm tra schema không thay thế việc người dùng đối chiếu nội dung.

Khi nhận tác vụ, ứng dụng chụp nguồn bất biến (cơ sở dữ liệu từ chối mọi `UPDATE` bảng bản chụp từ
migration schema SQLite v11) và khóa transcript, người nói cùng ngày họp của
cuộc họp đó. Tài khoản/model ChatGPT được giữ cố định; không đổi hoặc ngắt kết nối khi tác vụ còn
hoạt động. Vẫn xem nguồn, sửa notes cũ và làm việc với cuộc họp khác được. Một danh sách bước
**Nhận yêu cầu**, **Khởi chạy**, **Tạo notes**, **Lưu notes** đánh dấu từng bước là đã xong, đang
chạy hoặc chưa tới bằng chữ, kèm thời gian đã chạy và dòng phụ nhà cung cấp · model. Bước làm tác
vụ thất bại, bị hủy hoặc gián đoạn được ghi đúng như vậy; mở trang sau khi tác vụ đã kết thúc thì
không bước nào bị coi là đã xong, chỉ ghi cách tác vụ kết thúc. Bấm **Hủy tạo notes** chuyển tác vụ
sang đang dừng; chỉ khi tiến trình gọi provider đã kết thúc mới mở khóa và nhường slot. Lỗi,
hủy hoặc restart giữ transcript và các notes đã lưu; không công bố đầu ra dở hoặc tự gửi lại
inference. Đầu ra đã nhận đầy đủ nhưng không hợp lệ được phép sửa tối đa một lượt.

Notes đã lưu nằm trong tab **Meeting notes**, trong một khung toàn bề rộng với thanh công cụ chung: chọn phiên bản, nút chuyển
**Xem | Viết**, **Lưu bản nháp**, **Sao chép bản đã lưu** và **Tải Markdown đã lưu**; hàng cuối
của thanh công cụ là nút phụ **Tạo lại notes · …** cùng **Đổi…** (tạo lại luôn sinh một phiên bản
mới và giữ các phiên bản trước). **Xem** là mặc định và hiển thị bản render của bản nháp hiện tại; **Viết** là ô soạn thảo Markdown. Trình
duyệt nhớ chế độ cuối cùng; đổi chế độ không đổi bản nháp hay gọi API. Lưu dùng kiểm tra phiên bản
(Ctrl/⌘+Enter trong ô soạn thảo cũng lưu); xung đột giữ bản nháp để đối chiếu và hiện ở cả hai
chế độ. Khi còn thay đổi chưa lưu, nút **Viết** có chấm báo, **Xem** ghi “Đang xem bản nháp chưa
lưu”, và trình duyệt cảnh báo trước khi đóng hoặc tải lại trang còn bản nháp notes hoặc transcript
chưa lưu. Sao chép và tải Markdown lấy cùng nội dung đã lưu của phiên bản đang chọn; cần lưu hoặc
giải quyết bản nháp trước. Markdown đã lưu, chế độ **Viết**, bản sao chép và file tải về chỉ chứa
nội dung tóm tắt, không kèm liên kết timestamp. Markdown chỉnh tay có liên kết nguồn không mở được
bản chụp của bản notes vẫn được lưu và trả lại đúng nguyên văn; backend kèm `warnings`, **Xem** hiện
liên kết đó thành chữ cùng một dòng cảnh báo và không mở nguồn nào.

Trích dẫn nguồn là dữ liệu riêng của từng bản notes, lưu trong cột `notes_revisions.citations_json`
(migration schema SQLite v10, chỉ thêm cột nên bản v9 đang chạy được nâng cấp nguyên vẹn). Với mỗi
mục, bản notes giữ tiêu đề phần và văn bản mục đúng như đã render cùng các đoạn nguồn (`id` và
`start_seconds`) lấy từ `source_ids` của document; cùng một đoạn mã dựng cả dòng Markdown lẫn trích
dẫn nên hai bên không lệch nhau. Khi công bố, backend kiểm tra hình dạng, kích thước và việc mọi ID
đoạn cùng mốc đều thuộc bản chụp nguồn của bản notes; sửa Markdown về sau không đổi trích dẫn, và
`GET /api/notes/{id}` trả thêm `citations` (danh sách rỗng khi chưa có). Ở chế độ **Xem**, mục có
nguồn hiện sau nội dung một chip cho mỗi đoạn nguồn: `mm:ss` (`h:mm:ss` từ một giờ), là link `<a>` tới
`/meetings/{id}?notes_source={snapshot}&segment={segment}#transcript` với tên truy cập “Nghe lại đoạn
nguồn lúc …”. Chip chỉ gắn vào mục còn đúng tiêu đề phần và nội dung như lúc tạo: mục đã sửa hoặc
chuyển sang phần khác không có chip, và sửa một mục không làm mất chip của mục khác, trừ các mục
trùng tiêu đề phần và nội dung. Markdown không cho biết mục nào trong nhóm trùng là bản gốc, nên
nhóm chỉ giữ chip (mỗi mục đúng chip của mình, theo thứ tự) khi số mục của nhóm bằng lúc tạo; sửa
hay xoá một mục trong nhóm, hoặc thêm bản sao của chúng (kể cả sửa mục khác thành bản sao), làm cả
nhóm mất chip thay vì có chip gắn nhầm. Bản notes tạo trước khi có trích dẫn (cột NULL) không
hiện chip.

Bấm chip, hoặc dán link của chip, chọn tab **Transcript & bản ghi** bằng một mục lịch sử mới nên
Back quay lại **Meeting notes**. Thẻ **Nguồn đã lưu lúc tạo notes** hiện ngay dưới trình phát với văn
bản, người nói, ngày họp và mốc của bản chụp; trình phát tua tới mốc và phát (trình duyệt có thể chặn phát
với link vừa dán, khi đó thẻ nhắc bấm phát); đoạn tương ứng trong transcript được đánh dấu bằng
nhãn **Nguồn của mục notes** và đưa vào tầm nhìn, cuộn tức thì khi người dùng chọn giảm chuyển
động. Khi nguồn hiện tại đã khác bản chụp (transcript hoặc ngày họp), thẻ vẫn hiện văn bản của bản chụp
kèm ghi chú nói khác ở đâu. Bản chụp nguồn vẫn được giữ để kiểm tra nội bộ và lưu lịch sử. Notes cũ hiển thị nguồn
lịch sử hoặc cần cập nhật khi nguồn thay đổi; đổi riêng tên cuộc họp không làm notes cần cập nhật.

## Phát triển và kiểm tra

Cài Python 3.12, uv, Node.js, Docker Compose và actionlint v1.7.11 rồi chạy toàn bộ quality gate
bằng một lệnh (xem [hướng dẫn môi trường và workflow](agents/development.md)):

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
- Push tag dạng `v0.1.0-rc.1` phải khớp version trong source, metadata và lock; RC nhận tag version
  cùng SHA, không cập nhật `latest` hoặc alias stable.
- Tag stable dạng `v1.2.3` phát hành image `ghcr.io/nguyencanhtrung/asr-en-vi` với tag version,
  major.minor, `latest` và SHA.
- Image phát hành cho `linux/amd64` và `linux/arm64` trên runner native song song, sau đó ghép
  manifest đa kiến trúc kèm SBOM, provenance và attestation.

Workflow chỉ dùng `GITHUB_TOKEN`; không cần secret registry riêng. Các action được pin bằng commit
SHA bất biến, còn Dependabot kiểm tra cập nhật hằng tuần cho uv, GitHub Actions và Docker base image.

Trong production image, Docker build context chỉ chứa `pyproject.toml`, `README.md`, `LICENSE`, `LICENSE.vi`, `uv.lock` và
`src/asr_en_vi`. Hướng dẫn, tài liệu thiết kế và prototype không được đưa vào image.
