# T01 · Metric theo budget K và hard slice

> ⚠️ **SỐ GẦN ĐÚNG, KHÔNG PHẢI ĐIỂM CHÍNH THỨC.** Repo học viên không có `gt/`, nên tag dùng để chấm là tag **nhìn thấy** trong `candidates.csv` (có nhiễu, `unknown` chỉ khớp ô `*`). Chạy qua đúng evaluator chuẩn `eval_t01`, nhưng không dán vào Bảng 1. Điểm chính thức do giảng viên chạy với GT.
>
> Thiên lệch: PoC chọn clip dựa trên chính các tag nhìn thấy này, còn random baseline thì không, nên số proxy của PoC **thiên lạc quan** và Δ PoC − Baseline bên dưới có thể **lớn hơn thực tế**: chấm bằng tag đã kiểm chứng có thể cho Δ nhỏ hơn (metadata sai → khai khống coverage).

Sinh bởi script, không sửa tay: `python -m src.t01_slices --run baseline=out/baseline/pick.csv --run poc=out/poc/pick.csv --visible-proxy --out reports/t01_slices_visible_proxy.md`  
git `f9fbb8c` · 2026-11-14 17:26

## Kiểm tra pick.csv (đúng K dòng, K clip_id khác nhau, thuộc pool)

| Run | File | K | Kết quả |
|---|---|---:|---|
| baseline | `out/baseline/pick.csv` | 30 | OK |
| poc | `out/poc/pick.csv` | 30 | OK |

## Bảng theo budget (K dòng đầu theo `rank`)

| Run | K | Weighted Coverage@K | Σw phủ | Ô phủ | Hard: ô phủ = Rare Recall [Wilson 95%] | Hard Σw | Non-hard Σw | Trùng kịch bản | Phút / ô phủ | Ô còn thiếu (**hard**) |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| baseline | 10 | 0.0833 | 4/48 | 2/15 | 0/4 = 0.00 [0.00, 0.49] | 0/18 | 4/30 | 0 | 57.50 | C02, C03, C04, C05, C06, **C08**, **C09**, **C10**, **C11**, C12, C13, C14, C15 |
| baseline | 20 | 0.2708 | 13/48 | 5/15 | 1/4 = 0.25 [0.05, 0.70] | 5/18 | 8/30 | 4 | 34.00 | C02, C04, C05, C06, **C08**, **C09**, **C11**, C13, C14, C15 |
| baseline | 30 | 0.3750 | 18/48 | 7/15 | 1/4 = 0.25 [0.05, 0.70] | 5/18 | 13/30 | 12 | 33.14 | C05, C06, **C08**, **C09**, **C11**, C13, C14, C15 |
| poc | 10 | 0.7292 | 35/48 | 10/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 17/30 | 0 | 5.30 | C01, C03, C13, C14, C15 |
| poc | 20 | 0.8125 | 39/48 | 13/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 21/30 | 5 | 10.00 | C13, C15 |
| poc | 30 | 0.8125 | 39/48 | 13/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 21/30 | 7 | 16.46 | C13, C15 |

Hard slice = 4 ô `is_hard = 1` (C08–C11, Σw = 18). Non-hard = 11 ô (Σw = 30). Mẫu số Σw = 48 cố định, gồm cả ô pool không phủ nổi. N rất nhỏ (4 ô hard), nên Wilson CI rất rộng: đọc số thô trước, % sau.

## PoC − Baseline (cùng pool, cùng K, chênh lệch tuyệt đối)

| K | Δ Σw phủ (điểm / 48) | Δ ô phủ (/15) | Δ ô hard (/4) | Hard slice kết luận được? |
|---:|---:|---:|---:|---|
| 10 | +31 | +8 | +4 | có: PoC phủ nhiều hơn |
| 20 | +26 | +8 | +3 | có: PoC phủ nhiều hơn |
| 30 | +21 | +6 | +3 | có: PoC phủ nhiều hơn |

Báo chênh lệch tuyệt đối, không báo % cải thiện (baseline có thể = 0). Theo metric contract: chênh ≤ 1 ô hard thì không kết luận PoC tốt hơn trên hard slice.
