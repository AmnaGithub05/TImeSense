import pytest
from pydantic import ValidationError

from backend.schemas import TaskExtraction


def test_schema_rejects_unknown_category():
    with pytest.raises(ValidationError):
        TaskExtraction(
            category="book",
            summary="Unknown",
            page_count=1,
            num_questions=0,
            num_steps=0,
            num_ingredients=0,
            difficulty=2,
            estimated_minutes=10,
            range_low=5,
            range_high=15,
            confidence=0.8,
        )
