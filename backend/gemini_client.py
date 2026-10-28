"""Gemini multimodal extraction wrapper."""

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from google import genai
from google.genai import types
from pydantic import ValidationError

from .schemas import TaskExtraction

LOGGER = logging.getLogger(__name__)

SYSTEM_PROMPT = """You estimate how long a user needs to finish the uploaded task.
Return only JSON matching the supplied schema. Classify as recipe, lecture_notes, or
assignment. Use these explicit assumptions: read lecture notes at 250 words/minute,
read assignments at 200 words/minute, allow 3 minutes per written question, and
estimate recipe preparation and cooking time from visible steps and ingredients.
Do not invent counts that are not visible; use zero for non-applicable counts.
"""


def gemini_response_schema() -> dict[str, Any]:
    """Return a Gemini-compatible version of the Pydantic JSON schema."""
    schema = TaskExtraction.model_json_schema()

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            normalized = {
                key: normalize(item)
                for key, item in value.items()
                if key != "additionalProperties"
            }
            exclusive_minimum = normalized.pop("exclusiveMinimum", None)
            if exclusive_minimum is not None:
                normalized["minimum"] = exclusive_minimum + 1
            exclusive_maximum = normalized.pop("exclusiveMaximum", None)
            if exclusive_maximum is not None:
                normalized["maximum"] = exclusive_maximum - 1
            return normalized
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    return normalize(schema)


def load_few_shot_examples(path: str) -> list[dict[str, Any]]:
    """Load prompt examples from a dedicated JSON file."""
    examples_path = Path(path)
    if not examples_path.exists():
        return []
    with examples_path.open(encoding="utf-8") as file:
        examples = json.load(file)
    if not isinstance(examples, list):
        raise ValueError("Few-shot prompt file must contain a JSON list.")
    return examples


class GeminiModel(Protocol):
    """Minimal protocol used to make the wrapper easy to test."""

    def generate_content(self, **kwargs: Any) -> Any:
        """Generate multimodal content."""


class GeminiExtractor:
    """Call Gemini and validate its structured task extraction."""

    def __init__(
        self, api_key: str, model_name: str, few_shot_path: str = "prompts/few_shot.json"
    ) -> None:
        client = genai.Client(api_key=api_key)
        self.client = client
        self.model: GeminiModel = client.models
        self.model_name = model_name
        self.examples = load_few_shot_examples(few_shot_path)

    def extract(self, content: bytes, mime_type: str) -> TaskExtraction:
        """Extract a validated task, retrying once after malformed JSON."""
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self.model.generate_content(
                    model=self.model_name,
                    contents=[
                        types.Part.from_bytes(data=content, mime_type=mime_type),
                        "Analyze this task.",
                        self._format_examples(),
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0,
                        response_mime_type="application/json",
                        response_schema=gemini_response_schema(),
                    ),
                )
                raw_text = getattr(response, "text", None)
                if not raw_text:
                    raise ValueError("Gemini returned an empty response.")
                return TaskExtraction.model_validate(json.loads(raw_text))
            except (json.JSONDecodeError, TypeError, ValidationError, ValueError) as error:
                last_error = error
                LOGGER.warning("Invalid Gemini response on attempt %d: %s", attempt + 1, error)
        raise ValueError("Gemini returned invalid task data after one retry.") from last_error

    def _format_examples(self) -> str:
        """Render examples as prompt text while keeping them separate from test data."""
        examples = getattr(self, "examples", [])
        if not examples:
            return ""
        return "Reference examples (do not copy their content):\n" + "\n".join(
            json.dumps(example, ensure_ascii=True) for example in examples
        )
