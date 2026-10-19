# Kiểm chứng kết nối ChatGPT thật

Quy trình này kiểm tra direct Sign in with ChatGPT qua Docker và một yêu cầu Responses API
bằng dữ liệu tổng hợp. Người vận hành tự đăng nhập và cấp quyền trong trình duyệt. Không dùng
credential của Codex, không đưa token vào lệnh, log, ảnh chụp hoặc biên bản.

## Trạng thái bằng chứng

**Đã kiểm chứng đăng nhập và một yêu cầu tổng hợp bằng tài khoản thật trên bản preview.**
Trạng thái provider được đọc sau khi thay container nhưng giữ nguyên volume; ứng dụng vẫn báo
đã kết nối, giữ lựa chọn model/effort và có bản ghi kiểm chứng hoàn tất. Đây là bằng chứng cho
model và tài khoản đã dùng tại thời điểm đó, không bảo đảm quota hoặc model khác. Các bước
refresh token khi hết hạn và ngắt/thu hồi từ xa chưa được quan sát trên tài khoản thật.

## Chuẩn bị

- Dùng bản build chứa thay đổi và ghi commit cùng trạng thái working tree được kiểm tra.
- Dùng bản cài thử riêng hoặc bản cài đã được người vận hành chọn. Giữ nguyên volume cuộc họp;
  không chạy `docker compose down -v` để thử restart hoặc ngắt kết nối.
- Kiểm tra cổng app chỉ publish trên `127.0.0.1`, volume `provider` chỉ gắn vào app và access log
  không ghi query callback. Trình duyệt phải ở cùng máy chạy Docker.
- Mở access link của bản cài. Không ghi token localhost hoặc toàn bộ access link vào biên bản.

## Thực hiện

1. Mở **ChatGPT**, chọn **Continue with ChatGPT** và hoàn thành đăng nhập. Ghi loại gói và kết quả
   cấp quyền dùng gói, không ghi email, subject, client ID hay token.
2. Xác nhận callback trở về HTTP `127.0.0.1` tại `/auth/chatgpt/callback`, UI hiển thị tài khoản
   đã kết nối. URL đăng nhập hoặc callback có thể chứa dữ liệu nhạy cảm; không sao chép vào báo cáo.
3. Chọn model và effort từ catalog, bấm **Lưu mô hình và effort**. Ghi đúng model ID và effort.
4. Bấm **Chạy kiểm tra bằng dữ liệu tổng hợp** đúng một lần. Xác nhận ứng dụng nhận sự kiện hoàn
   tất và đầu ra đúng schema. Nếu có lỗi, ghi mã lỗi đã làm sạch và thời điểm; không tự thử model
   khác hoặc bật API billing. Mỗi lần thử lại phải là thao tác chủ động của người vận hành.
5. Restart app container của bản cài thử. Xác nhận phiên và model đã chọn còn được giữ. Nếu cần
   kiểm tra refresh thật, đợi gần hết hạn access token rồi tải lại catalog; không chỉnh credential
   thủ công. Ghi rõ refresh thật đã quan sát hay chưa.
6. Khi không có kiểm chứng đang chạy, bấm **Ngắt kết nối**. Xác nhận UI trở về chưa kết nối,
   không thể dùng phiên cũ qua ứng dụng và cuộc họp vẫn còn. Ghi kết quả thu hồi từ xa. Nếu chưa
   xác nhận được, ngắt quyền ứng dụng tại [ChatGPT Settings → Usage](https://chatgpt.com/settings/usage).
7. Đăng nhập lại khi cần và xác nhận có thể dùng đăng ký đã giữ. Hủy một lượt đăng nhập trước
   callback để kiểm tra UI hủy; các ca hết hạn, callback muộn và race được kiểm tra tự động.

## Biên bản không chứa secret

| Mục | Kết quả |
| --- | --- |
| Thời điểm UTC | 2026-10-19 00:19:17 (lần kiểm chứng tổng hợp thành công) |
| Commit / trạng thái mã nguồn | Working tree của issue #7, trước commit review |
| Image / cấu hình cổng Docker | `asr-en-vi:issue7-effort-preview`, `127.0.0.1:18765` |
| Loại gói và quyền dùng gói đã cấp | Người vận hành xác nhận đăng nhập và dùng được Luna; không ghi loại gói |
| Callback qua Docker | Người vận hành hoàn tất đăng nhập qua bản preview; không lưu URL callback |
| Model ID và effort đã chọn | `gpt-5.6-luna`, `max` |
| Một yêu cầu tổng hợp, schema và hoàn tất stream | Provider đã ghi `verification` cho `gpt-5.6-luna` / `max` sau khi kiểm tra đầu ra hợp lệ |
| Mã lỗi đã làm sạch nếu có | Không có lỗi trong lần kiểm chứng thành công này |
| Phiên và lựa chọn qua restart | Còn kết nối và giữ model/effort sau khi thay app container với cùng provider volume |
| Refresh thật | Chưa quan sát |
| Ngắt kết nối / thu hồi từ xa / cuộc họp còn nguyên | Chưa kiểm chứng thật |

## Nguồn giao thức

- [Đăng ký và đăng nhập](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Tài khoản, refresh và thu hồi phiên](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [Catalog và Responses API](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Giới hạn preview](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

Ứng dụng gửi inference với `store: false`, `stream: true`, chờ `response.completed` và kiểm tra
JSON. Phản hồi lỗi hoặc stream bị ngắt không được coi là thành công dù đã nhận một phần văn bản.

Nếu hủy hoặc từ chối callback sau khi OAuth đã cấp token, ứng dụng thử thu hồi phiên vừa nhận
với giới hạn thời gian rồi loại bỏ credential local. Khi mạng/provider không xác nhận thu hồi,
quyền ứng dụng có thể còn hiển thị ở ChatGPT; kiểm tra và thu hồi tại **Cài đặt → Mức sử dụng**.
