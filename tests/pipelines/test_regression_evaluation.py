"""Tests for chronological TrackFlow regression evaluation."""

from pathlib import Path

import pandas as pd

from data.pipelines.regression_evaluation import (
    build_chronological_folds,
    run_evaluation,
)
from data.pipelines.sales_forecasting import (
    TRAIN_END,
    TRAIN_START,
    engineer_features,
    load_sales_data,
    validate_sales_data,
)

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "data/raw/trackflow_sales.csv"


def test_each_cv_fold_has_training_timestamps_before_validation() -> None:
    sales = load_sales_data(CSV_PATH)
    validate_sales_data(sales)
    featured = engineer_features(sales).dropna().reset_index(drop=True)
    development = featured[
        (featured["month"] >= TRAIN_START) & (featured["month"] <= TRAIN_END)
    ].reset_index(drop=True)

    folds = build_chronological_folds(development, n_splits=5)

    assert len(folds) == 5
    for fold in folds:
        train_timestamps = development.iloc[fold.train_indices]["month"]
        validation_timestamps = development.iloc[fold.validation_indices]["month"]
        assert train_timestamps.max() < validation_timestamps.min()
        assert fold.train_end < fold.validation_start


def test_evaluation_writes_report_and_chronological_curve(tmp_path: Path) -> None:
    report_path = tmp_path / "evaluation_report.md"
    curve_path = tmp_path / "learning_curve.png"

    result = run_evaluation(CSV_PATH, report_path, curve_path, n_splits=5)

    assert len(result["folds"]) == 5
    assert report_path.is_file()
    assert curve_path.is_file()
    assert result["diagnosis"] in {"well fitted", "underfitting", "overfitting"}
    report = report_path.read_text(encoding="utf-8")
    assert "MAE (EUR)" in report
    assert "RMSE (EUR)" in report
    assert "no samples were shuffled" in report
