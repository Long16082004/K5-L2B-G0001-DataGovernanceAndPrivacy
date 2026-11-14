from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "t01_coverage"

CANDIDATES = FIXTURE / "candidates.csv"
TARGETS = FIXTURE / "targets.csv"
HOLDOUT = FIXTURE / "holdout_candidates.csv"

DIMS = ["route", "weather", "light", "object"]


def target_matches(candidate: pd.Series, target: pd.Series) -> bool:
    """Return True when candidate metadata satisfies a target cell."""
    for dim in DIMS:
        if target[dim] != "*" and candidate[dim] != target[dim]:
            return False
    return True


def main() -> None:
    candidates = pd.read_csv(CANDIDATES)
    targets = pd.read_csv(TARGETS)
    holdout = pd.read_csv(HOLDOUT)

    print("=== T01 DATA SUMMARY ===")
    print(f"Candidates: {len(candidates)}")
    print(f"Targets: {len(targets)}")
    print(f"Holdout candidates: {len(holdout)}")

    print("\n=== UNKNOWN METADATA ===")

    unknown_rows = candidates[
        candidates[DIMS].eq("unknown").any(axis=1)
    ]

    print(
        f"Clips with at least one explicit unknown: "
        f"{len(unknown_rows)}/{len(candidates)} "
        f"({len(unknown_rows) / len(candidates) * 100:.2f}%)"
    )

    for dim in DIMS:
        count = int((candidates[dim] == "unknown").sum())
        print(f"{dim}: {count}")

    print("\n=== PLANNER-VISIBLE TARGET COVERAGE ===")

    coverage_rows = []

    for _, target in targets.iterrows():
        matches = candidates[
            candidates.apply(
                lambda candidate: target_matches(candidate, target),
                axis=1,
            )
        ]

        coverage_rows.append(
            {
                "cell_id": target["cell_id"],
                "weight": int(target["weight"]),
                "is_hard": int(target["is_hard"]),
                "visible_matches": len(matches),
                "clips": matches["clip_id"].tolist(),
            }
        )

    coverage = pd.DataFrame(coverage_rows)

    for _, row in coverage.iterrows():
        print(
            f"{row['cell_id']}: "
            f"weight={row['weight']}, "
            f"hard={row['is_hard']}, "
            f"matches={row['visible_matches']}, "
            f"clips={row['clips']}"
        )

    covered = coverage["visible_matches"] > 0

    print("\n=== COVERAGE SUMMARY ===")
    print(f"Cells with >=1 visible match: {covered.sum()}/{len(coverage)}")

    missing = coverage[~covered]

    print(
        "Cells with 0 visible matches:",
        missing["cell_id"].tolist(),
    )

    total_weight = coverage["weight"].sum()
    missing_weight = missing["weight"].sum()
    visible_upper_bound = (total_weight - missing_weight) / total_weight

    print(f"Total target weight: {total_weight}")
    print(f"Missing target weight: {missing_weight}")
    print(
        "Planner-visible weighted coverage upper bound: "
        f"{visible_upper_bound:.2%}"
    )

    print("\n=== REPEATED SCENARIOS ===")

    repeated = (
        candidates.groupby(DIMS)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    print(repeated.head(15).to_string(index=False))


if __name__ == "__main__":
    main()