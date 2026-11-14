"""T01 · Ablation: random vs greedy baseline vs từng quy tắc của PoC, cùng pool / K / seed.

Sinh pick K=30 cho từng biến thể vào out/ablation/<name>/pick.csv rồi chấm bằng `src.t01_slices`
(đúng evaluator chuẩn `eval_t01`, budget 10/20/30). Có overlay GT của giảng viên thì là điểm chính thức;
không có thì phải thêm --visible-proxy (số gần đúng theo tag nhìn thấy, ghi rõ trong output).

Biến thể (mỗi bước thêm đúng một quy tắc):
  random              src.examples.random_baseline, seed 42 (đọc từ out/baseline/pick.csv)
  greedy_plain        greedy sách giáo khoa: tie-break clip_id, hết gain thì lấp theo clip_id
  greedy_cost         + tie-break theo cost_min (quy tắc (b) của PoC)
  poc                 + lấp chỗ theo quy tắc (c) = src.pipeline.greedy_select
  greedy_unknown_wild greedy_plain nhưng coi `unknown` là wildcard (bỏ quy tắc (a)) -> đo rủi ro khai khống

    python -m src.main --track t01 --pipeline src.examples.random_baseline --output out/baseline --run-name baseline --offline --seed 42
    python -m src.t01_ablation --visible-proxy --out reports/t01_ablation_visible_proxy.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from .common.io import resolve_config
from .examples.greedy_baseline import plain_greedy
from .pipeline import greedy_select, visible_metrics
from . import t01_slices

FIXTURE = Path("fixtures/t01_coverage")


def variants(cands: pd.DataFrame, targets: pd.DataFrame, k: int, fragile_max: int) -> dict[str, pd.DataFrame]:
    return {
        "greedy_plain": plain_greedy(cands, targets, k),
        "greedy_cost": plain_greedy(cands, targets, k, cost_tiebreak=True),
        "poc": greedy_select(cands, targets, k, fragile_max),
        "greedy_unknown_wild": plain_greedy(cands, targets, k, unknown_is_wildcard=True),
    }


def _holdout_md(fixture: Path, targets: pd.DataFrame, k_hold: int, fragile_max: int) -> str:
    hold = pd.read_csv(fixture / "holdout_candidates.csv")
    out = [f"## Holdout (25 clip, K = {k_hold}) — luôn là tag nhìn thấy (repo học viên không có GT holdout)", "",
           "| Run | Weighted Coverage (visible) | Ô hard phủ | Trùng kịch bản | Tổng phút | Ô không thể phủ |",
           "|---|---:|---:|---:|---:|---|"]
    for name, p in variants(hold, targets, k_hold, fragile_max).items():
        m = visible_metrics(p, hold, targets)
        out.append(f"| {name} | {m['weighted_coverage_visible']:.4f} | {m['hard_cells_covered']}/{m['hard_cells_total']} "
                   f"| {m['duplicate_scenarios']} | {m['cost_min_total']:g} | {m['uncoverable_cells'] or '—'} |")
    return "\n".join(out)


def _delta_md(rows: list[dict], budgets) -> str:
    """Δ so với greedy_plain (baseline mạnh): mỗi quy tắc của PoC thêm được bao nhiêu."""
    by = {(r["run"], r["k"]): r for r in rows}
    out = ["## Δ so với greedy_plain (baseline mạnh), chênh lệch tuyệt đối", "",
           "| Run | K | Δ Σw phủ (/48) | Δ ô phủ (/15) | Δ ô hard (/4) | Δ trùng kịch bản | Δ phút / ô phủ |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for name in ("random", "greedy_cost", "poc", "greedy_unknown_wild"):
        for b in budgets:
            g, r = by.get(("greedy_plain", b)), by.get((name, b))
            if not g or not r:
                continue
            dc = (r["cost_per_covered_cell"] or 0) - (g["cost_per_covered_cell"] or 0)
            out.append(f"| {name} | {b} | {r['w_covered'] - g['w_covered']:+g} | {r['cells_covered'] - g['cells_covered']:+d} "
                       f"| {r['hard_cells_covered'] - g['hard_cells_covered']:+d} "
                       f"| {(r['duplicate_scenarios'] or 0) - (g['duplicate_scenarios'] or 0):+g} | {dc:+.2f} |")
    out += ["", "Δ = 0 trên coverage nghĩa là quy tắc đó **không** làm tăng coverage so với greedy thuần; "
                "giá trị của nó (nếu có) nằm ở chi phí, độ đa dạng hoặc dự phòng cho ô mong manh.",
            "",
            "`greedy_unknown_wild` bị visible proxy phạt **theo cấu tạo**: nó chọn clip vì coi `unknown` khớp, còn proxy "
            "chấm `unknown` là không khớp. Số của nó ở đây chỉ cho thấy coverage *tự tin* bị thổi phồng thế nào; "
            "điểm thật của nó chỉ biết được khi chấm bằng tag đã kiểm chứng."]
    return "\n".join(out)


def _cost_md(picks: dict[str, pd.DataFrame], cands: pd.DataFrame, targets: pd.DataFrame, budgets) -> str:
    out = ["## Chi phí quay/duyệt theo budget (tag nhìn thấy)", "",
           "| Run | " + " | ".join(f"Tổng phút K={b}" for b in budgets) + " | Clip chọn vì marginal gain > 0 |",
           "|---|" + "---:|" * (len(budgets) + 1)]
    for name, p in picks.items():
        cells = [f"{visible_metrics(p[p['rank'] <= b], cands, targets)['cost_min_total']:g}" for b in budgets]
        n_gain = int((p["reason"] == "greedy_gain").sum()) if "reason" in p.columns else "n/a"
        out.append(f"| {name} | " + " | ".join(cells) + f" | {n_gain} |")
    return "\n".join(out)


def main(argv=None) -> int:
    import argparse
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/lab.yaml")
    ap.add_argument("--fixture", default=str(FIXTURE))
    ap.add_argument("--random", default="out/baseline/pick.csv", help="pick của random baseline (seed 42)")
    ap.add_argument("--workdir", default="out/ablation")
    ap.add_argument("--visible-proxy", action="store_true")
    ap.add_argument("--out", help="file markdown (JSON cùng tên ghi kèm cho bảng chính)")
    a = ap.parse_args(argv)

    params = resolve_config(a.config, "t01").get("params") or {}
    k = int(params.get("k", 30))
    fragile_max = int(params.get("fragile_max", 2))
    budgets = [int(b) for b in params.get("budgets_to_try", [10, 20, 30])]
    fixture = Path(a.fixture)
    if not Path(a.random).exists():
        print(f"không thấy {a.random}: chạy random baseline trước (xem docstring)", file=sys.stderr)
        return 2
    cands = pd.read_csv(fixture / "candidates.csv")
    targets = pd.read_csv(fixture / "targets.csv")

    picks = {"random": pd.read_csv(a.random)}
    runs = [f"random={Path(a.random).as_posix()}"]
    for name, p in variants(cands, targets, k, fragile_max).items():
        path = Path(a.workdir) / name / "pick.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        p.to_csv(path, index=False)
        picks[name] = p
        runs.append(f"{name}={path.as_posix()}")

    slice_args = [x for r in runs for x in ("--run", r)] + ["--config", a.config, "--fixture", a.fixture]
    if a.visible_proxy:
        slice_args.append("--visible-proxy")
    tmp_md = Path(a.workdir) / "slices.md"
    rc = t01_slices.main(slice_args + ["--out", str(tmp_md)])
    if rc != 0:
        return rc
    md = tmp_md.read_text(encoding="utf-8").replace("# T01 · Metric theo budget K và hard slice",
                                                    "# T01 · Ablation: random / greedy baseline / PoC", 1)
    md += "\n" + _cost_md(picks, cands, targets, budgets) + "\n\n" + _holdout_md(fixture, targets, int(params.get("k_holdout", 6)), fragile_max) + "\n"
    rows = json.loads(tmp_md.with_suffix(".json").read_text(encoding="utf-8"))["rows"]
    md = md.replace("\n## Chi phí", "\n" + _delta_md(rows, budgets) + "\n\n## Chi phí", 1)
    md += "\nSinh bởi `python -m src.t01_ablation " + " ".join(argv if argv is not None else sys.argv[1:]) + "`.\n"
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        out.with_suffix(".json").write_text(tmp_md.with_suffix(".json").read_text(encoding="utf-8"), encoding="utf-8")
        print(f"wrote {out} + {out.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
