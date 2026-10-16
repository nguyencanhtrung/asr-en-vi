# ASR EN VI Meeting Notes

Ứng dụng web chạy trên máy tự quản để chuyển bản ghi họp thành transcript và meeting notes.
Hiện ứng dụng có lớp truy cập localhost, SQLite bền, app/worker Compose và workspace để nhập,
kiểm tra, lưu và phát lại bản ghi. Xử lý ASR, diarization, lịch sử nhiều cuộc họp và provider
notes chưa được triển khai.

## Chạy trên máy local

Cần Docker Engine và Docker Compose v2. Mặc định ứng dụng mở tại
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

Compose tạo hai volume riêng:

- `data` giữ SQLite và trạng thái liveness tối thiểu của worker; app và worker cùng gắn volume này.
- `auth` giữ token và khóa ký cookie với quyền file hạn chế; chỉ app gắn volume này.

Restart hoặc recreate container vẫn giữ hai volume. Một Compose project/volume mới sinh token
riêng. Đổi cổng bằng `ASR_PORT` trong `.env`; link mặc định tự theo cổng đó. Có thể đặt
`ASR_PUBLIC_URL` nếu cần một URL loopback cụ thể. `ASR_COOKIE_SECURE` mặc định là `false` cho
HTTP localhost; bật khi đặt một TLS terminator local phía trước app.

Workspace nhận `wav`, `mp3`, `m4a`, `mp4`, `mov`, `webm`, `ogg`, `opus` và `flac`. Backend
kiểm tra codec/thời lượng bằng FFmpeg, rồi lưu một bản M4A/AAC do ứng dụng quản lý; file nguồn
không còn cần thiết sau khi upload hoàn tất. Mặc định mỗi file tối đa 4 GiB và 4 giờ. Có thể đổi
hai giới hạn bằng `ASR_MAX_UPLOAD_BYTES` và `ASR_MAX_RECORDING_SECONDS` trong `.env`.

Để thay token và vô hiệu link/session cũ:

```sh
./scripts/rotate-token.sh
```

Lệnh in link và QR mới. Việc này chỉ thay auth state; SQLite và worker tiếp tục dùng volume cũ.
`docker compose down` giữ volume. `docker compose down -v` xóa volume dữ liệu và auth của project.

## Phát triển và kiểm tra

Cài Python 3.12 và uv. Đồng bộ dependency theo lockfile rồi chạy các check:

```sh
uv sync --all-groups
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest
docker compose config --quiet
```

Một kiểm thử Chromium thực chạy HTTP server và xác nhận fragment được loại khỏi URL, token chỉ
được gửi trong body, và cookie không đọc được từ JavaScript. Để chạy, cài Chromium cho Playwright
và đặt `ASR_RUN_BROWSER_TESTS=1`:

```sh
uv run playwright install chromium
ASR_RUN_BROWSER_TESTS=1 uv run pytest -m browser
```

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
