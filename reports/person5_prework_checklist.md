# Người 5 — trạng thái việc report/review

## Đã hoàn thành sau khi cập nhật nhánh

- [x] Xác nhận workspace ở `feat/report`, khớp `origin/feat/report`, HEAD `6475a2a`.
- [x] Đọc output T01 đã tích hợp: thuật toán greedy, config G0001/T01, metric contract và data analysis.
- [x] Chạy random baseline và PoC offline; cả hai trả exit 0, pick K=30 hợp đồng.
- [x] Sinh lại báo cáo slices visible-proxy cho K=10/20/30; ghi rõ không phải official score do thiếu verified GT.
- [x] Cập nhật report nhóm với kết quả baseline/PoC, failure cases C13/C15, fragile cells C08/C09, holdout proxy, decision REWORK và caveat.
- [x] Cập nhật review/capture worksheet và dàn ý demo 4 slide.

## Còn cần trước khi nộp

- [ ] Domain reviewer thực sự xem/kiểm tra C08 `clip_101`, C09 `clip_108`, C13 candidate khả nghi; ký quyết định, ghi reviewer/note và lưu audit evidence. Worksheet hiện vẫn `PENDING`.
- [ ] Bổ sung kết quả verified-tag evaluation từ giảng viên (GT không có trong checkout). Visible proxy không được trình bày như điểm chính thức.
- [ ] Chạy `pytest -q` và thêm kết quả vào report.
- [x] Ghi Git author/email và commit evidence của Member 5 (`bac`, `kieubac2006@gmail.com`, `6475a2a`) vào contribution sheet.
- [x] Ghi tên report `kieubac2006` và presenter status `No`; Members 1–4 được ghi từ Git history/contribution notes.
- [ ] Bổ sung tag demo/final và ngày deadline.

## Cách đọc worksheet

`reports/t01_review_capture_plan.csv` chọn đúng 3 ô ưu tiên để review và đề xuất hành động: C09 (kiểm tra; tạo clip backup nếu bị bác), C13 và C15 (quay nếu không xác minh được clip phù hợp). C08 là hard cell khác chỉ có một candidate visible nên được ghi thành rủi ro bổ sung trong report. Các decision là đề xuất, chưa phải human approval.
