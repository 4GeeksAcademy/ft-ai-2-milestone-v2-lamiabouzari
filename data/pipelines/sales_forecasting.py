"""Sales forecasting pipeline for TrackFlow monthly revenue.

Implements the "Sales Forecasting with a Regression Model" deliverable described in
``CONTEXT-trackflow.en.md``:

* Loads and validates ``data/raw/trackflow_sales.csv`` (120 consolidated monthly rows,
  2016-01 .. 2025-12, no missing months, strictly positive ``revenue_eur``).
* Splits the series **chronologically** (never shuffled):
  - TRAIN = first 8 years  → 2016-01 .. 2023-12 (96 rows)
  - TEST  = last 2 years   → 2024-01 .. 2025-12 (24 rows)
* Engineers **causal** (leakage-free) features: calendar/seasonal flags, lagged
  revenue, and rolling statistics that only use past observations.
* Trains a Random Forest regressor with ``random_state=42``.
* Computes the four required metrics on the test period only: MSE, PSI, Gini, K2
(D'Agostino-Pearson normality test on the test residuals — a residual
diagnostic, not an accuracy score).
* Draws the 2024-2025 actual-vs-predicted chart with a variability band.

Every feature is computed from the *whole* series *after* sorting by month but the
split is done by date, so a training row can only ever reference months that are
strictly earlier than itself. See ``docs/sales-forecasting.md`` for the metric
definitions and the interpretation of the TrackFlow seasonal pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import normaltest
from sklearn.ensemble import RandomForestRegressor

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RANDOM_STATE = 42
TARGET = "revenue_eur"

# Chronological split boundaries (course requirement: 8 train years / 2 test years).
TRAIN_START = pd.Timestamp("2016-01-01")
TRAIN_END = pd.Timestamp("2023-12-01")
TEST_START = pd.Timestamp("2024-01-01")
TEST_END = pd.Timestamp("2025-12-01")

EXPECTED_ROWS = 120
EXPECTED_FIRST_MONTH = pd.Timestamp("2016-01-01")
EXPECTED_LAST_MONTH = pd.Timestamp("2025-12-01")

# Lag / rolling window configuration (in months). The largest lookback is 12
# months, so the first 12 rows of the whole series cannot produce a complete
# feature vector; those rows are dropped before training. Because the split is
# chronological and the lookback never crosses the train/test boundary in a
# harmful way (train rows only use train-period history), no test information
# can leak into the training features.
LAGS = (1, 2, 3, 12)
ROLLING_WINDOWS = (3, 6, 12)

# Model choice: Random Forest. Rationale (documented for the project review):
# * Small dataset (96 effective training rows) — boosted trees such as XGBoost
#   can overfit that few samples and need careful early stopping, while bagging
#   is more forgiving.
# * The series is dominated by a multiplicative growth trend + sharp seasonal
#   spikes; tree ensembles capture the non-linear seasonal interaction
#   (month-of-year x recent momentum) without feature scaling.
# * Fully deterministic with fixed ``random_state=42`` (bagging subsampling and
#   feature subsampling are seeded), which the course requires for
#   reproducibility.
# * No extra dependency: it ships with scikit-learn, which the repository's
#   existing requirements style prefers over adding a compiled XGBoost wheel.
MODEL_PARAMS = dict(
    n_estimators=500,
    max_depth=6,
    min_samples_leaf=2,
    random_state=RANDOM_STATE,
    n_jobs=1,  # keep runs deterministic and reproducible across machines
)

# How many months ahead the recursive forecast walks for the 2024-2025 chart.
FORECAST_HORIZON_MONTHS = 24

# Quantiles of the tree ensemble used as the prediction variability band.
BAND_LOW_Q = 0.1
BAND_HIGH_Q = 0.9


# ---------------------------------------------------------------------------
# Data loading and validation
# ---------------------------------------------------------------------------


def load_sales_data(csv_path: str | Path) -> pd.DataFrame:
    """Load the TrackFlow sales CSV and keep only the consolidated rows."""
    df = pd.read_csv(csv_path)
    df["month"] = pd.to_datetime(df["month"])
    consolidated = df[df["market"] == "consolidated"].copy()
    consolidated = consolidated.sort_values("month").reset_index(drop=True)
    return consolidated


def validate_sales_data(consolidated: pd.DataFrame) -> None:
    """Raise ``ValueError`` unless the dataset matches the TrackFlow contract.

    Contract (from ``CONTEXT-trackflow.en.md``):
    * exactly 120 consolidated monthly rows,
    * January 2016 through December 2025 with **no missing months**,
    * no null values in the modelling columns,
    * strictly positive ``revenue_eur``.
    """
    required = {"month", "revenue_eur", "shipments_processed", "avg_revenue_per_shipment_eur", "market"}
    missing_cols = required - set(consolidated.columns)
    if missing_cols:
        raise ValueError(f"dataset is missing required columns: {sorted(missing_cols)}")

    if len(consolidated) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} consolidated rows, found {len(consolidated)}")

    months = consolidated["month"]
    if months.min() != EXPECTED_FIRST_MONTH or months.max() != EXPECTED_LAST_MONTH:
        raise ValueError(
            f"date range must be {EXPECTED_FIRST_MONTH.date()} .. {EXPECTED_LAST_MONTH.date()}, "
            f"found {months.min().date()} .. {months.max().date()}"
        )
    if months.duplicated().any():
        raise ValueError("duplicated months found in the consolidated series")

    expected_months = pd.date_range(EXPECTED_FIRST_MONTH, EXPECTED_LAST_MONTH, freq="MS")
    month_list = list(months)
    if month_list != list(expected_months):
        raise ValueError("there are missing, duplicated or out-of-order months in the monthly series")

    numeric_cols = ["revenue_eur", "shipments_processed", "avg_revenue_per_shipment_eur"]
    if consolidated[numeric_cols].isnull().any().any():
        raise ValueError("null values found in numeric modelling columns")
    if consolidated["month"].isnull().any():
        raise ValueError("null values found in the month column")

    if (consolidated[TARGET] <= 0).any():
        raise ValueError("revenue_eur must be strictly positive for every month")
    if (consolidated["shipments_processed"] <= 0).any():
        raise ValueError("shipments_processed must be strictly positive for every month")


# ---------------------------------------------------------------------------
# Chronological split (no shuffling, no future leakage)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChronologicalSplit:
    """Result of the fixed 8-year train / 2-year test temporal split."""

    train: pd.DataFrame
    test: pd.DataFrame

    @property
    def train_months(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(self.train["month"])

    @property
    def test_months(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(self.test["month"])


def split_chronologically(df: pd.DataFrame) -> ChronologicalSplit:
    """Split by calendar date: TRAIN = 2016-01..2023-12, TEST = 2024-01..2025-12.

    The split is a hard date cut, never a random shuffle, so the model can never
    "see" the future at training time through the row order.
    """
    df = df.sort_values("month").reset_index(drop=True)
    train_mask = (df["month"] >= TRAIN_START) & (df["month"] <= TRAIN_END)
    test_mask = (df["month"] >= TEST_START) & (df["month"] <= TEST_END)

    train = df[train_mask].reset_index(drop=True)
    test = df[test_mask].reset_index(drop=True)

    if len(train) != 96 or len(test) != 24:
        raise ValueError(
            f"chronological split must yield 96 train rows and 24 test rows, got {len(train)}/{len(test)}"
        )
    if train["month"].max() >= test["month"].min():
        raise ValueError("training period must end strictly before the test period")
    return ChronologicalSplit(train=train, test=test)


# ---------------------------------------------------------------------------
# Causal feature engineering
# ---------------------------------------------------------------------------

FEATURE_COLUMNS = [
    "month_index",
    "year",
    "month_of_year",
    "quarter",
    "is_feb_slowdown",
    "is_nov_peak",
    "is_dec_peak",
    "is_peak_season",
    "sin_month",
    "cos_month",
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_12",
    "rolling_mean_3",
    "rolling_mean_12",
    "rolling_std_3",
    "rolling_std_12",
    "rolling_min_3",
    "rolling_max_3",
    "yoy_growth_1",
]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build the causal feature matrix for the sorted monthly series.

    All features at row *t* are functions of observations **strictly before** *t*
    (lags) or of the calendar position of *t* (known in advance). The 12-month
    rolling statistics are computed on a window that ends at ``t-1`` because the
    ``.shift(1)`` is applied before ``.rolling(...)`` — this is the key guard
    against leakage: the target of row *t* never enters its own features.

    Feature groups
    --------------
    Calendar / seasonal (known in advance):
        ``month_index``          months since 2016-01 — smooth growth trend proxy.
        ``year``, ``quarter``    slow trend + intra-year position.
        ``month_of_year``        raw calendar month.
        ``is_feb_slowdown``      flag for the February e-commerce slowdown.
        ``is_nov_peak``          Black Friday shipping peak.
        ``is_dec_peak``          holiday e-commerce peak.
        ``is_peak_season``       Nov+Dec combined peak flag.
        ``sin_month``/``cos_month``  cyclic encoding of the month of year.

    Lagged revenue (only past observations):
        ``lag_1``, ``lag_2``, ``lag_3``   recent momentum.
        ``lag_12``                        same calendar month one year earlier —
                                          captures the yearly seasonal level.

    Rolling statistics over past observations only:
        ``rolling_mean_3``   smoothed recent level.
        ``rolling_std_3``    recent volatility.
        ``rolling_mean_12``  annual mean — the "average" reference the seasonal
                             pattern is defined against (Nov/Dec +25-35%, Feb
                             -10-15% relative to the yearly average).
        ``rolling_std_12``   annual volatility.
        ``rolling_min_3`` / ``rolling_max_3``  recent envelope.
        ``yoy_growth_1``     year-over-year growth implied by lag_1/lag_12,
                             matching the 3-9% annual growth pattern.
    """
    df = df.sort_values("month").reset_index(drop=True)
    revenue = df[TARGET]

    # --- calendar / seasonal features (deterministic, known in advance) ---
    origin = pd.Timestamp("2016-01-01")
    df["month_index"] = ((df["month"].dt.year - origin.year) * 12 + (df["month"].dt.month - origin.month)).astype(int)
    df["year"] = df["month"].dt.year.astype(int)
    df["month_of_year"] = df["month"].dt.month.astype(int)
    df["quarter"] = df["month"].dt.quarter.astype(int)
    df["is_feb_slowdown"] = (df["month_of_year"] == 2).astype(int)
    df["is_nov_peak"] = (df["month_of_year"] == 11).astype(int)
    df["is_dec_peak"] = (df["month_of_year"] == 12).astype(int)
    df["is_peak_season"] = df["month_of_year"].isin([11, 12]).astype(int)
    angle = 2.0 * np.pi * (df["month_of_year"] - 1) / 12.0
    df["sin_month"] = np.sin(angle).round(6)
    df["cos_month"] = np.cos(angle).round(6)

    # --- lagged revenue (only past observations) ---
    for lag in LAGS:
        df[f"lag_{lag}"] = revenue.shift(lag)

    # --- rolling statistics over the *past* window only ---
    # shift(1) moves the window to end at t-1, so the current target is excluded.
    shifted = revenue.shift(1)
    for window in ROLLING_WINDOWS:
        df[f"rolling_mean_{window}"] = shifted.rolling(window, min_periods=window).mean()
    df["rolling_std_3"] = shifted.rolling(3, min_periods=3).std()
    df["rolling_std_12"] = shifted.rolling(12, min_periods=12).std()
    df["rolling_min_3"] = shifted.rolling(3, min_periods=3).min()
    df["rolling_max_3"] = shifted.rolling(3, min_periods=3).max()
    df["yoy_growth_1"] = (df["lag_1"] / df["lag_12"] - 1.0).where(df["lag_12"].notna())

    return df


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------


def train_model(X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestRegressor:
    """Fit the Random Forest regressor with the fixed seed."""
    model = RandomForestRegressor(**MODEL_PARAMS)
    model.fit(X_train, y_train)
    return model


# ---------------------------------------------------------------------------
# Metrics (definitions documented in docs/sales-forecasting.md)
# ---------------------------------------------------------------------------


def mean_squared_error(y_true: pd.Series | np.ndarray, y_pred: pd.Series | np.ndarray) -> float:
    """MSE in EUR² — mean squared deviation of predictions from actual revenue."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean((y_true - y_pred) ** 2))


def population_stability_index(
    expected: pd.Series | np.ndarray,
    actual: pd.Series | np.ndarray,
    n_bins: int = 10,
    eps: float = 1e-6,
) -> float:
    """Population Stability Index between train and test score distributions.

    Both distributions are binned on the *training* quantiles (the reference),
    then PSI = Σ (actual% - expected%) · ln(actual% / expected%). Values below
    ~0.1 mean the feature distribution did not shift between the 8-year training
    window and the 2-year test window (i.e. the LA/Zaragoza volume mix stayed
    stable from the model's point of view).
    """
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)

    # Bin edges come from the training (expected) distribution quantiles so that
    # both periods are measured against the same yardstick.
    edges = np.unique(np.quantile(expected, np.linspace(0.0, 1.0, n_bins + 1)))
    if edges.size < 2:  # pragma: no cover - degenerate constant input
        return 0.0
    edges[0] = -np.inf
    edges[-1] = np.inf

    expected_counts = np.histogram(expected, bins=edges)[0] / expected.size
    actual_counts = np.histogram(actual, bins=edges)[0] / actual.size

    # Avoid ln(0): floor every bin share at eps.
    expected_pct = np.clip(expected_counts, eps, None)
    actual_pct = np.clip(actual_counts, eps, None)

    psi = float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))
    return psi


def gini_coefficient(y_true: pd.Series | np.ndarray, y_pred: pd.Series | np.ndarray) -> float:
    """Normalized Gini of the ranking quality of the predictions.

    Course meaning: a high Gini means the model correctly *orders* months — it
    ranks a normal low-season February below an atypical collapse that deserves
    investigation. Computed as the Somers' D of the predictions against the
    target: the ratio between the covariance of the actuals with the predicted
    ranks and the covariance of the actuals with their own ranks. This yields
    +1 for a perfectly ranked prediction and -1 for a perfectly inverted one.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    n = y_true.size
    if n < 2:
        return 0.0

    # Average ranks handle ties deterministically.
    pred_ranks = pd.Series(y_pred).rank(method="average").to_numpy()
    true_ranks = pd.Series(y_true).rank(method="average").to_numpy()
    cov_pred = float(np.cov(y_true, pred_ranks, bias=True)[0, 1])
    cov_true = float(np.cov(y_true, true_ranks, bias=True)[0, 1])
    if cov_true == 0:  # pragma: no cover - constant target
        return 0.0
    return float(cov_pred / cov_true)


def k2_normality_test(
    y_true: pd.Series | np.ndarray, y_pred: pd.Series | np.ndarray
) -> tuple[float, float]:
    """K2 normality test (D'Agostino-Pearson) on the TEST residuals.

    Residual diagnostic, not an accuracy score: it tests whether
    ``residuals = y_true - y_pred`` are consistent with a normal
    distribution. ``scipy.stats.normaltest`` combines the skewness and
    kurtosis into a single chi-square statistic ``k2`` (always >= 0).

    Returns ``(k2_statistic, k2_p_value)``. A lower statistic / larger
    p-value means the residuals look more normally distributed.
    """
    residuals = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    statistic, p_value = normaltest(residuals)
    return float(statistic), float(p_value)


def evaluate_predictions(
    y_test: pd.Series,
    y_pred: pd.Series,
    y_train: pd.Series,
) -> dict[str, float]:
    """Compute all four required metrics on the test period only."""
    mse = mean_squared_error(y_test, y_pred)
    rmse = float(np.sqrt(mse))
    mean_test_revenue = float(np.mean(np.asarray(y_test, dtype=float)))
    k2_stat, k2_p = k2_normality_test(y_test, y_pred)
    return {
        "mse_eur2": mse,
        "rmse_eur": rmse,
        # Interpretable error relative to the average monthly test revenue.
        "rmse_pct_of_average_revenue": float(rmse / mean_test_revenue * 100.0),
        # Secondary scale-free figure: MSE relative to the squared mean revenue.
        "mse_pct_of_squared_mean_revenue": float(mse / mean_test_revenue**2 * 100.0),
        # Train-vs-test revenue-distribution PSI (see docs/sales-forecasting.md:
        # the CSV only has consolidated rows, so a true US-vs-Spain market-mix
        # PSI cannot be calculated from this dataset).
        "psi_test_vs_train": population_stability_index(y_train, y_test),
        "gini": gini_coefficient(y_test, y_pred),
        # Residual normality diagnostic (not an accuracy score).
        "k2_statistic": k2_stat,
        "k2_p_value": k2_p,
    }


# ---------------------------------------------------------------------------
# Recursive multi-step forecast with variability band
# ---------------------------------------------------------------------------


def recursive_forecast_with_band(
    model: RandomForestRegressor,
    history: pd.DataFrame,
    horizon: int = FORECAST_HORIZON_MONTHS,
) -> pd.DataFrame:
    """Walk the horizon forward, feeding predictions back as lag features.

    For each future month the full causal feature row is rebuilt from the
    history (which grows by one predicted value per step), then the ensemble's
    individual tree predictions give the variability band
    [q10, q90] around the mean forecast. This measures how much the forest's
    trees disagree — a natural uncertainty range for a Random Forest.
    """
    last_month = history["month"].max()
    history = history.sort_values("month").reset_index(drop=True)
    revenue = history[TARGET].astype(float).tolist()
    months = list(history["month"])

    rows: list[dict[str, float]] = []
    for step in range(1, horizon + 1):
        next_month = last_month + pd.offsets.MonthBegin(step)
        months.append(next_month)

        series = pd.Series(revenue)
        feat = {TARGET: np.nan}
        origin = pd.Timestamp("2016-01-01")
        m = next_month
        feat["month_index"] = (m.year - origin.year) * 12 + (m.month - origin.month)
        feat["year"] = m.year
        feat["month_of_year"] = m.month
        feat["quarter"] = (m.month - 1) // 3 + 1
        feat["is_feb_slowdown"] = int(m.month == 2)
        feat["is_nov_peak"] = int(m.month == 11)
        feat["is_dec_peak"] = int(m.month == 12)
        feat["is_peak_season"] = int(m.month in (11, 12))
        angle = 2.0 * np.pi * (m.month - 1) / 12.0
        feat["sin_month"] = round(float(np.sin(angle)), 6)
        feat["cos_month"] = round(float(np.cos(angle)), 6)

        for lag in LAGS:
            feat[f"lag_{lag}"] = float(series.iloc[-lag])
        shifted = series.iloc[:-1]  # window ends at t-1
        for window in ROLLING_WINDOWS:
            feat[f"rolling_mean_{window}"] = float(shifted.iloc[-window:].mean())
        feat["rolling_std_3"] = float(shifted.iloc[-3:].std(ddof=1))
        feat["rolling_std_12"] = float(shifted.iloc[-12:].std(ddof=1))
        feat["rolling_min_3"] = float(shifted.iloc[-3:].min())
        feat["rolling_max_3"] = float(shifted.iloc[-3:].max())
        lag12 = feat["lag_12"]
        feat["yoy_growth_1"] = feat["lag_1"] / lag12 - 1.0 if lag12 else np.nan

        feature_row = pd.DataFrame([feat])
        X = feature_row[FEATURE_COLUMNS]

        pred = float(model.predict(X)[0])
        tree_preds = np.asarray([tree.predict(X.to_numpy())[0] for tree in model.estimators_])
        low, high = np.quantile(tree_preds, [BAND_LOW_Q, BAND_HIGH_Q])

        rows.append(
            {
                "month": next_month,
                "predicted_revenue_eur": pred,
                "band_low_eur": float(low),
                "band_high_eur": float(high),
            }
        )
        revenue.append(pred)  # feedback loop: prediction becomes next step's history

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------


def plot_test_forecast(
    test: pd.DataFrame,
    y_test: pd.Series,
    y_pred: pd.Series,
    band_low: np.ndarray,
    band_high: np.ndarray,
    metrics: dict[str, float],
    out_path: str | Path,
) -> Path:
    """Draw actual vs predicted 2024-2025 revenue with the variability band."""
    import matplotlib

    matplotlib.use("Agg")  # headless rendering
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    months = pd.DatetimeIndex(test["month"])
    fig, ax = plt.subplots(figsize=(13, 6))

    ax.fill_between(
        months,
        band_low,
        band_high,
        color="#4c72b0",
        alpha=0.22,
        label=f"Prediction variability ({int(BAND_LOW_Q * 100)}–{int(BAND_HIGH_Q * 100)}% of forest trees)",
    )
    ax.plot(months, np.asarray(y_test, dtype=float), color="#1f77b4", marker="o", lw=2, label="Real revenue")
    ax.plot(months, np.asarray(y_pred, dtype=float), color="#dd8452", marker="s", lw=2, ls="--", label="Predicted revenue")

    ax.set_title(
        "TrackFlow — monthly revenue forecast, test period 2024-2025\n"
        f"MSE={metrics['mse_eur2']:,.0f} EUR²  |  RMSE={metrics['rmse_eur']:,.0f} EUR "
        f"({metrics['rmse_pct_of_average_revenue']:.1f}% of avg revenue)  |  "
        f"Gini={metrics['gini']:.3f}  |  PSI={metrics['psi_test_vs_train']:.3f}  |  "
        f"K2={metrics['k2_statistic']:.3f} (p={metrics['k2_p_value']:.3f})",
        fontsize=11,
    )
    ax.set_xlabel("Month")
    ax.set_ylabel("Consolidated revenue (EUR)")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.tick_params(axis="x", rotation=45)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    fig.tight_layout()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# End-to-end orchestration
# ---------------------------------------------------------------------------


def run_pipeline(csv_path: str | Path, artifacts_dir: str | Path) -> dict:
    """Run the whole forecasting pipeline and persist metrics + chart.

    Returns a dict with the split info, the model, the test predictions and the
    metric dictionary — handy for tests and notebooks.
    """
    artifacts_dir = Path(artifacts_dir)

    consolidated = load_sales_data(csv_path)
    validate_sales_data(consolidated)
    split = split_chronologically(consolidated)

    featurized = engineer_features(consolidated)
    # Rows whose 12-month lookback reaches before the series start are dropped
    # from *training* only; the 2024-2025 test rows have full history available.
    featurized_train = featurized[featurized["month"] <= TRAIN_END].dropna(subset=FEATURE_COLUMNS)
    featurized_test = featurized[featurized["month"] >= TEST_START].dropna(subset=FEATURE_COLUMNS)

    X_train = featurized_train[FEATURE_COLUMNS]
    y_train = featurized_train[TARGET]
    X_test = featurized_test[FEATURE_COLUMNS]
    y_test = featurized_test[TARGET]

    model = train_model(X_train, y_train)
    y_pred = model.predict(X_test)

    # Variability band: per-tree quantiles on the test rows.
    tree_matrix = np.asarray(
        [[tree.predict(X_test.to_numpy()) for tree in model.estimators_]]
    ).reshape(len(model.estimators_), len(X_test))
    band_low = np.quantile(tree_matrix, BAND_LOW_Q, axis=0)
    band_high = np.quantile(tree_matrix, BAND_HIGH_Q, axis=0)

    metrics = evaluate_predictions(y_test, pd.Series(y_pred, index=X_test.index), y_train)

    metrics_path = artifacts_dir / "sales_forecast_metrics.json"
    import json

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": "RandomForestRegressor",
        "random_state": RANDOM_STATE,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "train_range": [str(split.train_months.min().date()), str(split.train_months.max().date())],
        "test_range": [str(split.test_months.min().date()), str(split.test_months.max().date())],
        "metrics": metrics,
    }
    metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    chart_path = plot_test_forecast(
        featurized_test,
        y_test,
        pd.Series(y_pred, index=X_test.index),
        band_low,
        band_high,
        metrics,
        artifacts_dir / "sales_forecast_2024_2025.png",
    )

    return {
        "model": model,
        "split": split,
        "featurized": featurized,
        "X_train": X_train,
        "y_train": y_train,
        "X_test": X_test,
        "y_test": y_test,
        "y_pred": pd.Series(y_pred, index=X_test.index),
        "metrics": metrics,
        "metrics_path": metrics_path,
        "chart_path": chart_path,
    }