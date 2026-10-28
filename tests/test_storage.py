from backend.schemas import TaskExtraction
from backend.storage import TaskStore


def extraction(minutes: int = 20) -> TaskExtraction:
    return TaskExtraction(
        category="assignment",
        summary="Complete the worksheet.",
        page_count=2,
        num_questions=5,
        num_steps=0,
        num_ingredients=0,
        difficulty=3,
        estimated_minutes=minutes,
        range_low=15,
        range_high=30,
        confidence=0.9,
    )


def test_speed_factor_uses_exponential_moving_average(tmp_path):
    store = TaskStore(str(tmp_path / "timesense.db"), ema_alpha=0.3)
    task_id, adjusted = store.create_task(extraction(), "student")

    assert adjusted == 20
    assert store.record_feedback(task_id, 40, "student") == 1.3
    assert store.speed_factor("student") == 1.3

    _, adjusted_again = store.create_task(extraction(), "student")
    assert adjusted_again == 26
