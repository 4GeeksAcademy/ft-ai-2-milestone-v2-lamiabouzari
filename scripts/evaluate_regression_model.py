"""Run chronological TrackFlow regression-model evaluation and save artifacts."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.pipelines.regression_evaluation import run_evaluation


def main() -> None:
    result = run_evaluation(
        csv_path=ROOT / "data/raw/trackflow_sales.csv",
        report_path=ROOT / "data/eval/evaluation_report.md",
        learning_curve_path=ROOT / "data/eval/learning_curve.png",
    )
    print(f"Report: {ROOT / 'data/eval/evaluation_report.md'}")
    print(f"Learning curve: {ROOT / 'data/eval/learning_curve.png'}")
    print(f"CV summary: {result['cv_summary']}")
    print(f"Training: {result['training_errors']}")
    print(f"Validation: {result['validation_errors']}")
    print(f"Diagnosis: {result['diagnosis']}")


if __name__ == "__main__":
    main()
