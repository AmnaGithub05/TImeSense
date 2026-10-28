import json

import pytest

from backend.gemini_client import GeminiExtractor


class FakeModel:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        return type("Response", (), {"text": next(self.responses)})()


def valid_payload():
    return {
        "category": "assignment",
        "summary": "Answer the worksheet.",
        "page_count": 2,
        "num_questions": 5,
        "num_steps": 0,
        "num_ingredients": 0,
        "difficulty": 3,
        "estimated_minutes": 20,
        "range_low": 15,
        "range_high": 30,
        "confidence": 0.9,
    }


def test_extract_validates_structured_response():
    model = FakeModel([json.dumps(valid_payload())])
    extractor = GeminiExtractor.__new__(GeminiExtractor)
    extractor.model = model
    extractor.model_name = "test-model"

    result = extractor.extract(b"file", "application/pdf")

    assert result.category == "assignment"
    assert model.calls == 1


def test_extract_retries_once_for_invalid_response():
    model = FakeModel(["not-json", json.dumps(valid_payload())])
    extractor = GeminiExtractor.__new__(GeminiExtractor)
    extractor.model = model
    extractor.model_name = "test-model"

    result = extractor.extract(b"file", "application/pdf")

    assert result.estimated_minutes == 20
    assert model.calls == 2


def test_extract_raises_after_retry():
    model = FakeModel(["not-json", "still-not-json"])
    extractor = GeminiExtractor.__new__(GeminiExtractor)
    extractor.model = model
    extractor.model_name = "test-model"

    with pytest.raises(ValueError, match="invalid task data"):
        extractor.extract(b"file", "application/pdf")
