# TrackFlow — Sales Forecasting with a Regression Model

Deliverable documentation for the project described in
[`CONTEXT-trackflow.en.md`](../CONTEXT-trackflow.en.md).

---

## 1. Goal

Thomas (CEO) wants to know whether it is feasible to **predict TrackFlow's monthly
revenue for the coming months** before investing in a full executive dashboard.
TrackFlow bills on shipment volume for e-commerce brands, so revenue follows the
e-commerce calendar: a **November–December peak** (Black Friday + holiday season)
and a **February slowdown** after the peak season.

This project trains a regression model on the consolidated monthly revenue
(`revenue_eur`) and evaluates it with the four required metrics.

---

## 2. Files

| File | Purpose |
| --- | --- |
| `data/raw/trackflow_sales.csv` | Source dataset (provided, not modified). |
| `data/pipelines/sales_forecasting.py` | Pipeline module: loading, validation, split, feature engineering, model, metrics, chart. |
| `scripts/train_sales_forecast.py` | Runnable end-to-end training script. |
| `tests/pipelines/test_sales_forecast.py` | Unit tests for the 8/2-year split and leakage prevention. |
| `data/eval/sales_forecast/` | Output artifacts: metrics JSON + forecast chart. |

Run it:

```bash
python scripts/train_sales_forecast.py
```

---

## 3. Dataset and validation

`data/raw/trackflow_sales.csv` contains the monthly consolidated revenue for
TrackFlow. The pipeline (`load_sales_data` + `validate_sales_data`) enforces the
contract from the context:

- exactly **120 consolidated monthly rows**,
- covering **2016-01 through 2025-12** with **no missing months**,
- **no null values** in the modelling columns,
- **strictly positive** `revenue_eur` (business constraint).

The target variable is `revenue_eur` from the `consolidated` row.

---

## 4. Train/test split — chronological, never shuffled

Time series data must not be split randomly: random splits let the model "see
the future" and inflate the metrics. The split is a hard calendar cut:

| Period | Range | Rows |
| --- | --- | --- |
| **TRAIN** (8 years) | 2016-01 .. 2023-12 | 96 monthly rows |
| **TEST** (2 years) | 2024-01 .. 2025-12 | 24 monthly rows |

`split_chronologically()` asserts both row counts and that every training date
is strictly before every test date. Rows are kept in ascending month order
(no shuffling anywhere in the pipeline).

---

## 5. Feature engineering (causal / leakage-free)

All features at row *t* depend only on **calendar information of *t*** (known in
advance) or on observations **strictly before *t***. The largest lookback is
12 months, so the first 12 rows of the series cannot produce a complete feature
vector; those warm-up rows are dropped from training (96 → 84 training rows).

### Calendar / seasonal features (known in advance)

- `month_index` — months since 2016-01; smooth proxy for the growth trend.
- `year`, `quarter`, `month_of_year` — slow trend and intra-year position.
- `is_feb_slowdown` — flag for the February e-commerce slowdown (−10–15% vs the
  yearly average).
- `is_nov_peak`, `is_dec_peak`, `is_peak_season` — flags for the Black Friday /
  holiday shipping peak (+25–35% vs the yearly average).
- `sin_month`, `cos_month` — cyclic encoding of the month of year.

### Lagged revenue (only past observations)

- `lag_1`, `lag_2`, `lag_3` — recent momentum.
- `lag_12` — same calendar month one year earlier; carries the yearly seasonal
  level and the 3–9% annual growth.

### Rolling statistics over the past window only

- `rolling_mean_3`, `rolling_std_3`, `rolling_min_3`, `rolling_max_3` — smoothed
  recent level, volatility and envelope over the 3 months **ending at t−1**.
- `rolling_mean_12`, `rolling_std_12` — annual average and volatility. The
  annual average is the reference the TrackFlow seasonal pattern is defined
  against.
- `yoy_growth_1` — year-over-year growth implied by `lag_1 / lag_12 − 1`,
  matching the 3–9% annual growth pattern.

### Leakage prevention

`shift(1)` is applied **before** `rolling(...)`, so every rolling window ends at
`t−1` and the current target never enters its own features. Lags are pure
`shift(k)` operations. The tests
(`tests/pipelines/test_sales_forecast.py`) verify this in three ways:

1. `lag_k[t] == revenue[t−k]` for every row, and warm-up rows are NaN.
2. Perturbing the target of row *t* does not change row *t*'s features (no
   self-leakage), while row *t+1* does change (the lag machinery works).
3. The training design matrix contains only months ≤ 2023-12; no test-period
   timestamp ever appears in a training feature row.

---

## 6. Model choice: Random Forest

**Selected model:** `RandomForestRegressor(n_estimators=500, max_depth=6,
min_samples_leaf=2, random_state=42)`.

**Why Random Forest instead of XGBoost:**

1. **Small data.** After the 12-month warm-up there are only **84 complete
   training rows**. Boosted trees (XGBoost) add trees sequentially and can
   overfit such a small sample; Random Forest averages many de-correlated trees
   (bagging), which is more robust here.
2. **Non-linear seasonality without tuning.** The series combines a multiplicative
   growth trend with sharp seasonal spikes; trees capture the interaction
   between calendar features and recent momentum without any feature scaling.
3. **Determinism.** With `random_state=42` (and `n_jobs=1`) the training and all
   predictions are fully reproducible, as the project requires.
4. **No extra dependency.** It ships with scikit-learn, keeping the repository's
   existing dependency style (no compiled XGBoost wheel needed).
5. **Built-in uncertainty estimate.** The individual trees' predictions give a
   natural variability band for the 2024–2025 chart (see §8).

---

## 7. Metrics (evaluated on the test period only)

All four metrics are computed on **2024-01 .. 2025-12 only**; the training data
never participates in the evaluation.

### MSE — Mean Squared Error (EUR²)

`MSE = (1/n) · Σ (actual − predicted)²`, in **EUR²**. Because EUR² is hard to
interpret, the metrics also report:

- **RMSE in EUR** — the square root of MSE, back on the revenue scale.
- **RMSE as a percentage of the average monthly test revenue** —
  `RMSE / mean(test revenue) · 100`; the primary interpretable error figure.
- **MSE as a percentage of the squared mean revenue** —
  `MSE / (mean test revenue)² · 100` (a scale-free secondary figure, kept
  clearly labelled as such because EUR² alone is meaningless).

### PSI — Population Stability Index

PSI compares the **distribution** of the scored values between the training and
the test window: both periods are binned on the training quantiles and
`PSI = Σ (actual% − expected%) · ln(actual% / expected%)`.

- PSI < 0.1 → no significant shift: the volume mix (LA/Zaragoza) that the model
  learned stayed stable.
- 0.1 ≤ PSI < 0.25 → moderate shift worth reporting (possible expansion or
  contraction of operations in one country).
- PSI ≥ 0.25 → major shift; the model should be re-examined.

In this project PSI is computed between the **training actuals** and the
**test actuals** of the target series — i.e. it is a **train-vs-test
revenue-distribution PSI**.

**Scope limitation:** the provided TrackFlow CSV (`data/raw/trackflow_sales.csv`)
contains **only consolidated rows** (no per-market breakdown). Therefore a true
**US-vs-Spain market-mix PSI** — the check the context describes for detecting a
shift in the Los Angeles / Zaragoza volume split — **cannot be calculated from
this dataset**. We do **not** synthesize a 60/40 market split just to compute
PSI; the reported value is the consolidated revenue-distribution shift, which
here is dominated by the 3–9% annual growth trend (a large PSI is expected and
indicates trend, not a market-mix anomaly).

### Gini

The Gini coefficient here measures the **ranking quality** of the predictions:
it is the covariance between the actual values and the predicted ranks
(normalized), i.e. how well the model *orders* the months by revenue. It ranges
from −1 (perfectly inverted ranking) to +1 (perfect ranking); 0 is random.

Thomas' use case: a high Gini means the model correctly ranks a **normal
low-season February** below an **atypical drop** — so an anomalous February that
falls below the model's expectation is a signal worth investigating, while a
predictably seasonal low month is not.

### K2 — D'Agostino-Pearson normality test on the residuals

K2 here is **not** an accuracy score: it is a **residual diagnostic**. The
test residuals `residuals = actual − predicted` are tested for normality with
`scipy.stats.normaltest`, which combines the sample skewness and kurtosis into
a single chi-square statistic:

- **`k2_statistic`** — always ≥ 0; small values mean the residuals are
  consistent with a normal distribution.
- **`k2_p_value`** — probability of observing this statistic if the residuals
  were normal; a **larger p-value** means the residuals look more normal.

**Interpretation:** lower K2 / larger p-value → residuals are more consistent
with a normal distribution, i.e. the model's errors are well-behaved
(unbiased noise) rather than systematically biased or heavy-tailed. A large K2
with a small p-value indicates skewed or heavy-tailed residuals worth
investigating (e.g. the November/December peaks, which a Random Forest tends to
smooth).

---

## 8. Visualization (2024–2025)

`plot_test_forecast()` renders the two test years:

- **real revenue** (solid line),
- **predicted revenue** (dashed line),
- **prediction variability band** — the 10th–90th percentile of the individual
  tree predictions, i.e. how much the forest's trees disagree for each month
  (a natural uncertainty range for a Random Forest).

Saved to `data/eval/sales_forecast/sales_forecast_2024_2025.png`.

---

## 9. Interpretation of the TrackFlow seasonal pattern

The dataset (fixed seed `random_state=42`) exhibits, every year:

- **November–December peak:** revenue rises **+25–35%** relative to the yearly
  average (Black Friday shipping peak and holiday e-commerce season). The model
  sees this through `is_nov_peak`, `is_dec_peak`, `is_peak_season`, the cyclic
  month encoding, and `lag_12` (last year's November/December level).
- **February slowdown:** revenue drops **−10–15%** relative to the yearly
  average (post-peak-season e-commerce slowdown). Captured by `is_feb_slowdown`
  and by the rolling statistics, which place February below the annual mean.
- **Growth:** base annual growth of 6% with ±3% variation (3% or 9% per year,
  always positive). Captured by `month_index`, `year`, `lag_12` and
  `yoy_growth_1`.
- All other months fluctuate moderately (±5%) around the annual growth trend.

**What to expect:** the predictions should reproduce the November/December
humps and the February dips of 2024–2025. Because the test years continue the
3–9% annual growth, small underestimation of the trend is the expected error
mode; a low Gini or a large PSI would indicate the seasonal ranking or the
volume mix moved between the training and the test windows, which would warrant
re-investigating the feature set before Thomas invests in the dashboard.

---

## 10. Reproducibility

- Fixed seed `random_state=42` for the model (and the dataset generator).
- `n_jobs=1` so results do not depend on thread scheduling.
- Metrics JSON written to `data/eval/sales_forecast/sales_forecast_metrics.json`
  on every run for traceability.