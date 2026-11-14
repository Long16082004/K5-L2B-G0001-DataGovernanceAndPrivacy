"""Thuật toán lõi T01: khớp wildcard/unknown, greedy set cover, tính tất định, nối dây pipeline."""
import pandas as pd
import pytest

from src import main as runner
from src.pipeline import coverage_table, greedy_select, match, visible_metrics

T = pd.DataFrame([
    {"cell_id": "A", "route": "urban", "weather": "*", "light": "night", "object": "car", "weight": 5, "is_hard": 1},
    {"cell_id": "B", "route": "*", "weather": "rain", "light": "*", "object": "*", "weight": 3, "is_hard": 0},
    {"cell_id": "Z", "route": "alley", "weather": "fog", "light": "dusk", "object": "car", "weight": 4, "is_hard": 0},
])


def _c(cid, route, weather, light, obj, cost=5, risk="low"):
    return {"clip_id": cid, "route": route, "weather": weather, "light": light, "object": obj,
            "risk": risk, "cost_min": cost, "duration_s": 20}


C = pd.DataFrame([
    _c("c1", "urban", "clear", "night", "car"),            # phủ ô A
    _c("c2", "urban", "rain", "night", "car"),             # phủ ô A và B
    _c("c3", "highway", "rain", "day", "car"),             # phủ ô B
    _c("c4", "urban", "unknown", "night", "car"),          # weather unknown: chỉ khớp ô có weather '*', không khớp giá trị cụ thể
    _c("c5", "highway", "clear", "day", "pedestrian"),     # không phủ ô nào
])


def test_wildcard_khop_moi_gia_tri_nhung_gia_tri_cu_the_phai_bang():
    cell = T.iloc[0].to_dict()
    assert match(_c("x", "urban", "fog", "night", "car"), cell)          # weather '*' khớp mọi giá trị
    assert not match(_c("x", "urban", "fog", "day", "car"), cell)        # light khác
    assert not match(_c("x", "highway", "fog", "night", "car"), cell)    # route khác


def test_unknown_khong_bao_gio_khop_gia_tri_cu_the():
    cell_b = T.iloc[1].to_dict()                                         # weather bắt buộc là 'rain'
    assert not match(_c("x", "urban", "unknown", "day", "car"), cell_b)
    assert match(_c("x", "urban", "unknown", "day", "car"), cell_b, unknown_is_wildcard=True)
    cell_a = T.iloc[0].to_dict()                                         # weather là '*': unknown vẫn hợp lệ
    assert match(_c("x", "urban", "unknown", "night", "car"), cell_a)


def test_greedy_tra_dung_k_clip_khong_trung_va_uu_tien_marginal_gain():
    p = greedy_select(C, T, k=2)
    assert len(p) == 2 and p["clip_id"].is_unique
    assert p.loc[0, "clip_id"] == "c2"                                   # gain 5+3 cao nhất
    # sau c2 cả A và B đã phủ: không clip nào còn gain dương ở pha greedy
    assert (p[p["phase"] == "greedy"]["score"] > 0).all() and (p["phase"] == "greedy").sum() == 1


def test_greedy_khong_tinh_lai_trong_so_o_da_phu():
    p = greedy_select(C, T, k=5)
    greedy = p[p["phase"] == "greedy"]
    assert greedy["score"].sum() == 8.0                                  # A(5)+B(3) chỉ tính một lần, Z không thể phủ


def test_tat_dinh_va_k_lon_hon_pool():
    a, b = greedy_select(C, T, k=5), greedy_select(C, T, k=5)
    pd.testing.assert_frame_equal(a, b)
    assert len(greedy_select(C, T, k=50)) == len(C)                      # biên: K > pool -> bị chặn trên, không lỗi


def test_exclude_thay_the_clip_bi_tu_choi():
    p = greedy_select(C, T, k=2, exclude={"c2"})
    assert "c2" not in set(p["clip_id"])
    assert len(p) == 2


def test_o_khong_the_phu_duoc_danh_dau_de_quay_bo_sung():
    p = greedy_select(C, T, k=3)
    cov = coverage_table(p, C, T).set_index("cell_id")
    assert cov.loc["Z", "status"] == "UNCOVERABLE"
    assert visible_metrics(p, C, T)["uncoverable_cells"] == "Z"


def test_pipeline_end_to_end_tren_fixture_that(tmp_path):
    rc = runner.main(["--config", "configs/lab.yaml", "--track", "t01", "--output", str(tmp_path),
                      "--offline", "--seed", "42"])
    assert rc == 0
    pick = pd.read_csv(tmp_path / "pick.csv")
    assert len(pick) == 30 and pick["clip_id"].is_unique
    assert (tmp_path / "coverage.csv").exists() and (tmp_path / "decision.json").exists()


def test_pipeline_tai_lap_duoc(tmp_path):
    for name in ("r1", "r2"):
        assert runner.main(["--config", "configs/lab.yaml", "--track", "t01", "--output", str(tmp_path / name),
                            "--offline", "--seed", "42"]) == 0
    a = pd.read_csv(tmp_path / "r1" / "pick.csv")["clip_id"].tolist()
    b = pd.read_csv(tmp_path / "r2" / "pick.csv")["clip_id"].tolist()
    assert a == b
