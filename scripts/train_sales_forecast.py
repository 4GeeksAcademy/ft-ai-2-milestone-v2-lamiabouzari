#!/usr/bin/env python3
"""Train the TrackFlow sales forecasting model and report the required metrics.

End-to-end entry point for the "Sales Forecasting with a Regression Model"
project (see ``CONTEXT-trackflow.en.md`` and ``docs/sales-forecasting.md``):

    python scripts/train_sales_forecast.py [csv_path] [--artifacts-dir DIR]

Steps
-----
1. Load ``data/raw/trackflow_sales.csv`` (consolidated rows only) and validate
   the dataset contract (120 monthly rows, 2016-01..2025-12, no missing months,
   positive ``revenue_eur``, no nulls).
2. Split chronologically — TRAIN 2016-01..2023-12 (8 years), TEST 2024-01..2025-12
   (2 years). The time series is never shuffled.
3. Engineer causal lag/rolling/calendar features (no future leakage).
4. Train a ``RandomForestRegressor`` with ``random_state=42``.
5. Evaluate on the test period only: MSE (EUR² + % of avg monthly revenue),
   PSI, Gini, K2 (D'Agostino-Pearson normality test on residuals).
6. Save metrics JSON and the 2024-2025 forecast visualization into
   ``data/eval/sales_forecast/`` by default.

Why Random Forest (see also ``data/pipelines/sales_forecasting.py``):
the series has only 96 effective training rows, so bagging is more robust than
boosting; it is fully deterministic with a fixed seed; and it ships with
scikit-learn, matching the repository's existing dependency style.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow ``python scripts/train_sales_forecast.py ...`` from the repository root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.pipelines.sales_forecasting import (  # noqa: E402
    RANDOM_STATE,
    run_pipeline,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the TrackFlow sales forecast model")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=str(ROOT / "data" / "raw" / "trackflow_sales.csv"),
        help="path to the consolidated TrackFlow sales CSV",
    )
    parser.add_argument(
        "--artifacts-dir",
        default=str(ROOT / "data" / "eval" / "sales_forecast"),
        help="directory where metrics JSON and the forecast chart are written",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"Error: dataset not found: {csv_path}", file=sys.stderr)
        return 1

    print("TRACKFLOW — SALES FORECASTING (regression model)")
    print("=" * 60)
    print(f"Dataset           : {csv_path}")
    print(f"Artifacts dir     : {args.artifacts_dir}")
    print(f"Random state      : {RANDOM_STATE}")

    try:
        result = run_pipeline(csv_path, args.artifacts_dir)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    split = result["split"]
    metrics = result["metrics"]

    print("\n1) Dataset validation passed")
    print("-" * 60)
    print(f"   Consolidated monthly rows : 120 (2016-01 .. 2025-12)")
    print(f"   Missing months            : none")
    print(f"   Null values               : none")
    print(f"   revenue_eur > 0           : yes")

    print("\n2) Chronological split (no shuffling)")
    print("-" * 60)
    print(f"   TRAIN: {split.train_months.min().date()} .. {split.train_months.max().date()}  ({len(result['X_train'])} feature rows, 8 years)")
    print(f"   TEST : {split.test_months.min().date()} .. {split.test_months.max().date()}  ({len(result['X_test'])} feature rows, 2 years)")

    print("\n3) Model")
    print("-" * 60)
    print("   RandomForestRegressor(n_estimators=500, max_depth=6,")
    print("                         min_samples_leaf=2, random_state=42)")
    print("   Why: bagging is robust on this small dataset (96 raw training")
    print("   months; 84 complete feature rows after lag warm-up), captures the")
    print("   non-linear seasonal interactions without scaling, is fully")
    print("   deterministic with the fixed seed, and needs no extra dependency.")

    print("\n4) Test-period metrics (2024-01 .. 2025-12)")
    print("-" * 60)
    print(f"   MSE   : {metrics['mse_eur2']:,.0f} EUR²")
    print(
        f"           (MSE = {metrics['mse_pct_of_squared_mean_revenue']:.2f}% of the squared mean revenue)"
    )
    print(f"   RMSE  : {metrics['rmse_eur']:,.0f} EUR  (interpretable EUR scale)")
    print(
        f"   RMSE %: {metrics['rmse_pct_of_average_revenue']:.2f}% of average monthly test revenue"
    )
    print(f"   PSI   : {metrics['psi_test_vs_train']:.4f}  (train vs test revenue distribution)")
    print(f"   Gini  : {metrics['gini']:.4f}   (ranking quality of the monthly predictions)")
    print(
        f"   K2    : {metrics['k2_statistic']:.4f}  (p={metrics['k2_p_value']:.4f})"
        "   (D'Agostino-Pearson normality test on the test residuals —"
        " residual diagnostic, not an accuracy score)"
    )

    print("\n5) Artifacts")
    print("-" * 60)
    print(f"   Metrics JSON : {result['metrics_path']}")
    print(f"   Chart        : {result['chart_path']}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())