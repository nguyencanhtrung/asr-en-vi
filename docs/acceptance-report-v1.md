# Báo cáo nghiệm thu release candidate v0.1.0-rc.1 (#16)

## 0. Thông tin chung

| Mục | Giá trị |
| --- | --- |
| Ứng viên phát hành | image `asr-issue16:151f3e4` (build từ source), revision `151f3e4d6249ea6f75d74251d37fc7addb711557` (nhãn `org.opencontainers.image.revision` khớp `git rev-parse HEAD`), phiên bản `0.1.0-rc.1`, schema 12 |
| Ngày đo | 2026-10-24; chấm chất lượng và các xác nhận của người vận hành hoàn tất 2026-10-25 |
| Thực hiện | Các agent worker t1–t10 (cài đặt, baseline, annotation, bảo mật, vòng đời, UI, hiệu năng, provider, UI notes, chất lượng). Người vận hành làm các checkpoint: chạy bước sao chép dữ liệu từ bản cài chính, đăng nhập hai provider, duyệt annotation, ước lượng thời gian duyệt draft, chạy `curl` từ máy thứ hai |
| Nguyên tắc | Kết luận theo đúng worker (pass / fail / partial / not done); không sửa mã sản phẩm; không đổi tiêu chí để tuyên bố đạt. Bằng chứng nằm ở thư mục riêng tư `EV` (ngoài repo, mode 700) và được trích bằng tên tệp tương đối so với `EV` |
| Quyền riêng tư | Báo cáo không chứa nội dung transcript hoặc notes, mục annotation, tên người, nhãn tài khoản, mốc thời gian trong cuộc họp hay ảnh chụp màn hình. Cuộc họp được gọi bằng nhãn 13/10, 16/10, 20/10 và mã ID rút gọn |

## 1. Tóm tắt

### 1.1. Tám tiêu chí của #16

Cột cuối là phần nối vào dòng checkbox tương ứng của issue. Số `#NN` là issue follow-up trên GitHub (mục 9).

| # | Tiêu chí (tóm tắt) | Kết quả | Dòng cho issue #16 |
| --- | --- | --- | --- |
| 1 | Bộ nghiệm thu: EN, VI xen thuật ngữ Anh, code-switch; 2–3 người nói; mẫu 2 giờ; annotation trước | **chưa đạt** | `— Not done: không có cuộc họp toàn tiếng Anh; cả 3 bản ghi có khoảng 6 người nói, không có bản 2–3 người; mẫu 2 giờ là ghép audio 20/10 và 16/10, không phải một cuộc họp #88` |
| 2 | Luồng import, transcript, diarization, notes qua từng provider, review, edit, rerun, history, copy/export, cancel, restart, delete trên Chrome và Firefox | **đạt** | `- [x]` (không thêm gì). Copy/xuất chỉ có cho notes; transcript không có control (mục 4) |
| 3 | Đo AC-01..AC-49 và FE-01..FE-16 ở các viewport đã chốt; mỗi tiêu chí có bằng chứng pass/fail và sai lệch | **chưa đạt** | `— Not done: một số phần chưa đo được: nghe chip (AC-05), bấm giờ 16/10 (AC-14), luồng trên trình duyệt stable hiện hành (AC-15), đường pull và kết nối provider trên bản cài mới (AC-17), kết nối độc lập/ngắt kết nối/phiên mất hiệu lực/quota/billing (AC-35..38, AC-44) và phần UI tương ứng (FE-11, 12, 14, 16); AC-01 thiếu thể loại 1 #89 #87 #88` |
| 4 | Báo cáo ghi phần cứng, driver/runtime, image, model/config, provider, quota, mạng, số lượt gọi/sửa, Recording | **đạt** | `- [x]` (quota không biết; lượt gọi t8-ChatGPT không đếm riêng, xem 2.6). Quota ghi là "không được người dùng nêu; bản cài không lưu" (mục 2) |
| 5 | Mẫu 2 giờ đo từ bắt đầu xử lý đến khi transcript và notes sẵn; báo rõ có đạt 30 phút không | **chưa đạt** | `— Not done: #16: mẫu 2 giờ (ghép) có transcript sẵn sau 128,9 phút (4,3 lần mục tiêu), notes lỗi provider_output_too_large nên không có mốc cả hai sẵn; #99 (đo lại trên main 4a88ec8): transcript sẵn sau 10,4 phút nhưng notes lỗi provider_output_too_large ở lượt 29 sau 24,4 phút, không có mốc cả hai sẵn, mốc lỗi ở 34,8 phút; không đạt mục tiêu 30 phút #71 #72 #73 #101 #102` |
| 6 | Người vận hành đo thời gian đưa draft về mức dùng được; báo rõ có đạt 5–10 phút mỗi giờ họp không | **chưa đạt** | `— Not done: 16/10 không có draft notes để đo (#72 #76); 13/10 và 20/10 chỉ là ước lượng của người vận hành, 20/10 vượt mục tiêu (10,8 phút/giờ) #89` |
| 7 | Kiểm tra riêng chất lượng: source timestamp, speaker, quyết định đổi ở cuối, action item qua ranh giới chunk, deadline tương đối, nội dung mơ hồ | **chưa đạt** | `— Not done: đã chạy đủ 6 kiểm tra nhưng không kiểm tra nào đạt trọn (1 fail, 5 partial); chưa nghe chip để xác nhận bằng chứng #77 #78 #79 #80 #89` |
| 8 | Mọi lỗi nghiệm thu tạo kết quả hành động được hoặc ticket follow-up trước release; không đổi tiêu chí âm thầm | **đạt** | `- [x]`: đã tạo đủ 20 issue follow-up #70–#89 (mục 9); mỗi lỗi hoặc phần chưa đo ở mục 5 dẫn tới ít nhất một follow-up |

Tiêu chí 3, 5, 6 và 7 không được tick: chỉ tick khi tiêu chí được đáp ứng trọn vẹn; với 5 và 7 phép đo đã chạy nhưng kết quả không đạt (5: không có mốc notes sẵn; #16 transcript đã vượt 30 phút, #99 transcript sẵn sau 10,4 phút nhưng notes lỗi và mốc lỗi ở 34,8 phút; 7: có kiểm tra fail và phần nghe chưa làm).

### 1.2. Số lượng kết luận

| Nhóm | Tổng | pass | partial | fail | not done |
| --- | --- | --- | --- | --- | --- |
| AC-01..AC-49 | 49 | 31 | 12 | 6 | 0 |
| FE-01..FE-16 | 16 | 10 | 6 | 0 | 0 |
| FE-17, FE-18 (ngoài phạm vi #16) | 2 | 2 | 0 | 0 | 0 |

- **fail (6):** AC-02, AC-03, AC-10, AC-13, AC-17, AC-39.
- **partial (12 AC):** AC-01, AC-04, AC-05, AC-06, AC-14, AC-15, AC-29, AC-35, AC-36, AC-37, AC-38, AC-44.
- **partial (6 FE):** FE-02, FE-10, FE-11, FE-12, FE-14, FE-16.
- Hàng gộp từ hai nửa (không có provider và có provider) lấy nửa xấu nhất; hàng đổi hoặc suy ra so với worker có ghi lý do ở cột "Ghi chú của người tổng hợp" (mục 5, danh sách tại mục 10).

### 1.3. Điểm chính

- **AC-13 fail:** #16: transcript của mẫu 2 giờ sẵn sau 128,9 phút; notes lỗi `provider_output_too_large` sau 16,0 phút; chi phí diarization tăng theo bình phương thời lượng (mục 6). #99 (đo lại trên main `4a88ec8`, có #71, #72, #74): diarization 96,7 s, transcript sẵn sau 10,4 phút, nhưng notes chạy 24,4 phút (29 lượt gọi nối tiếp) rồi lỗi `provider_output_too_large` ở lượt phục hồi; không có mốc cả hai sẵn, mốc lỗi ở 34,8 phút; bước chậm nhất là notes, 70% thời gian (mục 6.5, #101, #102).
- **AC-10 fail:** với mạng bật, runner diarization gửi telemetry ONNX Runtime tới Microsoft; OMP liên hệ các máy chủ ngoài provider đã chọn (mục 5, #74, #75).
- **AC-17 fail:** `./scripts/start.sh` không tải được model Whisper trên Compose v5.1.4; đường pull chưa kiểm (#70, #87).
- **AC-02, AC-03 fail:** 119/126 mục quan trọng được tìm thấy (3 thiếu); 22/77 quyết định/action bị nâng mức chắc chắn, trong đó 5 ý mơ hồ thành quyết định hoặc action đã xác nhận (mục 8).
- **AC-29 partial:** theme tối đầy đủ và thao tác được; chỉ lệch ở độ tương phản (#81).
- **AC-14:** 13/10 8,0 phút/giờ (đạt, ước lượng); 20/10 10,8 phút/giờ (không đạt, ước lượng); 16/10 không đo (mục 7).
- **FE-02 và FE-10 partial:** FE-02 theo quyết định của lead, đọc literal: tài liệu thiết kế ghi brand là "ASR EN VI" còn chữ hiển thị của wordmark là `ASR / EN VI` (tiêu đề trang và tên truy cập đúng; #86). FE-10: t4 pass phần UI demo, token và tài nguyên; mệnh đề chọn provider chưa được t4 đánh giá, FE-11 partial và AC-10 fail (mục 10.1).
- Luồng đầy đủ trên Chrome 149 và Firefox 158 chạy được ở mọi bước có control (mục 4); 31/49 AC và 10/16 FE đạt trọn.

## 2. Tiêu chí 4: môi trường đo

### 2.1. Phần cứng, hệ điều hành, GPU

| Hạng mục | Giá trị |
| --- | --- |
| OS / kernel | Ubuntu 24.04.4 LTS, Linux 6.17.0-35-generic x86_64 |
| CPU | AMD Ryzen 9 9950X, 16 nhân / 32 luồng |
| RAM / swap | 60 GiB (63.369.668 kB) / 15 GiB (swap đầy nhưng nhàn rỗi trong các lần đo) |
| GPU | NVIDIA GeForce RTX 5080, 16.303 MiB, compute capability 12.0 |
| Driver | 590.48.01 (`nvidia-smi` báo CUDA 13.1) |
| GPU dùng chung | Một tiến trình python khác trên máy, không thuộc ASR (260 MiB, có từ trước các lần đo; sửa ở #99, trước đó ghi nhầm là worker của bản cài chính) và phiên desktop (khoảng 0,85 GiB); mức nền 1,1–1,2 GiB. Worker của bản cài chính nhàn rỗi, không giữ bộ nhớ GPU. Các lần đo AC-13 chạy khi không có tác vụ GPU nào khác của đợt nghiệm thu (khóa `gpu.lock`) |

### 2.2. Docker, image, runtime

| Hạng mục | Giá trị |
| --- | --- |
| Docker / Compose | Docker 29.5.2 (API 1.54), Compose v5.1.4, NVIDIA Container Toolkit CLI 1.19.0, runtime nvidia và runc, overlay2 |
| Image | `asr-issue16:151f3e4`, `sha256:c4e2938c…54b51bb4`, 13.171.314.578 byte, user 10001:10001; build từ source khoảng 2 phút |
| Phiên bản | `0.1.0-rc.1`, schema 12 (`cli version --json`) |
| Runtime trong image | CUDA 12.8.1 (libcudart 12.8.90, cuBLAS 12.8.4.1, cuDNN 9.19.0), Python 3.12.3, ctranslate2 4.8.3, faster-whisper 1.2.1, onnxruntime 1.31.0, torch 2.11.0+cu128, pyannote.audio 4.0.7, ffmpeg 6.1.1, omp 18.5.0 |
| Bản cài dùng để đo | `asr-issue16-eval` (127.0.0.1:8767, dữ liệu sao chép từ bản cài chính): t1, t3, t7–t10; `asr-issue16-src` (8768): t4; `asr-issue16-life` (8769): t5, t6; `asr-issue16-eval-t8nl` (8771, không kết nối provider): t8 |
| Cấu hình | `ASR_COOKIE_SECURE=false`, `ASR_MAX_UPLOAD_BYTES=4294967296`, `ASR_MAX_RECORDING_SECONDS=14400`, `ASR_DEVICE=auto`, `ASR_GPU_MODEL_PATH=/models/whisper-large-v3`, `ASR_GPU_COMPUTE_TYPE=float16`, `ASR_CPU_MODEL_PATH=/models/whisper-small`, `ASR_CPU_COMPUTE_TYPE=int8`; `ASR_DIARIZATION_MODEL_PATH` để mặc định. Rootfs chỉ đọc, `cap_drop ALL`, `no-new-privileges`; app không yêu cầu GPU, worker dùng `compose.gpu.yaml` |
| Kiểm tra trước đo | Suite đầy đủ 1049 passed, 10 skipped, 0 failed (1059 test thu thập; 12 phút 8 giây); `tests/test_omp_contract.py` với `ASR_RUN_OMP_CONTRACT=1`: 8/8 |

### 2.3. Model và cấu hình xử lý

| Hạng mục | Giá trị |
| --- | --- |
| ASR | Whisper large-v3, float16, CUDA; `beam_size=5`, không VAD; `language=None, multilingual=True` (lựa chọn ngôn ngữ lúc import chỉ là metadata, không điều khiển nhận dạng) |
| Diarization | pyannote `speaker-diarization-community-1` (33 MB) trên CUDA; clustering `VBxClustering` với PLDA |
| Tệp model | `whisper-large-v3` 2,9 GB (`model.bin` 3.087.284.237 byte), mount chỉ đọc từ máy chủ; `pho-whisper-large` có sẵn nhưng không dùng |
| Notes | Prompt `notes-hierarchical-v6`. Ngân sách: prompt tối đa 32.129 byte (23.957 khi cần chừa chỗ cho lượt sửa), câu trả lời chunk 8.000, reduce 10.700, cuối 128.000 byte; tối đa 24 chunk, 24 lượt reduce, 49 lượt gọi, 1.000.000 byte nguồn; chồng lấn 2.000 byte |

### 2.4. Provider, model, gói và quota

| Hạng mục | Giá trị |
| --- | --- |
| ChatGPT | `gpt-5.6-sol`, mức suy luận `medium`, đầu ra English (lựa chọn lưu sẵn); cả 7 model trong danh mục đều dùng được |
| Google Antigravity (OMP 18.5.0) | `gemini-3.8-flash`, mức suy nghĩ High, đầu ra English |
| Đăng nhập | Do người dùng thực hiện trên bản cài eval (ChatGPT; Google Antigravity qua OMP) |
| Gói / quota | Không được người dùng nêu; bản cài không lưu (không có khóa plan, tier hay subscription trong API hoặc trạng thái provider). Không lần chạy nào gặp thông báo quota, rate-limit, xác thực hay model |
| Notes sao chép từ bản cài chính | 20/10: Antigravity ×2 và ChatGPT ×1 (prompt v5, không có trích dẫn); 16/10: Antigravity ×1 (prompt v6, trạng thái `stale`). Không do ứng viên này tạo |

### 2.5. Điều kiện mạng

| Hạng mục | Giá trị |
| --- | --- |
| Bình thường | Máy có mạng có dây tới Internet; Wi-Fi gần như không mang lưu lượng provider (≤ 0,1 MB mỗi lần đo) |
| Ngoại tuyến gây ra | Mạng Compose `internal` kèm relay loopback theo mẫu `scripts/offline-smoke.py` (t4); `docker network disconnect/connect` worker, `docker pause/unpause`, `docker kill -s KILL`, `pkill -9` trên bản cài (t5 trên `asr-issue16-life`; t8, t9 trên `asr-issue16-eval`). Không thay đổi mạng của máy chủ |
| Quan sát lưu lượng | Sidecar sniffer chung network namespace (chỉ tên, IP, cổng, số byte; không payload), `connwatch`/`procwatch` trong container, mẫu `/proc/net/*` mỗi 0,2–1 giây |

### 2.6. Số lượt gọi provider và lượt sửa

| Đợt | Provider / model | Lượt gọi | Lượt sửa (repair) | Kết quả |
| --- | --- | --- | --- | --- |
| t7, mẫu 2 giờ (16 chunk) | ChatGPT `gpt-5.6-sol` / medium | 25 (kèm 1 kết nối xác thực) | 0 | lỗi ở lượt 25 |
| t7, 13/10 (8 chunk) | như trên | 13 (kèm 1 kết nối xác thực) | 0 | lỗi ở lượt 13 |
| t7, 20/10 (6 chunk) | như trên | 7 | 0 | thành công |
| t7, 16/10 (10 chunk) | như trên | 16 | 0 | lỗi ở lượt 16 |
| t8 bước 0, 13/10 (8 chunk) | Antigravity `gemini-3.8-flash` / High | 9 (8 chunk + 1 cuối) | 0 | thành công |
| t8 bước 0, 16/10 lần 1 | như trên | 6 | 0 | lỗi ở lượt 6 |
| t8 bước 0, 16/10 thử lại một lần | như trên | 14 (10 chunk + 3 hợp nhất + lượt lỗi) | 0 | lỗi ở lượt 14 |
| t8, cả phiên | Antigravity | 62 lượt suy luận OMP (4 lượt bị OMP hủy) | 0 | |
| t8, ChatGPT (N02, N11–N17, các lần gây lỗi) | ChatGPT | không đếm riêng | 0 lượt sửa quan sát được | |
| t9 | ChatGPT | 40 tác vụ notes (11 thành công, 16 hủy, 12 lỗi do cắt mạng chủ ý, 1 gián đoạn) | 0 | |
| t10, AC-06 không có ngày họp | ChatGPT | 1 + 1 | 0 | thành công cả hai |

Tổng 61 lượt gọi ChatGPT ở bốn lần chạy AC-13: mỗi lượt một kết nối, độ song song tối đa 1, không có lượt gửi lại. Chưa có lượt sửa đầu ra nào xảy ra ở lượt gọi thật; AC-40 được kiểm bằng mô phỏng (mục 5).

### 2.7. Recording dùng để đo

Bản sao nằm ở `EV/recordings/`; bản gốc trong `~/Downloads` chỉ đọc (kích thước, mtime và sha256 trước/sau không đổi: `EV/setup/originals-{stat,sha256}-{before,after}.txt`). Cả ba có audio AAC-LC 48 kHz stereo 160 kb/s (bỏ phần video H.264 1080p khi cần).

| Tệp (bản sao) | Dung lượng (byte) | Thời lượng | sha256 (đầu…cuối) |
| --- | --- | --- | --- |
| `meeting-13-10-26.mp4` | 3.468.138.686 | 4498,17 s (75,0 phút) | `79d3aab0…70502a57` |
| `meeting-2026-10-16.mp4` | 3.103.941.107 | 4025,83 s (67,1 phút) | `ca51d1c9…190305ea` |
| `meeting-20-10-26.mp4` | 2.575.438.147 | 3340,37 s (55,7 phút) | `04082712…8a20f05e` |
| `composite-2h.m4a` | 148.706.069 | 7366,14 s (122,8 phút) | `7c03215f…98ca364e` |

- Mẫu 2 giờ là **ghép**: audio 20/10 rồi audio 16/10, nối không mã hóa lại (345.289 gói; bằng tổng hai nguồn 156.579 + 188.710). Không phải một cuộc họp.
- Meeting trong bản cài eval: 20/10 `881f18e4…` (3340,33 s) và 16/10 `ea7ff272…` (4025,79 s) sao chép từ bản cài chính cùng transcript đã có; 13/10 `c093edb9…` (4498,1 s) và các bản chạy lại 20/10 `d9280fae…`, 16/10 `4bbb06d7…` do t7 tạo bằng ASR mới.
- Các clip cắt (audio, không tái mã hóa) dùng cho kiểm tra chức năng nằm ở `EV/clips/` (danh mục `EV/clips/MANIFEST-t5.md`, `EV/t4-security/clips.sha256`).

### 2.8. Trình duyệt và công cụ

| Hạng mục | Giá trị |
| --- | --- |
| Chrome | Google Chrome 149.0.7827.53 (gói `google-chrome-stable` 149.0.7827.53-1), Playwright 1.64.0 `channel="chrome"`, headless |
| Firefox | Firefox 158.0 (snap 158.0-2, kênh `latest/stable/ubuntu-24.04`), Playwright `channel="moz-firefox"`, headless; `TMPDIR` trong vùng snap, tệp upload dưới `$HOME`, theme tối và giảm chuyển động qua `firefox_user_prefs` |
| Bản "ổn định" (AC-15) | Không phải bản stable hiện hành tại ngày đo: Firefox `latest/stable` là 158.0.1-1 (phát hành 2026-10-20, `snap info firefox`); kho apt của Google có `google-chrome-stable` 156.0.8078.47-1 (`apt-cache policy`), bản 149 cài trên máy từ tháng 6/2026 |
| Viewport | 1440×1000, 1280×800, 1024×768 (UI), thêm 360×740 cho FE-17/FE-18 |
| Không dùng | Chromium/Firefox đóng gói kèm Playwright không dùng làm bằng chứng nghiệm thu; ngoại lệ duy nhất là kiểm tra dữ liệu ban đầu của t1 (`EV/setup/step4-browser.*`, Chromium đóng gói, không tiêu chí nào dựa vào nó); không dùng màn hình của người dùng |

## 3. Tiêu chí 1: bộ dữ liệu nghiệm thu

Kết quả: **chưa đạt** (#88). Spec 8.1 cần ít nhất ba bản ghi: (1) hoàn toàn tiếng Anh, (2) tiếng Việt xen thuật ngữ Anh, (3) cả hai ngôn ngữ trong cùng bản ghi; dài 1–2 giờ, 2–3 người nói, có mẫu 2 giờ và annotation trước.

### 3.1. Từng bản ghi

Khối ngôn ngữ tính theo thời lượng và số segment (heuristic dấu tiếng Việt, nêu trong từng bản annotation: segment dưới 3 từ là `short`; `VI` nếu ít nhất 25% số từ, hoặc ít nhất 3 từ, có chữ đặc trưng tiếng Việt; `EN` nếu không từ nào có; còn lại `mixed`).

| Bản ghi | Thể loại (spec 8.1) | Thời lượng | Segment | Khối ngôn ngữ | Nhãn người nói / ước lượng người thật |
| --- | --- | --- | --- | --- | --- |
| 16/10 (`ea7ff272…`) | 2: tiếng Việt xen thuật ngữ Anh | 67,1 phút | 996 (VI 792, EN 19, short 183, mixed 2) | Một ngôn ngữ suốt bản ghi: 98,9% ký tự là tiếng Việt; 170/792 segment VI có thuật ngữ Anh; 19 segment EN là nhiễu, hallucination, URL, mảnh vụn | 7 nhãn (7 dùng); ≈6 người (5–7); 50 segment chưa gán |
| 20/10 (`881f18e4…`) | 3: code-switch EN/VI | 55,7 phút | 736 (EN 413, VI 141, short 182) | EN ≈40 phút đầu (564 segment: 412 EN, 0 VI); VI ≈15 phút cuối (172 segment: 141 VI, 1 EN; 39/141 có thuật ngữ Anh). 71,4% ký tự EN, 28,6% VI; chuyển ngôn ngữ dứt khoát | 10 nhãn (9 dùng); ≈6 người (5–8); 12 segment chưa gán |
| 13/10 (`c093edb9…`) | 3: code-switch EN/VI | 75,0 phút | 827 (EN 390, VI 315, short 122) | EN ≈44,8 phút đầu (436 segment: 387 EN, 0 VI); VI ≈30,2 phút cuối (391 segment: 315 VI, 3 EN do hallucination; 88/315 có thuật ngữ Anh). 59,2% ký tự EN, 40,8% VI | 7 nhãn (7 dùng); ≈6 người (5–7); 28 segment chưa gán |
| Mẫu 2 giờ | ghép 20/10 + 16/10 | 122,8 phút (7366,14 s) | 1838 (lần chạy ASR mới) | như hai bản ghép | 12 nhãn (lần chạy mới) |

### 3.2. Vì sao chưa đạt

| Yêu cầu | Thực tế |
| --- | --- |
| Có cuộc họp hoàn toàn tiếng Anh | **Không có.** 20/10 có khối tiếng Việt ≈15 phút; 13/10 có khối tiếng Việt ≈30 phút (40,8% ký tự). Chỉ có thể cắt phần toàn tiếng Anh (≈40–44 phút) thành mẫu dẫn xuất; đó không phải bản ghi loại 1 và chưa được quyết định dùng |
| Một cuộc họp tiếng Việt xen thuật ngữ Anh | Có: 16/10 |
| Một cuộc họp code-switch EN/VI | Có: 20/10 và 13/10 |
| 2–3 người nói | **Không có.** Cả ba bản ghi là cuộc họp nhóm với khoảng 6 người nói (7–10 nhãn do diarizer định nghĩa). Ước lượng dựa vào dấu hiệu trong transcript, không nghe lại |
| Dài 1–2 giờ | 16/10 (67,1 phút) và 13/10 (75,0 phút) nằm trong khoảng; 20/10 (55,7 phút) ngắn hơn 1 giờ |
| Mẫu dài 2 giờ | Chỉ có mẫu ghép từ hai bản ghi (7366,14 s). Chi phí diarization phụ thuộc thời lượng và số lượt đổi người nói (2585 ở mẫu ghép) nên kết quả AC-13 là xấp xỉ cho một cuộc họp 2 giờ liền |
| Annotation trước về ý quan trọng, quyết định, action item | Có cho cả ba bản ghi (mục 3.3) |

### 3.3. Annotation: phương pháp và thiên lệch

| Bản ghi | Điểm quan trọng | Quyết định | Action item | Tình huống đặc biệt | Duyệt |
| --- | --- | --- | --- | --- | --- |
| 16/10 | 17 | 6 (2 đã thống nhất, 4 kế hoạch hoặc có điều kiện) | 15 (8 chắc chắn, 7 cần xác nhận) | 46 | Người vận hành duyệt nguyên bản, 0 mục sửa; không nêu số phút duyệt |
| 20/10 | 15 | 7 (4 đã thống nhất, 3 kế hoạch, mềm hoặc có điều kiện) | 15 (11 chắc chắn, 4 cần xác nhận) | 45 | như trên |
| 13/10 | 23 | 10 (4 đã thống nhất, 6 kế hoạch, mềm hoặc có điều kiện) | 18 (5 chắc chắn, 13 cần xác nhận) | 66 | Người vận hành duyệt nguyên bản ngày 2026-10-25, 0 mục sửa |

Tình huống đặc biệt gồm năm nhóm: (a) quyết định đổi về sau, (b) mục đi qua ranh giới chunk (tính bằng cách chạy lại đúng hàm chia nguồn của ứng dụng, không gọi provider), (c) deadline tương đối hoặc không đầy đủ, (d) nội dung mơ hồ hoặc nhiễu, (e) bẫy nhãn người nói và câu ngôi thứ nhất. Tệp: `EV/annotations/<ngày>-draft.md` (nội dung, riêng tư), `classification.md`, `<ngày>-segment-index.tsv`, `<ngày>-chunk-plan.json`.

Thiên lệch cần biết khi đọc điểm chất lượng ở các mục 5 và 8:

1. **Do agent soạn từ transcript ASR đã lưu**, không nghe lại và không đọc notes. Vì vậy tham chiếu là "điều transcript nói", lỗi ASR có thể lọt vào tham chiếu. 174 đoạn trích nguyên văn của 20/10 và 16/10 (89 + 85) và 182 đoạn của 13/10 được kiểm máy với văn bản segment được trích: khớp 100%.
2. **Duyệt "nguyên bản, 0 mục sửa, không nêu số phút"** là bằng chứng yếu về độ đúng của tham chiếu: không phân biệt được tin tưởng với duyệt lướt.
3. **Người chấm (t10) cũng là một agent AI**, một lượt chấm cho mỗi bản, không có người chấm thứ hai và không lặp lại để đo tính ngẫu nhiên của notes.
4. Các mục `cần xác nhận`, trạng thái `kế hoạch`/`mềm`/`có điều kiện` và độ tin cậy `L` là nơi notes trung thực có thể khác tham chiếu một cách hợp lý.
5. Annotation của 20/10 bám transcript lưu trên bản cài chính (736 segment); notes 20/10 được chấm là bản tạo trên lần chạy ASR mới (661 segment), khớp theo thời gian và nghĩa (mục 10).
6. Từ "tôi" không được dùng làm đại từ ngôi thứ nhất trong cả ba bản ghi (0, 2, 2 lần xuất hiện, đều không phải tự xưng); ngôi thứ nhất là "anh"/"em" và "I". Nửa kiểm tra "tôi" của AC-04 vì thế chỉ chạy trên các dạng này.
7. Ngôn ngữ gợi ý lưu cho cả ba là `en`, nhưng runner gọi model với `language=None, multilingual=True` nên gợi ý không điều khiển nhận dạng.

## 4. Tiêu chí 2: luồng đầy đủ trên Chrome 149 và Firefox 158

Kết quả: **đạt**. Cùng một kịch bản, cùng dữ liệu, UI tiếng Việt, viewport 1440×1000 (các viewport còn lại ở mục 5). Nửa không provider là t5, nửa notes là t8 (t9 bổ sung chức năng notes).

| Bước | Chrome 149 | Firefox 158 | Số liệu chính (Chrome / Firefox) | Nguồn |
| --- | --- | --- | --- | --- |
| Import (chọn file, tạo cuộc họp) | pass | pass | 2,47 s / 3,09 s cho clip 180,01 s; audio `HEAD` 200, `Range` 206 | t5 S02 |
| Transcript (ASR) | pass | pass | tác vụ 30,1 s / 30,5 s; 23 / 27 segment; 5 nhãn giai đoạn; phần trăm không giảm | t5 S03; t8 N01 |
| Diarization | pass | pass | 3 người nói; 6 / 13 segment gắn cờ; số lượt nói khớp API | t5 S04 |
| Notes qua ChatGPT (`gpt-5.6-sol`, medium) | pass | pass | 16,4 s / 23,4 s; 11 / 13 trích dẫn; 0 cảnh báo; transcript không đổi; danh sách bốn bước đi đúng thứ tự | t8 N02 |
| Notes qua Google Antigravity (`gemini-3.8-flash`, High), tức tạo lại bằng provider kia | pass | pass | 38,7 s / 52,7 s; bản 2 mới, bản 1 giữ nguyên từng byte, transcript không đổi | t8 N07 |
| Review: nghe lại, tua, chip nguồn | pass | pass | tua tới 96,8 s rơi vào 98,2 s / 98,3 s; chip 47 / 50 = số trích dẫn; 3 chip mỗi bên mở thẻ nguồn và phát (+1,2 s) | t5 S05; t8 N03 |
| Edit: văn bản, gán người nói, đặt tên, thêm nhãn, sửa notes (Viết) | pass | pass | sửa tồn tại sau tải lại; chỉ bullet đã sửa mất chip (47 → 43 / 50 → 48); `original_speaker_id` giữ | t5 S06; t8 N04 |
| Rerun: chạy lại bản ghi; tạo lại notes | pass | pass | chạy lại 29,9 s / 29,9 s; thế hệ 2 mặc định, thế hệ 1 giữ nguyên hash và chỉ đọc; notes cũ vẫn mở được | t5 S07; t8 N07, N16 |
| History: gần đây, tìm kiếm, lịch, chọn bản notes | pass | pass | danh sách gần đây, tìm kiếm, dấu lịch, mở từ lịch lớn; hai bản notes liệt kê provider/model/effort | t5 S08; t8 N08 |
| Copy / xuất notes | pass | pass | copy (đọc lại clipboard thật), tải tệp và `GET /api/notes/{id}/export` đều bằng Markdown đã lưu; không có link nguồn | t8 N05 |
| Copy / xuất transcript | không áp dụng | không áp dụng | Không có control; `GET /api/meetings/{id}/transcript` và `/export` trả 404. Spec 6.2 chỉ định nghĩa copy/xuất cho notes | t5 S09 |
| Cancel (chép lời; notes) | pass | pass | chép lời tới `canceled` sau 0,29 s / 0,45 s; notes ở `accepted` hủy ngay không gọi provider; ở `stopping` khóa nguồn giữ cho tới khi worker xác nhận | t5 S10; t8 N14 |
| Restart (khởi động lại và tạo lại container) | pass | pass | `compose restart` về healthy 6,6 s / 6,6 s; tạo lại 12,2 s / 12,2 s; kết nối provider giữ nguyên (phiên bản kết nối 1, 1); notes tạo lại được ngay sau đó | t5 S11; t8 N15 |
| Delete (xác nhận bằng cách gõ tên) | pass | pass | 0 hàng còn lại (notes, nguồn, tác vụ, ghi âm, thế hệ); tệp ghi âm của ứng dụng bị xóa; tệp ngoài giữ sha256 | t5 S12; t8 N17 |

Ghi chú:

- Bước "Copy / xuất transcript" không áp dụng vì sản phẩm không có control này theo đúng spec 6.2; không tính là pass.
- Không có bước nào fail ở bất kỳ trình duyệt nào. Ghi nhận sai lệch không chặn luồng: lần thử đầu của Firefox với WAV 2 giờ coi request `complete` (79 s) là lỗi phía client (#85); abort "Thinking loop" của OMP làm hai lần notes Antigravity thất bại (#76).
- Âm thanh được kiểm qua phần tử media (`currentTime` tăng, `readyState` 4, không lỗi); chưa nghe bằng tai (mục 10).

## 5. Tiêu chí 3: AC-01..AC-49 và FE-01..FE-16

Quy ước:

- **Kết luận** theo đúng worker: pass / fail / partial / not done. Hàng có hai nửa (không provider: t4, t5, t6; có provider hoặc notes: t8, t9) ghi cả hai nửa; nửa xấu nhất quyết định. Hàng đổi hoặc suy ra so với worker có lý do ở cột "Ghi chú của người tổng hợp".
- **Phạm vi:** `C` Chrome 149, `F` Firefox 158; `V1` = 1440×1000; `V3` = 1440×1000, 1280×800 và 1024×768, theme sáng và tối (kèm giảm chuyển động và 360 px ở t6/t9); `—` không dùng trình duyệt. Bằng chứng là tên tệp dưới `EV` (riêng tư) hoặc dưới `EV99` (riêng tư, lần đo lại AC-13 của #99; mục 11); `EV/t8/nf-{chrome,firefox}/` viết gọn là `nf-*`.
- `<cfg>` (ở các mục 10–11 và trong follow-up viết `<cấu hình>`): tên thư mục cấu hình đo `<chrome|firefox>-<light|dark>-<rộng>x<cao>` với rộng×cao là 1440x1000, 1280x800, 1024x768 hoặc 360x740, cộng `<chrome|firefox>-light-rm-1280x800` (giảm chuyển động).
- Phương pháp mô phỏng được dùng đúng nơi spec nói "mô phỏng" (AC-24, AC-40, AC-47): bằng chứng là test fake-provider của repo cộng quan sát sống.

### 5.1. AC-01..AC-49

| Mã | Tiêu chí | Kết luận | Phạm vi | Bằng chứng | Sai lệch / phần chưa làm | FU | Ghi chú của người tổng hợp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AC-01 | Nhận đúng nội dung ở cả ba trường hợp ngôn ngữ | **partial** (t10) | — (đối chiếu văn bản) | `EV/t10/2026-10-13-scoring.md`, `2026-10-16-scoring.md`, `2026-10-20-scoring.md` | Thiếu thể loại 1. Đủ dùng (C+P): EN 43/43; VI 14/14 (20/10) và 26/27 (13/10); 16/10 37/38. Tỷ lệ mục "rõ" (C): EN 70% (20/10) và 52% (13/10), VI 29% và 4%, 16/10 47%; 2 mục độ tin cậy L. Chấm từ văn bản, không nghe | #80 #88 | — |
| AC-02 | Notes ghi đủ ý quan trọng đã đánh dấu | **fail** (t10) | — | như AC-01 | 20/10: 34/37 tìm thấy (2 một phần, 1 thiếu); 16/10: 35/38 (2, 1); 13/10: 50/51 (0, 1). Tổng 119/126; 4 một phần; 3 thiếu. Quy tắc: thiếu bất kỳ mục nào là fail; mục độ tin cậy L và mục nhỏ tính như mục lớn | #79 | — |
| AC-03 | Không bịa quyết định, người phụ trách, deadline | **fail** (t10) | — | như AC-01 | 0 mục hoàn toàn không có văn bản nguồn; 0 deadline bịa; mọi owner có trong nguồn. Nhưng 22/77 quyết định/action bị nâng mức chắc chắn (20/10: 4/25; 16/10: 10/27; 13/10: 8/25), trong đó 5 ý mơ hồ đã chú thích (ở 2 cuộc họp) thành quyết định hoặc action đã xác nhận; spec 4 cấm | #77 #79 | — |
| AC-04 | Đúng nhãn người nói tại đoạn quan trọng | **partial** (t10) | — | như AC-01 | 42 đoạn: nhãn transcript đúng 36, trượt 6 (20/10: 1, 16/10: 1, 13/10: 4); notes sai 1 (16/10), tranh cãi 1 (13/10), phần còn lại đúng hoặc trung tính. Ngôi thứ nhất: 13 mục, owner đúng 9, không mang hoặc trung tính 3, tranh cãi 1. Từ "tôi" không dùng làm đại từ ngôi thứ nhất nên nửa kiểm tra "tôi" chạy trên "anh/em/I" | #79 #80 | — |
| AC-05 | Mốc thời gian tìm đúng bằng chứng | **partial** (t8 partial · t10 partial) | C+F, V1 | `EV/t8/nf-chrome/steps.jsonl` (N03–N05), `EV/t8/chips-real-chrome/`, `EV/t8/chips-real-firefox/`; `EV/t10/*-scoring.md` | Cơ chế đúng: nhãn chip = mốc bắt đầu của segment được trích, thẻ nguồn = snapshot đã lưu, player tua và phát (+1,2 s), 0 lỗi media; 47/50 chip trên notes mới, 484 chip trên notes thật 16/10, 398 chip trên 20/10 mới. Nội dung: 147/155 bullet (94,8%) trỏ tới đoạn mang đủ ý, 8 yếu (2 + 4 + 2). Số liệu theo báo cáo t10 §4.2; bảng chấm 20/10 (63/63) và 16/10 (46/49) phân loại khác (N29, N36; ba bullet đọc thêm gồm N15). **Chưa làm:** nghe khoảng 10 chip và xét "đoạn có hỗ trợ ý" bằng tai (cần người vận hành) | #89 #79 | Hai worker cùng partial; giữ nguyên |
| AC-06 | Deadline tương đối đúng điều kiện | **partial** (t10) | C, V1 (clip không ngày) | `EV/t10/ac06-nodate/`, `EV/t10/ac06-nodate-2/`, `*-scoring.md` | Có ngày họp: 37/39 đúng (1 sai, 1 tranh cãi). Không ngày: 2/2 clip pass, 0 ngày lịch được tạo, không dùng ngày xử lý. Chưa thử "tomorrow" ở đầu ra không ngày (câu đó không thành bullet). Chuỗi deadline ngôn ngữ nguồn nằm trong notes tiếng Anh (13/10: 4, 20/10: 1) | #77 #79 | — |
| AC-07 | Giữ chỉnh sửa và các bản notes | **pass** (t8) | C+F, V1 | `EV/t8/nf-*/` (N06–N08) | Cảnh báo notes cũ là nhãn "Nguồn đã thay đổi" trong danh sách bản và dòng meta; dòng trạng thái vẫn đọc "Notes đã được lưu…" | — | — |
| AC-08 | Lịch sử không phụ thuộc vị trí file nguồn | **pass** (t5) | C+F, V1 | `EV/t5/flow-chrome/steps.jsonl`, `EV/t5/flow-firefox/steps.jsonl` (S12, mục ac08) | File nguồn đổi tên và di chuyển sau import, chạy lại và restart; mở lại và phát từ bản sao (180,01 s, không lỗi media) | — | — |
| AC-09 | Xóa đúng phạm vi | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/flow-*/steps.jsonl` (S12, mục ac09); `EV/t8/nf-*/` (N17) | Xóa một ghi âm; meeting khác nguyên vẹn; không segment hay speaker mồ côi; `uploads/` và `.recording-tmp/` rỗng; tệp ngoài giữ sha256. Meeting có 14 và 8 bản notes: 0 hàng còn lại | — | — |
| AC-10 | ASR/diarization và duyệt dữ liệu local; notes qua provider; mạng bật chỉ có kết nối của provider | **fail** (t4 partial · t8 partial · t8 fail) | C+F, V1 | `EV/t4-security/browser/offline-offline-{chrome,firefox}.json`, `offline-notes-{chrome,firefox}.json`, `net/offline*-deltas.json`; `EV/t8/faults-offline/`, `faults-a10/summary.json`, `audit/`, `LEDGER.md`; `EV/t7/ort-telemetry-attribution.md` | **Ngoại tuyến:** ASR, diarization, xem/sửa transcript, copy/xuất/sửa notes đã lưu chạy được; 0 kết nối ra ngoài (`OutNoRoutes` 0); copy/xuất chỉ thử trên notes tổng hợp. Notes mới báo "chưa kết nối" hoặc "tạm thời không khả dụng", không phải thông báo thiếu kết nối. **Mạng bật:** (1) runner diarization gửi telemetry ONNX Runtime tới `mobile.events.data.microsoft.com` (4.698 byte trong 197 s; thấy ở cả 4 lần chạy t7 và lần xác nhận độc lập t8); (2) OMP liên hệ `catalog.stencil.so` khoảng mỗi 5 phút, một lần quét discovery tới 6 gateway LLM và dịch vụ cập nhật của Google, dò loopback 11434/8080/1234; (3) app gọi `api.openai.com` (danh mục model) mỗi lần mở trang cuộc họp dù chọn provider nào. Không có âm thanh rời container | #74 #75 #84 | Gộp ba nửa, nửa xấu nhất quyết định. Bản copy/xuất offline của t4 là bản notes tổng hợp, không phải đầu ra provider |
| AC-11 | Copy và Markdown phản ánh bản được chọn | **pass** (t8) | C+F, V1 | `EV/t8/nf-*/` (N05, N11), `chips-real-*/` | copy = tải = `GET /api/notes/{id}/export` = Markdown đã lưu, gồm chỉnh sửa; đọc lại clipboard thật ở cả hai trình duyệt; không có link mốc thời gian; copy/xuất bị tắt khi còn bản nháp chưa lưu. Notes thử nghiệm không có mục action item (0) nên action item chỉ đối chiếu trong toàn văn | — | — |
| AC-12 | Tiến độ, hủy và lỗi hiển thị đúng | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/flow-*/steps.jsonl` (S03, S10), `EV/t5/ac12-api/`, `ac12-chrome/`, `ac12-firefox/`; `EV/t8/nf-*/` (N14), `faults-cut/`, `faults-model2/`, `faults-offline/` | 7 đầu vào lỗi qua API (6 bị từ chối: 415, 422 ×4, 413; file m4a cắt cụt 60% được nhận không cảnh báo) và 5 qua hộp thoại; 2 lỗi xử lý; tác vụ lỗi, hủy hay gián đoạn không bao giờ hiện "Hoàn tất". Sai lệch về câu chữ và kiểm tra đầu vào | #82 #85 #86 | — |
| AC-13 | Bản ghi 2 giờ xử lý trong tối đa 30 phút | **fail** (t7; đo lại #99: fail; #104: đạt về thời gian theo số đo ghép) | C, V1 | `EV/t7/composite/` (`summary.json`, `events.jsonl`, `metrics.json`, `dbfacts.json`, `gpu.csv`, `conn.jsonl`, `provider-last-diagnostic.json`), `EV/t7/fresh-13-10/`, `fresh-20-10/`, `fresh-16-10/`; đo lại #99: `EV99/composite99/` (`summary.json`, `events.jsonl`, `metrics.json`, `dbfacts.json`, `gpu.csv`, `conn.jsonl`, `provider-last-diagnostic.txt`); #104: báo cáo số đo mới | #16: mẫu 2 giờ (ghép): transcript sẵn sau 128,9 phút; notes lỗi `provider_output_too_large` sau 16,0 phút; không có mốc cả hai sẵn (mục 6). #99 (main `4a88ec8`): transcript sẵn sau 10,4 phút; notes lỗi `provider_output_too_large` ở lượt 29 sau 24,4 phút; không có mốc cả hai sẵn, mốc lỗi ở 34,8 phút (mục 6.5). #104: 651,7 s + 0,2 s + 81,3 s = 733,2 s (12,2 phút), là số đo ghép; một lần chạy timed trước đó là 723,3 s (mục 6.6) | #71 #72 #73 #101 #102 #107 #108 | Giữ lịch sử fail của #16/#99; #104 đạt ngưỡng thời gian theo phép đo ghép, nhưng không phải một lần chạy liên tục |
| AC-14 | Duyệt/sửa khoảng 5–10 phút mỗi giờ họp | **partial** (người vận hành, ước lượng) | — | báo cáo của người vận hành (không có tệp EV) | 13/10: 8,0 phút/giờ (trong khoảng); 20/10: 10,8 phút/giờ (vượt nhẹ); 16/10: không đo vì không có draft notes sau 3 lần thất bại. Ước lượng "khoảng 10 phút", không phải đồng hồ bấm (mục 7) | #72 #76 #89 | Không có worker chấm; kết luận dựng từ số liệu lead cung cấp |
| AC-15 | Toàn bộ luồng chạy qua UI trên Chrome và Firefox | **partial** (suy ra từ t5 + t8) | C+F, V1 | `EV/t5/flow-chrome/`, `EV/t5/flow-firefox/`; `EV/t8/nf-chrome/`, `EV/t8/nf-firefox/` | Mở URL, nhập, xử lý, nghe lại, sửa, mở lịch sử, copy và xuất: pass ở cả hai trình duyệt. "Nghe lại" kiểm qua phần tử media (không nghe bằng tai). Trình duyệt là bản cài trên máy (Chrome: gói `google-chrome-stable`; Firefox: snap kênh `latest/stable/ubuntu-24.04`); không phải bản stable hiện hành tại ngày đo (Firefox 158.0.1, Chrome 156; mục 2.8), nên điều kiện "bản ổn định tại thời điểm kiểm thử" chưa đạt | #89 | Suy ra: không worker nào có hàng AC-15. Dựng từ bảng bước ở mục 4. partial theo review: luồng đạt trên Chrome 149 / Firefox 158.0, chưa chạy trên bản stable hiện hành |
| AC-16 | Tác vụ đã nhận tiếp tục khi trình duyệt mất kết nối | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/ac16-chrome/`, `ac16-firefox/`; `EV/t8/ac16n-chrome/`, `ac16n-firefox/` | Đóng tab, SIGKILL trình duyệt, ngắt kết nối 20–23 s: backend chạy tiếp; mở lại thấy tiến độ, chạy xong, ra kết quả (transcript và notes). Firefox, đóng tab, notes: backend vẫn chạy nhưng tác vụ lỗi vì OMP "Thinking loop" (2 lần), không do trình duyệt | #76 | — |
| AC-17 | Cài mới từ source hoặc image công khai bằng Docker Compose | **fail** (t4: source fail · pull not done) | C, V1 (mẫu xử lý qua UI Chrome; không dùng Firefox) | `EV/t4-security/steps/s1-*.out`, `steps/s1-diag-mount.out`, `steps/s1-diag-control.out`, `logs/commands.tsv`, `state-sample1.json`; `net/ac17-pull-manifest-probe.txt`, `net/ac17-pull-image-labels.txt` | **Source:** `./scripts/start.sh` thoát 1 ở `model prepare` ("Read-only file system", Compose v5.1.4). Sau khi chép model thủ công mọi bước sau pass (build, kiểm tra, khởi động, QR, xử lý mẫu 90 s: 12 segment, 3 người nói, 19,9 s); build lần này dùng cache toàn bộ. **Pull:** không kiểm được (ứng viên chưa có image; image công khai `v0.1.0-rc.1` mang revision `f0179a1`, không phải ứng viên). Chưa kết nối provider từ UI trên bản cài mới | #70 #87 #89 | — |
| AC-18 | Giữ lịch sử khi container được thay thế | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/ac18/`; `EV/t8/nf-*/` (N15) | `up --force-recreate` 12,1 s, `down` rồi `up` 12,4 s: 2 container đổi ID, 3 volume giữ, hash DB và âm thanh y nguyên; lịch sử, chỉnh sửa, tên người nói, âm thanh (150,005 s) và notes hiện đủ ở cả hai trình duyệt. Tác vụ đang chạy lúc thay chuyển `interrupted` (`worker_stopped`), không tự chạy lại | — | — |
| AC-19 | Tác vụ bị ngắt được nhận diện, chạy lại có chủ đích | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/ac19-chrome/`, `ac19-chrome-e/`, `ac19-firefox/`; `EV/t8/ac19n-chrome/`, `ac19n-firefox/` | `docker kill -s KILL` worker: `interrupted` sau 22,2 s (chép lời) và 24,5 s (notes); Docker không tự khởi động lại container bị kill, harness khởi động tay sau 20–22,5 s. `pkill -9` tiến trình: 1,5 s và 2,1 s. 30–45 s sau không có tác vụ tự chạy; kết quả hoàn tất và notes đã sửa giữ nguyên; chạy lại có chủ đích tạo tác vụ mới. UI notes vẫn nói "đang tạo notes" khoảng 19–22 s khi worker đã chết | #83 | — |
| AC-20 | Một tác vụ; không hàng đợi ẩn | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/ac20-33-chrome/`, `ac20-33-firefox/`; `EV/t8/nf-*/` (N14) | Yêu cầu thứ hai: 409 `system_busy` (meeting khác, cùng meeting, ID lặp) hoặc 503 `provider_busy`; không tạo tác vụ, 10 s sau vẫn 0; meeting đã xong vẫn xem và sửa được; retry HTTP cùng request ID trả 202 cùng tác vụ. Lý do từ chối hiện bằng tiếng Anh | #82 | — |
| AC-21 | Upload bị ngắt không tạo kết quả giả hay giữ file dở | **pass** (t5) | C+F, V1 | `EV/t5/ac21-api/`, `ac21-chrome/`, `ac21-firefox/`, `diag/ac21-firefox-first-attempt*` | Đóng socket (FIN/RST) ở 30–40%, treo 65 s, nút hủy của hộp thoại (303–457 MB), SIGKILL trình duyệt (khoảng 500 MB): phần dở bị dọn trong ≤ 0,11 s (hoặc ở giới hạn nhàn rỗi 60 s), upload `failed`, không có meeting hay tác vụ; tải lại từ đầu thành công (7366,165 s). Lần Firefox đầu coi request `complete` dài là lỗi phía client; chạy lại pass | #85 | — |
| AC-22 | Không có token hợp lệ thì không truy cập được | **pass** (t4) | C+F, V1 | `EV/t4-security/api/ac22-matrix.tsv`, `ac22-extra.tsv`, `ac22-route-table.md`, `browser/ac22-{chrome,firefox}.json` | 63 route (65 mục method), 284 request, 0 vi phạm; 76 chuỗi dò (token, ID, từ transcript, byte âm thanh) không xuất hiện trong phản hồi bị từ chối. URL xuất notes thử trên một note tổng hợp | — | — |
| AC-23 | QR và link truy cập được trên cùng máy | **pass** (t4) | C+F, V1 | `EV/t4-security/qr/decode-start.json`, `decode-offline.json`, `browser/ac23-{chrome,firefox}.json`, `logs/ac23-log-scan.json` | QR giải mã đúng bằng 2 decoder (zxing-cpp đọc cả hai chiều màu, OpenCV chỉ nền sáng); link xác thực; token bị xóa khỏi thanh địa chỉ; cookie HttpOnly, SameSite=Strict, theo phiên; 0 request mang token; 0 lần token xuất hiện trong log (log app chỉ có banner khởi động vì `--no-access-log`); link và QR tạo được khi ngắt mạng | #87 | — |
| AC-24 | Token dùng lại được; không tự hết hạn | **pass** (t4) | C+F, V1 | `EV/t4-security/browser/ac24-{chrome,firefox}.json`, `api/ac24-clock.jsonl` | 8 lần đăng nhập mỗi trình duyệt, mọi cookie cũ vẫn hợp lệ; mở lại link sau khi xóa cookie; đồng hồ mô phỏng +1 giờ tới +100 năm: token và cookie không bị vô hiệu. Đồng hồ mô phỏng chạy trên instance phụ có trạng thái auth riêng (không dịch được đồng hồ của container đang chạy) | — | — |
| AC-25 | Chỉ truy cập ứng dụng qua localhost | **pass** (người vận hành báo cáo; t4 partial) | — | `EV/t4-security/net/ac25-ports.txt`, `ac25-lan.txt`, `ac25-fw.txt` | Cấu hình publish `127.0.0.1:<cổng>` cho app, worker không publish; `ss` chỉ có một listener loopback; kết nối từ chính máy tới 7 địa chỉ không phải `127.0.0.1` đều `ECONNREFUSED`. Máy thứ hai: người vận hành báo cả 3 lần `curl` không kết nối được; không có output chi tiết. Không đọc được luật tường lửa (cần root) | — | Đổi partial (t4) thành pass: nửa còn thiếu là máy thứ hai, người vận hành đã báo kết quả. Bằng chứng nửa này yếu hơn đo trực tiếp |
| AC-26 | Token giữ nguyên trong bản cài, riêng giữa các bản cài | **pass** (t4) | — (HTTP/CLI và quét image, không dùng trình duyệt) | `EV/t4-security/api/ac26-lifecycle.json`, `ac26-cross.json`, `steps/ac26-imagescan.out` | restart, force-recreate, down rồi up: link và cookie cũ vẫn dùng được, dữ liệu y nguyên. Hai bản cài có token khác nhau; cookie và token không dùng chéo được. Token không có trong source, lịch sử git, metadata image và toàn bộ filesystem image (0 hit). Bản cài chính không được so sánh (được bảo vệ) | — | — |
| AC-27 | Thay token vô hiệu mọi quyền cũ | **pass** (t4) | C+F, V1 | `EV/t4-security/rotate/ac27.json`, `rotate/rotate-output.txt` (riêng tư), `qr/decode-rotated.json` | Hai phiên Chrome và Firefox; `scripts/rotate-token.sh` (0,2 s): token và cookie cũ bị backend từ chối (401 ở API, audio, tác vụ, PATCH); link và QR mới dùng được; dữ liệu giữ nguyên; tác vụ đang chạy (stage `loading_model`) hoàn tất. Trang đang mở vẫn hiện "Tạm mất kết nối" cho tới khi tải lại | #86 | — |
| AC-28 | Đặt tên người nói thủ công, riêng từng cuộc họp | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/flow-*/steps.jsonl` (S06, S11), `EV/t5/extra-*/steps.jsonl` (X01); `EV/t8/nf-*/` (N11, N15) | Đặt, sửa, xóa (ô trống và nút), thêm nhãn; nhãn gốc giữ; tồn tại sau restart; meeting khác không đổi. Notes cũ `stale` nhưng nguyên văn và snapshot; snapshot của notes mới mang tên (tên có trong Markdown ở Firefox, không ở Chrome: do lựa chọn của model) | — | — |
| AC-29 | Giao diện A dùng dark theme | **partial** (t6 partial · t9 partial) | C+F, V3 | `EV/t6/<cfg>/results-{empty,static,upload,running}.json`, `EV/t6/summary.json`, `matrix.md`; `EV/t9/<cfg>/results-{nstatic,nobs,nconn,nchip,nrun,nended,ndyn}.json`, `summary.json`, `matrix.md` | Theme tối đầy đủ và thao tác được ở 14 cấu hình cộng 4 cấu hình 360 px: 0 tràn ngang, 0 control bị che, mọi điểm dừng Tab có vòng focus (thấp nhất 5,61:1 ở tối), hộp thoại giữ focus. Dưới ngưỡng: số ngày ngoài tháng 1,67:1 (tối) và 1,55:1 (sáng); placeholder thêm người nói 3,87:1; metadata của mục đang chọn 3,96:1; mực mờ trên nền phụ 4,45:1 (sáng); 13 viền control 1,2–1,7:1 (quy tắc UI 3:1) | #81 | AC-29 ghi "dark theme", FE-01 ghi "light/dark"; ứng dụng có cả hai nên đã đo cả hai. Không đổi cách hiểu tiêu chí |
| AC-30 | Duyệt lịch sử bằng lịch tháng nhỏ và lớn | **pass** (t5 pass · t6 pass) | C+F, V1 (logic), V3 (hiển thị) | `EV/t5/calendar-chrome/`, `calendar-firefox/`; `EV/t6/<cfg>/results-static.json` (hàng CAL-*) | 14 meeting thử: ngày có và không có, 3 meeting cùng ngày (2 chip và "+1 khác"), tháng trống, tháng 12 sang tháng 1, năm nhuận (29/2 của 2000, 2024, 2028), năm 1000 và 1999, chưa đặt ngày, dấu ngày cập nhật sau nhập/xóa, điều hướng không đổi metadata. API từ chối 29/2 của 1900, 2027, 2100 | #85 | — |
| AC-31 | Khóa nguồn trong lúc tạo notes | **pass** (t8) | C+F, V1 | `EV/t8/nf-*/` (N12, N14), `faults-cut/`, `faults-offline/` | Đang chạy: sửa text, gán lại, đổi tên, thêm nhãn, đổi ngày đều `409 notes_source_locked`; tiêu đề vẫn sửa được; đọc nguồn, sửa notes cũ và meeting khác vẫn được. Nhả khóa sau hoàn tất, hủy, lỗi và gián đoạn. Tab đã mở trước không biết khóa cho tới khi tải lại (bị từ chối 409, bản nháp giữ) | #86 | — |
| AC-32 | Giữ transcript khi notes lỗi hoặc bị hủy | **pass** (t8; t7 quan sát) | C+F, V1 | `EV/t8/nf-*/` (N14), `faults-cut/`, `faults-model2/`; `EV/t7/composite/shots/12-notes-not-succeeded.png` | Hủy, cắt mạng giữa lượt gọi, model không dùng được, ngoại tuyến, và 3 lỗi tự nhiên `provider_output_too_large` (t7): tác vụ không bao giờ báo hoàn tất, transcript và notes cũ nguyên vẹn, sửa nguồn được sau đó, tạo notes là tác vụ riêng; chạy lại cả bản ghi bắt đầu từ đầu | — | Lỗi gây bằng cách thực: không dùng mô phỏng, theo quyết định của lead |
| AC-33 | Không xóa cuộc họp khi worker còn xử lý | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/ac20-33-*/steps.jsonl`, `ac33-delete-refused-running.png`, `ac33-delete-refused-stopping.png`; `EV/t8/nf-*/` (N14, N17) | Xóa bị `409 meeting_task_active` khi `running` và `stopping` (worker bị `docker pause`); sau khi xác nhận dừng thì xóa được; meeting khác xóa được trong lúc đó | — | — |
| AC-34 | Chạy lại giữ nguồn cũ và chỉnh sửa | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/flow-*/steps.jsonl` (S07), `EV/t5/ac19-*/steps.jsonl`; `EV/t8/nf-*/` (N16) | Thế hệ 2 lưu riêng; thế hệ 1 giữ nguyên hash và chỉ đọc; notes cũ ở trạng thái `historical`, vẫn sửa và xuất được, bằng chứng mở snapshot của thế hệ 1 | — | — |
| AC-35 | Chọn và kết nối độc lập hai provider tạo notes | **partial** (t8) | C+F, V1 | `EV/t8/nf-*/` (N02, N07), `EV/t8/step0-13-10/` | Notes qua từng provider; tạo lại bằng provider kia sinh bản mới, giữ bản cũ, transcript không đổi. **Chưa làm:** kết nối một provider qua UI mà không đăng nhập bên kia (người dùng đã đăng nhập cả hai trước khi đo); phần A của `needs-user-4` trên bản cài tạm 8771 chưa có kết quả | #89 | — |
| AC-36 | Dùng lại phiên provider và có ngắt kết nối | **partial** (t8) | C+F, V1 | `EV/t8/nf-*/` (N15) | Nhiều lần tạo notes và 2 lần tạo lại container cùng volume: không hỏi đăng nhập, phiên bản kết nối giữ (1, 1). **Chưa làm:** phiên mất hiệu lực (cần thu hồi quyền ở provider) và ngắt kết nối khi rảnh (đăng xuất tài khoản thật) | #89 | — |
| AC-37 | Có transcript trước khi provider dùng được | **partial** (t8) | C, V1 | `EV/t8/faults-offline/`, `EV/t8/faults-nologin/` | Ngoại tuyến: ASR, lưu transcript, hiện "chưa có notes", sửa được, 93 s sau khi mạng trở lại vẫn không tự sinh notes, tạo thủ công không chạy lại âm thanh. Bản cài tạm chưa kết nối gì: đúng. **Chưa làm:** hết quota (không tạo được trung thực); "kết nối sau" trên bản cài tạm (phần A) | #89 #84 | — |
| AC-38 | Không tự đổi provider hoặc bật API billing khi notes lỗi | **partial** (t8) | C, V1 | `EV/t8/faults-model2/`, `faults-cut/`, `step0-13-10/` | Lỗi gây ở provider đã chọn (model tài khoản không dùng được; cắt mạng): không có tiến trình `omp` hay host Google khi ChatGPT lỗi, không có `api.openai.com` khi Antigravity lỗi; chọn bên khác thì bản mới thành công, transcript và notes cũ nguyên. **Chưa làm:** hết quota; mã nguồn không có đường API-key nhưng billing không chứng minh được qua lưu lượng (phần D của `needs-user-4`) | #89 | — |
| AC-39 | Transcript dài xử lý đầy đủ qua chia/hợp nhất | **fail** (t10 partial · t7 quan sát) | C, V1 | `EV/t7/<run>/dbfacts.json`, `conn.jsonl`; `EV/t10/manifests.json`; `EV/t10/*-scoring.md` | **Tiêu đề không đạt:** mẫu 2 giờ và 2 trong 3 lần chạy dài khác của t7 (13/10, 16/10, qua ChatGPT) không ra notes: câu trả lời reduce cấp 2 dài 10.703–10.711 byte (cận dưới, mục 6.3) vượt trần 10.700 byte nên cả tác vụ lỗi. **Ngân sách mỗi bước:** bị vượt ở 3/4 lần chạy dài (kể cả mẫu 2 giờ). **Chất lượng như AC-02/03/05:** AC-02 và AC-03 fail, AC-05 partial. Cơ chế đúng trên 3 bản notes thành công: span sở hữu liên tục và đủ, chunk sau lặp đuôi chunk trước, mỗi chunk đóng góp trích dẫn, 0 trích dẫn không giải được. Chất lượng sau hợp nhất: quyết định đổi ở cuối 10 ok / 4 một phần / 1 fail trên 15; action item qua ranh giới 3/7 được nối; hiện vật ranh giới còn trong notes | #72 #76 #78 | Đổi partial (t10) thành fail theo quyết định của lead: tiêu đề yêu cầu xử lý đầy đủ qua chia/hợp nhất; phép kiểm yêu cầu không bước nào vượt ngân sách và chất lượng như AC-02/03/05. Mẫu 2 giờ và 2 trong 3 lần chạy dài khác không có notes (đầu ra reduce cấp 2 vượt trần 10.700 byte, t7); AC-02 và AC-03 fail |
| AC-40 | Tối đa một lượt sửa đầu ra không hợp lệ cho cả tác vụ notes | **pass** (t8; mô phỏng + quan sát) | — | `EV/t8/sim/ac40-ac47-sim-tests.log`, nhật ký suite đầy đủ của t2 | 25 test fake-provider pass. Không có đầu ra sai schema hoặc ID trong lượt gọi thật nào (mọi lần thử là `primary`, 0 lượt sửa), nên chưa thấy lượt sửa thật. Đầu ra quá lớn không phải trường hợp sửa mà là lỗi cuối (#72) | #72 | Phương pháp theo spec và quyết định của capsule: mô phỏng |
| AC-41 | Notes cũ giữ đúng nguồn trước chỉnh sửa | **pass** (t8) | C+F, V1 | `EV/t8/nf-*/` (N06, N08, N11, N13, N16), `chips-real-*/` | Sau sửa text, tên, ngày, gán lại và chạy lại: bằng chứng notes cũ mở văn bản, tên, ngày gốc, khác nguồn hiện tại; sửa notes cũ không đổi hash snapshot; notes mới gắn nguồn mới. Bản sao thật của 16/10: 2/4 chip kèm chú thích "người nói đã đổi" | — | — |
| AC-42 | Tab cũ không ghi đè chỉnh sửa mới | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/stale-chrome/`, `stale-firefox/`; `EV/t8/nf-*/` (N10) | Lưu từ tab B cũ bị từ chối 409 (văn bản, đổi tên, gán lại, notes), bản nháp của B giữ; "Giữ bản nháp" lưu lên bản mới nhất theo lựa chọn; tạo notes mới trong lúc sửa bản cũ không đổi đích ghi. Tab thứ hai không biết revision hay khóa mới tới khi tải lại | #86 | — |
| AC-43 | Mặc định đúng thế hệ transcript; không tự ghép tên | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/flow-*/steps.jsonl` (S07), `EV/t5/ac19-*/steps.jsonl`; `EV/t8/nf-*/` (N16) | Thế hệ mới là mặc định, thế hệ cũ chỉ đọc (0 nút sửa); tên không sang thế hệ mới (nhãn `Speaker N`); lỗi trước khi lưu giữ mặc định cũ; lỗi ở notes giữ transcript mới đã hoàn tất | — | — |
| AC-44 | Không ngắt hoặc đổi tài khoản provider của tác vụ đang hoạt động | **partial** (t8) | C+F, V1 | `EV/t8/nf-*/` (`n14-out.json`) | Ở `accepted`, `running`, `stopping`: ngắt kết nối (API), bắt đầu đăng nhập và danh mục model của provider đang dùng bị từ chối (409 `provider_in_use` hoặc 503 `provider_busy`); danh mục provider kia trả 200; sau khi dừng xác nhận, guard được gỡ. UI: nút "Ngắt kết nối" vẫn bật cho provider đang dùng (bấm thì 409 và thông báo chung). **Chưa làm:** ngắt thật sau khi dừng và ngắt provider không thuộc tác vụ (sẽ đăng xuất tài khoản thật; phần B của `needs-user-4`) | #84 #89 | — |
| AC-45 | Sửa tên/ngày họp giữ đúng nguồn và lịch sử | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/calendar-*/steps.jsonl` (C11); `EV/t8/nf-*/` (N12, N13) | Đổi tên: `metadata_version` tăng, nguồn notes không đổi; đổi hoặc xóa ngày: cả hai tăng, notes `stale`, snapshot nguyên; sửa trong lúc tạo notes bị từ chối; version cũ bị 409 `stale_version`; chạy lại với ngôn ngữ khác không đổi thế hệ cũ | — | — |
| AC-46 | Sửa người nói từng đoạn và thêm nhãn đúng phạm vi | **pass** (t5 pass · t8 pass) | C+F, V1 | `EV/t5/flow-*/steps.jsonl` (S06), `EV/t5/stale-*/steps.jsonl` (R01); `EV/t8/nf-*/` (N12, N13) | Gán lại một segment, thêm nhãn rồi gán: `original_speaker_id` giữ, đoạn khác và timestamp không đổi, notes cần cập nhật, notes mới dùng nguồn đã sửa. Sai thế hệ, thế hệ cũ, tab cũ, nhãn lạ, lúc khóa nguồn đều bị từ chối (409, 404, 400) | — | — |
| AC-47 | Lỗi mạng không tự gửi lại inference | **pass** (t8; mô phỏng + sống) | C, V1 (+ mô phỏng) | `EV/t8/sim/`, `faults-cut/`, `faults-apiid/`, `step0-16-10-*/` | 25 test mô phỏng pass. Sống: cắt mạng giữa lượt gọi (299 s): không DNS, SYN hay ClientHello, không tiến trình `omp` mới; abort "Thinking loop" của OMP không sinh lượt gọi thứ hai (auto-retry của OMP bị tắt); replay cùng request ID: 202 cùng tác vụ, body khác 409 `idempotency_conflict`, 0 kết nối mới. 61 lượt gọi ChatGPT ở t7: một kết nối mỗi lượt, không gửi lại. Lỗi mạng chỉ được báo sau trần đọc 300 s | #83 | — |
| AC-48 | Lưu Markdown chỉnh tay có link hỏng mà không mở sai nguồn | **pass** (t8) | C+F, V1 | `EV/t8/nf-*/` (N09) | 4 link gõ tay (hợp lệ, segment không tồn tại, snapshot lạ, meeting khác): lưu đúng như gõ, 3 cảnh báo, link hỏng hiện như chữ và không mở gì; link hợp lệ mở đúng nguồn; copy và xuất đúng nội dung | — | — |
| AC-49 | Chọn và nhớ model; giữ lựa chọn suốt tác vụ | **pass** (t8) | C, V1 | `EV/t8/faults-prefs/`, `faults-model2/` | Hai model ở hai provider được nhớ trong context trình duyệt mới. Đổi lựa chọn giữa tác vụ: tác vụ và bản notes giữ `gpt-5.6-sol`, lần sau dùng `gpt-5.6-luna`. Model tài khoản không dùng được báo lỗi, không tự đổi. Trường hợp mất quyền phải gây qua API vì UI không cho chọn model ngoài danh mục (cả 7 model ChatGPT đều dùng được) | #84 | — |

### 5.2. FE-01..FE-16

| Mã | Điều kiện | Kết luận | Phạm vi | Bằng chứng | Sai lệch / phần chưa làm | FU | Ghi chú của người tổng hợp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FE-01 | Bố cục A, hệ editorial-engineering sáng/tối | **pass** (t6) | C+F, V3 | `EV/t6/<cfg>/results-static.json` (hàng FE01-structure, FE01-tokens, FE01-fonts) | Cấu trúc theo DESIGN.md; 12 token màu mỗi theme khớp tài liệu; font Inter, Newsreader, JetBrains Mono tải từ gói. Sidebar rộng 236 px, tài liệu ghi 228 px làm giá trị tham chiếu (t6 chấp nhận ±10 px; `EV/t6/summary.json` còn 28 hàng `SBW` ghi fail theo quy tắc ±2 px ban đầu). Đối chiếu AC-29 (partial) | #81 #86 | Giữ pass theo t6; độ lệch +8 px ghi ở #86 |
| FE-02 | Brand ASR EN VI; footer chỉ có icon GitHub và dòng Version | **partial** (t6 pass · chữ hiển thị lệch tài liệu) | C+F, V3 | `EV/t6/<cfg>/results-static.json` (hàng FOOTER, BRAND, FOOTER-visible), `EV/t6/expected-version.json` | Footer có đúng hai liên kết; `Version 0.1.0-rc.1` khớp `cli version` và nhãn revision image khớp HEAD. **Lệch:** `frontend-design-v1.md` ghi brand là "ASR EN VI", chữ hiển thị của wordmark là `ASR / EN VI` (có dấu gạch chéo), còn tiêu đề trang và tên truy cập là `ASR EN VI`. Dòng Version 4,45:1 ở theme sáng và nằm dưới màn hình ở 1024×768 | #81 #86 | Đổi pass (t6) thành partial theo quyết định của lead, đọc literal tài liệu: t6 để việc đánh giá dấu "/" trong wordmark cho lead |
| FE-03 | Danh sách gần đây gọn, tìm kiếm toàn lịch sử, lịch nhỏ, lịch lớn | **pass** (t6) | C+F, V3 | hàng FE03-recent, FE03-search, CAL-sync | 3 mục gần đây; tìm 5 meeting theo từ có trong 5 tiêu đề (nhiều hơn 3 mục gần đây); lịch nhỏ nằm ngay dưới danh sách (cách 26 px); lịch lớn mở bằng Enter và bằng chuột | — | — |
| FE-04 | Lịch nhỏ/lớn đồng bộ; các trường hợp biên | **pass** (t5 · t6) | C+F, V1 (logic), V3 (hiển thị) | `EV/t5/calendar-*/`; hàng CAL-sync, CAL-tour | So sánh từng trường (tháng, năm, ngày chọn, số chưa đặt ngày, mọi dấu ngày); đi qua 12/2025 sang 1/2026, 29/2/2024, tháng trống, nhóm chưa đặt ngày | #86 | Chỉ hiển thị ở t6; logic ở t5 |
| FE-05 | Mở đúng cuộc họp từ lịch; dấu ngày cập nhật | **pass** (t5 · t6) | C+F, V1, V3 | `EV/t5/calendar-*/` (C06–C10); hàng CAL-day-panel, FE05-open | Ngày một cuộc họp mở đúng cuộc họp; ngày ba cuộc họp có 2 chip và "+1 khác", bảng ngày liệt kê đủ ba; dấu ngày và bộ đếm chưa đặt ngày cập nhật sau nhập/xóa; điều hướng không đổi tiêu đề, ngày, version hay tên người nói | — | — |
| FE-06 | Đặt/sửa/xóa tên người nói riêng từng cuộc họp; không ghi đè notes cũ | **pass** (t5 · t9) | C+F, V1 | `EV/t9/func-chrome/results-func.json`, `func-firefox/results-func.json` (stage speaker, notes1, rename2, notes2, meta); `EV/t5/flow-*/steps.jsonl` (S06) | Form hiện nhãn gốc `SPEAKER_nn`; xóa thì về "Speaker N"; meeting khác không đổi; notes cũ giữ nguyên văn, bị đánh dấu đã đổi và có nhắc cập nhật; notes mới có cả hai tên, bản cũ thì không | — | — |
| FE-07 | Timestamp dẫn tới nguồn; sửa làm notes cần cập nhật; tạo lại ra bản mới; copy/xuất đúng bản | **pass** (t9) | C+F, V1 (chip: V3) | `EV/t9/func-*/results-func.json` (stage chips, toolbar, stale, notes2), `EV/t9/<cfg>/results-nchip.json` | Chip bằng bàn phím: chuyển tab Transcript (thêm mục lịch sử), thẻ nguồn dưới player, hàng được đánh dấu và nằm dưới thanh; "Tua bản ghi tới mốc này"; Back về notes. Sửa segment hoặc ngày đánh dấu "Nguồn đã thay đổi" mà không đổi văn bản notes. Tạo lại thêm `Bản n`; copy và tải bằng Markdown đã lưu, không link | — | Đối chiếu AC-05 (partial: chưa nghe) |
| FE-08 | Upload, tiến độ, bận, hủy, lỗi, gián đoạn hiển thị đúng | **pass** (t6 partial · t9 pass) | C+F, V3 | `EV/t6/<cfg>/results-{upload,running,static}.json`; `EV/t9/<cfg>/results-{nrun,nobs,nended}.json`, `EV/t9/chrome-light-1440x1000-intr/results-intr.json` | 14 cấu hình mỗi nửa. Upload (17–28%), hủy từ bàn phím, từ chối; thanh `<progress>`; hủy `Đang dừng…` rồi `Đã hủy`; đóng và mở lại tab vẫn thấy tác vụ chạy. Notes: bốn bước, `Hủy tạo notes`, bận, lỗi, gián đoạn, hủy. Lệch: lý do bận và lỗi bằng tiếng Anh; alert từ chối của hộp thoại tạo nằm dưới màn hình hộp thoại; từ chối bận ở notes mất khoảng 5 s; thanh tiến độ không xác định không tạo được từ UI | #82 #83 #86 | t6 ghi partial vì nửa notes chưa làm và nêu lệch F8, F9; t9 đã làm nửa notes, ghi pass kèm lệch tương tự (F15, F18). Lệch giữ ở cột Sai lệch (#82 #83 #86), cùng cách xử lý như AC-12, AC-20, FE-15 |
| FE-09 | Bàn phím, ba viewport, không che hay tràn ngang, player dính | **pass** (t6 · t9) | C+F, V3 (kèm giảm chuyển động, 360 px) | hàng OVF, COV, CLP, STK-*, FOC, KBD-*, TAB-roving (t6); `EV/t9/<cfg>/` | 0 tràn ngang (376 + 459 trạng thái); 13.538 + 23.351 control không bị che; 9.535 + 26.423 điểm dừng Tab đều có vòng focus; player 64 px, dính, đục; hàng đang phát cách thanh ≥ 11,9 px. Vòng focus ở mép thanh mất tới 5,45 px phía trên | #86 | — |
| FE-10 | Không UI demo; backend và lưu trữ thật; kiểm soát token; tài nguyên UI đóng gói; kết nối provider theo lựa chọn | **partial** (t4 pass: UI demo/token/tài nguyên · mệnh đề chọn provider: FE-11 partial, AC-10 fail) | C+F, V3 | `EV/t4-security/browser/fe10-*.json`, `api/fe10-static.json`, `browser/fe10-demo-scan-*.json` | 6 phiên UI đầy đủ: mọi request tới origin của app, 0 vi phạm CSP, font từ `/assets/fonts/*`; 25 asset phục vụ giống tệp nguồn; không chuỗi demo; token không nằm trong storage hay DOM. Khối comment thiết kế còn trong HTML. **Chưa đánh giá ở t4:** mệnh đề kết nối provider theo lựa chọn (t4 coi là việc của worker provider); xem FE-11, AC-35 và AC-10 mục (3) | #74 #75 #87 #89 | Đổi pass (t4) thành partial: mệnh đề chọn provider chưa được t4 đánh giá; FE-11 partial, AC-10 fail (egress ngoài UI, không phải tài nguyên UI: #74, #75). Quy tắc mục 10.1: pass chỉ khi mọi phần của phương pháp đã được đo |
| FE-11 | Chọn và kết nối riêng ChatGPT hoặc Antigravity từ UI, không buộc cả hai | **partial** (t9) | C+F, V3 | `EV/t9/<cfg>/results-nconn.json` | Hai launcher mở cùng hộp thoại ở đúng phần; mỗi provider có trạng thái, tài khoản, model/effort, xác minh và ngắt riêng; lời giới thiệu nói tài khoản tách khỏi truy cập workspace. **Chưa làm:** kết nối từ đầu, chỉ một provider (cả hai đã kết nối) | #89 | — |
| FE-12 | Dùng lại phiên; "có transcript, chưa có notes"; lỗi/quota; đổi bên là chủ động | **partial** (t9) | C+F, V1 | `EV/t9/old-nrun/*.json`, `EV/t9/func-*/`, `EV/t9/<cfg>/results-nchip.json` | Phiên dùng lại ở hàng trăm context; "Notes · Chưa có" kèm nút `Tạo notes · English · ChatGPT GPT-5.6-Sol`; sau lỗi, nút bắt đầu còn và không tự chạy lại (20 s); panel `Đổi…` mặc định đóng, không ghi API. **Chưa làm:** trạng thái hết quota; đổi provider trong `Đổi…` rồi chạy lại | #89 #84 | — |
| FE-13 | Notes cũ mở đúng snapshot; xung đột giữ bản nháp | **pass** (t9) | C+F, V3 | `EV/t9/<cfg>/results-{ndyn,nstatic}.json`, `EV/t9/func-*/` (stage stale, unload) | Thẻ nguồn nói transcript đã khác khi có sửa (14/14), không có ghi chú khi nguồn không đổi (14/14). Xung đột: khối cảnh báo với 2 hành động ở cả Write và View, bản nháp giữ; `beforeunload` cảnh báo khi có bản nháp | — | — |
| FE-14 | Chọn thế hệ transcript; cũ chỉ đọc; không ghép tên; chặn ngắt/đổi provider đang dùng | **partial** (t9) | C+F, V1 (thế hệ), V3 (hộp thoại) | `EV/t9/func-*/` (stage generation), `EV/t9/<cfg>/results-nobs.json`, `EV/t9/{chrome,firefox}-light-1440x1000-inuse/results-inuse.json` | Nửa thế hệ pass: selector 2 mục, bản cũ 0 nút sửa, 2 tên đã đặt không sang bản mới, gợi ý `en` giữ. Nửa provider: server chặn (409 `provider_in_use`) nhưng UI không tắt "Ngắt kết nối" cho provider đang dùng và diễn đạt lệch giữa hai provider (Antigravity: "Không khả dụng" kèm thông báo chung; ChatGPT: lý do rõ). **Chưa làm:** bấm ngắt hoặc đổi trong lúc chạy (thuộc AC-44) | #84 #89 | — |
| FE-15 | Sửa tên/ngày và gán người nói theo version/khóa nguồn | **pass** (t9) | C+F, V1 | `EV/t9/func-*/` (stage lock, meta), `EV/t9/<cfg>/results-nobs.json` | Khi chạy: mọi nút `Sửa` (23 và 38) và 3 chip người nói bị tắt kèm lý do; trường ngày và `Xóa ngày` bị tắt nhưng không có lý do. Sau đó: đổi tiêu đề giữ `current`; đổi ngày đánh dấu `stale` và snapshot nguyên; gán lại giữ `original_speaker_id` | #86 | — |
| FE-16 | Lỗi mạng không tự retry; link hỏng lưu kèm cảnh báo; chọn/nhớ model | **partial** (t9) | C+F, V1 (+ tối) | `EV/t9/func-*/` (stage neterr, brokenlink), `EV/t9/<cfg>/results-ndyn.json` | Cắt mạng trước khi bắt đầu (4 lượt): `failed provider_unavailable` sau 3–5 s, một tác vụ (20 s không gửi lại), bản cũ giữ. Link hỏng lưu kèm cảnh báo (291 ký tự), không có anchor, không mở nguồn nào. **Chưa làm:** chọn model và kiểm tra ghi nhớ; cắt mạng sau khi đã gửi (AC-47 do t8 đo) | #89 | — |

### 5.3. Ngoài phạm vi #16: FE-17 và FE-18

| Mã | Điều kiện | Kết luận | Phạm vi | Bằng chứng | Ghi chú |
| --- | --- | --- | --- | --- | --- |
| FE-17 | Trang cuộc họp hai tab theo WAI-ARIA | **pass** (t6 pass · t9 pass) | C+F, V3 và 360 px | `EV/t6/<cfg>/results-static.json` (hàng FE17-*, TAB-roving), `EV/t6/<browser>-<theme>-360x740/results-narrow.json`; `EV/t9/<cfg>/results-{nstatic,nrun,nobs}.json` | Mũi tên, Home, End; chỉ tab đang chọn trong thứ tự Tab; `#notes`/`#transcript` với `pushState`, Back, Forward, tải lại; tab mặc định theo trạng thái; "Cần transcript trước"; không tràn ngang ở 360 px; sáng/tối; giảm chuyển động. Ở 360 px thứ tự vẽ của header khác thứ tự Tab (#86) |
| FE-18 | Chip trích dẫn mốc thời gian của notes | **pass** (t9) | C+F, V3 và 360 px | `EV/t9/<cfg>/results-{nstatic,nchip}.json`, `EV/t9/{chrome,firefox}-{light,dark}-360x740/results-nnarrow.json` | 484 và 398 chip, đều dạng `mm:ss`, đều có tên truy cập, 0 chip ngoài khung; chỉ ở chế độ Xem (Viết: 0 link, 42 lần kiểm); thẻ nguồn dưới player; Back về notes; cuộn 27–43 vị trí khi có chuyển động và 2–3 khi giảm chuyển động |

## 6. Tiêu chí 5: AC-13, mẫu 2 giờ

Kết quả: **fail**. Cách đo: Chrome 149 thật, import qua hộp thoại, giá trị mặc định của sản phẩm (tự chép lời sau khi tạo bật), lựa chọn ChatGPT đã lưu (`gpt-5.6-sol`, medium, đầu ra English), một lần đo mỗi mẫu, GPU không có tác vụ eval khác (khóa `gpu.lock`), mạng có dây. Mốc bắt đầu là request `POST /api/tasks` mà trang cuộc họp tự gửi sau import; upload (0,2 s) và kiểm tra phía server (81 s) nằm ngoài AC-13 và chỉ cộng thêm 1,4 phút. Không thử lại vì lỗi là giới hạn của sản phẩm, không phải sự cố môi trường (không có lỗi mạng, quota, máy chủ hay GPU). Mục 6.1–6.4 là số đo của #16 (revision `151f3e4`); mục 6.5 đo lại sau #71, #72, #74 (#99, revision `4a88ec8`), kết quả vẫn **fail**.

### 6.1. Số liệu

| | Mẫu 2 giờ (ghép) | 13/10 | 20/10 | 16/10 |
| --- | --- | --- | --- | --- |
| Thời lượng audio | 7366,14 s (122,8 phút) | 4498,11 s (75,0) | 3340,33 s (55,7) | 4025,79 s (67,1) |
| Upload / kiểm tra phía server (ngoài AC-13) | 0,19 s / 81,2 s | 2,93 s / 46,9 s | 3,67 s / 38,1 s | 3,90 s / 43,8 s |
| ASR (giai đoạn `transcribing`) | 510,0 s, 14,4× thời gian thực | 340,2 s, 13,2× | 266,7 s, 12,5× | 287,1 s, 14,0× |
| Diarization (nạp model + chạy) | 7.222,6 s | 2.715,0 s | 1.508,5 s | 2.206,6 s |
| Diarization ÷ thời lượng² (×10⁻⁴) | 1,331 | 1,342 | 1,352 | 1,362 |
| Segment / nhãn người nói / gắn cờ | 1838 / 12 / 817 | 827 / 7 / 377 | 661 / 10 / 284 | 1269 / 7 / 521 |
| **Transcript sẵn** (từ lúc bắt đầu xử lý) | **128,9 phút** (7.734 s) | 51,0 phút | 29,7 phút | 41,6 phút |
| Từ transcript sẵn tới lúc bấm "Tạo notes" | 0,87 s | 0,19 s | 0,40 s | 1,14 s |
| Notes: chunk / byte nguồn / lượt gọi | 16 / 340.521 / 25 | 8 / 161.031 / 13 | 6 / 125.915 / 7 | 10 / 223.414 / 16 |
| Kết quả notes | **lỗi** `provider_output_too_large` ở lượt 25, sau 958,6 s (16,0 phút) | **lỗi** như trên ở lượt 13, sau 571,3 s | thành công sau 320,8 s | **lỗi** như trên ở lượt 16, sau 638,8 s |
| **AC-13: bắt đầu → transcript và notes sẵn** | không có mốc (tác vụ notes kết thúc lỗi sau 144,9 phút) | không có mốc (60,5 phút) | **35,0 phút** (29,7 + 0,4 s + 5,3) | không có mốc (52,3 phút) |

### 6.2. So với mục tiêu

| | Mục tiêu | Đo được |
| --- | --- | --- |
| Bắt đầu xử lý → transcript sẵn, mẫu 7366 s | trong 30 phút | **128,9 phút**, gấp 4,3 lần cả ngân sách |
| Bắt đầu xử lý → transcript và notes sẵn | 30 phút | **không đạt mốc**: tác vụ notes lỗi sau 16,0 phút (144,9 phút kể từ lúc bắt đầu) |
| Cận dưới nếu notes mất 0 giây | 30 phút | 128,9 phút |
| Mẫu duy nhất ra notes (20/10, 55,7 phút audio) | 30 phút | 35,0 phút, vẫn vượt cho bản ghi chưa bằng một nửa độ dài mục tiêu |

### 6.3. Nguyên nhân

- **Diarization quyết định kết quả và tăng theo bình phương thời lượng:** thời gian = (1,331–1,362)×10⁻⁴ × thời lượng² (lệch ±1,2% trên bốn lần chạy). Dự đoán cho 7200 s: khoảng 116 phút; riêng diarization chạm 30 phút ở khoảng 61 phút audio. Chiếm 85–93% thời gian tác vụ; chạy trên một lõi CPU (container 110–125%), GPU trung bình 2–3% với 4,2 GiB chiếm giữ. Các lần chạy trước đó trên bản cài chính khớp (20/10: 1774 s, 16/10: 2583 s; lần chạy mới 1779 s và 2496 s). ASR tuyến tính và nhanh (0,07–0,08 s mỗi giây audio) (#71).
- **Notes lỗi vì vượt trần vài byte:** ở bước reduce cấp 2 đầu tiên, câu trả lời của ChatGPT dài 10.706, 10.711 và 10.703 byte so với trần 10.700 (vượt 6, 11, 3 byte; HTTP 200, lần thử `primary`); toàn bộ 9,5–16 phút lượt gọi trước đó bị mất, không có lượt sửa hay checkpoint. Cả ba nguồn cần reduce cấp 2 đều lỗi; nguồn không cần (20/10) thành công (#72).
- **Cỡ vượt trần là cận dưới (ghi chú thêm sau #99):** client ChatGPT ngừng đọc stream ngay khi tổng văn bản vượt trần (`src/asr_en_vi/chatgpt.py`, cùng logic ở `151f3e4`) và ghi số byte tại điểm đó. Vì vậy 10.706, 10.711 và 10.703 byte (vượt 6, 11, 3 byte) ở trên là cận dưới của độ dài thật, không phải độ dài đầy đủ của câu trả lời. Số liệu #16 giữ nguyên (mục 6.5, #102).
- **Notes không tự chạy:** AC-13 viết một khoảng "từ bắt đầu xử lý đến khi cả transcript và notes sẵn" nhưng notes chờ một cú bấm; harness bấm sau 0,2–1,1 s, người thật có thể lâu hơn bất kỳ (#73).

### 6.4. Giới hạn của phép đo

1. Mẫu 2 giờ là ghép hai bản ghi, không phải một cuộc họp; phép khớp bậc hai phủ cả bản ghi đơn 56, 67 và 75 phút nên một cuộc họp 2 giờ liền được kỳ vọng ở quanh 116 phút.
2. Thời gian notes cho nguồn 2 giờ không đo được vì tác vụ lỗi (đã dùng 16,0 phút cho 25 lượt và còn cần thêm lượt hợp nhất và lượt cuối). Thời gian gọi provider chỉ biết từ các lượt đã xong: lượt chunk 24,3–60,9 s (trung vị 36,5 s), 17 lượt hợp nhất cấp 1 31,3–52,1 s (trung vị 41,7 s), lượt cuối 95,6 s, ba lượt cấp 2 bị lỗi 65,2 / 68,5 / 62,4 s.
3. Một lần đo, một provider và model; độ trễ phụ thuộc giờ trong ngày; không gặp quota hay rate-limit.
4. Tải máy: swap đầy nhưng nhàn rỗi; load1 trung bình 1,5–1,6 (đỉnh 4,7–7,6); RAM khả dụng thấp nhất 14,9 GiB. GPU đỉnh khi ASR 6.685 MiB tổng (5.554 MiB runner), khi diarization 5.592 MiB; GPU trung bình khi ASR 83,9%; công suất tối đa 182 W; nhiệt tối đa 60 °C.

Evidence: `EV/t7/composite/` (`summary.json`, `events.jsonl`, `metrics.json`, `dbfacts.json`, `gpu.csv`, `gpu-apps.csv`, `host.csv`, `worker-stats.csv`, `conn.jsonl`, `provider-last-diagnostic.json`), `EV/t7/fresh-13-10/`, `fresh-20-10/`, `fresh-16-10/`.

### 6.5. Đo lại sau #71, #72, #74 (#99)

Kết quả: **fail**. Transcript sẵn sau 10,4 phút (#16: 128,9 phút) nhưng notes vẫn lỗi `provider_output_too_large` sau 24,4 phút, nên không có mốc cả hai sẵn; ngay cả mốc tác vụ notes kết thúc lỗi (34,8 phút) đã vượt 30 phút. Bước chậm nhất chuyển từ diarization sang notes (70,0% thời gian).

- **Revision, image:** main `4a88ec8` (`4a88ec8be964aa5b818d854ef207eb0a2905718f`; có #71 (PR #98), #72 (PR #94), #74 (PR #91)), image `asr-issue99:4a88ec8` (`sha256:651944db0134…`, nhãn `org.opencontainers.image.revision` khớp), schema 12. Chạy trên bản cài eval `asr-issue16-eval` với các volume sẵn có.
- **Ngày đo:** 2026-10-25, 16:22–16:59 (giờ +07).
- **Cách đo:** như mục 6. Chrome 149.0.7827.53 headless, import mẫu ghép `composite-2h.m4a` (7366,14 s, cùng tệp như mục 2.7) qua hộp thoại, gợi ý ngôn ngữ `en`, tự chép lời sau khi tạo bật, mạng có dây, một lần đo, giữ khóa `gpu.lock` suốt lần chạy. Mốc bắt đầu là request `POST /api/tasks` mà trang cuộc họp tự gửi; import (bấm tạo → trang cuộc họp) tính riêng, ngoài AC-13. Notes qua ChatGPT `gpt-5.6-sol`, medium, đầu ra English; harness bấm "Tạo notes" ngay khi nút bật và ghi khoảng chờ riêng. Không thử lại vì lỗi là giới hạn của sản phẩm, không phải sự cố môi trường (không có lỗi mạng, quota, máy chủ hay GPU).

| | #99: main `4a88ec8` | Tỷ trọng trong 2.090,2 s | #16: `151f3e4` (cột mẫu 2 giờ, mục 6.1) |
| --- | --- | --- | --- |
| Upload / kiểm tra phía server (ngoài AC-13) | 0,24 s / 81,0 s (bấm tạo → trang cuộc họp: 81,4 s) | | 0,19 s / 81,2 s |
| Nạp model ASR (`loading_model`) | 2,86 s | 0,1% | không ghi riêng |
| ASR (`transcribing`) | 525,55 s, 14,0× thời gian thực | 25,1% | 510,0 s, 14,4× |
| Diarization: nạp model (`loading_diarization_model`) | 4,26 s | 0,2% | không ghi riêng |
| Diarization: giải mã đầu vào (`decoding_input`) | 2,85 s | 0,1% | không ghi riêng |
| Diarization: chạy (`diarizing`) | 89,62 s | 4,3% | không ghi riêng |
| **Diarization, tổng ba stage** | **96,73 s** (1,6 phút) | 4,6% | 7.222,6 s (nạp model + chạy) |
| Segment / nhãn người nói / gắn cờ | 1706 / 13 / 733 | | 1838 / 12 / 817 |
| **Transcript sẵn** (từ lúc bắt đầu xử lý) | **10,4 phút** (626,53 s theo UI; tác vụ chép lời xong ở 625,99 s) | | **128,9 phút** (7.734 s) |
| Từ transcript sẵn tới lúc bấm "Tạo notes" (ghi riêng) | 0,75 s (tác vụ chép lời xong → `POST` notes); 0,17 s (UI báo transcript sẵn → bấm) | | 0,87 s (tác vụ chép lời xong → `POST` notes) |
| Notes: chunk / byte nguồn / lượt gọi | 14 / 307.154 / 29 | | 16 / 340.521 / 25 |
| Kết quả notes | **lỗi** `provider_output_too_large` ở lượt 29, sau 1.463,47 s (24,4 phút) | 70,0% | **lỗi** như trên ở lượt 25, sau 958,6 s (16,0 phút) |
| **AC-13: bắt đầu → transcript và notes sẵn** | **không có mốc** (không lưu bản notes nào); tác vụ notes kết thúc lỗi ở 2.090,2 s (**34,8 phút**) | | không có mốc (tác vụ notes kết thúc lỗi sau 144,9 phút) |
| Từ lúc bấm tạo (cộng import) tới khi tác vụ notes kết thúc lỗi | 2.171,6 s (36,2 phút) | | |

Tỷ trọng tính trên cửa sổ AC-13 (`POST /api/tasks` → tác vụ notes kết thúc, 2.090,2 s); 0,1% còn lại là hai khoảng chờ (0,85 s trước khi nạp model ASR, 0,75 s trước `POST` notes). ASR lần này cho 1706 segment (#16: 1838), nên nguồn notes nhỏ hơn và ít chunk hơn.

**Lượt gọi notes:**

- 14 chunk, 29 lượt gọi ChatGPT nối tiếp: 29 kết nối ra ngoài, đều nằm trong cửa sổ notes, tối đa 1 kết nối cùng lúc (`conn.jsonl`, `metrics.json`).
- 14 lượt đầu (bằng số chunk) mất 615 s, trung vị 41,3 s mỗi lượt; 15 lượt sau mất 847 s, trung vị 61,7 s mỗi lượt. Chỉ stage của lượt cuối được ghi (`reduce`, `recovery`); stage của các lượt trước không ghi.
- Chẩn đoán lượt cuối (`provider-last-diagnostic.txt`): `stage` `reduce`, `attempt` `recovery`, lượt 29, `prompt_bytes` 25.432, `output_bytes` 10.701, `response_limit` 10.700, HTTP 200. `output_bytes` là cận dưới (mục 6.3).

**Nguyên nhân:**

- **Notes là bước chậm nhất:** 1.463,5 s, 70,0% cửa sổ AC-13 (ASR 25,1%, diarization 4,6%). Sau transcript chỉ còn 30 − 10,4 = 19,6 phút trong ngân sách; notes đã dùng 24,4 phút mà chưa tới lượt cuối. 29 lượt chạy nối tiếp (độ song song 1) và lượt reduce chậm hơn lượt chunk (#101).
- **Diarization không còn là điểm nghẽn (#71):** 96,73 s so với 7.222,6 s ở #16 (nhanh gấp khoảng 75 lần); transcript sẵn nhanh gấp khoảng 12 lần. ASR gần như không đổi (525,55 s so với 510,0 s).
- **Notes vẫn lỗi sau khi có lượt phục hồi (#72):** lượt 29 là lượt phục hồi của bước reduce và câu trả lời vẫn vượt trần 10.700 byte; không còn lượt phục hồi nào nên cả tác vụ lỗi, không lưu bản notes nào, mất toàn bộ 24,4 phút lượt gọi (#102).

**Giới hạn của phép đo:**

1. Một lần đo, một provider và model; độ trễ phụ thuộc giờ trong ngày; không gặp quota hay rate-limit. Mẫu 2 giờ vẫn là ghép (mục 6.4, điểm 1).
2. Thời gian notes khi thành công chưa đo được: 24,4 phút là thời gian tới lúc lỗi ở bước reduce, trước lượt cuối, nên chỉ là cận dưới.
3. Harness bấm "Tạo notes" ngay (0,17 s; 0,75 s); người thật có thể chờ lâu hơn và khoảng chờ đó cộng vào AC-13 (#73).
4. `output_bytes` 10.701 là cận dưới; độ dài thật của câu trả lời ở lượt 29 không biết (#102).
5. Tải máy: GPU nền 1.155 MiB (gồm một tiến trình python khác trên máy, không thuộc ASR, 260 MiB, có từ trước lần đo; worker bản cài chính nhàn rỗi, không giữ bộ nhớ GPU); khi ASR GPU trung bình 83,5%, đỉnh 6.652 MiB; khi diarization trung bình 90,0%, đỉnh 5.361 MiB; load1 trung bình 1,13 (đỉnh 3,37); RAM khả dụng thấp nhất 22,0 GiB; mạng có dây (`enp7s0`), Wi-Fi không dùng.
6. Mốc chuyển stage lấy từ việc harness hỏi API tác vụ khoảng mỗi 0,7 s, nên thời gian từng stage (ghi tới 0,01 s) có sai số tới khoảng 1 s.

Evidence: `EV99/composite99/` (`summary.json`, `events.jsonl`, `metrics.json`, `dbfacts.json`, `gpu.csv`, `gpu-apps.csv`, `host.csv`, `worker-stats.csv`, `conn.jsonl`, `provider-last-diagnostic.txt`, `lock.txt`), `EV99/setup/` (`swap-up.txt`, `restore-up.txt`). `EV99` là thư mục bằng chứng riêng tư của #99, ngoài repo (mục 11).

### 6.6. Đo sau #104 / PR #109

Kết quả về thời gian: **đạt theo số đo ghép**, nhưng không phải một lần chạy liên tục. Code final là `b78711d`, prompt `notes-hierarchical-v7`; ba lượt ChatGPT `gpt-5.6-sol` medium và Flash final dưới đây là notes-only, English, đều thành công trong **1** lượt. Số đo import có transcript sẵn là lần chạy timed của candidate trước: **651,7 s** từ `POST /api/tasks`; notes được gửi sau **0,2 s**. Vì vậy mốc dùng cho AC-13 được công bố rõ là `651,7 + 0,2 + 81,3 = 733,2 s (12,2 phút)`; phép đo liên tục trước đó trên candidate cũ là `723,3 s`.

| Lần | Segment / citation unit | Cấu hình | Notes POST → ready | Lượt gọi | Estimate → input (tỷ lệ) | Kết quả |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| Single 1 | 661 / — | ChatGPT `gpt-5.6-sol` medium | 116,5 s | 1 | 77.812 → 33.184 (2,34×) | thành công |
| Single 2 | 1.269 / 635 (unit 2) | ChatGPT `gpt-5.6-sol` medium | 67,2 s | 1 | 127.849 → 56.286 (2,27×) | thành công |
| Single 3, mẫu ghép | 1.779 / 890 (unit 2) | ChatGPT `gpt-5.6-sol` medium | **81,3 s** | 1 | 179.196 → 77.048 (2,33×) | thành công; dùng trong số đo ghép AC-13 |
| Flash final | 1.779 / 890 (unit 2) | Antigravity `gemini-3.8-flash` high | **241,7 s** | 1 | 179.312 → 96.692 (1,85×) | thành công; không chấm quality |

Flash final output là 33.200 token, trong đó 28.325 reasoning; notes có 79 bullet, 1.306 từ, đọc 5,7 phút. Ghi chú candidate trước (prompt v7, trước citation units): Flash recall 37/75 so với baseline 69/75; không dùng làm số đo final. Về chất lượng, AC-5 của #104 vẫn **Not done**: ba lượt ChatGPT lần lượt tìm thấy 31/37, 28/38 và 48/75; partly là 4, 7 và 19; thiếu là 2, 3 và 8; 0 mục bịa. Các mục partly chủ yếu là ngày dự kiến/kế hoạch bị đặt dưới `Items Requiring Confirmation` thay vì `Decisions`. Việc đáp ứng ngưỡng thời gian không được dùng để tick AC-5.

Nguồn: `report-tester-3b.md` (transcript 651,7 s, notes POST sau 0,2 s và lần chạy liên tục 723,3 s); `report-tester-4b.md` (Flash candidate trước và recall); `report-tester-6b.md` (ba lượt sol final, grouped units, usage và scoring); `report-tester-7a.md` (Flash final); `capsule.yaml` D14–D17.

## 7. Tiêu chí 6: AC-14, thời gian đưa draft về mức dùng được

Kết quả: **chưa đạt** (partial). Người vận hành xem draft (transcript mới + notes mới) của hai bản ghi và cho biết cả hai **dùng được như hiện có, không sửa, không tạo lại**, mỗi bản mất khoảng 10 phút. Đây là ước lượng, không phải số đo bằng đồng hồ.

| Bản ghi | Thời lượng audio | Draft | Ước lượng của người vận hành | Phút / giờ họp | Khoảng đạt cho thời lượng này (5–10 phút/giờ) | Kết luận |
| --- | --- | --- | --- | --- | --- | --- |
| 13/10 | 75,0 phút | transcript mới + notes Antigravity (`gemini-3.8-flash`, High) | khoảng 10 phút; không sửa, không tạo lại | **8,0** | 6,2–12,5 phút | đạt (ước lượng) |
| 20/10 | 55,7 phút | transcript mới + notes ChatGPT (`gpt-5.6-sol`, medium) | khoảng 10 phút; không sửa, không tạo lại | **10,8** | 4,6–9,3 phút | không đạt (ước lượng, vượt nhẹ) |
| 16/10 | 67,1 phút | không có notes mới sau 3 lần thất bại (ChatGPT `provider_output_too_large`; Antigravity "Thinking loop" hai lần) | không đo | không có | 5,6–11,2 phút | không đo |

Giới hạn khi đọc kết quả:

1. Hai con số dựa trên ước lượng "khoảng 10 phút", không phải đồng hồ bấm; cả hai bản cùng được ước lượng 10 phút nên chênh lệch phút/giờ chỉ do độ dài audio. Chưa rõ ước lượng được làm tròn tới mức nào, nên độ không chắc có thể lớn hơn khoảng cách 0,8 phút/giờ giữa 10,8 và ngưỡng 10. Không nêu số phút duyệt annotation.
2. Không ghi các bước người vận hành thực hiện. "Dùng được không cần sửa" là đánh giá của người vận hành, không dựa trên đối chiếu từng mục với annotation; đối chiếu đó cho kết quả khác ở tiêu chí 7 (mục 8: 13/10 thiếu 1 mục quan trọng và 8 mục bị nâng mức; 20/10 thiếu 1, một phần 2 và 4 mục bị nâng mức).
3. Draft thuộc các bản chạy lại ASR (13/10: 827 segment, 377 gắn cờ; 20/10: 661 segment, 284 gắn cờ). Khối lượng cần duyệt rất lớn: 41–46% segment mang cờ "cần kiểm tra", 7–12 nhãn người nói cho khoảng 6 người (#80).
4. Không tuyên bố đạt mục tiêu 5–10 phút/giờ. 16/10 chưa thể đo vì không có notes (#72, #76); cần đo lại bằng đồng hồ cho cả ba bản ghi (#89).

Evidence: `EV/t7/fresh-20-10/` (`notes.json`, `meeting.json`), `EV/t8/step0-13-10/`, báo cáo của người vận hành.

## 8. Tiêu chí 7: sáu kiểm tra chất lượng riêng

Người chấm là một agent (t10), một lượt chấm cho mỗi bản; nhận dạng được đánh giá từ văn bản transcript, không nghe (mục 10). Ba bản notes được chấm: 13/10 (Antigravity, EN, bản mới), 16/10 (**bản sao** từ bản cài chính: Antigravity, VI, prompt v6, trạng thái `stale`), 20/10 (ChatGPT, EN, bản mới trên lần chạy ASR 661 segment). Không bản nào được sửa tay. Mỗi bản notes dùng manifest chunk thật (13/10: 8 chunk, 16/10: 9 chunk, 20/10: 6 chunk).

### 8.1. Sáu kiểm tra

| # | Kiểm tra | Kết luận | 20/10 | 16/10 | 13/10 | Tổng / ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Source timestamp: chip trỏ tới đoạn mang đủ ý (AC-05, nửa đúng nội dung) | partial | 61/63 | 48/52 | 38/40 | 147/155 (94,8%); 8 yếu. Số liệu theo báo cáo t10 §4.2; bảng chấm 20/10 (63/63) và 16/10 (46/49) phân loại khác (N29, N36; ba bullet đọc thêm gồm N15). Chưa nghe chip (cần người vận hành) |
| 2 | Speaker tại đoạn quan trọng (AC-04): 42 đoạn | partial | transcript trượt 1/12; notes sai 0 | transcript trượt 1/13; notes sai 1 | transcript trượt 4/17; notes sai 0, tranh cãi 1 | Nhãn transcript đúng 36/42; ngôi thứ nhất 13 mục, owner đúng 9; không dùng "tôi" |
| 3 | Quyết định đổi ở cuối (15 mục) | partial | 1 ok, 2 một phần (3 mục) | 4 ok (4 mục) | 5 ok, 2 một phần, 1 fail (8 mục) | 10 ok / 4 một phần / 1 fail: kế hoạch bị thay thế vẫn nằm trong action đã xác nhận ở 13/10 |
| 4 | Action item qua ranh giới chunk (7 mục theo dõi) | partial | 0/1 được nối | 1/3 | 2/3 | 3/7 được nối; 4 mục còn lại hiện thành hai mục riêng hoặc giữ trạng thái cũ |
| 5 | Deadline tương đối (AC-06) | partial | có ngày 11/12 | có ngày 12/12 | có ngày 14/15 | 37/39 có ngày; không ngày: 2/2 clip pass, 0 ngày lịch được tạo |
| 6 | Nội dung mơ hồ (42 mục) | **fail** | 10 xử lý đúng, 1 một phần, 2 nâng mức | 8 đúng, 1 một phần, 3 nâng mức | 14 đúng, 2 một phần hoặc tranh cãi, 1 chưa xử lý | 32 đúng / 4 một phần / 6 thành quyết định, owner, deadline hoặc thuật ngữ mở rộng |

### 8.2. Tỷ lệ theo bản ghi và khối ngôn ngữ

| Khối | Số mục | AC-01 đủ dùng (C+P) | Tỷ lệ mục "rõ" (C) | Segment gắn cờ không chắc | AC-02 đủ / một phần / thiếu | AC-03 bị nâng mức | AC-04 notes sai (trên số đoạn) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20/10 khối EN (≈40 phút) | 20 | 20/20 | 70% | 40,2% | 17 / 2 / 1 | 4/15 | 0/7 |
| 20/10 khối VI (≈15 phút) | 14 | 14/14 | 29% | 50,9% | 14 / 0 / 0 | 0/10 | 0/5 |
| 20/10 mục thuộc cả hai khối | 3 | 3/3 | — | — | 3 / 0 / 0 | — | — |
| 13/10 khối EN (≈45 phút) | 23 | 23/23 | 52% | 40,6% | 23 / 0 / 0 | 6/12 | 0/7 |
| 13/10 khối VI (≈30 phút) | 27 | 26/27 | 4% | 51,2% | 26 / 0 / 1 | 2/13 | 0/10 (1 tranh cãi) |
| 13/10 mục thuộc cả hai khối | 1 | 1/1 | — | — | 1 / 0 / 0 | — | — |
| 16/10 VI xen thuật ngữ Anh (≈67 phút) | 38 | 37/38 | 47% | 47,0% | 35 / 2 / 1 | 10/27 | 1/13 |

- Khối tiếng Việt được nhận dạng kém hơn khối tiếng Anh, điều mà tỷ lệ gộp sẽ che đi. Thuật ngữ và tên riêng tiếng Anh là phần không ổn định.
- Vòng lặp và hallucination có ở cả ba bản ghi (segment lặp: 20/10 EN 40, VI 15; 13/10 EN 21, VI 30; 16/10 33); chỉ một segment trong chuỗi giống hệt được trích trong notes (một câu thật bị lặp 3 lần); không vòng lặp hay khối hallucination nào được đưa vào bullet.
- Không có quyết định, owner hoặc deadline nào hoàn toàn thiếu nguồn.

### 8.3. Cơ chế chia/hợp nhất (AC-39)

Kết luận AC-39: **fail** (t10 chấm partial; đổi theo quyết định của lead, mục 10.1). Tiêu đề yêu cầu xử lý đầy đủ transcript dài qua chia/hợp nhất; phép kiểm yêu cầu không bước nào vượt ngân sách và chất lượng như AC-02/03/05. Ở t7, mẫu 2 giờ và 2 trong 3 lần chạy dài khác (13/10, 16/10, qua ChatGPT) không ra notes vì đầu ra reduce cấp 2 vượt trần 10.700 byte (10.703–10.711 byte (cận dưới, mục 6.3); mục 6, #72); AC-02 và AC-03 fail (mục 5).

Cơ chế vẫn đúng trên ba bản notes thành công. Trên cả ba bản: span sở hữu liên tục và đủ (mỗi segment thuộc đúng một chunk), mỗi chunk sau chunk đầu lặp đuôi chunk trước, mỗi chunk có một chỉ số lượt gọi, 398 / 521 / 484 tham chiếu trích dẫn (20/10, 13/10, 16/10) khớp mốc bắt đầu trong nguồn đã đóng băng (0 không giải được), 0 cảnh báo, mọi chunk đều đóng góp trích dẫn. Các segment được trích: 41,5% (20/10), 39,9% (13/10), 33,6% (16/10). Ba bản được chấm là bản thành công, không cần hợp nhất cấp 2; ba lần chạy cần cấp 2 ở t7 đều lỗi (mục 6, #72).

Evidence: `EV/t10/2026-10-13-scoring.md`, `2026-10-16-scoring.md`, `2026-10-20-scoring.md` (có nội dung, riêng tư), `EV/t10/manifests.json` (chỉ vị trí), `EV/t10/ac06-nodate/`, `EV/t10/ac06-nodate-2/`.

## 9. Tiêu chí 8: danh sách follow-up

Mỗi lỗi hoặc phần chưa đo ở mục 5–8 dẫn tới ít nhất một follow-up. Nội dung từng follow-up (quan sát, cách tái hiện không chứa nội dung cuộc họp, tiêu chí liên quan, bằng chứng) nằm trong issue tương ứng (nhãn `needs-triage`). Mức độ là ước lượng của worker; khi gộp lấy mức cao nhất (medium-high tính là high, low-medium tính là medium). #80, #88, #89: mức do người tổng hợp đặt. #101 và #102 là follow-up của lần đo lại AC-13 (#99, mục 6.5), #107 và #108 là follow-up của đường single-pass (#104, mục 6.6), chưa phân mức. Không follow-up nào sửa mã sản phẩm trong đợt này.

| FU | Tiêu đề | Mức độ | Tiêu chí |
| --- | --- | --- | --- |
| #70 | start.sh không tải được model Whisper vì /models bị gắn chỉ đọc | high | AC-17; tiêu chí 3 |
| #71 | Diarization tăng theo bình phương thời lượng: bản ghi 2 giờ mất khoảng 2 giờ | high | AC-13; tiêu chí 5 |
| #72 | Notes dừng với provider_output_too_large khi bước reduce vượt trần vài byte | high | AC-13, AC-39, AC-14; tiêu chí 5, 6 |
| #73 | Notes không tự chạy sau transcript: cần quyết định đặc tả cho cách đo AC-13 | medium | AC-13; tiêu chí 5 |
| #74 | Runner diarization gửi telemetry ONNX Runtime tới Microsoft khi có mạng | high | AC-10 |
| #75 | Kết nối ngoài provider đã chọn: OMP (catalog, discovery) và danh mục ChatGPT | medium | AC-10 |
| #76 | OMP bỏ stream vì Thinking loop bị báo là provider_unavailable và mất cả tác vụ | medium | AC-14, AC-39; tiêu chí 6 |
| #77 | Notes nâng ý mơ hồ hoặc chưa xác nhận thành quyết định và action đã xác nhận | high | AC-03, AC-06; tiêu chí 7 |
| #78 | Hợp nhất notes giữ cả trạng thái cũ lẫn cuối và để lại hiện vật ranh giới chunk | high | AC-39; tiêu chí 7 |
| #79 | Notes bỏ sót mục đã đánh dấu và thêm thông tin không có trong nguồn | medium | AC-02, AC-03, AC-04, AC-05, AC-06; tiêu chí 7 |
| #80 | ASR/diarization: tiếng Việt kém, vòng lặp chưa gắn cờ, quá nhiều nhãn người nói | medium | AC-01, AC-04, AC-14; tiêu chí 7 |
| #81 | Độ tương phản dưới ngưỡng ở theme sáng và tối (AC-29) | low | AC-29, FE-01, FE-02 |
| #82 | Chuỗi tiếng Anh từ server hiện trong giao diện tiếng Việt | low | AC-12, AC-20, FE-08 |
| #83 | Tiến độ và trạng thái tác vụ lệch thực tế (diarization, notes, worker dừng) | medium | AC-19, AC-47, FE-08 |
| #84 | Kết nối provider: UI chưa chặn ngắt khi provider đang dùng, thông báo lệch chuẩn | medium | AC-10, AC-37, AC-44, AC-49, FE-12, FE-14 |
| #85 | Upload và kiểm tra đầu vào: file cắt cụt, thông báo giới hạn, hàng upload lỗi | medium | AC-12, AC-21, AC-30 |
| #86 | Chi tiết giao diện nhỏ: thông báo, vùng live, thứ tự Tab, tooltip, chân trang | low | AC-12, AC-27, AC-31, AC-42, FE-01, FE-02, FE-04, FE-08, FE-09, FE-15, FE-17 |
| #87 | Phát hành: tag, image công khai, tài liệu cài đặt và artefact lệch ứng viên | medium | AC-17, AC-23, FE-02, FE-10 |
| #88 | Bộ nghiệm thu thiếu cuộc họp toàn tiếng Anh, 2–3 người nói và mẫu 2 giờ thật | medium | tiêu chí 1; AC-01 |
| #89 | Hoàn tất các kiểm tra nghiệm thu cần người vận hành, quota hoặc image công khai | medium | tiêu chí 3, 6, 7; AC-05, AC-14, AC-15, AC-17, AC-35..38, AC-44; FE-11, FE-12, FE-14, FE-16 |
| #101 | Notes của bản ghi 2 giờ mất hơn 24 phút với 29 lượt gọi tuần tự, vượt ngân sách AC-13 | chưa phân mức | AC-13; tiêu chí 5 |
| #102 | Notes bản ghi 2 giờ vẫn lỗi vượt trần đầu ra sau khi hết lượt phục hồi | chưa phân mức | AC-13; tiêu chí 5 |
| #107 | Notes single-pass đặt ngày dự kiến và kế hoạch dưới Items Requiring Confirmation thay vì Decisions | chưa phân mức | AC-5 của #104; chất lượng notes |
| #108 | Bản ghi dài hơn khoảng một giờ: chia thành các phần khoảng một giờ, chạy song song rồi hợp nhất một lượt | chưa phân mức | AC-13; hiệu năng và notes |

## 10. Phương pháp và giới hạn

### 10.1. Quy tắc kết luận và các hàng đổi hoặc suy ra

- Mỗi hàng dùng đúng kết luận của worker: **pass**, **fail**, **partial**, **not done**. Hàng gộp hai nửa lấy nửa xấu nhất. Một tiêu chí chỉ ghi pass khi mọi phần của phương pháp trong spec đã được đo; phần không làm được như spec ghi là chưa làm, không thay bằng kiểm tra dễ hơn. Không có tiêu chí nào bị đổi cách hiểu.
- Các hàng đổi hoặc suy ra (cột "Ghi chú của người tổng hợp" ở mục 5):

| Hàng | Worker | Báo cáo này | Lý do |
| --- | --- | --- | --- |
| AC-25 | t4: partial (chờ máy thứ hai) | pass, người vận hành báo cáo | Người vận hành báo 3/3 lần `curl` từ máy thứ hai không kết nối được; không có output chi tiết nên bằng chứng yếu hơn đo trực tiếp |
| AC-15 | không có hàng riêng | partial, suy ra | Dựng từ bảng bước ở mục 4 (t5 + t8, hai trình duyệt); luồng đạt, nhưng Chrome 149 và Firefox 158.0 không phải bản stable hiện hành tại ngày đo (mục 2.8) |
| Tiêu chí 2 của #16 | t5: partial; t8: pass | đạt | Phần partial của t5 là nửa notes chưa làm khi đó; t8 đã làm nửa này. Copy/xuất transcript không áp dụng (không có control) |
| FE-08 | t6: partial; t9: pass | pass | t6 ghi partial vì nửa notes chưa làm và nêu lệch F8, F9; t9 đã làm nửa notes, ghi pass kèm lệch tương tự (F15, F18). Lệch giữ ở cột Sai lệch (#82 #83 #86), cùng cách xử lý như AC-12, AC-20, FE-15 |
| AC-14 | không có worker | partial | Số liệu ước lượng của người vận hành (mục 7) |
| AC-39 | t10: partial | fail, theo quyết định của lead | Tiêu đề yêu cầu xử lý đầy đủ qua chia/hợp nhất; phép kiểm yêu cầu không bước nào vượt ngân sách và chất lượng như AC-02/03/05. Mẫu 2 giờ và 2 trong 3 lần chạy dài khác không có notes (đầu ra reduce cấp 2 vượt trần 10.700 byte, t7); AC-02 và AC-03 fail |
| FE-10 | t4: pass | partial | Mệnh đề chọn provider chưa được t4 đánh giá; FE-11 partial, AC-10 fail |
| FE-02 | t6: pass | partial, theo quyết định của lead | Đọc literal: tài liệu thiết kế ghi brand là "ASR EN VI", chữ hiển thị của wordmark là `ASR / EN VI` (tiêu đề trang và tên truy cập đúng); t6 để việc đánh giá dấu "/" cho lead |

### 10.2. Phương pháp theo nhóm

| Nhóm | Cách đo | Thật hay mô phỏng |
| --- | --- | --- |
| Chất lượng (AC-01..06, AC-39) | Đối chiếu từng mục annotation với notes và các segment được trích; một agent chấm một lượt | Hệ thống thật (ASR và provider thật); nhận dạng chấm từ văn bản, không nghe |
| Hiệu năng (AC-13) | Import qua UI thật, đồng hồ từ `POST /api/tasks` đến khi notes sẵn; lấy mẫu GPU, CPU, mạng | Hệ thống thật |
| UI (AC-29, FE-01..09, FE-13..18) | Cùng một kịch bản, hai trình duyệt, ba viewport, hai theme, tính toán trong trang: tràn ngang, che phủ, vòng focus, tương phản từ màu tính toán | Hệ thống thật; không có đánh giá thị giác của người, không có âm thanh ra loa |
| Vòng đời (AC-08..21, AC-28, AC-31..34, AC-41..48) | Bản cài thật; lỗi gây ở mức container (`docker kill/pause/restart`, ngắt mạng worker) và ở mức socket | Hệ thống thật. AC-40 và AC-47 thêm test mô phỏng của repo (đúng chỗ spec nói "mô phỏng") |
| Bảo mật và cài đặt (AC-17, AC-22..27, FE-10) | Bản cài riêng từ clone của revision ứng viên; quét 63 route; giải mã QR; thử rotate | Hệ thống thật; AC-24 dịch đồng hồ trên instance phụ |
| Provider (AC-05, 10, 35..38, 44, 49) | Hai tài khoản thật do người dùng đăng nhập; lỗi gây ở mức container và qua API (model không dùng được) | Hệ thống thật; quota không tạo được |

### 10.3. Phần cần người vận hành mà chưa làm

Các phần A–D của `needs-user-4` là tùy chọn; tại thời điểm viết chưa có kết quả nên ghi là chưa làm, cần người vận hành.

| Mục | Tiêu chí | Vì sao chưa làm | Trạng thái |
| --- | --- | --- | --- |
| NU-1 (phần B) | AC-36 ngắt khi rảnh; AC-44 ngắt sau khi dừng xác nhận và ngắt provider không thuộc tác vụ | Ngắt xóa thông tin đăng nhập thật; kết nối lại cần trình duyệt của người dùng | Not done: cần người vận hành |
| NU-2 | AC-36 phiên mất hiệu lực | Cần thu hồi quyền của ứng dụng ở provider | Not done: không yêu cầu (quá xâm lấn) |
| NU-3 (phần A) | AC-35 độc lập, AC-37 "kết nối sau, không tự sinh notes" | Cả hai tài khoản đã kết nối trước khi đo; bản cài tạm `asr-issue16-eval-t8nl` (8771) đã chuẩn bị | Not done: cần người vận hành |
| NU-4 | AC-37, AC-38 hết quota | Không thể tạo hoặc mô phỏng trung thực; chỉ gói của người dùng tạo được | Not done |
| NU-5 (phần D) | AC-38 không tính phí API | Lưu lượng cho thấy ChatGPT dùng `api.openai.com` với token OAuth và mã nguồn không có đường API-key, nhưng phí không đọc được từ lưu lượng | Not done: cần người vận hành (xem trang usage OpenAI và Google Cloud) |
| NU-6 (phần C) | AC-05 nghe chip | Cần người nghe | Not done: cần người vận hành |
| — | AC-25 máy thứ hai; AC-14 thời gian duyệt | Đã làm: người vận hành báo cáo | Mục 5 và mục 7 |

### 10.4. Sai lệch của harness đáng chú ý

1. **Sao chép dữ liệu từ bản cài chính do người dùng chạy:** bộ phân loại auto-mode từ chối `docker exec` vào bản cài chính (`[Remote Shell Writes]`). Người dùng chạy script sao lưu SQLite online và chép thư mục ghi âm; bản cài chính chỉ thay đổi một tệp sao lưu trong `backups/` của volume dữ liệu (tệp còn nguyên, việc xóa do người dùng hoặc lead quyết định). Hai lần từ chối khác của auto-mode (đọc `.env` của bản chính; xóa thư mục khóa của t8) đều được ghi nhận và không đi vòng.
2. **t4:** clone bằng https; model chép từ thư mục models của bản chính (nguồn chỉ đọc) vì lỗi #70 và vì Community-1 cần truy cập có điều kiện; build toàn cache nên không phải build lạnh; đồng hồ AC-24 dịch trên instance phụ; copy/xuất/sửa khi ngoại tuyến thử trên một notes tổng hợp do hàm của repo tạo, không phải đầu ra provider.
3. **Trình duyệt:** Firefox snap cần `TMPDIR` trong vùng snap và tệp upload dưới `$HOME`; theme tối và giảm chuyển động chỉ áp dụng qua `firefox_user_prefs` (mỗi lần mở trình duyệt); CSP của ứng dụng chặn `eval` chuỗi trong `wait_for_function`; chạy headless nên không kiểm được âm thanh ra loa, hộp thoại chọn file gốc và quyền clipboard thật (clipboard được kiểm bằng dán vào ô văn bản).
4. **Kill worker:** `docker kill -s KILL` để worker dừng hẳn (chính sách `unless-stopped` coi là dừng thủ công), harness khởi động lại bằng tay sau 20–22,5 s nên thời gian từ lúc kill tới `interrupted` gồm cả độ trễ đó; `pkill -9` trong container cho thấy đường khởi động lại theo chính sách (1,5–2,1 s).
5. **Hiệu năng:** một lần đo mỗi mẫu, mẫu 2 giờ là ghép; harness bấm "Tạo notes" ngay khi nút bật.
6. **Provider:** lỗi gây ở mức container hoặc qua API; model "không dùng được" được lưu qua API vì UI chỉ cho chọn model trong danh mục; sniffer chỉ ghi tên, IP, cổng và số byte. Bản bắt thô một khung giờ của container app bị ghi đè khi khởi động lại script; các số liệu đã đọc trước đó nằm ở `EV/t8/LEDGER.md`.
7. **Khóa dùng chung:** t8, t9, t10 dùng khóa slot của bản cài eval nên có thời gian chờ (đến khoảng 13 phút); mọi lần bắt đầu xử lý đều kiểm `gpu.lock`.
8. **Chấm chất lượng:** người chấm là một agent, một lượt, không đo tính ngẫu nhiên của notes. Notes khác provider và ngôn ngữ đầu ra theo từng bản ghi (ChatGPT/English cho 20/10; Antigravity/English cho 13/10; Antigravity/Tiếng Việt cho 16/10), nên so sánh giữa các bản ghi bị nhiễu. 16/10 được chấm trên **bản sao** notes của bản cài chính (prompt v6, trạng thái `stale`) trên transcript của annotation. 20/10 được chấm trên lần chạy ASR mới (661 segment) trong khi annotation bám transcript 736 segment; các mục được khớp theo thời gian và nghĩa, và lần chạy mới mất một câu then chốt mà lần trước có. 13/10 chỉ có lần chạy mới (827 segment).
9. **Bản cài khác nhau:** mỗi nhóm đo dùng bản cài riêng (mục 2.2); số liệu hiệu năng và chất lượng đều từ bản cài eval.
10. **Trình duyệt "stable":** Chrome 149.0.7827.53 và Firefox 158.0 (snap) là bản cài trên máy đo, không phải bản stable hiện hành tại ngày đo (Chrome 156, Firefox 158.0.1); AC-15 vì vậy partial.
11. **Độ tương phản** được tính từ màu tính toán trong trang, không có đánh giá thị giác của người.
12. **Độ rộng sidebar:** quy tắc ban đầu của t6 là 228 ±2 px; sau khi thấy tài liệu gọi 228 px là giá trị tham chiếu, t6 chấm lại theo ±10 px (sidebar đo được 236 px: pass). Tệp `EV/t6/<cấu hình>/results-empty.json` và `EV/t6/summary.json` chưa được ghi lại nên còn 28 hàng `SBW` ghi fail; tổng trong báo cáo t6 (2652 pass, 648 fail) đã tính theo quy tắc mới, còn tổng cộng từ `summary.json` là 2624 pass và 676 fail.
13. **Cắt mạng FE-16 (t9):** một lần chạy (Chrome, theme tối) bị loại vì lỗi báo sau 43 s thay vì 3–5 s và giao diện không hiện lỗi; nguyên nhân chưa xác lập. Chạy lại 4/4 lần hiện lỗi sau 3–5 s. Bằng chứng: `EV/t9/backups/func-chrome-dark.invalid-network-run.json`.

## 11. Danh mục bằng chứng

`EV` = thư mục bằng chứng riêng tư `asr-acceptance/issue-16` của đợt nghiệm thu (mode 700, ngoài repo). Ảnh chụp màn hình và JSON thô chứa nội dung cuộc họp nên chỉ nằm trong `EV`. Báo cáo từng worker, ma trận tiêu chí và nhật ký chạy nằm ở thư mục chạy riêng của lead, cũng ngoài repo. `EV99` = thư mục bằng chứng riêng tư của lần đo lại AC-13 (#99), cũng ngoài repo; ảnh chụp màn hình và JSON thô của lần đó chỉ nằm ở đó.

| Thư mục | Nhiệm vụ | Nội dung (tên) |
| --- | --- | --- |
| `EV/setup/` | t1 | nhật ký build, kiểm tra stack, GPU, hash, ffprobe; bước sao chép dữ liệu (`user-step3.log`, `main-backup.txt`); `originals-{stat,sha256}-{before,after}.txt`; `step4-*` (chỉ số meeting, trình duyệt, cấu trúc state provider) |
| `EV/recordings/` | t1 | bản sao ba bản ghi và `composite-2h.m4a` |
| `EV/clips/` | t4, t5, t10 | clip audio cắt; `MANIFEST-t5.md` |
| `EV/annotations/` | t3, t3b | `<ngày>-draft.md`, `classification.md`, `<ngày>-segment-index.tsv`, `<ngày>-chunk-plan.json`, `raw/`, `work/` |
| `EV/t4-security/` | t4 | `steps/`, `logs/`, `api/`, `browser/`, `net/`, `qr/`, `rotate/`, `state-sample1.json`, `clips.sha256` |
| `EV/t5/` | t5 | `flow-{chrome,firefox}/`, `ac12-*`, `ac16-*`, `ac18/`, `ac19-*`, `ac20-33-*`, `ac21-*`, `calendar-*`, `stale-*`, `extra-*`, `diag/`, `logs/`, `src-*` |
| `EV/t6/` | t6 | `<cấu hình>/` (14 cấu hình và 4 cấu hình 360 px), `summary.json`, `matrix.md`, `seed.json`, `expected-version.json`, `logs/`, `explore/` |
| `EV/t7/` | t7 | `composite/`, `fresh-13-10/`, `fresh-20-10/`, `fresh-16-10/`, `dry/`, `dry-1-aborted-harness-bug/`, `ort-telemetry-attribution.md`, `pre-run-state.txt`, `chain.log` |
| `EV/t8/` | t8 | `nf-{chrome,firefox}/`, `ac16n-*`, `ac19n-*`, `chips-real-*`, `faults-{a10,offline,cut,model,model2,apiid,prefs,nologin}/`, `step0-*`, `sim/`, `audit*/`, `LEDGER.md` |
| `EV/t9/` | t9 | `<cấu hình>/`, `func-{chrome,firefox}[-dark]/`, `chrome-light-1440x1000-{intr,inuse}/`, `summary.json`, `matrix.md`, `seed.json`, `console-walk.json`, `backups/`, `logs/` |
| `EV/t10/` | t10 | `2026-10-13-scoring.md`, `2026-10-16-scoring.md`, `2026-10-20-scoring.md`, `snapshot/`, `manifests.json`, `work/`, `ac06-nodate/`, `ac06-nodate-2/` |
| `EV99/composite99/` | #99 | `summary.json`, `events.jsonl`, `metrics.json`, `dbfacts.json`, `gpu.csv`, `gpu-apps.csv`, `host.csv`, `worker-stats.csv`, `conn.jsonl`, `provider-last-diagnostic.txt`, `lock.txt`; `meeting.json`, `notes.json`, `shots/` (có nội dung cuộc họp, riêng tư) |
| `EV99/setup/` | #99 | `swap-up.txt`, `restore-up.txt` (đổi image của bản cài eval sang `asr-issue99:4a88ec8` rồi trả về `asr-issue16:151f3e4`) |
