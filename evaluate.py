"""Evaluate time estimates from CSV data and save tables/plots to reports."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    """Calculate MAE, MAPE, and percentage within 20 percent."""
    error = (predicted - actual).abs()
    return {
        "mae": float(error.mean()),
        "mape": float((error / actual.where(actual != 0)).mean() * 100),
        "within_20_percent": float(((error / actual.where(actual != 0)) <= 0.2).mean() * 100),
    }


def evaluate_frame(frame: pd.DataFrame, prediction_columns: list[str]) -> pd.DataFrame:
    """Evaluate each prediction column, including category mean baseline."""
    actual = frame["actual_minutes"]
    results: list[dict[str, object]] = []
    baseline = frame.groupby("category")["actual_minutes"].transform("mean")
    for name, prediction in [("mean_baseline", baseline), *[(column, frame[column]) for column in prediction_columns]]:
        result = metrics(actual, prediction)
        result["method"] = name
        results.append(result)
    return pd.DataFrame(results)[["method", "mae", "mape", "within_20_percent"]]


def perception_metrics(frame: pd.DataFrame) -> dict[str, float]:
    """Score optional category and visible-size labels from a perception set."""
    metrics_result: dict[str, float] = {}
    if {"category", "predicted_category"} <= set(frame.columns):
        metrics_result["category_accuracy"] = float(
            (frame["category"] == frame["predicted_category"]).mean() * 100
        )
    for label in ("page_count", "num_questions", "num_steps", "num_ingredients"):
        predicted = f"predicted_{label}"
        if {label, predicted} <= set(frame.columns):
            metrics_result[f"{label}_accuracy"] = float(
                (frame[label] == frame[predicted]).mean() * 100
            )
    return metrics_result


def main() -> None:
    """Run evaluation for a CSV and save CSV/PNG artifacts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/evaluation.csv")
    parser.add_argument("--reports", default="reports")
    parser.add_argument("--perception", default=None)
    args = parser.parse_args()
    frame = pd.read_csv(args.input)
    required = {"category", "actual_minutes"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    prediction_columns = [
        column for column in ("gemini_estimate", "plain_zero_shot", "final_prompt", "with_speed_factor")
        if column in frame
    ]
    results = evaluate_frame(frame, prediction_columns)
    reports = Path(args.reports)
    reports.mkdir(parents=True, exist_ok=True)
    results.to_csv(reports / "results.csv", index=False)
    axis = results.plot.bar(x="method", y="mae", legend=False, title="TimeSense MAE")
    axis.set_ylabel("Minutes")
    axis.figure.tight_layout()
    axis.figure.savefig(reports / "mae.png", dpi=150)
    plt.close(axis.figure)
    if args.perception:
        perception = pd.DataFrame([perception_metrics(pd.read_csv(args.perception))])
        perception.to_csv(reports / "perception_results.csv", index=False)


if __name__ == "__main__":
    main()
