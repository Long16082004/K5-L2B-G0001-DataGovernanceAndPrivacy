# Group Report — Day 06 Data Lab: T01 Coverage Planner

> T01 PoC and random baseline were run offline on the visible fixture metadata. All scores below are **visible-metadata proxy results**, not official evaluation: verified GT is absent from this student checkout. Official values must be supplied by the instructor evaluator and must replace or supplement these proxy values with clear labels.

## 00 · Header

| Item | Value |
|---|---|
| Group ID | G0001 |
| Challenge | T01 · Coverage Planner |
| Members and roles | Member 1 Lead/Integrator: Ngô Ngọc Trường (`truongnnhe172873`); Member 2 Data/Fixtures: LeVinhKhai; Member 3 Core algorithm: `Long16082004`; Member 4 QA/Metric: Pham Duy Thanh (`PDTnhah`); Member 5 Human Review/Report: name pending. |
| Git URL | https://github.com/Long16082004/K5-L2B-G0001-DataGovernanceAndPrivacy |
| Branch / analyzed commit | `dev` (integration branch) · `160c449` |
| Demo/final tags; deadline | Not present / pending |

## 01 · Problem statement

Choose a small set of clips from a 120-clip candidate pool to cover 15 target scenarios with fixed risk weights. Poor coverage can leave rare or difficult driving scenes untested and mislead data collection or model evaluation teams.

- **Input → output:** candidate metadata and target matrix → K=30 selected clips, per-cell coverage evidence, human review of high-risk cells, and a capture plan for gaps.
- **Decision policy:** the current pipeline returns REWORK when any target is uncovered in the visible metadata pool. The report recommends HOLD for unverified hard-cell tags and GO only after human verification and domain-owner sign-off. These are operational recommendations, not legal conclusions.
- **Assumptions:** fixture tags are noisy planner-visible metadata. A match does not prove the visual scene is correct; unknown is not a verified match.

## 02 · Data and provenance

| Split | N | Source | License | Synthetic |
|---|---:|---|---|---|
| Main candidates | 120 clips | `fixtures/t01_coverage/candidates.csv` | CC0-1.0 as declared in fixture provenance | Yes |
| Targets | 15 cells | `fixtures/t01_coverage/targets.csv` | Same fixture provenance | Yes |
| Holdout candidates | 25 clips; K=6 | `fixtures/t01_coverage/holdout_candidates.csv` | Same fixture provenance | Yes |

Candidate fields: `clip_id, route, weather, light, object, risk, cost_min, duration_s`. Target fields: `cell_id, route, weather, light, object, weight, is_hard`. A target `*` matches any value. `unknown` does not match a specific required value. The supplied manifests were verified: `python -m tools.verify_manifests` reported 14 manifests and 0 failures (per checked-in data analysis). No real footage or hidden GT was used. The supplied `split` value is `na`; dev/holdout labels here describe the lab's file roles.

There are 11/120 candidates with at least one unknown field: weather 5, light 3, object 3, route 0. See [`t01_data_analysis.md`](t01_data_analysis.md).

## 03 · Research and design

- **References:** BDD100K official site and CVPR 2020 paper; Google Data Cards Playbook; ISO/IEC TR 5259-6:2026 as cited in the T01 handout. Access dates and relevance are listed in Section 11.
- **Flow:** load and verify manifest → match candidates to targets → deterministic greedy weighted set cover with cost tie-break → fill remaining K slots with fragile/unknown/high-risk candidates under the committed rules → emit coverage, review queue, decision, and audit log.
- **Offline components:** no model or network dependency.
- **Trade-offs:** visible tags enable a fast, interpretable planner but can misstate actual scene coverage. Unknown values are excluded from strict coverage; backup selection may still surface them for human inspection. Greedy selection is deterministic and prioritizes marginal weighted gain, but the 30-clip budget can exceed what is needed to cover available cells.

## 04 · Baseline versus PoC

Both runs used the same 120-clip pool, K=30, seed 42, offline mode, and were valid 30-row, unique-ID picks. The baseline is random (`src.examples.random_baseline`); the PoC is deterministic greedy weighted set cover (`src.pipeline`). Results below use the checked-in visible-proxy evaluator output [`t01_slices_visible_proxy.md`](t01_slices_visible_proxy.md), not hidden verified tags.

| K | Run | Weighted Coverage@K (Σw/48) | Cells covered | Hard recall (n/4; Wilson 95%) | Duplicate scenarios | Cost / covered cell (min) |
|---:|---|---:|---:|---:|---:|---:|
| 10 | Random | 0.0833 (4/48) | 2/15 | 0/4; 0.00 [0.00, 0.49] | 0 | 57.50 |
| 10 | PoC | 0.7292 (35/48) | 10/15 | 4/4; 1.00 [0.51, 1.00] | 0 | 5.30 |
| 20 | Random | 0.2708 (13/48) | 5/15 | 1/4; 0.25 [0.05, 0.70] | 4 | 34.00 |
| 20 | PoC | 0.8125 (39/48) | 13/15 | 4/4; 1.00 [0.51, 1.00] | 5 | 10.00 |
| 30 | Random | 0.3750 (18/48) | 7/15 | 1/4; 0.25 [0.05, 0.70] | 12 | 33.14 |
| 30 | PoC | 0.8125 (39/48) | 13/15 | 4/4; 1.00 [0.51, 1.00] | 7 | 16.46 |

At K=30, the visible-proxy difference is +21 weight points / 48 and +3/4 hard cells. This is not evidence of official performance: PoC optimizes the same noisy visible metadata used by the proxy evaluator, so its score may be optimistic. Wilson intervals are wide because the hard slice has only four cells. See the detailed report for per-budget changes and caveats.

The requested baseline comparison bar chart is [`t01_coverage_proxy.png`](../demo/t01_coverage_proxy.png); it is explicitly labeled as visible-metadata proxy.

### 04b · Strong baseline: textbook greedy set cover, and ablation

The T01 handout asks for a comparison against a greedy set-cover baseline, not only random. `src.examples.greedy_baseline` is a textbook weighted greedy set cover: pick the clip with the largest uncovered weight, tie-break by `clip_id`, and fill remaining slots by `clip_id` once no clip adds weight. The ablation adds one PoC rule at a time on the same pool, K, and seed. Full table: [`t01_ablation_visible_proxy.md`](t01_ablation_visible_proxy.md) (visible proxy, same evaluator `eval_t01`).

| Run (K=30) | Weighted Coverage@K | Cells | Hard | Duplicate scenarios | Total min | Min / covered cell |
|---|---:|---:|---:|---:|---:|---:|
| Random (seed 42) | 0.3750 (18/48) | 7/15 | 1/4 | 12 | 232 | 33.14 |
| Greedy plain (baseline) | 0.8125 (39/48) | 13/15 | 4/4 | 7 | 266 | 20.46 |
| + cost tie-break (rule b) | 0.8125 (39/48) | 13/15 | 4/4 | 8 | 240 | 18.46 |
| + fill rule (c) = **PoC** | 0.8125 (39/48) | 13/15 | 4/4 | 7 | 214 | 16.46 |
| Greedy, `unknown` as wildcard (rule a removed) | 0.5833 (28/48) | 9/15 | 4/4 | 8 | 271 | 30.11 |

**The PoC does not beat the greedy baseline on coverage.** At K=10, 20 and 30, and on holdout K=6, its weighted coverage, cells covered and hard recall equal the greedy baseline's (Δ = 0). Its gain is cost only: both pick 13 marginal-gain clips covering the same 13 cells, but the cost tie-break chooses cheaper clips for them (64 vs 94 minutes). Total cost is 53 vs 77 minutes at K=10 and 214 vs 266 minutes at K=30 (−4.0 min per covered cell). The fill rule (c) changes *which* extra clips are kept, not coverage: under visible tags, coverage saturates at 39/48 from K=20, and the last slots go to backups and high-risk clips (in the PoC, 13 clips are chosen for marginal gain; the other 17 are fill: 9 risk-high, 5 fragile-cell backups, 1 unknown-may-cover, 2 diverse). Whether those backups pay off can only be shown with verified tags, if a primary clip turns out to be mislabeled.

Treating `unknown` as a wildcard makes greedy confidently pick clips whose unknown tag "matches"; under visible scoring this drops coverage to 28/48. This is penalized by construction (the proxy scores `unknown` as non-matching), so it measures how much apparent coverage rests on unverified tags rather than a true score. It supports rule (a), but the real effect needs the verified-tag evaluation.

## 05 · Evaluation protocol

Primary metric: Weighted Coverage@K = total weight of covered target cells / fixed total target weight 48; each cell counts once. Higher is better. A cell is covered only when a selected clip's verified tags match all specified dimensions; target `*` is wildcard. K=30 is primary; report K=10/20/30 and holdout K=6 separately. Seed 42; do not tune on holdout. The full frozen contract is [`metric_contract.md`](metric_contract.md).

The checked-in visible-proxy run evaluates using visible `candidates.csv` tags in place of verified tags. This was done solely to exercise the evaluator and compare visible-metadata behavior. It is not the official score. No official verified-tag or hidden evaluation is available in this checkout.

## 06 · Results, slices, and failure cases

At K=30, the PoC visible proxy covers 13/15 cells, weight 39/48 (81.25%), including all 4 hard cells (18/18 hard weight). C13 and C15 remain uncovered. C08 and C09 are fragile single-candidate cells (`clip_101`, `clip_108`). PoC spends 214 minutes across selected clips, 16.462 minutes per covered cell, and selects 7 repeated scenarios. These values come from `out/poc/coverage.csv` and `out/poc/run_info.json` generated at commit `160c449`.

- **Repeated scenarios (handout failure mode "chọn lại toàn cảnh giống nhau"):** the 7 duplicates at K=30 are fill-phase picks made after coverage saturated, not greedy picks: the 13 marginal-gain clips are all distinct scenarios. The greedy baseline has the same count (7), and random has 12. At K=10 there are 0 duplicates. If a smaller budget is acceptable, K=20 reaches the same visible coverage.

- **Failure 1 — C13:** urban/fog/night/pedestrian has no strict visible metadata match. `clip_093` has unknown light; other fog/night candidates have another object. Inspect uncertain candidates, then capture if no verified match exists.
- **Failure 2 — C15:** alley/rain/dusk/pedestrian has no strict visible metadata match. Capture that complete combination; do not claim coverage from a nearby scene.
- **Fragility — C08/C09:** each has one visible candidate. Review `clip_101` and `clip_108`; a wrong tag would invalidate apparent coverage.
- **Holdout visible check:** K=6, weighted coverage 0.3958, 2/4 hard cells covered, 0 duplicate scenarios. This is also a visible-tag proxy, not official heldout scoring.
- Runtime: baseline 0.0268 s; PoC 0.3537 s on Windows 11 (10.0.26200), Python 3.14.3, Intel64 Family 6 Model 141 Stepping 1. Runtime is from `run_info.json` at commit `160c449` and reflects this environment only.

## 07 · Human review and decision

- **Three prioritized review cells and capture proposals:**

| Cell / target | Coverage evidence | Proposed decision | Capture or verification action | Owner / reason | Reviewer |
|---|---|---|---|---|---|
| C09 · urban/rain/night/motorbike · w=5, hard | One visible match: `clip_108`; selected by PoC | HOLD pending verification | Verify all dimensions; capture a verified backup if it fails | Capture coordinator · protect single-point hard coverage | Domain reviewer; name pending |
| C13 · urban/fog/night/pedestrian · w=5 | No strict visible match; `clip_093` has unknown light | REWORK if review finds no verified match | Inspect plausible fog/night clips; otherwise capture exact scenario | Capture coordinator · no strict match | Domain reviewer; name pending |
| C15 · alley/rain/dusk/pedestrian · w=4 | No strict visible match | REWORK | Capture and verify the complete combination | Capture coordinator · no strict match | Domain reviewer; name pending |

An additional risk outside the three prioritized rows is C08 (hard, weight 4, only `clip_101`); verify it before relying on its apparent coverage. The structured worksheet is [`t01_review_capture_plan.csv`](t01_review_capture_plan.csv). It records proposed decisions, not approvals; reviewer name, actual decision, note, and review status remain pending.
- Current machine decision: **REWORK**, reason code `UNCOVERABLE_TARGET_CELLS`, owner Ngô Ngọc Trường (Lead), based on C13/C15 in `out/poc/decision.json`. This is a pipeline decision from visible metadata, not human approval.
- **Review mechanism:** the reviewer fills `out/poc/review_queue_reviewed.csv` (copy of `review_queue.csv`: `reviewer`, `reviewer_decision` ∈ approve/reject/edit/escalate/skip, `review_note`, `reviewed_at`) and re-runs the PoC. Every decision is written to `audit_log.jsonl` as `review:<decision>` (actor = reviewer, reason = note), plus a `review:summary` event. `reject` also logs `override:reject`, removes the clip and re-runs greedy, keeping the original pick in `pick_raw.csv`. A reviewed row without a reviewer name makes the run fail.
- `out/poc/audit_log.jsonl` currently contains only the pipeline's `greedy_select` event. No reviewer event exists yet. Add reviewer evidence only after an actual review; T01 has metadata only (no footage), so review notes must say the judgment is based on metadata. Do not fabricate audit records.

## 08 · Reproduction and tests

Runs completed successfully offline on branch `dev` at commit `160c449`, from a clean `out/`:

```powershell
.\.venv\Scripts\python.exe -m tools.preflight
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m src.main --track t01 --pipeline src.examples.random_baseline --output out/baseline --run-name baseline --offline --seed 42
.\.venv\Scripts\python.exe -m src.main --track t01 --pipeline src.examples.greedy_baseline --output out/greedy --run-name greedy --offline --seed 42
.\.venv\Scripts\python.exe -m src.main --config configs/lab.yaml --track t01 --output out/poc --run-name poc --offline --seed 42
.\.venv\Scripts\python.exe -m src.t01_slices --run baseline=out/baseline/pick.csv --run poc=out/poc/pick.csv --visible-proxy --out reports/t01_slices_visible_proxy.md
.\.venv\Scripts\python.exe -m src.t01_ablation --visible-proxy --out reports/t01_ablation_visible_proxy.md
```

- `tools.preflight`: 0 FAIL, 2 WARN (`data/real` and `models_optional/` absent; neither is used by T01). `tools.verify_manifests`: 14 manifests, 0 failing.
- `pytest -q`: **71 passed, 39 skipped, 0 failed** (skips are other tracks' tests that need instructor GT). The group's T01 tests (`tests/test_t01_algo.py`, `tests/test_t01_metric.py`, `tests/test_t01_greedy_baseline.py`, `tests/test_t01_review_audit.py`) are 24 passed, covering success cases and edge/failure cases (wildcard vs `unknown`, no recount of covered cells, exact K unique IDs, invalid picks, prefix consistency across budgets, every reviewer decision audited, reviewed row without reviewer fails).
- All three `src.main` runs exited 0. Running the PoC twice gives a byte-identical `pick.csv` (deterministic; no RNG used).
- Outputs under `out/` are git-ignored; regenerate them with the commands above. Environment: Python 3.14.3, Windows 11 (10.0.26200), Intel64 Family 6 Model 141 Stepping 1. `make` is not available on Windows, so the commands are given without it. On Windows, `.gitattributes` forces LF on fixture text files; without it, `core.autocrlf` breaks manifest hashes.

## 09 · Limitations and ethics

Synthetic metadata does not establish real-world scene availability, visual correctness, licensing, or model performance. The visible proxy is optimistic by construction because the PoC selects against the same visible tags. Human visual verification and official verified-tag evaluation remain necessary. Do not commit real footage or PII without rights, privacy review, and access controls. No claim of GDPR or Vietnamese-law compliance is made; consult the domain owner and DPO/legal as applicable.

## 10 · Team contribution

See [`team_contributions.csv`](team_contributions.csv). Members 1–4 are mapped to Git authors and relevant commits from `git shortlog -sne --all` and the visible commit history. Member 5's name and commit evidence, and presenter status for most members, remain pending. Git author labels are preserved where the legal/display name is not known.

## 11 · References

| URL / source | Access date | Relevance |
|---|---|---|
| https://bdd-data.berkeley.edu/ | 2026-11-14 | Official BDD100K dataset context; no BDD footage used. |
| https://openaccess.thecvf.com/content_CVPR_2020/papers/Yu_BDD100K_A_Diverse_Driving_Dataset_for_Heterogeneous_Multitask_Learning_CVPR_2020_paper.pdf | 2026-11-14 | BDD100K dataset paper cited by T01; no BDD footage used. |
| https://sites.research.google/datacardsplaybook/ | 2026-11-14 | Guidance for documenting dataset provenance and limitations. |
| ISO/IEC TR 5259-6:2026 (reference as cited in T01 handout) | 2026-11-14 (handout) | Data-quality reference; full text not independently accessed. |

## Final completion checklist

- [x] T01 offline baseline and PoC runs; picks validated at K=30.
- [x] Visible proxy results for budgets 10/20/30 and holdout K=6, labeled non-official.
- [x] Baseline-versus-PoC bar chart prepared for the demo (visible proxy only).
- [x] Manifest verification reported 14 manifests, 0 failures in the data-analysis artifact.
- [x] Greedy set-cover baseline and ablation (Section 04b); PoC ties greedy on coverage, wins on cost only.
- [x] `pytest -q`: 71 passed, 39 skipped, 0 failed (24 group T01 tests).
- [x] Every reviewer decision (not only reject) is recorded in the audit log.
- [ ] Official verified-tag evaluation / instructor result.
- [ ] Human reviewer completes worksheet and records actual decisions plus audit evidence.
- [ ] Member 5 identity/commit and presenter status; tags and deadline.
- [ ] Present the 4-slide demo in [`../demo/t01_demo.md`](../demo/t01_demo.md).
