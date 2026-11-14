"""PIPELINE PoC CỦA NHÓM — đây là file nhóm sở hữu.

Hợp đồng lab gồm 5 bước tự động, chạy bằng `python -m src.main ...`:
    01 load      đọc đầu vào + kiểm tra nguồn gốc dữ liệu (manifest.csv)
    02 process   thuật toán / mô hình của nhóm (phần nghiên cứu)
    03 rank      xếp ưu tiên theo ngân sách review B cố định
    04 review    người duyệt: hàng chờ -> quyết định -> ghi đè + audit log
    05 decide    GO / HOLD / REWORK kèm reason_code + owner, ghi kết quả

T01 · Coverage Planner — greedy weighted set cover (phủ tập có trọng số), tie-break theo chi phí.

QUY TẮC THUẬT TOÁN (chốt TRƯỚC khi xem bất kỳ kết quả đánh giá nào; không đổi về sau)
  (a) `unknown`   Tag ứng viên bằng `unknown` không bao giờ khớp giá trị cụ thể của ô mục tiêu
                  (chiều `*` của ô vẫn khớp). Clip như vậy không được "nhận" ô ở pha greedy
                  chính; chỉ dùng làm dự phòng ở bước lấp chỗ (c).
  (b) Tie-break   gain có trọng số cao nhất -> cost_min thấp nhất -> clip_id nhỏ nhất.
                  Hoàn toàn tất định: không dùng ngẫu nhiên (không cần ctx.rng).
  (c) Lấp chỗ     Greedy dừng khi không clip nào thêm được trọng số (có ô không thể phủ).
                  Các chỗ còn lại được lấp theo thứ tự ưu tiên:
                    1. clip dự phòng cho ô MONG MANH (<= `fragile_max` clip khớp, tối đa 2 clip/ô),
                    2. clip có tag `unknown` có thể phủ ô còn thiếu,
                    3. clip risk=high,
                  tránh lặp lại cùng một kịch bản; hòa thì xét như (b).
  Trọng số trong targets.csv không bao giờ bị sửa. Không bao giờ đọc gt/.

Đầu ra (out/<run>/): pick.csv (clip_id,rank,score,reason,...), coverage.csv (trạng thái từng ô,
theo tag planner nhìn thấy), coverage_by_budget.csv (budget 10/20/30), pick_holdout.csv (K=6),
review_queue.csv, decision.json.  LƯU Ý: mọi số coverage ghi ở đây được tính từ tag PLANNER NHÌN THẤY
(có nhiễu) — chỉ là số gần đúng, không phải điểm chính thức (điểm chính thức dùng tag đã kiểm chứng).
"""
from __future__ import annotations

from collections import Counter

import pandas as pd

from .common.context import RunContext
from .common.decision import Decision, write_decision
from .common.manifest import verify_manifest
from .common.review import load_review_decisions, make_review_queue, write_review_queue
from .metrics.tracks import get_track

DIMS = ["route", "weather", "light", "object"]
UNKNOWN = "unknown"
CAND_COLS = ["clip_id", *DIMS, "risk", "cost_min", "duration_s"]
TARGET_COLS = ["cell_id", *DIMS, "weight", "is_hard"]
RISK_RANK = {"high": 2, "med": 1, "low": 0}


# ====================================================================== thuật toán thuần
def match(clip: dict, cell: dict, unknown_is_wildcard: bool = False) -> bool:
    """True nếu `clip` phủ được `cell`. Dấu `*` trong ô khớp mọi giá trị.
    Quy tắc (a): giá trị `unknown` của clip KHÔNG khớp giá trị cụ thể của ô
    (trừ khi `unknown_is_wildcard`, chỉ dùng để tìm khả năng phủ *tiềm năng* khi lấp chỗ)."""
    for d in DIMS:
        want = cell[d]
        if want == "*":
            continue
        have = clip[d]
        if have == UNKNOWN:
            if unknown_is_wildcard:
                continue
            return False
        if have != want:
            return False
    return True


def cover_map(cands: pd.DataFrame, targets: pd.DataFrame, unknown_is_wildcard: bool = False) -> dict[str, set]:
    """clip_id -> tập cell_id mà clip đó phủ được."""
    cells = targets.to_dict("records")
    return {
        c["clip_id"]: {t["cell_id"] for t in cells if match(c, t, unknown_is_wildcard)}
        for c in cands.to_dict("records")
    }


def greedy_select(cands: pd.DataFrame, targets: pd.DataFrame, k: int, fragile_max: int = 2,
                  exclude: set | None = None) -> pd.DataFrame:
    """Chọn `k` clip (greedy weighted set cover). Trả về mỗi clip một dòng, theo thứ tự chọn:
    clip_id, rank, score, reason, phase, covers, relaxed_covers.
    Tất định. `exclude` = các clip_id không được chọn (ví dụ bị người duyệt từ chối)."""
    exclude = set(exclude or ())
    pool = cands[~cands["clip_id"].isin(exclude)].reset_index(drop=True)
    k = min(int(k), len(pool))
    w = dict(zip(targets["cell_id"], targets["weight"].astype(float)))
    strict = cover_map(pool, targets)
    relaxed = cover_map(pool, targets, unknown_is_wildcard=True)
    n_match = Counter(cell for cells in strict.values() for cell in cells)
    fragile = {c for c in w if n_match.get(c, 0) <= fragile_max}      # gồm cả ô không thể phủ (0 clip)
    info = pool.set_index("clip_id")
    scen = {cid: tuple(info.loc[cid, DIMS]) for cid in info.index}

    chosen: list[str] = []
    rows: list[dict] = []
    sel_count: Counter = Counter()          # ô -> số clip đã chọn phủ ô đó
    scen_count: Counter = Counter()         # kịch bản -> số clip đã chọn

    def commit(cid: str, score: float, reason: str, phase: str) -> None:
        chosen.append(cid)
        for cell in strict[cid]:
            sel_count[cell] += 1
        scen_count[scen[cid]] += 1
        rows.append({"clip_id": cid, "rank": len(chosen), "score": round(float(score), 6), "reason": reason,
                     "phase": phase, "covers": ";".join(sorted(strict[cid])),
                     "relaxed_covers": ";".join(sorted(relaxed[cid] - strict[cid]))})

    remaining = lambda: [c for c in pool["clip_id"] if c not in chosen]  # noqa: E731

    # ---- pha 1: greedy theo marginal gain có trọng số, tie-break (b)
    while len(chosen) < k:
        best = None
        for cid in remaining():
            gain = sum(w[c] for c in strict[cid] if sel_count[c] == 0)
            if gain <= 0:
                continue
            key = (-gain, float(info.loc[cid, "cost_min"]), cid)
            if best is None or key < best[0]:
                best = (key, cid, gain)
        if best is None:
            break
        commit(best[1], best[2], "greedy_gain", "greedy")

    # ---- pha 2: lấp các chỗ còn lại, quy tắc (c)
    while len(chosen) < k:
        best = None
        for cid in remaining():
            backup = sum(w[c] / (1 + sel_count[c]) for c in strict[cid] if c in fragile and sel_count[c] < 2)
            potential = sum(w[c] for c in (relaxed[cid] - strict[cid]) if sel_count[c] == 0)
            risk = RISK_RANK.get(str(info.loc[cid, "risk"]), 0)
            key = (-backup, -potential, -risk, scen_count[scen[cid]], float(info.loc[cid, "cost_min"]), cid)
            if best is None or key < best[0]:
                best = (key, cid, backup, potential, risk)
        _, cid, backup, potential, risk = best
        if backup > 0:
            reason = "backup_fragile"
        elif potential > 0:
            reason = "unknown_may_cover"
        elif risk == RISK_RANK["high"]:
            reason = "risk_high"
        else:
            reason = "fill_diverse"
        commit(cid, backup + potential, reason, "fill")
    return pd.DataFrame(rows, columns=["clip_id", "rank", "score", "reason", "phase", "covers", "relaxed_covers"])


def coverage_table(picks: pd.DataFrame, cands: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Trạng thái từng ô, tính từ TAG PLANNER NHÌN THẤY (số gần đúng). status:
    covered / fragile_single (chỉ 1 clip phủ, ô hiếm) / uncovered_but_candidate_exists /
    UNCOVERABLE (pool không có clip nào -> cần quay bổ sung)."""
    strict = cover_map(cands, targets)
    n_match = Counter(cell for cells in strict.values() for cell in cells)
    pick_ids = list(picks["clip_id"])
    rows = []
    for t in targets.to_dict("records"):
        by = [c for c in pick_ids if t["cell_id"] in strict[c]]
        if n_match.get(t["cell_id"], 0) == 0:
            status = "UNCOVERABLE"
        elif not by:
            status = "uncovered_but_candidate_exists"
        elif len(by) == 1 and n_match[t["cell_id"]] <= 2:
            status = "fragile_single"
        else:
            status = "covered"
        rows.append({**{c: t[c] for c in TARGET_COLS}, "visible_matches_in_pool": n_match.get(t["cell_id"], 0),
                     "n_picks_covering": len(by), "covering_clips": ";".join(by), "status": status})
    return pd.DataFrame(rows)


def visible_metrics(picks: pd.DataFrame, cands: pd.DataFrame, targets: pd.DataFrame) -> dict:
    """Các chỉ số gần đúng (theo tag nhìn thấy): coverage có trọng số, ô khó, trùng kịch bản, chi phí."""
    cov = coverage_table(picks, cands, targets)
    covered = cov[cov["n_picks_covering"] > 0]
    total_w = float(cov["weight"].sum())
    hard = cov[cov["is_hard"] == 1]
    info = cands.set_index("clip_id")
    ids = list(picks["clip_id"])
    scen = [tuple(info.loc[c, DIMS]) for c in ids]
    cost = float(info.loc[ids, "cost_min"].sum()) if ids else 0.0
    return {
        "k": len(ids),
        "weighted_coverage_visible": round(float(covered["weight"].sum()) / total_w, 4),
        "hard_cells_covered": int((hard["n_picks_covering"] > 0).sum()),
        "hard_cells_total": int(len(hard)),
        "duplicate_scenarios": len(scen) - len(set(scen)),
        "cost_min_total": cost,
        "cost_per_covered_cell": round(cost / max(1, len(covered)), 3),
        "uncoverable_cells": ";".join(cov.loc[cov["status"] == "UNCOVERABLE", "cell_id"]),
    }


# ====================================================================== 01 load
def _clean(df: pd.DataFrame, required: list[str], name: str, numeric: list[str]) -> pd.DataFrame:
    """Kiểm tra đủ cột, bỏ khoảng trắng thừa, ép các cột số về kiểu số."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{name} thiếu các cột bắt buộc {missing}")
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip()
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="raise")
    return df


def load(ctx: RunContext) -> dict:
    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems:
        ctx.audit.log(actor="pipeline", action="provenance_problems", item_id=str(manifest), after=problems[:20])
        if ctx.config.get("strict_provenance", True):
            raise ValueError(f"kiểm tra nguồn gốc dữ liệu thất bại ({len(problems)} vấn đề), vấn đề đầu tiên: {problems[:3]}")
    data = {"manifest": pd.read_csv(manifest) if manifest.exists() else None}
    if ctx.track == "t01":
        data["candidates"] = _clean(pd.read_csv(ctx.input_dir / "candidates.csv"), CAND_COLS, "candidates.csv",
                                    ["cost_min", "duration_s"])
        data["targets"] = _clean(pd.read_csv(ctx.input_dir / "targets.csv"), TARGET_COLS, "targets.csv",
                                 ["weight", "is_hard"])
        if data["candidates"]["clip_id"].duplicated().any():
            raise ValueError("candidates.csv có clip_id bị trùng")
        hold = ctx.input_dir / "holdout_candidates.csv"
        data["holdout"] = _clean(pd.read_csv(hold), CAND_COLS, "holdout_candidates.csv",
                                 ["cost_min", "duration_s"]) if hold.exists() else None
    return data


# ====================================================================== 02 process
def process(ctx: RunContext, data: dict) -> pd.DataFrame:
    spec = get_track(ctx.track)
    if ctx.track != "t01":
        raise NotImplementedError(
            f"Chưa cài process() cho {spec.track} ({spec.title}). Phải trả về DataFrame có tối thiểu các cột "
            f"{spec.pred_columns} (lưu thành out/{spec.pred_file}). Xem docs/tracks/{spec.track.upper()}.md"
        )
    cands, targets = data["candidates"], data["targets"]
    k = int(ctx.param("k", 30))
    fragile_max = int(ctx.param("fragile_max", 2))
    picks = greedy_select(cands, targets, k, fragile_max)
    info = cands.set_index("clip_id")
    picks["risk"] = picks["clip_id"].map(info["risk"])
    picks["cost_min"] = picks["clip_id"].map(info["cost_min"])

    # độ ưu tiên review: clip mang ô mong manh hoặc tag unknown cần người xem trước
    cov = coverage_table(picks, cands, targets)
    fragile_cells = set(cov.loc[(cov["visible_matches_in_pool"] <= fragile_max) &
                                (cov["visible_matches_in_pool"] > 0), "cell_id"])
    wmap = dict(zip(targets["cell_id"], targets["weight"].astype(float)))
    has_unk = picks["clip_id"].map(lambda c: UNKNOWN in info.loc[c, DIMS].tolist())
    picks["review_priority"] = [
        sum(wmap[x] for x in s.split(";") if x in fragile_cells) + (0.5 if u else 0.0)
        for s, u in zip(picks["covers"].fillna(""), has_unk)
    ]

    # ---- đầu ra phụ (số gần đúng, chỉ dùng tag nhìn thấy)
    cov.to_csv(ctx.out("coverage.csv"), index=False)
    budgets = ctx.param("budgets_to_try", [10, 20, 30])
    rows = []
    for b in budgets:
        m = visible_metrics(greedy_select(cands, targets, int(b), fragile_max), cands, targets)
        rows.append(m)
    pd.DataFrame(rows).to_csv(ctx.out("coverage_by_budget.csv"), index=False)
    if data.get("holdout") is not None:
        kh = int(ctx.param("k_holdout", 6))
        hp = greedy_select(data["holdout"], targets, kh, fragile_max)
        hp[["clip_id", "rank"]].to_csv(ctx.out("pick_holdout.csv"), index=False)
        ctx.stats["holdout_visible"] = visible_metrics(hp, data["holdout"], targets)
    ctx.stats["visible"] = visible_metrics(picks, cands, targets)
    ctx.audit.log(actor="pipeline", action="greedy_select", item_id="t01",
                  after={"k": k, **ctx.stats["visible"]}, reason="quy tắc (a)(b)(c) đã chốt trong docstring đầu file")
    return picks


# ====================================================================== 03 rank
def rank(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    """Hàng chờ review = các clip người duyệt nên xem trước (ô mong manh / tag unknown).
    Ngân sách lấy từ `review_budget` (mặc định 10); KHÔNG phải ngân sách chọn clip K."""
    budget = int(ctx.param("review_budget", 10))
    if ctx.track == "t01":
        q = make_review_queue(scored, id_col="clip_id", score_col="review_priority", budget=budget,
                              reason_col="reason")
    else:
        if "score" not in scored.columns:
            raise ValueError("rank(): đầu ra của process() cần cột số `score` (cao = review trước), "
                             "hoặc chỉnh rank() cho phù hợp track")
        q = make_review_queue(scored, id_col=scored.columns[0], score_col="score", budget=budget,
                              reason_col="reason" if "reason" in scored.columns else None)
    write_review_queue(q, ctx.out("review_queue.csv"))
    return q


# ====================================================================== 04 review
def review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame, data: dict | None = None) -> pd.DataFrame:
    """Nếu có out/review_queue_reviewed.csv thì áp dụng. Với T01, `reject` loại clip khỏi kế hoạch và
    clip tốt nhất kế tiếp thế chỗ (chạy lại greedy với clip bị loại); mọi thay đổi đều ghi vào audit log.
    Bản chọn gốc được giữ ở pick_raw.csv để có thể đối chiếu diff."""
    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    if not reviewed_path.exists():
        return scored
    reviewed = load_review_decisions(reviewed_path)
    ctx.stats["n_reviewed"] = len(reviewed)
    if ctx.track != "t01" or data is None:
        return scored
    rejected = set(reviewed.loc[reviewed["reviewer_decision"] == "reject", "item_id"].astype(str))
    if not rejected:
        return scored
    scored.to_csv(ctx.out("pick_raw.csv"), index=False)
    for r in reviewed[reviewed["reviewer_decision"] == "reject"].itertuples(index=False):
        ctx.audit.log(actor=r.reviewer, action="override:reject", item_id=str(r.item_id),
                      before="picked", after="excluded", reason=r.review_note)
    k = int(ctx.param("k", 30))
    new = greedy_select(data["candidates"], data["targets"], k, int(ctx.param("fragile_max", 2)), exclude=rejected)
    info = data["candidates"].set_index("clip_id")
    new["risk"] = new["clip_id"].map(info["risk"])
    new["cost_min"] = new["clip_id"].map(info["cost_min"])
    new["review_priority"] = 0.0
    ctx.stats["visible_after_review"] = visible_metrics(new, data["candidates"], data["targets"])
    return new


# ====================================================================== 05 decide
def decide(ctx: RunContext, final: pd.DataFrame, data: dict | None = None) -> Decision:
    owner = ctx.config.get("owner", "TODO-owner")
    if ctx.track != "t01" or data is None:
        return Decision(status="HOLD", reason_code="POLICY_NOT_IMPLEMENTED",
                        reason="Chưa cài chính sách ra quyết định", owner=owner, scope=ctx.track)
    m = visible_metrics(final, data["candidates"], data["targets"])
    evidence = [str(ctx.out("pick.csv")), str(ctx.out("coverage.csv"))]
    if m["uncoverable_cells"]:
        return Decision(status="REWORK", reason_code="UNCOVERABLE_TARGET_CELLS",
                        reason=(f"Các ô {m['uncoverable_cells']} không có clip nào trong pool (theo tag nhìn thấy); "
                                f"cần quay bổ sung. Coverage nhìn thấy {m['weighted_coverage_visible']:.1%} "
                                f"chỉ là số gần đúng, không phải điểm chính thức."),
                        owner=owner, scope="t01", evidence=evidence, metrics=m)
    return Decision(status="GO", reason_code="ALL_CELLS_COVERABLE",
                    reason="Mọi ô mục tiêu đều có clip ứng viên và đã được phủ bởi các clip đã chọn (theo tag nhìn thấy).",
                    owner=owner, scope="t01", evidence=evidence, metrics=m)


def run(ctx: RunContext) -> None:
    spec = get_track(ctx.track)
    data = load(ctx)
    scored = process(ctx, data)
    ctx.stats["n_items"] = len(scored)
    queue = rank(ctx, scored)
    final = review(ctx, scored, queue, data)
    final[spec.pred_columns + [c for c in final.columns if c not in spec.pred_columns]].to_csv(ctx.out(spec.pred_file), index=False)
    write_decision(decide(ctx, final, data), ctx.out("decision.json"), ctx.out("decision_log.csv"))
