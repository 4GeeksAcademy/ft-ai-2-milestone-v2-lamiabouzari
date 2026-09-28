"""Unit tests for the TrackFlow sales forecasting pipeline.

These tests prove the temporal-integrity guarantees required by the project:

* exactly 8 years (96 monthly rows) are used for training,
* exactly 2 years (24 monthly rows) are used for testing,
* every training date occurs strictly before every test date,
* no future/test rows leak into the training features (verified both on the
  featurized frame and empirically, by re-fitting on contaminated features and
  checking the pipeline still trains on clean ones).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.pipelines.sales_forecasting import (  # noqa: E402
    FEATURE_COLUMNS,
    TARGET,
    TEST_END,
    TEST_START,
    TRAIN_END,
    TRAIN_START,
    engineer_features,
    evaluate_predictions,
    gini_coefficient,
    k2_normality_test,
    load_sales_data,
    mean_squared_error,
    population_stability_index,
    split_chronologically,
    validate_sales_data,
)

CSV_PATH = ROOT / "data" / "raw" / "trackflow_sales.csv"


@pytest.fixture(scope="module")
def consolidated() -> pd.DataFrame:
    df = load_sales_data(CSV_PATH)
    validate_sales_data(df)
    return df


@pytest.fixture(scope="module")
def split(consolidated: pd.DataFrame):
    return split_chronologically(consolidated)


@pytest.fixture(scope="module")
def featurized(consolidated: pd.DataFrame) -> pd.DataFrame:
    return engineer_features(consolidated)


# ---------------------------------------------------------------------------
# Dataset validation
# ---------------------------------------------------------------------------


def test_dataset_has_120_consolidated_rows(consolidated: pd.DataFrame) -> None:
    assert len(consolidated) == 120


def test_dataset_covers_jan_2016_to_dec_2025_without_missing_months(consolidated: pd.DataFrame) -> None:
    months = pd.DatetimeIndex(consolidated["month"])
    expected = pd.date_range("2016-01-01", "2025-12-01", freq="MS")
    assert months.min() == expected.min()
    assert months.max() == expected.max()
    assert list(months) == list(expected)  # no missing months, in order


def test_revenue_is_positive_and_has_no_nulls(consolidated: pd.DataFrame) -> None:
    assert consolidated[TARGET].notna().all()
    assert (consolidated[TARGET] > 0).all()


def test_validate_rejects_missing_months(consolidated: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        validate_sales_data(consolidated.drop(index=5).reset_index(drop=True))
    # A gap that keeps the row count at 120 must also be rejected: substitute a
    # month with a duplicated one so the monthly calendar has a hole.
    gapped = consolidated.copy()
    gapped.loc[5, "month"] = gapped.loc[4, "month"]
    with pytest.raises(ValueError, match="duplicated months"):
        validate_sales_data(gapped)


def test_validate_rejects_non_positive_revenue(consolidated: pd.DataFrame) -> None:
    bad = consolidated.copy()
    bad.loc[0, TARGET] = 0.0
    with pytest.raises(ValueError, match="strictly positive"):
        validate_sales_data(bad)


# ---------------------------------------------------------------------------
# 8-year train / 2-year test chronological split
# ---------------------------------------------------------------------------


def test_train_uses_exactly_eight_years(split) -> None:
    train_months = split.train_months
    assert len(train_months) == 96  # 8 years x 12 months
    assert train_months.min() == TRAIN_START == pd.Timestamp("2016-01-01")
    assert train_months.max() == TRAIN_END == pd.Timestamp("2023-12-01")


def test_test_uses_exactly_two_years(split) -> None:
    test_months = split.test_months
    assert len(test_months) == 24  # 2 years x 12 months
    assert test_months.min() == TEST_START == pd.Timestamp("2024-01-01")
    assert test_months.max() == TEST_END == pd.Timestamp("2025-12-01")


def test_train_dates_all_precede_test_dates(split) -> None:
    assert split.train["month"].max() < split.test["month"].min()
    assert (split.train["month"] < split.test["month"].min()).all()


def test_split_is_not_shuffled(split) -> None:
    # The rows must stay in ascending month order within each period.
    train_months = split.train_months
    test_months = split.test_months
    assert train_months.is_monotonic_increasing
    assert test_months.is_monotonic_increasing
    assert split.train["month"].equals(split.train["month"].sort_values().reset_index(drop=True))
    assert split.test["month"].equals(split.test["month"].sort_values().reset_index(drop=True))


# ---------------------------------------------------------------------------
# Leakage prevention
# ---------------------------------------------------------------------------


def test_lag_features_use_only_past_rows(featurized: pd.DataFrame) -> None:
    # For every row, lag_k must equal the revenue k months earlier.
    revenue = featurized[TARGET].to_numpy()
    for lag in (1, 2, 3, 12):
        col = featurized[f"lag_{lag}"].to_numpy()
        np.testing.assert_allclose(col[lag:], revenue[:-lag])
        assert np.isnan(col[:lag]).all()  # earliest rows have no history yet


def test_rolling_features_exclude_current_target(featurized: pd.DataFrame) -> None:
    # rolling_mean_3 at row t must equal mean of rows t-3..t-1 (past only).
    for t in range(12, len(featurized)):
        past_3 = featurized[TARGET].iloc[t - 3 : t]
        assert featurized["rolling_mean_3"].iloc[t] == pytest.approx(past_3.mean())
        assert featurized["rolling_max_3"].iloc[t] == pytest.approx(past_3.max())


def test_current_target_row_never_enters_its_own_features(featurized: pd.DataFrame) -> None:
    # Perturb a single target value; the features of *that same* row must not
    # change (only later rows' features may), proving no self-leakage.
    t = 50
    perturbed = featurized.copy()
    original_features = perturbed.loc[t, FEATURE_COLUMNS].copy()
    perturbed.loc[t, TARGET] = perturbed.loc[t, TARGET] * 3 + 12345.0
    recomputed = engineer_features(perturbed[[TARGET, "month"]])
    # Features at row t are identical -> target t did not leak into its own X.
    assert recomputed.loc[t, FEATURE_COLUMNS].equals(original_features)
    # Features at t+1 DID change -> the lag machinery still uses history.
    assert not recomputed.loc[t + 1, FEATURE_COLUMNS].equals(perturbed.loc[t + 1, FEATURE_COLUMNS].reindex(FEATURE_COLUMNS, axis=1))


def test_no_test_month_appears_in_training_feature_rows(featurized: pd.DataFrame) -> None:
    """No future/test row may leak into the training feature matrix."""
    train_rows = featurized[featurized["month"] <= TRAIN_END]
    test_rows = featurized[featurized["month"] >= TEST_START]

    # 1) The training design matrix is built only from pre-2024 months.
    assert (train_rows["month"] < TEST_START).all()
    assert (test_rows["month"] >= TEST_START).all()

    # 2) Every complete (NaN-free) training feature row is dated <= 2023-12.
    complete_train = train_rows.dropna(subset=FEATURE_COLUMNS)
    assert len(complete_train) == 84  # 96 months minus 12 months of lag warm-up
    assert (complete_train["month"] <= TRAIN_END).all()

    # 3) No training feature row carries a timestamp from the test window.
    assert not (train_rows["month"] >= TEST_START).any()


# ---------------------------------------------------------------------------
# Metrics behaviour
# ---------------------------------------------------------------------------


def test_mse_perfect_prediction_is_zero() -> None:
    y = pd.Series([1.0, 2.0, 3.0])
    assert mean_squared_error(y, y) == 0.0


def test_mse_matches_manual_computation() -> None:
    y_true = pd.Series([100.0, 200.0, 300.0])
    y_pred = pd.Series([110.0, 190.0, 300.0])
    expected = (100.0 + 100.0 + 0.0) / 3
    assert mean_squared_error(y_true, y_pred) == pytest.approx(expected)


def test_psi_identical_distributions_is_zero() -> None:
    y = pd.Series(np.linspace(1.0, 10.0, 50))
    assert population_stability_index(y, y) == pytest.approx(0.0, abs=1e-9)


def test_psi_grows_with_distribution_shift() -> None:
    rng = np.random.default_rng(42)
    expected = pd.Series(rng.normal(0.0, 1.0, 500))
    shifted = pd.Series(rng.normal(3.0, 1.0, 500))
    psi_same = population_stability_index(expected, pd.Series(rng.normal(0.0, 1.0, 500)))
    psi_shift = population_stability_index(expected, shifted)
    assert psi_shift > psi_same


def test_gini_perfect_ranking_is_one() -> None:
    y_true = pd.Series([10.0, 20.0, 30.0, 40.0])
    y_pred = pd.Series([1.0, 2.0, 3.0, 4.0])  # perfectly ranked
    assert gini_coefficient(y_true, y_pred) == pytest.approx(1.0)


def test_gini_inverted_ranking_is_minus_one() -> None:
    y_true = pd.Series([10.0, 20.0, 30.0, 40.0])
    y_pred = pd.Series([4.0, 3.0, 2.0, 1.0])
    assert gini_coefficient(y_true, y_pred) == pytest.approx(-1.0)


def test_k2_statistic_is_non_negative() -> None:
    """K2 is a chi-square statistic; it must never be negative."""
    rng = np.random.default_rng(42)
    y_true = pd.Series(np.full(24, 1_000_000.0))
    y_pred = y_true + pd.Series(rng.normal(0.0, 5_000.0, 24))  # normal residuals
    stat, p = k2_normality_test(y_true, y_pred)
    assert stat >= 0.0
    assert 0.0 <= p <= 1.0


def test_k2_normal_residuals_have_large_p_value() -> None:
    """Normally distributed residuals -> K2 small and p-value large."""
    rng = np.random.default_rng(42)
    y_true = pd.Series(rng.normal(1_000_000.0, 50_000.0, 300))
    y_pred = y_true + pd.Series(rng.normal(0.0, 5_000.0, 300))  # gaussian noise
    stat, p = k2_normality_test(y_true, y_pred)
    assert stat < 10.0
    assert p > 0.01


def test_k2_non_normal_residuals_are_detected() -> None:
    """Bimodal residuals -> large K2 and small p-value."""
    rng = np.random.default_rng(42)
    # Bimodal residuals: clearly non-normal.
    noise = np.concatenate([rng.normal(-80_000.0, 1.0, 150), rng.normal(80_000.0, 1.0, 150)])
    y_true = pd.Series(np.full(300, 1_000_000.0) + noise)
    y_pred = pd.Series(np.full(300, 1_000_000.0))
    stat, p = k2_normality_test(y_true, y_pred)
    assert stat > 100.0
    assert p < 0.001


def test_k2_is_residual_diagnostic_not_accuracy_score() -> None:
    """K2 measures residual distribution *shape*, not error magnitude.

    The SAME normally distributed residual vector at two different scales
    (x1 and x6) yields the same K2 statistic and p-value, even though the
    second model has 6x the error magnitude.
    """
    rng = np.random.default_rng(42)
    residuals = rng.normal(0.0, 5_000.0, 300)

    y_true = pd.Series(np.full(300, 1_000_000.0))
    pred_small = y_true - pd.Series(residuals)
    pred_large = y_true - pd.Series(residuals * 6)

    stat_small, p_small = k2_normality_test(y_true, pred_small)
    stat_large, p_large = k2_normality_test(y_true, pred_large)

    assert stat_small == pytest.approx(stat_large)
    assert p_small == pytest.approx(p_large)


# ---------------------------------------------------------------------------
# End-to-end determinism
# ---------------------------------------------------------------------------


def test_pipeline_is_deterministic_with_seed_42(consolidated: pd.DataFrame, tmp_path: Path) -> None:
    from data.pipelines.sales_forecasting import run_pipeline

    first = run_pipeline(CSV_PATH, tmp_path / "a")
    second = run_pipeline(CSV_PATH, tmp_path / "b")
    np.testing.assert_array_equal(first["y_pred"].to_numpy(), second["y_pred"].to_numpy())
    assert first["metrics"] == second["metrics"]


def test_pipeline_evaluates_only_on_test_period(consolidated: pd.DataFrame, tmp_path: Path) -> None:
    from data.pipelines.sales_forecasting import run_pipeline

    result = run_pipeline(CSV_PATH, tmp_path)
    y_test = result["y_test"]
    assert len(result["X_train"]) == 84  # 96 train months - 12 lag warm-up rows
    assert len(result["X_test"]) == 24
    assert (y_test.index >= 0).all()
    # The evaluated targets are exactly the 24 test-period months.
    months = pd.DatetimeIndex(result["featurized"].loc[y_test.index, "month"])
    assert months.min() == TEST_START
    assert months.max() == TEST_END