"""T01 · Baseline mạnh: greedy weighted set cover "sách giáo khoa" (handout §8 yêu cầu so PoC với greedy, không chỉ random).

Khác PoC (`src.pipeline.greedy_select`) ở đúng 3 chỗ — mỗi chỗ là một tham số để làm ablation:
  * tie-break: chỉ theo `clip_id` (PoC: gain -> cost_min thấp -> clip_id)          -> `cost_tiebreak`
  * lấp chỗ khi không còn gain: lấy clip kế tiếp theo `clip_id` (PoC: quy tắc (c):
    backup ô mong manh -> clip unknown có thể phủ -> risk high, tránh trùng kịch bản) -> (không có ở đây)
  * `unknown`: mặc định giống PoC (không khớp giá trị cụ thể); `unknown_is_wildcard=True` là biến thể
    "lạc quan" coi unknown khớp mọi giá trị — dùng để đo rủi ro metadata khai khống coverage.
Tất định, không dùng ngẫu nhiên. Pick K nhỏ là tiền tố của pick K lớn (chọn tuần tự).

    python -m src.main --track t01 --pipeline src.examples.greedy_baseline --output out/greedy --run-name greedy --offline --seed 42
"""
from __future__ import annotations

import pandas as pd

from ..common.context import RunContext
from ..common.decision import Decision, write_decision
from ..common.review import make_review_queue, write_review_queue
from ..metrics.tracks import get_track
from ..pipeline import cover_map, load, visible_metrics


def plain_greedy(cands: pd.DataFrame, targets: pd.DataFrame, k: int, cost_tiebreak: bool = False,
                 unknown_is_wildcard: bool = False) -> pd.DataFrame:
    """Chọn `k` clip: mỗi vòng lấy clip có tổng weight ô CHƯA phủ lớn nhất; hết gain thì lấp theo clip_id.
    Trả về clip_id, rank, score (= marginal gain lúc chọn), reason, covers."""
    k = min(int(k), len(cands))
    w = dict(zip(targets["cell_id"], targets["weight"].astype(float)))
    covers = cover_map(cands, targets, unknown_is_wildcard=unknown_is_wildcard)
    cost = dict(zip(cands["clip_id"], cands["cost_min"].astype(float)))
    order = sorted(cands["clip_id"])
    covered: set = set()
    chosen: list[str] = []
    rows: list[dict] = []
    while len(chosen) < k:
        best = None
        for cid in order:
            if cid in chosen:
                continue
            gain = sum(w[c] for c in covers[cid] - covered)
            if gain <= 0:
                continue
            key = (-gain, cost[cid] if cost_tiebreak else 0.0, cid)
            if best is None or key < best[0]:
                best = (key, cid, gain)
        if best is None:
            break
        _, cid, gain = best
        chosen.append(cid)
        covered |= covers[cid]
        rows.append({"clip_id": cid, "rank": len(chosen), "score": gain, "reason": "greedy_gain",
                     "covers": ";".join(sorted(covers[cid]))})
    for cid in order:                                     # hết gain: lấp chỗ theo clip_id, không có quy tắc nào
        if len(chosen) >= k:
            break
        if cid not in chosen:
            chosen.append(cid)
            rows.append({"clip_id": cid, "rank": len(chosen), "score": 0.0, "reason": "fill_by_id",
                         "covers": ";".join(sorted(covers[cid]))})
    return pd.DataFrame(rows, columns=["clip_id", "rank", "score", "reason", "covers"])


def run(ctx: RunContext) -> None:
    spec = get_track(ctx.track)
    if ctx.track != "t01":
        raise NotImplementedError("greedy_baseline chỉ dành cho t01")
    data = load(ctx)                                                    # 01 load (+ kiểm manifest)
    cands, targets = data["candidates"], data["targets"]
    k = int(ctx.param("k", 30))
    picks = plain_greedy(cands, targets, k)                             # 02 process
    ctx.stats["n_items"] = len(picks)
    ctx.stats["visible"] = visible_metrics(picks, cands, targets)
    q = make_review_queue(picks, "clip_id", "score", int(ctx.param("review_budget", 10)), reason_col="reason")
    write_review_queue(q, ctx.out("review_queue.csv"))                  # 03 rank
    picks.to_csv(ctx.out(spec.pred_file), index=False)                  # 04 review: baseline không có bước người duyệt
    ctx.audit.log(actor="pipeline", action="greedy_baseline_select", item_id="t01",
                  after={"k": k, **ctx.stats["visible"]}, reason="greedy sách giáo khoa: tie-break clip_id, lấp theo clip_id")
    write_decision(Decision(status="HOLD", reason_code="BASELINE_ONLY",                       # 05 decide
                            reason="Greedy baseline để so sánh với PoC; không dùng để ra quyết định thu dữ liệu.",
                            owner=ctx.config.get("owner", "baseline"), scope=ctx.track,
                            evidence=[str(ctx.out(spec.pred_file))], metrics=ctx.stats["visible"]),
                   ctx.out("decision.json"), ctx.out("decision_log.csv"))
