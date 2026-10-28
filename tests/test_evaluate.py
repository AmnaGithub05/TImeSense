import pandas as pd

from evaluate import evaluate_frame


def test_evaluation_reports_required_metrics():
    frame = pd.DataFrame(
        {
            "category": ["assignment", "assignment"],
            "actual_minutes": [10, 20],
            "final_prompt": [10, 24],
        }
    )

    results = evaluate_frame(frame, ["final_prompt"])

    assert list(results.columns) == ["method", "mae", "mape", "within_20_percent"]
    assert set(results["method"]) == {"mean_baseline", "final_prompt"}
