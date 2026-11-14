# T01 · Ablation: random / greedy baseline / PoC

> ⚠️ **SỐ GẦN ĐÚNG, KHÔNG PHẢI ĐIỂM CHÍNH THỨC.** Repo học viên không có `gt/`, nên tag dùng để chấm là tag **nhìn thấy** trong `candidates.csv` (có nhiễu, `unknown` chỉ khớp ô `*`). Chạy qua đúng evaluator chuẩn `eval_t01`, nhưng không dán vào Bảng 1. Điểm chính thức do giảng viên chạy với GT.
>
> Thiên lệch: PoC chọn clip dựa trên chính các tag nhìn thấy này, còn random baseline thì không, nên số proxy của PoC **thiên lạc quan** và Δ PoC − Baseline bên dưới có thể **lớn hơn thực tế**: chấm bằng tag đã kiểm chứng có thể cho Δ nhỏ hơn (metadata sai → khai khống coverage).

Sinh bởi script, không sửa tay: `python -m src.t01_slices --run random=out/baseline/pick.csv --run greedy_plain=out/ablation/greedy_plain/pick.csv --run greedy_cost=out/ablation/greedy_cost/pick.csv --run poc=out/ablation/poc/pick.csv --run greedy_unknown_wild=out/ablation/greedy_unknown_wild/pick.csv --config configs/lab.yaml --fixture fixtures\t01_coverage --visible-proxy --out out\ablation\slices.md`  
git `eccc4ea` · 2026-11-14 21:46

## Kiểm tra pick.csv (đúng K dòng, K clip_id khác nhau, thuộc pool)

| Run | File | K | Kết quả |
|---|---|---:|---|
| random | `out/baseline/pick.csv` | 30 | OK |
| greedy_plain | `out/ablation/greedy_plain/pick.csv` | 30 | OK |
| greedy_cost | `out/ablation/greedy_cost/pick.csv` | 30 | OK |
| poc | `out/ablation/poc/pick.csv` | 30 | OK |
| greedy_unknown_wild | `out/ablation/greedy_unknown_wild/pick.csv` | 30 | OK |

## Bảng theo budget (K dòng đầu theo `rank`)

| Run | K | Weighted Coverage@K | Σw phủ | Ô phủ | Hard: ô phủ = Rare Recall [Wilson 95%] | Hard Σw | Non-hard Σw | Trùng kịch bản | Phút / ô phủ | Ô còn thiếu (**hard**) |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| random | 10 | 0.0833 | 4/48 | 2/15 | 0/4 = 0.00 [0.00, 0.49] | 0/18 | 4/30 | 0 | 57.50 | C02, C03, C04, C05, C06, **C08**, **C09**, **C10**, **C11**, C12, C13, C14, C15 |
| random | 20 | 0.2708 | 13/48 | 5/15 | 1/4 = 0.25 [0.05, 0.70] | 5/18 | 8/30 | 4 | 34.00 | C02, C04, C05, C06, **C08**, **C09**, **C11**, C13, C14, C15 |
| random | 30 | 0.3750 | 18/48 | 7/15 | 1/4 = 0.25 [0.05, 0.70] | 5/18 | 13/30 | 12 | 33.14 | C05, C06, **C08**, **C09**, **C11**, C13, C14, C15 |
| greedy_plain | 10 | 0.7292 | 35/48 | 10/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 17/30 | 0 | 7.70 | C01, C03, C13, C14, C15 |
| greedy_plain | 20 | 0.8125 | 39/48 | 13/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 21/30 | 1 | 13.54 | C13, C15 |
| greedy_plain | 30 | 0.8125 | 39/48 | 13/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 21/30 | 7 | 20.46 | C13, C15 |
| greedy_cost | 10 | 0.7292 | 35/48 | 10/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 17/30 | 0 | 5.30 | C01, C03, C13, C14, C15 |
| greedy_cost | 20 | 0.8125 | 39/48 | 13/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 21/30 | 1 | 11.23 | C13, C15 |
| greedy_cost | 30 | 0.8125 | 39/48 | 13/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 21/30 | 8 | 18.46 | C13, C15 |
| poc | 10 | 0.7292 | 35/48 | 10/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 17/30 | 0 | 5.30 | C01, C03, C13, C14, C15 |
| poc | 20 | 0.8125 | 39/48 | 13/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 21/30 | 5 | 10.00 | C13, C15 |
| poc | 30 | 0.8125 | 39/48 | 13/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 21/30 | 7 | 16.46 | C13, C15 |
| greedy_unknown_wild | 10 | 0.4167 | 20/48 | 6/15 | 3/4 = 0.75 [0.30, 0.95] | 14/18 | 6/30 | 0 | 13.83 | C03, C04, C05, C06, **C11**, C12, C13, C14, C15 |
| greedy_unknown_wild | 20 | 0.4375 | 21/48 | 7/15 | 3/4 = 0.75 [0.30, 0.95] | 14/18 | 7/30 | 3 | 26.71 | C04, C05, C06, **C11**, C12, C13, C14, C15 |
| greedy_unknown_wild | 30 | 0.5833 | 28/48 | 9/15 | 4/4 = 1.00 [0.51, 1.00] | 18/18 | 10/30 | 8 | 30.11 | C05, C06, C12, C13, C14, C15 |

Hard slice = 4 ô `is_hard = 1` (C08–C11, Σw = 18). Non-hard = 11 ô (Σw = 30). Mẫu số Σw = 48 cố định, gồm cả ô pool không phủ nổi. N rất nhỏ (4 ô hard), nên Wilson CI rất rộng: đọc số thô trước, % sau.

## Δ so với greedy_plain (baseline mạnh), chênh lệch tuyệt đối

| Run | K | Δ Σw phủ (/48) | Δ ô phủ (/15) | Δ ô hard (/4) | Δ trùng kịch bản | Δ phút / ô phủ |
|---|---:|---:|---:|---:|---:|---:|
| random | 10 | -31 | -8 | -4 | +0 | +49.80 |
| random | 20 | -26 | -8 | -3 | +3 | +20.46 |
| random | 30 | -21 | -6 | -3 | +5 | +12.68 |
| greedy_cost | 10 | +0 | +0 | +0 | +0 | -2.40 |
| greedy_cost | 20 | +0 | +0 | +0 | +0 | -2.31 |
| greedy_cost | 30 | +0 | +0 | +0 | +1 | -2.00 |
| poc | 10 | +0 | +0 | +0 | +0 | -2.40 |
| poc | 20 | +0 | +0 | +0 | +4 | -3.54 |
| poc | 30 | +0 | +0 | +0 | +0 | -4.00 |
| greedy_unknown_wild | 10 | -15 | -4 | -1 | +0 | +6.13 |
| greedy_unknown_wild | 20 | -18 | -6 | -1 | +2 | +13.18 |
| greedy_unknown_wild | 30 | -11 | -4 | +0 | +1 | +9.65 |

Δ = 0 trên coverage nghĩa là quy tắc đó **không** làm tăng coverage so với greedy thuần; giá trị của nó (nếu có) nằm ở chi phí, độ đa dạng hoặc dự phòng cho ô mong manh.

`greedy_unknown_wild` bị visible proxy phạt **theo cấu tạo**: nó chọn clip vì coi `unknown` khớp, còn proxy chấm `unknown` là không khớp. Số của nó ở đây chỉ cho thấy coverage *tự tin* bị thổi phồng thế nào; điểm thật của nó chỉ biết được khi chấm bằng tag đã kiểm chứng.

## Chi phí quay/duyệt theo budget (tag nhìn thấy)

| Run | Tổng phút K=10 | Tổng phút K=20 | Tổng phút K=30 | Clip chọn vì marginal gain > 0 |
|---|---:|---:|---:|---:|
| random | 115 | 170 | 232 | n/a |
| greedy_plain | 77 | 176 | 266 | 13 |
| greedy_cost | 53 | 146 | 240 | 13 |
| poc | 53 | 130 | 214 | 13 |
| greedy_unknown_wild | 83 | 187 | 271 | 10 |

## Holdout (25 clip, K = 6) — luôn là tag nhìn thấy (repo học viên không có GT holdout)

| Run | Weighted Coverage (visible) | Ô hard phủ | Trùng kịch bản | Tổng phút | Ô không thể phủ |
|---|---:|---:|---:|---:|---|
| greedy_plain | 0.3958 | 2/4 | 0 | 53 | C02;C04;C07;C09;C10;C13;C15 |
| greedy_cost | 0.3958 | 2/4 | 0 | 45 | C02;C04;C07;C09;C10;C13;C15 |
| poc | 0.3958 | 2/4 | 0 | 45 | C02;C04;C07;C09;C10;C13;C15 |
| greedy_unknown_wild | 0.3333 | 2/4 | 0 | 51 | C02;C04;C07;C09;C10;C13;C15 |

Sinh bởi `python -m src.t01_ablation --visible-proxy --out reports/t01_ablation_visible_proxy.md`.
