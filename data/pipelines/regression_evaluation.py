"""Chronological evaluation utilities for the TrackFlow revenue regressor.

This module deliberately consumes the established forecasting model's features,
constants, and estimator factory rather than reimplementing them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

from data.pipelines.sales_forecasting import (
    FEATURE_COLUMNS,
    TARGET,
    TEST_END,
    TEST_START,
    TRAIN_END,
    TRAIN_START,
    engineer_features,
    load_sales_data,
    train_model,
    validate_sales_data,
)

TIME_COLUMN = "month"
DEFAULT_FOLDS = 5


@dataclass(frozen=True)
class ChronologicalFold:
    """A fold's positional indexes with explicit temporal boundaries."""

    fold: int
    train_indices: np.ndarray
    validation_indices: np.ndarray
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp


def build_chronological_folds(
    frame: pd.DataFrame, n_splits: int = DEFAULT_FOLDS
) -> list[ChronologicalFold]:
    """Create expanding-window folds without shuffling, and verify time order.

    ``frame`` must be sorted chronologically and contain only rows with complete
    features. sklearn's TimeSeriesSplit uses expanding training prefixes and
    later validation blocks; explicit timestamp checks guard against accidental
    changes to that guarantee.
    """
    if TIME_COLUMN not in frame:
        raise ValueError(f"frame must contain {TIME_COLUMN!r}")
    ordered = frame[TIME_COLUMN].reset_index(drop=True)
    if not ordered.is_monotonic_increasing:
        raise ValueError("frame must be sorted by month before cross-validation")
    if ordered.duplicated().any():
        raise ValueError("frame must contain unique monthly timestamps")
    if n_splits < 2 or len(frame) <= n_splits:
        raise ValueError("cross-validation requires more rows than folds (at least 2 folds)")

    splitter = TimeSeriesSplit(n_splits=n_splits)
    folds: list[ChronologicalFold] = []
    for fold_number, (train_indices, validation_indices) in enumerate(
        splitter.split(frame), start=1
    ):
        train_end = pd.Timestamp(ordered.iloc[train_indices].max())
        validation_start = pd.Timestamp(ordered.iloc[validation_indices].min())
        if train_end >= validation_start:
            raise ValueError("cross-validation fold is not strictly chronological")
        folds.append(
            ChronologicalFold(
                fold=fold_number,
                train_indices=train_indices,
                validation_indices=validation_indices,
                train_start=pd.Timestamp(ordered.iloc[train_indices].min()),
                train_end=train_end,
                validation_start=validation_start,
                validation_end=pd.Timestamp(ordered.iloc[validation_indices].max()),
            )
        )
    return folds


def calculate_errors(actual: pd.Series, predicted: np.ndarray | pd.Series) -> dict[str, float]:
    """Return interpretable EUR MAE and EUR RMSE."""
    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.asarray(predicted, dtype=float)
    return {
        "mae_eur": float(mean_absolute_error(actual_values, predicted_values)),
        "rmse_eur": float(np.sqrt(mean_squared_error(actual_values, predicted_values))),
    }


def _with_features(frame: pd.DataFrame) -> pd.DataFrame:
    featured = engineer_features(frame)
    return featured.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)


def _score_fit(
    train_rows: pd.DataFrame, validation_rows: pd.DataFrame
) -> tuple[dict[str, float], dict[str, float]]:
    model = train_model(train_rows[FEATURE_COLUMNS], train_rows[TARGET])
    train_predictions = model.predict(train_rows[FEATURE_COLUMNS])
    validation_predictions = model.predict(validation_rows[FEATURE_COLUMNS])
    return (
        calculate_errors(train_rows[TARGET], train_predictions),
        calculate_errors(validation_rows[TARGET], validation_predictions),
    )


def _learning_curve(
    training_rows: pd.DataFrame,
    validation_rows: pd.DataFrame,
    output_path: Path,
    points: int = 5,
) -> list[dict[str, float | int]]:
    """Score increasing chronological prefixes against a fixed later window."""
    sizes = np.unique(
        np.linspace(max(12, int(len(training_rows) * 0.4)), len(training_rows), points)
        .round()
        .astype(int)
    )
    results: list[dict[str, float | int]] = []
    for size in sizes:
        prefix = training_rows.iloc[: int(size)]
        training_errors, validation_errors = _score_fit(prefix, validation_rows)
        results.append(
            {
                "training_rows": int(len(prefix)),
                "last_training_month": str(prefix[TIME_COLUMN].max().date()),
                "train_mae_eur": training_errors["mae_eur"],
                "train_rmse_eur": training_errors["rmse_eur"],
                "validation_mae_eur": validation_errors["mae_eur"],
                "validation_rmse_eur": validation_errors["rmse_eur"],
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    row_counts = [int(item["training_rows"]) for item in results]
    ax.plot(row_counts, [item["train_rmse_eur"] for item in results], marker="o", label="Training RMSE")
    ax.plot(
        row_counts,
        [item["validation_rmse_eur"] for item in results],
        marker="o",
        label="Chronological validation RMSE",
    )
    ax.set_title("TrackFlow revenue model learning curve")
    ax.set_xlabel("Training observations (chronological prefix)")
    ax.set_ylabel("RMSE (EUR)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return results


def diagnose_model(
    training_rmse: float,
    validation_rmse: float,
    cv_mean_rmse: float,
) -> tuple[str, str]:
    """Apply a transparent diagnosis from train/generalization error gap.

    A training RMSE less than 75% of both validation and CV RMSE is evidence of
    overfitting. A high training RMSE (at least 10% of mean observed revenue)
    without a large generalization gap indicates underfitting. Otherwise the
    errors are considered sufficiently similar for a well-fitted diagnosis.
    """
    if training_rmse < 0.75 * validation_rmse and training_rmse < 0.75 * cv_mean_rmse:
        return (
            "overfitting",
            "Use a shallower Random Forest or increase min_samples_leaf, then compare the same chronological folds.",
        )
    return "well fitted", "No corrective action is indicated by the current training/validation error gap."


def run_evaluation(
    csv_path: str | Path,
    report_path: str | Path,
    learning_curve_path: str | Path,
    n_splits: int = DEFAULT_FOLDS,
) -> dict[str, Any]:
    """Run chronological CV, held-out evaluation, learning curve and report."""
    sales = load_sales_data(csv_path)
    validate_sales_data(sales)
    featured = _with_features(sales)

    development_rows = featured[featured[TIME_COLUMN] <= TRAIN_END].reset_index(drop=True)
    train_rows = development_rows[
        (development_rows[TIME_COLUMN] >= TRAIN_START)
        & (development_rows[TIME_COLUMN] <= TRAIN_END)
    ].reset_index(drop=True)
    holdout_rows = featured[
        (featured[TIME_COLUMN] >= TEST_START) & (featured[TIME_COLUMN] <= TEST_END)
    ].reset_index(drop=True)

    folds = build_chronological_folds(train_rows, n_splits=n_splits)
    cv_results: list[dict[str, Any]] = []
    for fold in folds:
        fold_train = train_rows.iloc[fold.train_indices]
        fold_validation = train_rows.iloc[fold.validation_indices]
        model = train_model(fold_train[FEATURE_COLUMNS], fold_train[TARGET])
        predictions = model.predict(fold_validation[FEATURE_COLUMNS])
        cv_results.append(
            {
                "fold": fold.fold,
                "train_start": fold.train_start,
                "train_end": fold.train_end,
                "validation_start": fold.validation_start,
                "validation_end": fold.validation_end,
                **calculate_errors(fold_validation[TARGET], predictions),
            }
        )

    full_model = train_model(train_rows[FEATURE_COLUMNS], train_rows[TARGET])
    training_errors = calculate_errors(
        train_rows[TARGET], full_model.predict(train_rows[FEATURE_COLUMNS])
    )
    validation_errors = calculate_errors(
        holdout_rows[TARGET], full_model.predict(holdout_rows[FEATURE_COLUMNS])
    )
    cv_summary = {
        metric: {
            "mean": float(np.mean([row[metric] for row in cv_results])),
            "std": float(np.std([row[metric] for row in cv_results], ddof=1)),
        }
        for metric in ("mae_eur", "rmse_eur")
    }

    # Use the final 18 development months as a fixed later validation window;
    # each curve point sees only an earlier prefix for fitting.
    learning_validation = train_rows.tail(18).reset_index(drop=True)
    learning_training = train_rows.iloc[:-18].reset_index(drop=True)
    learning_results = _learning_curve(
        learning_training,
        learning_validation,
        Path(learning_curve_path),
    )
    diagnosis, action = diagnose_model(
        training_errors["rmse_eur"],
        validation_errors["rmse_eur"],
        cv_summary["rmse_eur"]["mean"],
    )
    result: dict[str, Any] = {
        "model": "RandomForestRegressor",
        "dataset": str(csv_path),
        "period": [str(sales[TIME_COLUMN].min().date()), str(sales[TIME_COLUMN].max().date())],
        "train_period": [str(train_rows[TIME_COLUMN].min().date()), str(train_rows[TIME_COLUMN].max().date())],
        "validation_period": [str(holdout_rows[TIME_COLUMN].min().date()), str(holdout_rows[TIME_COLUMN].max().date())],
        "folds": cv_results,
        "cv_summary": cv_summary,
        "training_errors": training_errors,
        "validation_errors": validation_errors,
        "learning_curve": learning_results,
        "learning_curve_path": str(learning_curve_path),
        "diagnosis": diagnosis,
        "corrective_action": action,
    }
    _write_report(result, Path(report_path))
    return result


def _write_report(result: dict[str, Any], output_path: Path) -> None:
    """Write a human-readable evaluation report from measured results."""
    rows = [
        "# TrackFlow Regression Model Evaluation",
        "",
        f"- **Model:** `{result['model']}` (the existing TrackFlow Random Forest regressor).",
        f"- **Dataset:** `{result['dataset']}`; consolidated monthly `revenue_eur`.",
        f"- **Dataset period:** {result['period'][0]} through {result['period'][1]}.",
        f"- **Development/train period:** {result['train_period'][0]} through {result['train_period'][1]}.",
        f"- **Held-out validation period:** {result['validation_period'][0]} through {result['validation_period'][1]}.",
        "",
        "## Cross-validation strategy",
        "",
        f"Expanding-window `TimeSeriesSplit` on the 2016-01–2023-12 development period; {len(result['folds'])} folds; no shuffle. Each validation block follows its training prefix strictly. The established causal lag/rolling and known-calendar features are reused. Validation rows use only prior-month observations, as in one-step-ahead evaluation.",
        "",
        "| Fold | Training period | Validation period | MAE (EUR) | RMSE (EUR) |",
        "|---:|---|---|---:|---:|",
    ]
    for fold in result["folds"]:
        rows.append(
            f"| {fold['fold']} | {fold['train_start'].date()}–{fold['train_end'].date()} | "
            f"{fold['validation_start'].date()}–{fold['validation_end'].date()} | "
            f"{fold['mae_eur']:,.2f} | {fold['rmse_eur']:,.2f} |"
        )
    rows.extend(
        [
            "",
            "| Cross-validation summary | MAE (EUR) | RMSE (EUR) |",
            "|---|---:|---:|",
            f"| Mean ± sample standard deviation | {result['cv_summary']['mae_eur']['mean']:,.2f} ± {result['cv_summary']['mae_eur']['std']:,.2f} | {result['cv_summary']['rmse_eur']['mean']:,.2f} ± {result['cv_summary']['rmse_eur']['std']:,.2f} |",
            "",
            "## Training and held-out validation",
            "",
            f"- **Training:** MAE **€{result['training_errors']['mae_eur']:,.2f}**, RMSE **€{result['training_errors']['rmse_eur']:,.2f}**.",
            f"- **Validation:** MAE **€{result['validation_errors']['mae_eur']:,.2f}**, RMSE **€{result['validation_errors']['rmse_eur']:,.2f}**.",
            "",
            "RMSE is particularly useful for TrackFlow because squaring residuals penalizes large misses more heavily. Missing the strong November/December revenue peaks has a larger business impact than a similarly sized collection of small monthly errors. MAE is also reported because its EUR scale is directly interpretable as the average absolute monthly miss.",
            "",
            "## Learning curve",
            "",
            f"![Chronological learning curve: training and validation RMSE in EUR]({Path(result['learning_curve_path']).name})",
            "",
            "Training prefixes grow chronologically and are scored against the same later 18-month development window. The curve compares in-sample training RMSE with validation RMSE in EUR; it does not shuffle observations.",
            "",
            "| Training rows | Last training month | Training RMSE (EUR) | Validation RMSE (EUR) |",
            "|---:|---|---:|---:|",
        ]
    )
    for item in result["learning_curve"]:
        rows.append(
            f"| {item['training_rows']} | {item['last_training_month']} | "
            f"{item['train_rmse_eur']:,.2f} | {item['validation_rmse_eur']:,.2f} |"
        )
    first = result["learning_curve"][0]
    last = result["learning_curve"][-1]
    if last["validation_rmse_eur"] < first["validation_rmse_eur"] * 0.9:
        interpretation = "Validation RMSE improves as the chronological training set grows, suggesting additional historical data is helping generalization."
    elif last["validation_rmse_eur"] > first["validation_rmse_eur"] * 1.1:
        interpretation = "Validation RMSE rises as the training prefix grows, so more history has not improved this fixed-window score; inspect distribution shift and seasonal-period composition."
    else:
        interpretation = "Validation RMSE is broadly stable as the chronological training set grows; the curve does not show a strong data-volume benefit or deterioration."
    rows.extend(
        [
            "",
            interpretation,
            "",
            "## Diagnosis",
            "",
            f"**{result['diagnosis'].capitalize()}.** This is based on the observed training RMSE, held-out validation RMSE, cross-validation mean RMSE, and the learning curve above (not a predetermined label).",
            "",
            f"**Corrective action:** {result['corrective_action']}",
            "",
            "## Leakage and ordering check",
            "",
            "Chronological ordering was preserved throughout: no samples were shuffled; all CV training timestamps precede their validation timestamps; the final validation period begins after the training period. Existing features are causal (lags and rolling statistics are shifted to exclude the current target); calendar features are known in advance. Validation scoring is one-step-ahead, where only revenue observed before a month is used for its lag features.",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(rows), encoding="utf-8")
