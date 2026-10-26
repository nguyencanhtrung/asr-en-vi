# Thay đổi kiến trúc và tối ưu v1 — ASR EN VI

## 1. Mở đầu

**Mục đích.** Tổng kết các tối ưu và thay đổi kiến trúc/thiết kế kể từ đợt nghiệm thu #16 (image build từ revision `151f3e4`, xem [báo cáo nghiệm thu](acceptance-report-v1.md)). Tài liệu sống theo giai đoạn phát triển; khi release (#17) nó được tách theo tag thành các tài liệu chuyên biệt. Số `#NN` là issue hoặc PR của repo trên GitHub.

**Quy tắc.**

1. Mỗi PR có tối ưu hoặc thay đổi thiết kế thêm một mục mới, hoặc cập nhật mục đã có, ngay trong PR đó (giai đoạn documentation của issue), theo mẫu ở mục 6. Việc chưa có PR nằm ở mục 5 và chuyển thành mục đầy đủ trong PR của nó.
2. Mỗi mục tự đủ nghĩa: nêu bối cảnh cần thiết trong một dòng thay vì "xem mục trên"; chỉ liên kết sang mục khác để tra cứu thêm.
3. Mọi số có nguồn công khai (issue, PR hoặc tài liệu trong repo), ghi ngay dưới bảng. Nguồn lệch nhau thì dùng số đo mới nhất và ghi một dòng chênh lệch.
4. Không ghi nội dung cuộc họp, thông tin xác thực, đường dẫn cá nhân, bằng chứng riêng tư hay chi tiết công cụ phát triển.

**Bảng tách khi release (#17).** Mỗi mục có một hoặc nhiều tag. Khi release, mục chuyển nguyên sang tài liệu đích của từng tag của nó. Cần tag mới thì thêm một hàng vào bảng này trong PR đầu tiên dùng tag đó.

| Tag | Nội dung | Tài liệu đích (mục) |
| --- | --- | --- |
| Hiệu năng | thời gian, bộ nhớ, thông lượng; lần đo lại tiêu chí nghiệm thu | `docs/acceptance-report-v1.md` (mục 6 AC-13; mục 5.1 các dòng AC liên quan); `docs/backend-design-v1.md` (mục 5, hàng "Pipeline model"); release notes (kết quả nghiệm thu, giới hạn đã biết) |
| Kiến trúc | ranh giới module, luồng dữ liệu, vòng đời tác vụ | `docs/backend-contract-v1.md` (mục 1–3); `docs/backend-design-v1.md`; `docs/adr/` khi là quyết định khó đảo ngược và có đánh đổi |
| Quyền riêng tư | dữ liệu hoặc kết nối ra ngoài máy, telemetry | `docs/backend-contract-v1.md` (mục 3, 6); `docs/adr/` (ADR 0001, 0007); `docs/acceptance-report-v1.md` (AC-10); release notes (giới hạn đã biết) |
| Notes | pipeline tạo notes: chia/hợp nhất, ngân sách, phục hồi, prompt | `docs/backend-contract-v1.md` (mục 5); `docs/backend-design-v1.md` (mục 4, 8); `docs/adr/` (ADR 0005, 0007, 0008, 0009 khi đổi quyết định); `docs/acceptance-report-v1.md` (AC-01..06, AC-14, AC-39) |

Bảng mốc AC-13 (mục 4) chuyển vào `docs/acceptance-report-v1.md` mục 6; việc còn mở ở mục 5 thành giới hạn đã biết trong release notes.

## 2. Chuỗi xử lý và chỗ mỗi thay đổi tác động

```text
upload
  │
chuẩn hoá — kiểm tra và chuyển audio phía server            (ngoài mốc AC-13)
  │
  ▼ POST /api/tasks: bắt đầu mốc AC-13
ASR — Whisper large-v3, CUDA
  │
diarization — pyannote Community-1, CUDA
  │   nạp model → giải mã đầu vào → diarizing
  │   ◄── [#71] giải mã một lần thành waveform 16 kHz mono; pipeline nhận waveform, không nhận đường dẫn
ghép người nói — căn đoạn ASR với lượt nói
  │
  ▼ transcript sẵn: mốc 1 của AC-13
bấm "Tạo notes" — notes không tự chạy sau transcript (#73)
  │
notes — chia chunk → trích xuất → hợp nhất → kiểm tra → render
  │   ◄── [#72] đầu ra vượt trần → gọi lại với mục tiêu độ dài nhỏ hơn
  ▼ notes sẵn: mốc 2 của AC-13

[#74] bao trùm ASR → notes: ORT_DISABLE_TELEMETRY=1 trong mọi tiến trình con của worker
[#99] đo cả đoạn từ POST /api/tasks tới notes sẵn (không đổi mã)
```

## 3. Các thay đổi và lần đo đã merge

Theo thứ tự merge: PR #91, #94, #98, #103, #109, #111.

### #74 / PR #91 — Tắt telemetry ONNX Runtime trong tiến trình con của worker

#### Vấn đề

Worker chạy ASR, diarization và kiểm tra runtime (preflight) trong các tiến trình con. AC-10 yêu cầu khi có mạng chỉ có kết nối của provider đã chọn, nhưng runner diarization mở kết nối tới `*.events.data.microsoft.com`.

#### Nguyên nhân đo được

- onnxruntime 1.31.0 (phụ thuộc của faster-whisper, được pyannote import) nhúng client telemetry với cờ tắt `ORT_DISABLE_TELEMETRY`. Môi trường worker đã đặt các cờ tắt telemetry khác (Hugging Face, pyannote) nhưng không đặt cờ này.
- Runner diarization mở 1–2 kết nối TCP/443 ngắn (khoảng 1 s) khoảng 8 s sau khi diarizing bắt đầu. Thấy ở cả 4 lần chạy hiệu năng của #16 và ở lần xác nhận trên clip 14 phút (2 kết nối, 4.698 byte gửi đi trong 197 s, toàn bộ tới Microsoft); không thấy trong ASR, notes, clip 3 phút (diarization xong sau 8 s) hay khi ngoại tuyến.
- Giới hạn: không kiểm tra nội dung TLS; quy kết dựa trên đích đến, tiến trình sở hữu và mã thư viện.

Nguồn: issue #74 (mục Quan sát).

#### Thay đổi thiết kế

Đặt `ORT_DISABLE_TELEMETRY=1` ở hai chỗ dựng môi trường tiến trình con, cạnh các cờ tắt telemetry sẵn có:

- `worker._safe_runner_environment()`: môi trường của mọi tiến trình con worker (runner ASR, runner diarization, notes, probe CUDA của torch).
- `diarization_runner._set_offline_environment()`: chạy đầu `diarize_file` và preflight `--check-runtime`, trước khi pyannote và onnxruntime được import; gọi trực tiếp `python -m asr_en_vi.diarization_runner` vẫn có biến.

Không vá thư viện; Dockerfile và compose không đổi. Test đổ nếu biến bị bỏ khỏi một trong các đường: runner ASR và diarization do worker khởi chạy, probe CUDA, runner diarization gọi trực tiếp, preflight.

#### Số đo trước và sau

Clip 14 phút (840 s audio), CUDA float16, mạng bật; theo dõi kết nối của container worker suốt tác vụ (lấy mẫu `/proc/net/tcp*` mỗi 0,2 s kèm tiến trình sở hữu socket, cộng bộ ghi SYN/DNS/SNI không giữ payload).

| | Trước sửa (đối chứng, `151f3e4`) | Sau sửa (`b153a25`) |
| --- | --- | --- |
| Diarizing | 115,2 s | 109,0 s |
| Người nói / số đoạn | 5 / 205 | 5 / 187 |
| Kết nối TCP ra ngoài từ worker | TCP/443 từ runner diarization, 7,4 s sau khi diarizing bắt đầu | không có (chỉ một kết nối tự kiểm tra tới app) |
| DNS / SNI | DNS `mobile.events.data.microsoft.com` ×4; SNI cùng tên ×2 | không có |

Nguồn: PR #91 (tiêu chí 2 và 3). Baseline #16 của clip này: 5 người nói, 181 đoạn; số đoạn lệch giữa các lần chạy ASR trên cùng image cũ, không do thay đổi này. Kết nối tự kiểm tra hiện ra ở cả hai bộ theo dõi, nên "không có" là kết quả đo được, không phải bộ theo dõi bị mù.

#### Đánh đổi và phương án đã loại

- Dùng biến môi trường thay vì `disable_telemetry_events()` của onnxruntime: biến đủ chặn theo phép đo trên.
- Sửa ở môi trường tiến trình con thay vì vá thư viện (yêu cầu của issue).
- Runner ASR gọi trực tiếp không tự đặt biến: hiện onnxruntime không được nạp ở đó vì `vad_filter=False`; bật VAD thì cần đặt (#93). Tiến trình ASR do worker khởi chạy vẫn nhận biến.
- Chỉ có một lần đo tay trên một clip; chưa có kiểm tra tự động khi mạng bật, nên telemetry kiểu này có thể tái phát khi đổi phiên bản onnxruntime, pyannote hoặc faster-whisper (#92).

#### Follow-up

- #92: kiểm tra egress khi mạng bật trong `scripts/offline-smoke.py`, fail khi có đích ngoài danh sách cho phép.
- #93: test khóa thứ tự đặt biến trước khi nạp onnxruntime; đặt biến trong runner ASR nếu bật VAD.
- #75: kết nối ngoài provider đã chọn của OMP (catalog, discovery) và danh mục ChatGPT, phần còn lại của AC-10.

#### Liên kết issue/PR

Issue #74, PR #91; liên quan #16 (AC-10), #75, #92, #93.

#### Tag

Quyền riêng tư

#### Tài liệu đích

- `docs/backend-contract-v1.md` mục 3 (đoạn runtime chạy bằng tiến trình riêng: thêm quy tắc môi trường tắt telemetry).
- `docs/acceptance-report-v1.md` mục 5.1, dòng AC-10 (đo lại khi #75 xong).
- Release notes (#17): giới hạn đã biết của AC-10.

### #72 / PR #94 — Phục hồi notes khi đầu ra của provider vượt trần

#### Vấn đề

Trong mục này, “Mẫu ghép 2 giờ”/“mẫu ghép” là audio của hai bản ghi thuộc bộ nghiệm thu được nối lại (7366 s, không phải một cuộc họp); 13/10, 16/10 và 20/10 là các nhãn bản ghi của bộ nghiệm thu.

Notes của bản ghi dài được tạo qua nhiều lượt gọi provider (ChatGPT hoặc Antigravity): chia nguồn thành chunk, trích xuất từng chunk, hợp nhất bằng các lượt reduce theo tầng, rồi lượt cuối. Mỗi bước có trần byte cho câu trả lời (`response_limit`). Một lượt vượt trần làm cả lần tạo notes lỗi `provider_output_too_large`: 3 trong 4 nguồn dài của #16 không ra notes và mất 9,5–16 phút lượt gọi trước đó, không có lượt sửa hay checkpoint.

#### Nguyên nhân đo được

| Nguồn | Chunk | Lượt gọi lỗi | Độ dài ghi nhận | Trần | Công việc bị mất |
| --- | --- | --- | --- | --- | --- |
| Mẫu ghép 2 giờ | 16 | 25 | 10.706 byte | 10.700 | 958,6 s |
| Bản ghi 13/10 (75 phút) | 8 | 13 | 10.711 byte | 10.700 | 571,3 s |
| Bản ghi 16/10 (67 phút) | 10 | 16 | 10.703 byte | 10.700 | 638,8 s |

Nguồn: issue #72; `docs/acceptance-report-v1.md` mục 6.1 và 6.3.

- Cả ba lỗi ở lượt reduce cấp 2 đầu tiên (HTTP 200, lần thử `primary`). Nguồn không cần reduce cấp 2 (bản ghi 20/10, 56 phút, 6 chunk) thành công sau 320,8 s.
- `request_document` chỉ sửa lỗi validation; lỗi vượt trần ném ở transport trước khi tới validation. Trần reduce là 10.700 byte (`MAX_PROMPT_BYTES // 3 // 100 * 100`), trần câu trả lời chunk là 8000.
- Độ dài ghi nhận là cận dưới: client ChatGPT ngừng đọc stream ngay khi tổng vượt trần (ghi nhận sau #99, xem #102). Mức vượt thật có thể lớn hơn 3–11 byte.

#### Thay đổi thiết kế

Lượt vượt trần không dừng ngay. Với ChatGPT là `provider_output_too_large`; với Antigravity (OMP không áp trần phản hồi) là kiểm tra kích thước `size` sau khi nhận tài liệu. Pipeline gửi lại đúng prompt chính kèm một câu nêu mục tiêu độ dài thấp hơn (lượt `recovery`), trong giới hạn cố định:

- Tối đa 2 lượt mỗi yêu cầu (`MAX_OUTPUT_RECOVERY_ATTEMPTS`) và 4 lượt mỗi tác vụ (`MAX_OUTPUT_RECOVERY_CALLS`); `MAX_PROVIDER_CALLS` 49 → 53.
- Mục tiêu giảm còn 3/4 mỗi lượt, làm tròn xuống 100 byte: reduce và chunk 8000 → 6000 → 4500; final/single 128000 → 96000 → 72000.
- Trần phản hồi giữ nguyên; prompt phục hồi vẫn qua kiểm tra `MAX_PROMPT_BYTES`; không vừa thì không gửi và trả lỗi gốc.
- Hết lượt: lỗi của lượt cuối kèm chẩn đoán (stage, `attempt=recovery`, chỉ số lượt gọi, `output_bytes`, `response_limit`), không công bố notes. Antigravity vẫn lỗi `notes_invalid_output`.
- Prompt chính không đổi từng byte (test băm 8 prompt en/vi) nên `PROMPT_VERSION` giữ `notes-hierarchical-v6`; manifest coverage thêm `provider_calls` và `output_recoveries`.

#### Số đo trước và sau

Bản ghi 13/10 (75 phút, 8 chunk), ChatGPT `gpt-5.6-sol` medium, đầu ra English, bản cài eval (bản cài thử riêng, không phải bản cài chính).

| | Trước (#16, `151f3e4`) | Sau (PR #94, `3c96052`) |
| --- | --- | --- |
| Kết quả | lỗi `provider_output_too_large` ở lượt 13 (reduce, 10.711 > 10.700 byte), không có notes | thành công, đủ 8 chunk |
| Thời gian | 571,3 s tới lúc lỗi | 798,5 s tới khi hoàn tất |
| Lượt gọi / lượt phục hồi | 13 / 0 | 16 / 1 |

Nguồn: PR #94 (AC-5 và Evidence); `docs/acceptance-report-v1.md` mục 2.6. Sau sửa, lượt reduce thứ 13 trả 10.702 byte (vượt 10.700) và được gọi lại ở lượt 14. Hai thời gian không so trực tiếp được vì "trước" dừng ở lúc lỗi.

#### Đánh đổi và phương án đã loại

- Chọn gọi lại với mục tiêu độ dài thấp hơn. Đánh đổi: một tác vụ có lượt vượt trần tốn thêm tối đa 4 lượt gọi provider.
- Loại chia nhỏ đầu vào reduce: các lần vượt trần quan sát chỉ 0,03–0,1%, mục tiêu thấp hơn không đổi kế hoạch chunk/reduce và chỉ tốn thêm một lượt gọi. Issue còn nêu cắt bớt, khoảng đệm giữa mục tiêu prompt và trần cứng, checkpoint; PR không đánh giá các hướng này.
- Giới hạn lộ ra ở #99: mục tiêu trong prompt không giới hạn được độ dài thật; reduce của mẫu ghép 2 giờ vẫn vượt trần 10.700 sau khi hết lượt phục hồi (8000 → 6000 → 4500) và tác vụ lỗi sau 1.463,47 s. Mức vượt 0,03–0,1% chỉ là cận dưới, nên lý do chọn ở trên chưa được xác nhận (#102).
- Ngoài phạm vi: lượt repair (sửa lỗi validation, một lần mỗi tác vụ) vượt trần không được phục hồi; đầu vào repair ≤ 8000 byte nên hiếm gặp (#96).

#### Follow-up

- #102: lỗi vượt trần còn lại ở mẫu ghép 2 giờ sau khi hết lượt phục hồi (chặn #17).
- #96: lượt repair vượt trần không được phục hồi (mức thấp, chưa thấy ở lần chạy thật).
- #95: trạng thái provider (`last_diagnostic`) vẫn báo vượt trần sau khi tác vụ đã phục hồi và thành công.

#### Liên kết issue/PR

Issue #72, PR #94; liên quan #16 (AC-13, AC-39), #99.

#### Tag

Notes

#### Tài liệu đích

- `docs/backend-contract-v1.md` mục 5 (đoạn lượt gọi có đầu ra vượt trần; đã mô tả cơ chế, cập nhật khi #102 đổi hành vi).
- `docs/backend-design-v1.md` mục 4 và 8 (Q17, Q18: giới hạn lượt gọi lại của notes; thêm quan hệ giữa lượt sửa Q18 và lượt phục hồi).
- `docs/acceptance-report-v1.md` mục 8.3 (AC-39).

### #71 / PR #98 — Diarization giải mã bản ghi một lần thành waveform 16 kHz

#### Vấn đề

Diarization (pyannote Community-1 trên CUDA) tăng theo bình phương thời lượng. Mẫu ghép 2 giờ (7366 s, audio của hai bản ghi nối nhau, không phải một cuộc họp) mất 7.222,6 s ở diarization và có transcript sau 128,9 phút, gấp 4,3 lần mục tiêu 30 phút của AC-13 (transcript cùng notes sẵn để duyệt).

#### Nguyên nhân đo được

| Thời lượng audio | Cả tác vụ | ASR | Diarization | Diarization ÷ thời lượng² |
| --- | --- | --- | --- | --- |
| 3340 s | 1779 s | 267 s | 1509 s | 1,352×10⁻⁴ |
| 4026 s | 2496 s | 287 s | 2207 s | 1,362×10⁻⁴ |
| 4498 s | 3059 s | 340 s | 2715 s | 1,342×10⁻⁴ |
| 7366 s (ghép) | 7734 s | 510 s | 7223 s | 1,331×10⁻⁴ |

Nguồn: issue #71 (bảng Quan sát); khớp `docs/acceptance-report-v1.md` mục 6.1.

- Thời gian diarization = (1,331–1,362)×10⁻⁴ × thời lượng² (lệch ±1,2%), chiếm 85–93% tác vụ, chạy trên khoảng một lõi CPU (110–125%), GPU trung bình 2–3%. ASR tuyến tính, 12,5–14,4× thời gian thực. Riêng diarization chạm 30 phút ở khoảng 61 phút audio.
- Cơ chế: khi nhận đường dẫn file, mỗi `Audio.crop` của pyannote 4.0.7 tạo `AudioDecoder` mới và giải mã file AAC từ đầu tới vị trí cần cắt. Một crop 10 s ở giây t tốn khoảng 0,255 ms × t (0,02 s ở t=10; 0,93 s ở t=3600; 1,53 s ở t=6000). Bước embeddings crop một lần cho mỗi chunk (bước 1 s) nên tổng ≈ 0,000255 × d²/2 s; với d = 7366 s là khoảng 6900 s, khớp 7223 s đo được.

#### Thay đổi thiết kế

- `diarization_runner._decode_waveform` giải mã cả bản ghi đúng một lần bằng `torchcodec.decoders.AudioDecoder(path, sample_rate=16000, num_channels=1).get_all_samples()`. Decoder tự downmix và resample nên dữ liệu ở tốc độ mẫu gốc không vào Python. Bước này thay lần giải mã thử 1 giây trước đây.
- `diarize_file` truyền `{"waveform": (1, N) float32, "sample_rate": 16000}` vào pipeline Community-1, không truyền đường dẫn file. Test đổ nếu pipeline nhận đường dẫn (`str`, `Path`, dict chứa đường dẫn) hoặc decoder không được gọi đúng một lần với `sample_rate=16000, num_channels=1`.
- Kết quả giải mã không hợp lệ (lỗi mở/giải mã, rỗng, không mono, sai tốc độ mẫu) báo `diarization_input_decode_failed` ở stage `decoding_input`. Sự kiện, mã lỗi, thông điệp và thứ tự stage (`loading_diarization_model` → `decoding_input` → `diarizing`) giữ nguyên.
- Đổi hành vi có chủ đích: file m4a cắt cụt nhưng còn header trước đây qua kiểm tra 1 giây rồi lỗi `diarization_failed` ở `diarizing`; nay báo `diarization_input_decode_failed` ở `decoding_input`.

#### Số đo trước và sau

Mẫu ghép 2 giờ (7366 s), RTX 5080, torch 2.11.0+cu128, CUDA 12.8, pyannote.audio 4.0.7, torchcodec 0.11.1.

| | Trước: #16 (`151f3e4`) | Sau: PR #98 (`d515f36`) | Đo lại: #99 (`4a88ec8`) |
| --- | --- | --- | --- |
| Diarization, tổng | 7.222,6 s (nạp model + chạy) | 103,0 s | 96,73 s |
| Nạp model / giải mã đầu vào / diarizing | không tách | 3,0 / 4,3 / 95,7 s | 4,26 / 2,85 / 89,62 s |
| Tới transcript sẵn | 128,9 phút (từ `POST /api/tasks`) | 768 s = 12,8 phút (từ import) | 626,5 s = 10,4 phút (từ `POST /api/tasks`) |

| Chỉ số (PR #98) | Đo được | Tiêu chí |
| --- | --- | --- |
| Diarizing mỗi giây audio, 2 giờ / 56 phút | 0,01299 / 0,01179 s/s, tỷ lệ 1,10 | ≤ 2 lần |
| Mẫu tổng hợp 4 giờ | 0,0124 s/s | tuyến tính |
| RSS đỉnh (VmHWM) của runner, 2 giờ / 56 phút | 3,14 / 2,40 GiB | ≤ 4 GiB |
| RSS đỉnh, 4 giờ (mẫu tổng hợp) | 4,93 GiB | vượt 4 GiB từ khoảng 3 giờ |
| Số người nói, % thời lượng cùng nhãn với đầu ra `151f3e4` | mẫu ghép 12 → 13, 92,0%; bản 56 phút 10 → 10, 99,2% | chỉ tham khảo |
| Từng bước, mẫu 2 giờ (hook pyannote) | giải mã 3,6 s; segmentation 4,1 s; embeddings 78,8 s; clustering 4,5 s (kèm reconstruct 5,5 s) | embeddings chiếm 87% pipeline |

Nguồn: PR #98 (tiêu chí 2–6); `docs/acceptance-report-v1.md` mục 6.1 và 6.5 (cột #16 và #99). Thời gian stage và thời gian từng bước đo bằng hai cách khác nhau nên không cộng chéo. Chênh lệch nguồn: PR #98 và #99 là hai lần chạy khác nhau của cùng mẫu, mốc bắt đầu khác nhau (768 s tính từ import, 626,5 s từ `POST /api/tasks`); issue #97, tạo trước PR #98, ghi RSS đỉnh 3,10 GiB (2,05 giờ) và 2,35 GiB (0,93 giờ), nên dùng số của PR #98 vì đo sau.

#### Đánh đổi và phương án đã loại

- Chọn giải mã một lần ở decoder với downmix và resample về 16 kHz mono. Loại để pyannote nhận đường dẫn (thời gian bậc hai) và loại giải mã cả file ở 48 kHz stereo rồi resample (RSS đỉnh 16 GiB); decoder torchcodec giải mã cùng file trong 3,8 s với RSS đỉnh 1,7 GiB. Issue vẫn cho phép downmix/resample theo cửa sổ nếu giữ chất lượng; PR không dùng.
- Đánh đổi chất lượng: số học bộ resample của decoder (FFmpeg) khác torchaudio của pyannote, nên mẫu ghép đổi từ 12 sang 13 người nói (92,0% thời lượng cùng nhãn); bản 56 phút giữ 10 người nói (99,2%). Độ lệch âm lượng +3 dB của downmix không ảnh hưởng (nhãn giống hệt sau khi bù). Chủ sở hữu xác nhận đầu ra cũ không phải nguồn chuẩn (không biết 12 hay 13 người nói là đúng), nên số khớp chỉ để tham khảo.
- Chưa thử: diarization theo cửa sổ rồi nối người nói, tham số clustering, số thread, batch size, model khác. Embeddings chiếm 87% pipeline và tăng tuyến tính nên chưa cần.
- Bộ nhớ: waveform tăng tuyến tính (0,215 GiB mỗi giờ audio) nhưng RSS đỉnh có thêm thành phần bậc hai ở bước clustering (khoảng 0,1 GiB × giờ²), có từ trước thay đổi này; bản ghi 4 giờ (trần thời lượng mặc định) vượt 4 GiB (#97).

#### Follow-up

- #97: RSS đỉnh của diarization có thành phần bậc hai ở clustering; xác nhận nguồn, chọn giới hạn bộ nhớ cho bản ghi 4 giờ rồi giảm hoặc ghi yêu cầu RAM tối thiểu.

#### Liên kết issue/PR

Issue #71, PR #98; liên quan #16 (AC-13), #97, #99.

#### Tag

Hiệu năng

#### Tài liệu đích

- `docs/backend-contract-v1.md` mục 3 (dòng "Pipeline recording": diarization nhận waveform đã giải mã một lần; stage `decoding_input`, mã lỗi `diarization_input_decode_failed`).
- `docs/backend-design-v1.md` mục 5, hàng "Pipeline model" (số đo thời gian và bộ nhớ).
- `docs/acceptance-report-v1.md` mục 6.5 (AC-13 sau thay đổi).
- Release notes (#17): giới hạn bộ nhớ của bản ghi 4 giờ.

### #99 / PR #103 — Đo lại AC-13 trên main sau #71, #72, #74

#### Vấn đề

AC-13 yêu cầu bản ghi 2 giờ có cả transcript và notes sẵn để duyệt trong tối đa 30 phút kể từ khi bắt đầu xử lý (`POST /api/tasks`). Ở #16 nó fail: transcript sẵn sau 128,9 phút và notes lỗi `provider_output_too_large`. Sau #71, #72, #74 chưa có lần đo liền mạch của mẫu ghép 2 giờ (7366 s) từ import tới notes trên main.

#### Nguyên nhân đo được

Lần đo trên main `4a88ec8` (có #71, #72, #74), ChatGPT `gpt-5.6-sol` medium, đầu ra English: AC-13 vẫn fail và bước chậm nhất chuyển từ diarization sang notes.

- Notes chạy 1.463,5 s (70,0% của 2.090,2 s) với 29 lượt gọi ChatGPT nối tiếp (14 chunk, độ song song 1), rồi lỗi `provider_output_too_large` ở lượt 29 (stage `reduce`, lượt `recovery`, `output_bytes` 10.701 so với trần 10.700; `output_bytes` là cận dưới).
- Sau transcript (10,4 phút) chỉ còn 30 − 10,4 = 19,6 phút trong ngân sách; notes đã dùng 24,4 phút mà chưa tới lượt cuối.
- 14 lượt đầu (bằng số chunk) mất 615 s, trung vị 41,3 s mỗi lượt; 15 lượt sau mất 847 s, trung vị 61,7 s. Cách chia hai nhóm là suy ra, vì chỉ stage của lượt cuối được ghi.
- Ước tính trước khi đo (issue #99): notes khoảng 13–20 phút; đo được 24,4 phút tới lúc lỗi.

#### Thay đổi thiết kế

Không đổi mã sản phẩm. PR cập nhật `docs/acceptance-report-v1.md`: thêm mục 6.5 (bảng stage, lượt gọi, nguyên nhân, giới hạn phép đo); cập nhật mục 1.1 (tiêu chí 5), 1.3 và 5.1 (AC-13); ghi chú số byte vượt trần là cận dưới (mục 6.3, dòng AC-39, mục 8.3); thêm follow-up #101 và #102 ở mục 9. Phương pháp giữ như #16: mốc bắt đầu `POST /api/tasks`, import tính riêng ngoài AC-13, khoảng chờ trước khi bấm "Tạo notes" ghi riêng.

#### Số đo trước và sau

Mẫu ghép 2 giờ (7366 s), bản cài eval (RTX 5080).

| | Trước: #16 (`151f3e4`) | Sau: #99 (`4a88ec8`) |
| --- | --- | --- |
| Upload / kiểm tra phía server (ngoài AC-13) | 0,19 s / 81,2 s | 0,24 s / 81,0 s |
| ASR (`transcribing`) | 510,0 s, 14,4× thời gian thực | 525,55 s, 14,0× |
| Diarization | 7.222,6 s | 96,73 s (nạp model 4,26 + giải mã 2,85 + chạy 89,62) |
| Segment / nhãn người nói | 1838 / 12 | 1706 / 13 |
| Transcript sẵn (từ `POST /api/tasks`) | 128,9 phút (7.734 s) | 10,4 phút (626,53 s) |
| Từ transcript sẵn tới bấm "Tạo notes" | 0,87 s | 0,75 s (0,17 s từ lúc UI báo sẵn) |
| Notes: chunk / byte nguồn / lượt gọi | 16 / 340.521 / 25 | 14 / 307.154 / 29 |
| Kết quả notes | lỗi ở lượt 25 sau 958,6 s (16,0 phút) | lỗi ở lượt 29 sau 1.463,47 s (24,4 phút) |
| AC-13: bắt đầu → transcript và notes sẵn | không có mốc; tác vụ notes kết thúc lỗi sau 144,9 phút | không có mốc; tác vụ notes kết thúc lỗi ở 2.090,2 s (34,8 phút) |

Nguồn: `docs/acceptance-report-v1.md` mục 6.1 (cột mẫu 2 giờ) và 6.5; PR #103; issue #99. Tỷ trọng trong 2.090,2 s: ASR 25,1%, diarization 4,6%, notes 70,0%. Diarization nhanh khoảng 75 lần, transcript sẵn nhanh khoảng 12 lần. Thời gian stage lấy từ việc hỏi API tác vụ khoảng mỗi 0,7 s nên sai số tới khoảng 1 s.

#### Đánh đổi và phương án đã loại

- Một lần đo, một provider và model, trên mẫu ghép (không phải một cuộc họp 2 giờ liền); độ trễ phụ thuộc giờ trong ngày; không gặp quota hay rate-limit.
- Không đo lại: lỗi notes là giới hạn của sản phẩm, không phải sự cố hạ tầng (không có lỗi mạng, quota, máy chủ hay GPU).
- Không sửa mã sản phẩm trong PR đo; bước chậm nhất và lỗi còn lại đi vào follow-up.
- Không có mốc "notes sẵn" nên báo cáo ghi tổng tới lúc tác vụ notes kết thúc lỗi: 2.090,2 s từ `POST /api/tasks`, 2.171,6 s từ lúc bấm tạo (gồm import 81,4 s). Thời gian notes khi thành công chưa đo được; 24,4 phút chỉ là cận dưới.
- Công cụ đo bấm "Tạo notes" ngay (0,17 s và 0,75 s); người thật có thể chờ lâu hơn. Khoảng chờ đó có nằm trong AC-13 hay không là quyết định đặc tả (#73).

#### Follow-up

- #101: notes là bước chậm nhất (24,4 phút, 29 lượt gọi tuần tự); mục tiêu tổng ≤ 30 phút (chặn #17).
- #102: lỗi vượt trần còn lại sau khi hết lượt phục hồi (chặn #17).

#### Liên kết issue/PR

Issue #99, PR #103; liên quan #16 (AC-13), #71, #72, #73, #74.

#### Tag

Hiệu năng

#### Tài liệu đích

- `docs/acceptance-report-v1.md` mục 6.5 (PR #103 đã cập nhật), cùng mục 1.1, 1.3 và 5.1 (AC-13).
- Release notes (#17): kết quả nghiệm thu AC-13 và giới hạn đã biết.

### #104 / PR #109 — Notes một lượt theo context thật của model

#### Vấn đề

AC-13 cần transcript và notes của mẫu 2 giờ sẵn trong tối đa 30 phút từ `POST /api/tasks`. Trước #104, planner dùng ngân sách bảo thủ tương đương context 64K: mẫu ghép 2 giờ cần 14 chunk và 29 lượt gọi tuần tự; #99 mất 1.463,5 s ở notes rồi lỗi `provider_output_too_large`, tác vụ kết thúc lỗi sau 2.090,2 s. #104 mở đường một lượt chỉ khi transcript vừa ngân sách thật của đúng hai cấu hình chủ sở hữu; nguồn quá lớn và model khác vẫn dùng chia/hợp nhất hiện có.

#### Nguyên nhân đo được

- Giới hạn thực của `gpt-5.6-sol` là context 272.000 token; Codex dùng 95%, tương đương 258.400 token có thể lập kế hoạch. Không có trần output model được công bố; ứng dụng giữ guard body 1 MiB cho request ChatGPT, và các lần gọi thật đã đạt các kích thước được đo.
- `gemini-3.8-flash` qua OMP có context 1.048.576 token và trần 65.536 token cho output, gồm cả thinking; RPC frame của ứng dụng là 1 MiB. Vì vậy trần transport và trần token phải được kiểm riêng.
- Ước tính token của đường mới là `ceil(UTF-8 bytes × 2 / 3)` trên prompt, schema, phần dự phòng repair và headroom; đường single-pass dành 65.536 token cho output và 4.000 token headroom. `PROMPT_VERSION` là `notes-hierarchical-v7`.
- Schema enum nghiêm ngặt của structured outputs chỉ chứa tối đa 999 mã nguồn trong một scope. Với hơn 999 segment, pipeline gom các segment liên tiếp thành unit, `unit_size = ceil(n / 999)`; mỗi mục chịu giới hạn `200 // unit_size` unit và khi khôi phục sẽ trả lại toàn bộ mã segment thành viên.

Nguồn: PR #109 (AC checklist và Evidence); issue #104; giới hạn từ [Codex rust-v0.154.0 `codex-rs/protocol/src/openai_models.rs`](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/protocol/src/openai_models.rs#L400-L525) và [ChatGPT model catalog](https://chatgpt.com/backend-api/codex/models?client_version=0.154.0); [OMP v18.5.0 `packages/catalog/src/models.json`](https://github.com/can1357/oh-my-pi/blob/v18.5.0/packages/catalog/src/models.json#L1); code tại `src/asr_en_vi/notes_document.py`.

#### Thay đổi thiết kế

- Thêm bảng ngân sách tĩnh theo cặp `(provider, model)` đúng hai cấu hình: ChatGPT `gpt-5.6-sol` và Antigravity `gemini-3.8-flash`. Cặp khác giữ ngân sách bảo thủ trước #104.
- Chỉ chọn single-pass khi phép kiểm context, request guard và repair reserve cùng đạt. Chunk/reduce giữ các trần transport hiện có; không chuyển prompt rút gọn của #100 vào đường này.
- Giữ enum source ID bằng citation units thay vì đổi sang chuỗi tự do. Các unit liên tiếp có cùng alias trong prompt; validator vẫn kiểm tra scope và bước restore mở alias thành các segment gốc.
- Prompt single-pass thêm điều khoản bao quát: một mục riêng cho mỗi chủ đề, quyết định, câu hỏi, hành động và mục cần xác nhận khác nhau trong toàn bộ cuộc họp, theo thứ tự nguồn; mục ngắn nhưng không được bỏ hoặc gộp ý riêng. Prompt chunk/reduce không đổi. Việc ghi usage chỉ giữ số đếm `input/output/reasoning`, estimate và kích thước prompt, không ghi nội dung.

#### Số đo trước và sau

Điều kiện trước là #99 trên mẫu ghép 2 giờ, ChatGPT `gpt-5.6-sol` medium, đường chunk/reduce bảo thủ: 14 chunk, 29 lượt tuần tự, notes lỗi sau 1.463,5 s và tác vụ kết thúc lỗi ở 2.090,2 s. Điều kiện sau là lượt đo final trên revision `b78711d`, notes English, prompt `notes-hierarchical-v7`, ba lượt ChatGPT `gpt-5.6-sol` medium và một lượt Flash final chạy notes-only; nguồn trên 999 segment dùng citation units.

| Lượt | Segment / citation unit | POST → ready | Lượt gọi | Prompt B | Estimate → input (tỷ lệ) | Output / reasoning | Tìm thấy / partly / thiếu / bịa | Mơ hồ nâng (chắc / giáp ranh) | Bullet / từ / phút đọc |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |
| Single 1 | 661 / — | 116,5 s | 1 | 109.426 | 77.812 → 33.184 (2,34×) | 6.111 / 1.825 | 31 / 4 / 2 / 0 trên 37 | 2 / 3 | 85 / 1.585 / 6,9 |
| Single 2 | 1.269 / 635 (unit 2) | 67,2 s | 1 | 186.630 | 127.849 → 56.286 (2,27×) | 3.451 / 482 | 28 / 7 / 3 / 0 trên 38 | 2 / 1 | 65 / 1.286 / 5,6 |
| Single 3, mẫu ghép | 1.779 / 890 (unit 2) | 81,3 s | 1 | 262.375 | 179.196 → 77.048 (2,33×) | 4.258 / 239 | 48 / 19 / 8 / 0 trên 75 | 1 / 1 | 92 / 1.725 / 7,5 |
| Flash final | 1.779 / 890 (unit 2) | 241,7 s | 1 | 262.375 | 179.312 → 96.692 (1,85×) | 33.200 / 28.325 | không chấm | — | 79 / 1.227 / 5,3 |
| Baseline 20/10, chunked | — | — | — | — | — | — | baseline tìm thấy 34/37 | — | 63 / 1.458 / 6,3 |
| Baseline 16/10, chunked | — | — | — | — | — | — | baseline tìm thấy 35/38 | — | 97 / 2.469 / 10,7 |

Số tìm thấy cộng partly (cận trên) của ba lượt sol là 35/37, 35/38 và 67/75; ba lượt sol đều có 0 mục bịa. Flash final không chấm quality. Các mục partly được ghi nhận chủ yếu vì ngày dự kiến và kế hoạch được đặt dưới `Items Requiring Confirmation` thay vì `Decisions`. Các lượt đã ghi quality đều có estimate lớn hơn `input_tokens`; tỷ lệ thực tế trong bảng là phép chia estimate cho `input_tokens`.

Ghi chú candidate trước (prompt v7, trước citation units): Flash thành công một lượt nhưng recall chỉ 37/75 so với baseline 69/75; không dùng làm số đo final.

Nguồn: PR #109 (AC checklist và Evidence); issue #104; lượt đo final và các baseline trong Evidence.

#### Đánh đổi và phương án đã loại

- Chọn single-pass chỉ cho model và nguồn vừa ngân sách thật. Đánh đổi: nguồn quá lớn vẫn có nhiều lượt gọi; các nguồn trên 999 segment dùng citation unit nên độ hạt của tham chiếu thô hơn trong prompt, nhưng restore vẫn trả đủ segment gốc.
- Loại schema `source_id` dạng chuỗi không có enum: candidate trước từng trả `unknown_source_id`; output 21.527 B vượt giới hạn repair 8.000 B nên không còn repair, làm cả lượt single-pass lỗi.
- Điều khoản completeness là cần thiết nhưng chưa đủ: Flash v7 vẫn chỉ tìm thấy 37/75, partly 21 và thiếu 17; không dùng nó làm bằng chứng đã đạt AC-5.
- Hoãn phương án chia nguồn dài thành các phần khoảng một giờ chạy song song rồi hợp nhất một lượt sang #108. Không đưa quy tắc rút ngắn của #100 vào PR này; chủ sở hữu đã bỏ mục tiêu đọc 2–3 phút, nên không rút ngắn các notes mới theo mục tiêu đó.

#### Follow-up

- #107: chuyển các ngày dự kiến và kế hoạch đã chốt trong cuộc họp từ `Items Requiring Confirmation` sang `Decisions`; các đề xuất chưa được thống nhất vẫn ở `Items Requiring Confirmation`; AC-5 của #104 vẫn để **Not done** với các số đo trên.
- #108: nguồn dài hơn khoảng một giờ → chia thành các phần khoảng một giờ, chạy song song rồi hợp nhất một lượt.
- #100: giữ mục tiêu mỗi ý một mục và schema sáu nhóm theo hàng đã cập nhật ở mục 5; bỏ mục tiêu đọc 2–3 phút, không còn là blocker của #104.

#### Liên kết issue/PR

Issue #104, PR #109; liên quan #99, #100, #101, #102, #107, #108.

#### Tag

Notes; Hiệu năng

#### Tài liệu đích

- `docs/backend-contract-v1.md` mục 5 (ngân sách, single-pass, citation và phục hồi).
- `docs/backend-design-v1.md` mục 4 và 8 (Q17–Q18, model/provider và đánh đổi chia/hợp nhất).
- `docs/acceptance-report-v1.md` mục 6.6 và hàng AC-13 (mốc đo #104); release notes (#17) cho giới hạn đã biết.

### #100 / PR #111 — Notes văn phong telegraph, mỗi ý một mục

#### Vấn đề

Đường single-call v7 tạo notes dài 5,6–6,9 phút đọc và còn lặp ý giữa các mục; các ngày đã thống nhất bị xếp vào `Items Requiring Confirmation` (#107). Chủ sở hữu bỏ mục tiêu đọc 2–3 phút ngày 2026-10-26, giữ ưu tiên độ đầy đủ.

#### Nguyên nhân đo được

Theo thứ tự 13/10, 20/10, 16/10, baseline v7 có 27/38/15 ý lặp và 4/5/4 mục Overview; notes có 1.337/1.585/1.286 từ (5,8/6,9/5,6 phút đọc), với 1/2/2 mục #107 đặt sai.

#### Thay đổi thiết kế

- Thêm một bộ quy tắc dùng chung `_TELEGRAPH_RULE` và `_PLACEMENT_RULE` vào phần base text của `_source_instructions` (single + chunk) và `_reduction_instructions` (intermediate + final), cho cả EN và VI.
- Giữ nguyên các câu yêu cầu chất lượng hiện có; không đổi schema sáu mục, validator, ngân sách hoặc cap. `PROMPT_VERSION` tăng lên `notes-hierarchical-v8`. Test phủ từng cặp step × language.

#### Số đo trước và sau

Điều kiện đo: ChatGPT `gpt-5.6-sol` medium, EN, một lượt chạy mỗi cuộc họp, một AI scorer mỗi lượt; baseline là v7 single-call (các baseline 20/10 và 16/10 lấy từ #104).

| Cuộc họp | Phiên bản | Tìm thấy / partly / thiếu | Tìm thấy + partly | Ý lặp | Mục Overview | Số mục | Từ | Phút đọc | Ký tự MD | POST → ready | Lượt gọi | Token output | #107 đặt sai | Bịa | Sai owner |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 13/10 | v7 (trước) | 41 / 5 / 5 | 46 | 27 | 4 | 74 | 1.337 | 5,8 | 9.861 | 83,2 | 1 | 4.264 | 1 | 0 | 0 |
| 13/10 | candidate c1 | 41 / 6 / 4 | 47 | 10 | 3 | 72 | 891 | 3,9 | 7.288 | 83,3 | 1 | 4.397 | 1 | 0 | 0 |
| 13/10 | c2 (phát hành) | 44 / 3 / 4 | 47 | 12 | 2 | 57 | 832 | 3,6 | 6.700 | 112,4 | 1 | 5.994 | 0 | 0 | 0 |
| 20/10 | v7 (trước) | 31 / 4 / 2 | 35 | 38 | 5 | 85 | 1.585 | 6,9 | 11.189 | 116,5 | 1 | 6.111 | 2 | 0 | 1 |
| 20/10 | candidate c1 | 29 / 6 / 2 | 35 | 14 | 2 | 80 | 981 | 4,3 | 7.772 | 76,2 | 1 | 3.984 | 1 | 0 | 2 |
| 20/10 | c2 (phát hành) | 33 / 3 / 1 | 36 | 19 | 3 | 63 | 805 | 3,5 | 6.466 | 91,3 | 1 | 4.682 | 0 | 0 | 0 |
| 16/10 | v7 (trước) | 28 / 7 / 3 | 35 | 15 | 4 | 65 | 1.286 | 5,6 | 9.083 | 67,2 | 1 | 3.451 | 2 | 0 | 0 |
| 16/10 | candidate c1 | 27 / 10 / 1 | 37 | 11 | 3 | 84 | 882 | 3,8 | 7.163 | 77,2 | 1 | 3.931 | 2 | 0 | 0 |
| 16/10 | c2 (phát hành) | 26 / 7 / 5 | 33 | 15 | 3 | 66 | 837 | 3,6 | 6.567 | 81,4 | 1 | 4.269 | 2 | 0 | 0 |

Nguồn: issue #100; PR #111 (AC checklist và Evidence); các bảng đo tester-0/1/2 và baseline #104.

#### Đánh đổi và phương án đã loại

- Chọn c2 thay c1: tổng `Found` strict là 103 so với 97 của c1 và 100 của baseline; tổng #107 misplaced giảm còn 2 so với 4 của c1 và 5 của baseline v7; đổi lại tổng repeats tăng lên 46 so với 35. Một lượt chạy mỗi cuộc họp có nhiễu khoảng ±2 mục tìm thấy và khoảng ±3 lần lặp.
- Lần thử đầu (chunk/reduce c1–c5, branch `feat/issue-100-concise-notes`): mục tiêu độ dài mềm bị bỏ qua (vòng 2 của lần thử đầu: 890–1.192 từ); budget cứng rút ngắn notes nhưng làm giảm recall và đẩy ý sang confirmation; repeats còn 6–11, không về 0; effort high mất khoảng 2,1× thời gian mà không tăng chất lượng.
- Loại schema `maxItems`/validator cho Overview: sẽ buộc repair và làm các tài liệu cũ không còn hợp lệ.

#### Follow-up

- #110: repeats còn lại; AC-2 chưa đạt; strict Found ngày 16/10 là 26 so với 28, nên AC-4 và điều kiện chồng lấp của AC-3 chưa đạt ở đó; #110 yêu cầu ít nhất hai lượt chạy mỗi cuộc họp.
- #107: placement đã cải thiện nhưng một cuộc họp vẫn còn mục đặt sai; giữ issue mở.
- Prompt chunk/reduce chưa được đo bằng real runs.

#### Liên kết issue/PR

Issue #100, PR #111; liên quan #104, #107, #110, #16.

#### Tag

Notes

#### Tài liệu đích

- `docs/backend-contract-v1.md` mục 5 (prompt version).
- `docs/backend-design-v1.md` (quy tắc prompt notes).
- `docs/acceptance-report-v1.md` (số liệu chất lượng).
- Release notes (#17).

## 4. Mốc AC-13 (#16 → #99 → #104)

AC-13: bản ghi 2 giờ có transcript và notes sẵn để duyệt trong tối đa 30 phút kể từ `POST /api/tasks`. Mẫu ghép 2 giờ (7366 s) là audio của hai bản ghi nối nhau.

| Mốc | Revision đo | Nguồn đo | Số đo chính | AC-13 |
| --- | --- | --- | --- | --- |
| #16 nghiệm thu | `151f3e4` | mẫu ghép 2 giờ | transcript sẵn 128,9 phút (diarization 7.222,6 s); notes lỗi ở lượt 25 sau 958,6 s | fail |
| #72 / PR #94 | `3c96052` | bản ghi 13/10 (75 phút) | notes thành công sau 798,5 s, 16 lượt gọi, 1 lượt phục hồi (trước: lỗi ở lượt 13 sau 571,3 s) | không đo mẫu 2 giờ |
| #71 / PR #98 | `d515f36` | mẫu ghép 2 giờ | diarization 103,0 s (trước 7.222,6 s); import → transcript sẵn 768 s | không đo notes |
| #99 / PR #103 | `4a88ec8` (có #71, #72, #74) | mẫu ghép 2 giờ | transcript sẵn 626,5 s (10,4 phút); notes lỗi ở lượt 29 sau 1.463,5 s; tác vụ notes kết thúc lỗi ở 2.090,2 s (34,8 phút) | fail |
| #104 / PR #109 | `b78711d` | mẫu ghép 2 giờ, số đo ghép | **651,7 s transcript (lần chạy timed) + 0,2 s + 81,3 s notes = 733,2 s (12,2 phút)**; một lần chạy timed trên candidate trước là 723,3 s | đạt về thời gian, nhưng số đo 733,2 s là composed, không phải một lần chạy liên tục |

Nguồn: mục tương ứng của từng PR ở mục 3; `docs/acceptance-report-v1.md` mục 6.1, 6.5 và 6.6. #74 (PR #91) không nhằm giảm thời gian và đã có trong image đo của #99. Bước chậm nhất chuyển từ diarization (#16) sang notes (#99), rồi notes còn 67,2–116,5 s ở các lượt single-pass final. #104 có mốc thời gian composed dưới 30 phút; chất lượng AC-5 còn theo dõi ở #107 và phương án nguồn dài ở #108.

## 5. Đang làm / tiếp theo

Việc mở liên quan tới các thay đổi trên. Khi PR của một việc tới giai đoạn documentation, nó thêm mục của mình ở mục 3 (ví dụ #100) và bỏ hàng ở đây.

| # | Việc | Số đo nền | Tag dự kiến | Quan hệ |
| --- | --- | --- | --- | --- |
| #110 | Notes vẫn lặp ý giữa các mục sau #100 | Theo thứ tự 13/10, 20/10, 16/10: sau #100: 12/19/15 ý lặp; c1: 10/14/11; trước #100: 27/38/15 | Notes | AC-2 chưa đạt; strict Found ngày 16/10 là 26 so với 28, nên AC-4 và điều kiện chồng lấp của AC-3 chưa đạt ở đó; #110 yêu cầu ít nhất hai lượt chạy mỗi cuộc họp |
| #101 | Notes của bản ghi 2 giờ mất hơn 24 phút với 29 lượt gọi tuần tự | notes 1.463,5 s = 70% mốc AC-13; trung bình 50,5 s mỗi lượt; 8 lượt cuối 62–77 s. Hướng (chưa quyết): gọi song song chunk độc lập, giảm số lượt hoặc tầng reduce, rút ngắn output (#100) | Hiệu năng, Notes | chặn #17 |
| #102 | Notes vẫn lỗi vượt trần đầu ra sau khi hết lượt phục hồi | lượt 29: `output_bytes` 10.701 so với trần 10.700 (cận dưới); mục tiêu 8000 → 6000 → 4500 không giới hạn được độ dài thật | Notes | chặn #17 |
| #73 | Notes không tự chạy sau transcript: quyết định đặc tả cho cách đo AC-13 | người vận hành phải bấm "Tạo notes"; công cụ đo bấm sau 0,2–1,1 s, người thật không có giới hạn | Kiến trúc | quyết định đổi mốc đo AC-13 |
| #97 | RSS đỉnh của diarization tăng bậc hai ở clustering | 4,93 GiB ở 4 giờ (mẫu tổng hợp) so với 4 GiB; mô hình 1,98 + 0,35·d + 0,105·d² GiB (d tính bằng giờ), vượt 4 GiB ở khoảng 3 giờ | Hiệu năng | từ #71 |

Nguồn: chính các issue #104, #110, #101, #102, #73, #97; #101 và #102 khớp `docs/acceptance-report-v1.md` mục 6.5. #101 và #102 chặn #17 (release).

## 6. Mẫu mục mới

Mục mới sao chép mẫu dưới đây và giữ nguyên tên các heading, để việc tách theo tag không phải viết lại.

````markdown
### #<issue> / PR #<pr> — <tiêu đề ngắn: thay đổi gì>

#### Vấn đề

<Bối cảnh cần để hiểu mục này một mình (thuật ngữ, mốc AC) trong một hai dòng; điều gì sai hoặc chậm.>

#### Nguyên nhân đo được

<Nguyên nhân kèm số đo; bảng nếu nhiều số.>

Nguồn: <issue/PR/comment hoặc mục của tài liệu trong repo>.

#### Thay đổi thiết kế

<Thiết kế mới: module, hàm, hằng số, hành vi mới; điều gì không đổi.>

#### Số đo trước và sau

<Điều kiện đo (revision, mẫu, cấu hình), rồi bảng trước/sau.>

| | Trước | Sau |
| --- | --- | --- |
| <chỉ số> | <số> | <số> |

Nguồn: <issue/PR/tài liệu>. <Nếu nguồn lệch nhau: dùng số đo mới nhất, ghi một dòng chênh lệch.>

#### Đánh đổi và phương án đã loại

- <Phương án đã chọn>: <đánh đổi>.
- <Phương án đã loại>: <lý do>.

#### Follow-up

- #<n>: <một dòng>.

#### Liên kết issue/PR

Issue #<n>, PR #<n>; liên quan #<n>.

#### Tag

<một hoặc nhiều tag trong bảng ở mục 1: Hiệu năng | Kiến trúc | Quyền riêng tư | Notes>

#### Tài liệu đích

- <tệp và mục sẽ nhận nội dung khi release>
````
