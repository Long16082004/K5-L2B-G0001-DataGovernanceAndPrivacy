### Planner-visible coverage analysis

Coverage availability was calculated by matching the visible metadata in `candidates.csv` against the 15 target cells in `targets.csv`. A target dimension matches when the candidate value equals the required target value, while `*` in the target acts as a wildcard.

- 13 of 15 target cells have at least one visible candidate match.
- 2 target cells have no visible candidate match:
  - **C13** — `urban / fog / night / pedestrian`, weight = 5
  - **C15** — `alley / rain / dusk / pedestrian`, weight = 4
- **C08** and **C09** each have only one matching candidate:
  - C08 → `clip_101`
  - C09 → `clip_108`
- All four hard target cells (C08–C11) currently have at least one candidate according to visible metadata.

The total target weight is 48. C13 and C15 contribute a combined weight of 9, therefore the maximum coverage implied by the current visible candidate metadata is:

`(48 - 9) / 48 = 39 / 48 = 81.25%`

This is a planner-visible availability analysis only and is **not the official evaluation result**, because final evaluation uses verified tags through the evaluator.

#### Coverage gaps

| Cell | Scenario | Weight | Hard | Visible matches | Observation |
|---|---|---:|---:|---:|---|
| C13 | urban / fog / night / pedestrian | 5 | 0 | 0 | No candidate in current visible pool |
| C15 | alley / rain / dusk / pedestrian | 4 | 0 | 0 | No candidate in current visible pool |
| C08 | alley / * / night / * | 4 | 1 | 1 | Only `clip_101`; fragile coverage |
| C09 | urban / rain / night / motorbike | 5 | 1 | 1 | Only `clip_108`; fragile coverage |

C13 and C15 should be considered for the supplemental capture plan. C08 and C09 should be treated as high-risk cells because their apparent coverage depends on a single candidate clip.
### Failure case — Repeated/common scenarios

The candidate pool contains multiple repeated scenario combinations. The most frequent combinations observed from planner-visible metadata are:

| Route | Weather | Light | Object | Count |
|---|---|---|---|---:|
| urban | clear | day | car | 11 |
| urban | clear | day | pedestrian | 10 |
| highway | clear | day | car | 7 |
| alley | clear | day | car | 6 |
| urban | rain | day | car | 6 |
| urban | clear | day | motorbike | 5 |

**Root cause:** the candidate pool is imbalanced toward common daytime/clear-weather scenarios.

**Risk:** a selection method that does not account for marginal coverage may choose several clips representing the same scenario and waste the K=30 budget, while rare or high-weight target cells remain uncovered.

**Mitigation:** the PoC selection algorithm should prioritize marginal weighted coverage and avoid selecting redundant clips when they do not add coverage to new target cells.
### Data quality — explicit `unknown` metadata

Trong `candidates.csv`, có 11/120 clip chứa ít nhất một giá trị `unknown`:

- `route`: 0
- `weather`: 5
- `light`: 3
- `object`: 3

Weather là field có nhiều `unknown` nhất.

Các clip affected:
- Weather unknown: `clip_046`, `clip_050`, `clip_077`, `clip_095`, `clip_112`
- Light unknown: `clip_068`, `clip_093`, `clip_117`
- Object unknown: `clip_015`, `clip_036`, `clip_073`

Risk: metadata `unknown` có thể làm planner bỏ sót hoặc đánh giá sai coverage nếu rule xử lý không được chốt trước evaluation.