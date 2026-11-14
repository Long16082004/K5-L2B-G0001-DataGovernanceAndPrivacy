"""QA/metric T01: kiểm evaluator chuẩn `eval_t01` trên fixture tổng hợp nhỏ (không cần GT của giảng viên)
+ kiểm pick.csv thật của baseline / PoC theo metric contract (đúng K, unique, thuộc pool)."""
import pandas as pd
import pytest

from src import main as runner
from src.metrics.tracks import eval_t01
from src.pipeline import greedy_select
from src.t01_slices import build_visible_proxy, check_pick, evaluate_budgets

FX = "fixtures/t01_coverage"
DIMS = ["route", "weather", "light", "object"]

# 3 ô, Σw = 12. Ô Z không clip nào phủ được, nhưng vẫn nằm trong mẫu số.
TARGETS = pd.DataFrame([
    {"cell_id": "A", "route": "urban", "weather": "*", "light": "night", "object": "car", "weight": 5, "is_hard": 1},
    {"cell_id": "B", "route": "*", "weather": "rain", "light": "*", "object": "*", "weight": 3, "is_hard": 0},
    {"cell_id": "Z", "route": "alley", "weather": "fog", "light": "dusk", "object": "car", "weight": 4, "is_hard": 1},
])
VERIFIED = pd.DataFrame([
    ("c1", "urban", "fog", "night", "car"),               # phủ A nhờ weather '*'
    ("c2", "highway", "rain", "day", "pedestrian"),       # phủ B: 3 chiều '*', chỉ weather phải bằng
    ("c3", "urban", "fog", "day", "car"),                 # giống c1 nhưng light sai -> không phủ ô nào
    ("c4", "urban", "clear", "night", "car"),             # phủ A lần nữa (trùng ô với c1)
    ("c5", "highway", "clear", "day", "pedestrian"),      # không phủ ô nào
], columns=["clip_id", *DIMS])


def _fixture(tmp_path):
    """Thư mục fixture tạm đúng layout evaluator đọc: targets.csv, candidates.csv, gt/verified_tags.csv."""
    TARGETS.to_csv(tmp_path / "targets.csv", index=False)
    VERIFIED.assign(risk="low", cost_min=10, duration_s=20).to_csv(tmp_path / "candidates.csv", index=False)
    (tmp_path / "gt").mkdir()
    VERIFIED.to_csv(tmp_path / "gt" / "verified_tags.csv", index=False)
    return tmp_path / "gt" / "verified_tags.csv"


def _score(tmp_path, gt, ids, k):
    p = tmp_path / "pick.csv"
    pd.DataFrame({"clip_id": ids, "rank": range(1, len(ids) + 1)}).to_csv(p, index=False)
    res = eval_t01(gt, p, {"k": k})
    return {m.name: m for m in res.metrics}, res


def test_wildcard_khop_moi_gia_tri(tmp_path):
    gt = _fixture(tmp_path)
    m, res = _score(tmp_path, gt, ["c1", "c2"], k=2)
    wc = m["Weighted Coverage@K"]
    assert set(res.slices.loc[res.slices.covered == 1, "cell_id"]) == {"A", "B"}
    assert (wc.numerator, wc.denominator) == (8.0, 12.0)                  # A(5) + B(3), mẫu số cố định 12
    # chiều không phải '*' vẫn phải bằng đúng: c3 chỉ khác light so với c1 -> không phủ A
    m, res = _score(tmp_path, gt, ["c3"], k=1)
    assert m["Weighted Coverage@K"].numerator == 0.0 and res.slices.covered.sum() == 0


def test_clip_khong_match_thi_khong_tinh(tmp_path):
    gt = _fixture(tmp_path)
    m, res = _score(tmp_path, gt, ["c1", "c3", "c5", "clip_la"], k=4)
    wc = m["Weighted Coverage@K"]
    assert wc.numerator == 5.0                                            # chỉ c1 đóng góp (ô A)
    assert wc.denominator == 12.0                                         # không bỏ ô Z khó ra khỏi mẫu số
    assert wc.n == 3                                                      # clip_la không thuộc pool: bị bỏ
    assert any("not in candidate pool" in n for n in res.notes)
    # nhiều clip cùng phủ một ô: ô chỉ được cộng một lần
    m, _ = _score(tmp_path, gt, ["c1", "c4"], k=2)
    assert m["Weighted Coverage@K"].numerator == 5.0


@pytest.mark.parametrize("pipeline", ["src.pipeline", "src.examples.random_baseline"])
def test_pick_co_dung_k_unique(tmp_path, pipeline):
    rc = runner.main(["--config", "configs/lab.yaml", "--track", "t01", "--pipeline", pipeline,
                      "--output", str(tmp_path), "--offline", "--seed", "42"])
    assert rc == 0
    pick = pd.read_csv(tmp_path / "pick.csv")
    pool = pd.read_csv(f"{FX}/candidates.csv")["clip_id"]
    assert check_pick(pick, pool, k=30) == []
    assert len(pick) == 30 and pick["clip_id"].nunique() == 30 and pick["clip_id"].isin(pool).all()


def test_check_pick_bat_loi_pick_sai():
    pool = [f"c{i}" for i in range(5)]
    ok = pd.DataFrame({"clip_id": ["c0", "c1", "c2"], "rank": [1, 2, 3]})
    assert check_pick(ok, pool, k=3) == []
    assert any("cần đúng K=3" in p for p in check_pick(ok.head(2), pool, k=3))
    dup = pd.DataFrame({"clip_id": ["c0", "c0", "c2"], "rank": [1, 2, 3]})
    assert any("bị trùng" in p and "c0" in p for p in check_pick(dup, pool, k=3))
    foreign = pd.DataFrame({"clip_id": ["c0", "c1", "x9"], "rank": [1, 2, 3]})
    assert any("không thuộc pool" in p and "x9" in p for p in check_pick(foreign, pool, k=3))
    bad_rank = ok.assign(rank=[1, 1, 3])
    assert any("rank" in p for p in check_pick(bad_rank, pool, k=3))
    assert check_pick(pd.DataFrame({"id": ["c0"]}), pool, k=1) == ["thiếu cột clip_id"]


def test_budget_nho_la_tien_to_cua_pick_k30():
    """Cho phép chấm K = 10/20 bằng K dòng đầu của pick K = 30 (evaluator --k): chọn riêng với K nhỏ phải ra đúng tiền tố."""
    cands, targets = pd.read_csv(f"{FX}/candidates.csv"), pd.read_csv(f"{FX}/targets.csv")
    full = greedy_select(cands, targets, 30)["clip_id"].tolist()
    for b in (10, 20):
        assert greedy_select(cands, targets, b)["clip_id"].tolist() == full[:b]


def test_bang_budget_tach_hard_slice(tmp_path):
    gt = _fixture(tmp_path)
    p = tmp_path / "pick.csv"
    pd.DataFrame({"clip_id": ["c2", "c1", "c5"], "rank": [1, 2, 3]}).to_csv(p, index=False)
    r1, r3 = evaluate_budgets(gt, p, [1, 3])
    assert (r1["w_covered"], r1["hard_cells_covered"], r1["missing_hard_cells"]) == (3.0, 0, ["A", "Z"])
    assert (r3["w_covered"], r3["hard_cells_covered"], r3["hard_cells_total"]) == (8.0, 1, 2)
    assert (r3["hard_w_covered"], r3["hard_w_total"], r3["nonhard_w_covered"], r3["nonhard_w_total"]) == (5.0, 9.0, 3.0, 3.0)
    lo, hi = r3["rare_recall_wilson95"]
    assert lo < r3["rare_recall"] == 0.5 < hi


def test_visible_proxy_unknown_chi_khop_o_wildcard(tmp_path):
    """Chế độ không có GT: chấm bằng tag nhìn thấy; `unknown` không được tính là phủ ô có giá trị cụ thể."""
    fx = tmp_path / "fx"
    fx.mkdir()
    TARGETS.to_csv(fx / "targets.csv", index=False)
    pd.DataFrame([("u1", "urban", "unknown", "night", "car"), ("u2", "highway", "unknown", "day", "car")],
                 columns=["clip_id", *DIMS]).assign(risk="low", cost_min=5, duration_s=20).to_csv(fx / "candidates.csv", index=False)
    work = tmp_path / "work"
    work.mkdir()
    gt = build_visible_proxy(fx, work)
    p = tmp_path / "pick.csv"
    pd.DataFrame({"clip_id": ["u1", "u2"], "rank": [1, 2]}).to_csv(p, index=False)
    (r,) = evaluate_budgets(gt, p, [2])
    assert r["missing_cells"] == ["B", "Z"]                               # u1 phủ A (weather '*'); u2 không phủ B (cần rain)
