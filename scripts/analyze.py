#!/usr/bin/env python3
"""Analyze a TrackFlow incident CSV from the command line."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

# Allow ``python scripts/analyze.py ...`` from the repository root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.incident_analysis import (  # noqa: E402
    REQUIRED_FIELDS,
    AnalysisReport,
    analyze_incidents,
)


def load_incidents(path: Path) -> list[dict[str, str]]:
    """Load a CSV after checking its shape; never logs row contents."""
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError("the CSV is empty or has no header row")
            missing = [field for field in REQUIRED_FIELDS if field not in reader.fieldnames]
            if missing:
                raise ValueError("missing required columns: " + ", ".join(missing))
            rows = list(reader)
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except (PermissionError, OSError) as exc:
        raise ValueError(f"could not read CSV file '{path}': {exc}") from exc
    except csv.Error as exc:
        raise ValueError(f"could not parse CSV file '{path}': {exc}") from exc

    if not rows:
        raise ValueError("the CSV contains no incident records")
    return rows


def _print_breakdown(title: str, counts: dict[object, int], percentages: dict[object, float]) -> None:
    print(f"\n{title}")
    for key, value in counts.items():
        print(f"  {key}: {value} ({percentages.get(key, 0):.2f}%)")


def print_report(report: AnalysisReport) -> None:
    print("TRACKFLOW — INCIDENT REPORT ANALYSIS")
    print("=" * 40)
    print(f"Total records: {report.total_records}")
    print(f"Valid records: {report.valid_records}")
    print(f"Invalid records: {report.invalid_records}")
    _print_breakdown("Category breakdown", report.category_breakdown, report.category_percentages)
    _print_breakdown("Status breakdown", report.status_breakdown, report.status_percentages)
    _print_breakdown("Country breakdown", report.country_breakdown, report.country_percentages)
    print(f"\nClosed scored incidents: {report.closed_scored_incident_count}")
    average = "n/a" if report.average_satisfaction is None else f"{report.average_satisfaction:.2f}"
    print(f"Average satisfaction: {average}")
    print("Score distribution")
    for score, count in report.score_distribution.items():
        print(f"  {score}: {count}")
    print("\nInvalid records by reason")
    if report.invalid_by_reason:
        for reason, count in report.invalid_by_reason.items():
            print(f"  {reason}: {count}")
    else:
        print("  None")


def export_report(report: AnalysisReport, path: Path = Path("results.csv")) -> None:
    """Export aggregate metrics only; no source rows or email values are written."""
    rows: list[dict[str, object]] = []

    def add(metric: str, value: object, percentage: float | None = None) -> None:
        row: dict[str, object] = {"metric": metric, "value": value}
        if percentage is not None:
            row["percentage"] = percentage
        rows.append(row)

    add("total_records", report.total_records)
    add("valid_records", report.valid_records)
    add("invalid_records", report.invalid_records)
    for name, values, percentages in (
        ("category", report.category_breakdown, report.category_percentages),
        ("status", report.status_breakdown, report.status_percentages),
        ("country", report.country_breakdown, report.country_percentages),
    ):
        for key, value in values.items():
            add(f"{name}:{key}", value, percentages[key])
    for reason, count in report.invalid_by_reason.items():
        add(f"invalid_reason:{reason}", count)
    add("closed_scored_incident_count", report.closed_scored_incident_count)
    add("average_satisfaction", report.average_satisfaction)
    for score, count in report.score_distribution.items():
        add(f"score:{score}", count)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value", "percentage"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/analyze.py <incidents.csv>", file=sys.stderr)
        return 2
    try:
        report = analyze_incidents(load_incidents(Path(sys.argv[1])))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_report(report)
    try:
        answer = input("\nExport results to CSV? [y / n]: ").strip().lower()
    except EOFError:
        answer = "n"
    if answer == "y":
        try:
            export_report(report)
        except OSError as exc:
            print(f"Error: could not export results.csv: {exc}", file=sys.stderr)
            return 1
        print("Results exported to results.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
