"""Human-in-the-loop T01: mọi quyết định của người duyệt (không chỉ reject) phải vào audit log."""
import json

import pandas as pd

from src import main as runner

ARGS = ["--config", "configs/lab.yaml", "--track", "t01", "--offline", "--seed", "42"]


def _events(out):
    return [json.loads(x) for x in (out / "audit_log.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def _reviewed(out, decisions: dict, reviewer="Reviewer Test"):
    q = pd.read_csv(out / "review_queue.csv", dtype=str).fillna("")
    for i, d in decisions.items():
        q.loc[i, ["reviewer", "reviewer_decision", "review_note", "reviewed_at"]] = [reviewer, d, f"note {d}", "2026-11-14T10:00"]
    q.to_csv(out / "review_queue_reviewed.csv", index=False)
    return q


def test_moi_quyet_dinh_deu_duoc_ghi_audit_va_reject_duoc_ap_dung(tmp_path):
    assert runner.main(ARGS + ["--output", str(tmp_path)]) == 0
    q = _reviewed(tmp_path, {0: "approve", 1: "escalate", 2: "reject"})
    rejected = q.loc[2, "item_id"]
    assert runner.main(ARGS + ["--output", str(tmp_path)]) == 0

    ev = _events(tmp_path)
    actions = [e["action"] for e in ev]
    for a in ("review:approve", "review:escalate", "review:reject", "override:reject", "review:summary"):
        assert a in actions, a
    approve = next(e for e in ev if e["action"] == "review:approve")
    assert approve["actor"] == "Reviewer Test" and approve["reason"] == "note approve"
    assert approve["item_id"] == q.loc[0, "item_id"] and approve["before"] == "picked"
    summary = [e for e in ev if e["action"] == "review:summary"][-1]
    assert summary["after"] == {"approve": 1, "escalate": 1, "reject": 1}

    pick = pd.read_csv(tmp_path / "pick.csv")
    assert rejected not in set(pick["clip_id"]) and len(pick) == 30 and pick["clip_id"].is_unique
    assert (tmp_path / "pick_raw.csv").exists()                     # bản chọn gốc giữ lại để đối chiếu


def test_dong_da_duyet_ma_thieu_ten_nguoi_duyet_thi_fail_ro_rang(tmp_path):
    assert runner.main(ARGS + ["--output", str(tmp_path)]) == 0
    _reviewed(tmp_path, {0: "approve"}, reviewer="")
    assert runner.main(ARGS + ["--output", str(tmp_path)]) != 0      # owner bắt buộc, không âm thầm bỏ qua
