"""T01 · Bảng metric theo budget K = 10/20/30 + hard slice cho baseline và PoC (QA/metric).

Mỗi K đều chấm bằng đúng evaluator chuẩn `src.metrics.tracks.eval_t01` (lấy K dòng đầu theo `rank` của pick.csv),
rồi tách hard slice (is_hard = 1) / non-hard từ bảng slice của evaluator. File này KHÔNG định nghĩa lại metric.

    # Chính thức: cần overlay giảng viên (fixtures/t01_coverage/gt/verified_tags.csv)
    python -m src.t01_slices --run baseline=out/baseline/pick.csv --run poc=out/poc/pick.csv \
        --out reports/t01_slices.md

    # Repo học viên (không có gt/): số GẦN ĐÚNG theo tag nhìn thấy trong candidates.csv, KHÔNG phải điểm chính thức
    python -m src.t01_slices --run baseline=out/baseline/pick.csv --run poc=out/poc/pick.csv --visible-proxy \
        --out reports/t01_slices_visible_proxy.md

Chấm K < 30 bằng tiền tố của pick K = 30 là hợp lệ: random baseline (điểm cố định theo seed) và greedy của PoC
đều cho pick K nhỏ là tiền tố của pick K lớn (có test chặn trong tests/test_t01_metric.py).
Exit code: 0 OK · 2 thiếu file / không có GT mà không bật --visible-proxy / pick.csv sai contract.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from .common.io import git_sha, resolve_config
from .metrics.estimation import wilson_ci
from .metrics.tracks import default_gt_path, eval_t01

FIXTURE = Path("fixtures/t01_coverage")
DIMS = ["route", "weather", "light", "object"]


# ====================================================================== kiểm tra pick
def check_pick(pick: pd.DataFrame, pool_ids, k: int) -> list[str]:
    """Các lỗi của pick.csv theo metric contract (danh sách rỗng = hợp lệ):
    đúng K dòng, K clip_id khác nhau, tất cả thuộc pool, `rank` (nếu có) là 1..K không trùng.
    Evaluator tự bỏ dòng trùng / clip lạ, nhưng nhóm coi đó là output lỗi: chúng làm phí budget."""
    if "clip_id" not in pick.columns:
        return ["thiếu cột clip_id"]
    ids = pick["clip_id"].astype(str)
    problems = []
    if len(ids) != k:
        problems.append(f"có {len(ids)} dòng, cần đúng K={k}")
    dup = sorted(set(ids[ids.duplicated()]))
    if dup:
        problems.append(f"clip_id bị trùng: {dup}")
    foreign = sorted(set(ids) - set(map(str, pool_ids)))
    if foreign:
        problems.append(f"clip_id không thuộc pool: {foreign}")
    if "rank" in pick.columns and sorted(pick["rank"].tolist()) != list(range(1, len(pick) + 1)):
        problems.append("cột rank không phải 1..N không trùng (không lấy được tiền tố K theo rank)")
    return problems


# ====================================================================== chấm theo budget
def slice_row(res, k: int) -> dict:
    """Một dòng của bảng: metric chuẩn của evaluator + hard / non-hard slice tách từ `res.slices`."""
    m = {x.name: x for x in res.metrics}
    sl = res.slices
    hard, soft = sl[sl["is_hard"] == 1], sl[sl["is_hard"] == 0]
    z, n_hard = int(hard["covered"].sum()), len(hard)
    lo, hi = wilson_ci(z, n_hard)
    wc = m["Weighted Coverage@K"]
    return {
        "k": k,
        "n_picks_scored": wc.n,
        "weighted_coverage": wc.value,
        "w_covered": wc.numerator,
        "w_total": wc.denominator,
        "cells_covered": int(sl["covered"].sum()),
        "cells_total": len(sl),
        "hard_cells_covered": z,
        "hard_cells_total": n_hard,
        "rare_recall": m["Rare-scenario Recall@K"].value,
        "rare_recall_wilson95": [round(lo, 4), round(hi, 4)],
        "hard_w_covered": float(hard.loc[hard["covered"] == 1, "weight"].sum()),
        "hard_w_total": float(hard["weight"].sum()),
        "nonhard_w_covered": float(soft.loc[soft["covered"] == 1, "weight"].sum()),
        "nonhard_w_total": float(soft["weight"].sum()),
        "duplicate_scenarios": m["Duplicate clips in K"].value,
        "cost_per_covered_cell": m["Cost per covered cell"].value,
        "missing_cells": sl.loc[sl["covered"] == 0, "cell_id"].tolist(),
        "missing_hard_cells": hard.loc[hard["covered"] == 0, "cell_id"].tolist(),
        "notes": res.notes,
    }


def evaluate_budgets(gt_path: Path, pred_path: Path, budgets) -> list[dict]:
    return [slice_row(eval_t01(Path(gt_path), Path(pred_path), {"k": int(b)}), int(b)) for b in budgets]


def build_visible_proxy(fixture_dir: Path, workdir: Path) -> Path:
    """Fixture tạm có gt/verified_tags.csv = tag NHÌN THẤY của candidates.csv, để chạy đúng evaluator chuẩn khi repo
    không có GT. Evaluator so chuỗi nên `unknown` chỉ khớp ô có `*`, trùng với quy tắc (a) của pipeline.
    Đây là số gần đúng: tag nhìn thấy có nhiễu, so với tag đã kiểm chứng có thể khai khống hoặc bỏ sót coverage."""
    for f in ("targets.csv", "candidates.csv"):
        shutil.copy(fixture_dir / f, workdir / f)
    (workdir / "gt").mkdir()
    gt = workdir / "gt" / "verified_tags.csv"
    pd.read_csv(fixture_dir / "candidates.csv")[["clip_id", *DIMS]].to_csv(gt, index=False)
    return gt


# ====================================================================== markdown
def _n(x) -> str:
    return "n/a" if x is None else f"{x:g}"


def _md_table(rows: list[dict]) -> str:
    out = ["| Run | K | Weighted Coverage@K | Σw phủ | Ô phủ | Hard: ô phủ = Rare Recall [Wilson 95%] "
           "| Hard Σw | Non-hard Σw | Trùng kịch bản | Phút / ô phủ | Ô còn thiếu (**hard**) |",
           "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|"]
    for r in rows:
        lo, hi = r["rare_recall_wilson95"]
        hard = set(r["missing_hard_cells"])
        miss = ", ".join(f"**{c}**" if c in hard else c for c in r["missing_cells"]) or "—"
        cost = r["cost_per_covered_cell"]
        out.append(
            f"| {r['run']} | {r['k']} | {r['weighted_coverage']:.4f} | {_n(r['w_covered'])}/{_n(r['w_total'])} "
            f"| {r['cells_covered']}/{r['cells_total']} "
            f"| {r['hard_cells_covered']}/{r['hard_cells_total']} = {r['rare_recall']:.2f} [{lo:.2f}, {hi:.2f}] "
            f"| {_n(r['hard_w_covered'])}/{_n(r['hard_w_total'])} | {_n(r['nonhard_w_covered'])}/{_n(r['nonhard_w_total'])} "
            f"| {_n(r['duplicate_scenarios'])} | {'n/a' if cost is None else f'{cost:.2f}'} | {miss} |")
    return "\n".join(out)


def _md_delta(rows: list[dict]) -> str:
    by = {(r["run"], r["k"]): r for r in rows}
    ks = sorted({r["k"] for r in rows if ("baseline", r["k"]) in by and ("poc", r["k"]) in by})
    if not ks:
        return ""
    out = ["## PoC − Baseline (cùng pool, cùng K, chênh lệch tuyệt đối)", "",
           "| K | Δ Σw phủ (điểm / 48) | Δ ô phủ (/15) | Δ ô hard (/4) | Hard slice kết luận được? |",
           "|---:|---:|---:|---:|---|"]
    for k in ks:
        b, p = by[("baseline", k)], by[("poc", k)]
        dh = p["hard_cells_covered"] - b["hard_cells_covered"]
        verdict = "không: \\|Δ\\| ≤ 1 ô hard" if abs(dh) <= 1 else ("có: PoC phủ nhiều hơn" if dh > 0 else "có: PoC phủ ít hơn")
        out.append(f"| {k} | {p['w_covered'] - b['w_covered']:+g} | {p['cells_covered'] - b['cells_covered']:+d} "
                   f"| {dh:+d} | {verdict} |")
    out += ["", "Báo chênh lệch tuyệt đối, không báo % cải thiện (baseline có thể = 0). "
                "Theo metric contract: chênh ≤ 1 ô hard thì không kết luận PoC tốt hơn trên hard slice."]
    return "\n".join(out)


def render_md(rows: list[dict], checks: list[dict], source: str, gt_label: str, command: str) -> str:
    if source == "official":
        head = f"> Nguồn tag: **CHÍNH THỨC**, tag đã kiểm chứng `{gt_label}`."
    else:
        head = ("> ⚠️ **SỐ GẦN ĐÚNG, KHÔNG PHẢI ĐIỂM CHÍNH THỨC.** Repo học viên không có `gt/`, nên tag dùng để chấm là "
                "tag **nhìn thấy** trong `candidates.csv` (có nhiễu, `unknown` chỉ khớp ô `*`). Chạy qua đúng evaluator "
                "chuẩn `eval_t01`, nhưng không dán vào Bảng 1. Điểm chính thức do giảng viên chạy với GT.\n>\n"
                "> Thiên lệch: PoC chọn clip dựa trên chính các tag nhìn thấy này, còn random baseline thì không, nên số "
                "proxy của PoC **thiên lạc quan** và Δ PoC − Baseline bên dưới có thể **lớn hơn thực tế**: chấm bằng tag "
                "đã kiểm chứng có thể cho Δ nhỏ hơn (metadata sai → khai khống coverage).")
    check_rows = ["| Run | File | K | Kết quả |", "|---|---|---:|---|"]
    for c in checks:
        check_rows.append(f"| {c['run']} | `{c['pred']}` | {c['k']} | {'OK' if not c['problems'] else '; '.join(c['problems'])} |")
    parts = [
        "# T01 · Metric theo budget K và hard slice", "", head, "",
        f"Sinh bởi script, không sửa tay: `{command}`  ",
        f"git `{git_sha()}` · {datetime.now().strftime('%Y-%m-%d %H:%M')}", "",
        "## Kiểm tra pick.csv (đúng K dòng, K clip_id khác nhau, thuộc pool)", "", "\n".join(check_rows), "",
        "## Bảng theo budget (K dòng đầu theo `rank`)", "", _md_table(rows), "",
        "Hard slice = 4 ô `is_hard = 1` (C08–C11, Σw = 18). Non-hard = 11 ô (Σw = 30). Mẫu số Σw = 48 cố định, "
        "gồm cả ô pool không phủ nổi. N rất nhỏ (4 ô hard), nên Wilson CI rất rộng: đọc số thô trước, % sau.",
    ]
    delta = _md_delta(rows)
    if delta:
        parts += ["", delta]
    return "\n".join(parts) + "\n"


# ====================================================================== CLI
def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):              # Windows: console / pipe cp1252 không in được tiếng Việt
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="append", required=True, metavar="NAME=PICK_CSV",
                    help="vd. baseline=out/baseline/pick.csv (lặp lại cho nhiều run)")
    ap.add_argument("--config", default="configs/lab.yaml")
    ap.add_argument("--fixture", default=str(FIXTURE))
    ap.add_argument("--gt", help="tag đã kiểm chứng (mặc định fixtures/t01_coverage/gt/verified_tags.csv)")
    ap.add_argument("--visible-proxy", action="store_true",
                    help="không có GT: chấm bằng tag nhìn thấy (số gần đúng, ghi rõ trong output)")
    ap.add_argument("--budgets", type=int, nargs="+", help="mặc định params.budgets_to_try (10 20 30)")
    ap.add_argument("--k", type=int, help="K chính thức để kiểm pick.csv (mặc định params.k = 30)")
    ap.add_argument("--out", help="file markdown; JSON cùng tên được ghi kèm")
    a = ap.parse_args(argv)

    params = resolve_config(a.config, "t01").get("params") or {}
    k = int(a.k or params.get("k", 30))
    budgets = a.budgets or [int(b) for b in params.get("budgets_to_try", [10, 20, 30])]
    if max(budgets) > k:
        print(f"budget {max(budgets)} > K={k}: pick.csv chỉ có K dòng", file=sys.stderr)
        return 2
    fixture = Path(a.fixture)
    runs = []
    for item in a.run:
        name, sep, path = item.partition("=")
        if not sep or not name or not path:
            print(f"--run phải có dạng NAME=PATH, nhận được {item!r}", file=sys.stderr)
            return 2
        if not Path(path).exists():
            print(f"không thấy pick của run {name!r}: {path}", file=sys.stderr)
            return 2
        runs.append((name, Path(path)))

    pool = pd.read_csv(fixture / "candidates.csv")["clip_id"]
    checks = [{"run": n, "pred": p.as_posix(), "k": k, "problems": check_pick(pd.read_csv(p, dtype={"clip_id": str}), pool, k)}
              for n, p in runs]
    for c in checks:
        print(f"check {c['run']}: {'OK' if not c['problems'] else c['problems']}")
    if any(c["problems"] for c in checks):
        print("pick.csv sai contract: sửa pipeline trước khi báo metric", file=sys.stderr)
        return 2

    gt = Path(a.gt) if a.gt else default_gt_path("t01")
    with tempfile.TemporaryDirectory() as tmp:
        if gt.exists():
            source, gt_label = "official", gt.as_posix()
        elif a.visible_proxy:
            source, gt_label = "visible_proxy", f"{(fixture / 'candidates.csv').as_posix()} (tag nhìn thấy)"
            gt = build_visible_proxy(fixture, Path(tmp))
        else:
            print(f"không thấy GT: {gt}\nRepo học viên không có gt/. Thêm --visible-proxy để xem số gần đúng "
                  "theo tag nhìn thấy (không phải điểm chính thức).", file=sys.stderr)
            return 2
        rows = [{"run": n, **r} for n, p in runs for r in evaluate_budgets(gt, p, budgets)]

    command = "python -m src.t01_slices " + " ".join(argv if argv is not None else sys.argv[1:])
    md = render_md(rows, checks, source, gt_label, command)
    print(md)
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        payload = {"track": "t01", "source": source, "gt": gt_label, "k": k, "budgets": budgets,
                   "git_sha": git_sha(), "command": command, "checks": checks, "rows": rows}
        out.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out} + {out.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
