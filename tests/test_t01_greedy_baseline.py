"""Baseline greedy sách giáo khoa (src/examples/greedy_baseline.py) + ablation T01."""
import pandas as pd

from src import main as runner
from src.examples.greedy_baseline import plain_greedy
from src.pipeline import greedy_select

T = pd.DataFrame([
    {"cell_id": "A", "route": "urban", "weather": "*", "light": "night", "object": "car", "weight": 5, "is_hard": 1},
    {"cell_id": "B", "route": "*", "weather": "rain", "light": "*", "object": "*", "weight": 3, "is_hard": 0},
])


def _c(cid, route, weather, light, obj, cost=5):
    return {"clip_id": cid, "route": route, "weather": weather, "light": light, "object": obj,
            "risk": "low", "cost_min": cost, "duration_s": 20}


C = pd.DataFrame([
    _c("c1", "urban", "clear", "night", "car", cost=9),    # phủ A, đắt
    _c("c2", "urban", "clear", "night", "car", cost=1),    # phủ A, rẻ (cùng gain với c1)
    _c("c3", "highway", "rain", "day", "car"),             # phủ B
    _c("c4", "urban", "unknown", "night", "car"),          # weather unknown: vẫn phủ A vì A có weather '*'
    _c("c5", "highway", "clear", "day", "pedestrian"),     # không phủ ô nào
    _c("c6", "highway", "unknown", "day", "car"),          # chỉ phủ B nếu coi unknown là wildcard
])


def test_dung_k_clip_khong_trung_va_khong_tinh_lai_o_da_phu():
    p = plain_greedy(C, T, 4)
    assert len(p) == 4 and p["clip_id"].is_unique
    assert list(p["rank"]) == [1, 2, 3, 4]
    gain = p[p["reason"] == "greedy_gain"]
    assert list(gain["score"]) == [5.0, 3.0]                # A rồi B; clip phủ lại A không còn gain
    assert set(p["reason"][2:]) == {"fill_by_id"}


def test_tie_break_clip_id_hay_cost_la_khac_biet_duy_nhat():
    assert plain_greedy(C, T, 1)["clip_id"].iloc[0] == "c1"                      # sách giáo khoa: clip_id nhỏ nhất
    assert plain_greedy(C, T, 1, cost_tiebreak=True)["clip_id"].iloc[0] == "c2"  # quy tắc (b): rẻ hơn
    assert greedy_select(C, T, 1)["clip_id"].iloc[0] == "c2"                     # PoC dùng cùng quy tắc (b)


def test_unknown_wildcard_lam_tang_coverage_tu_tin():
    strict = plain_greedy(C[C["clip_id"] != "c3"], T, 6)
    wild = plain_greedy(C[C["clip_id"] != "c3"], T, 6, unknown_is_wildcard=True)
    assert "B" not in ";".join(strict.loc[strict["reason"] == "greedy_gain", "covers"])
    assert "B" in ";".join(wild.loc[wild["reason"] == "greedy_gain", "covers"])  # c6 'phủ' B chỉ nhờ unknown


def test_pick_k_nho_la_tien_to_cua_pick_k_lon():
    big = plain_greedy(C, T, 6)
    for k in (1, 2, 3, 5):
        assert list(plain_greedy(C, T, k)["clip_id"]) == list(big["clip_id"][:k])


def test_greedy_baseline_chay_end_to_end(tmp_path):
    out = tmp_path / "greedy"
    rc = runner.main(["--track", "t01", "--pipeline", "src.examples.greedy_baseline", "--output", str(out),
                      "--run-name", "greedy", "--offline", "--seed", "42"])
    assert rc == 0
    pick = pd.read_csv(out / "pick.csv")
    assert len(pick) == 30 and pick["clip_id"].is_unique
    assert (out / "decision.json").exists() and (out / "review_queue.csv").exists()
