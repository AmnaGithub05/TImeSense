"""Validated API and Gemini response schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskExtraction(BaseModel):
    """The structured task description returned by Gemini."""

    model_config = ConfigDict(extra="forbid")

    category: Literal["recipe", "lecture_notes", "assignment"]
    summary: str = Field(min_length=1, max_length=2000)
    page_count: int = Field(ge=0)
    num_questions: int = Field(ge=0)
    num_steps: int = Field(ge=0)
    num_ingredients: int = Field(ge=0)
    difficulty: int = Field(ge=1, le=5)
    estimated_minutes: int = Field(gt=0, le=24 * 60)
    range_low: int = Field(gt=0, le=24 * 60)
    range_high: int = Field(gt=0, le=24 * 60)
    confidence: float = Field(ge=0, le=1)


class AnalyzeResponse(TaskExtraction):
    """Successful analysis response returned by the API."""

    cached: bool = False
    task_id: int | None = None
    user_id: str = "default"


class TimerStartRequest(BaseModel):
    """Input needed to start a timer for a completed analysis."""

    estimated_minutes: int = Field(gt=0, le=24 * 60)
    task_id: int | None = None


class TimerStartResponse(BaseModel):
    """Timer duration expressed in minutes and seconds."""

    duration_minutes: int
    duration_seconds: int


class FeedbackRequest(BaseModel):
    """Actual completion time submitted by a user."""

    task_id: int
    actual_minutes: float = Field(gt=0, le=24 * 60)
    user_id: str = "default"


class FeedbackResponse(BaseModel):
    """Updated speed factor after recording feedback."""

    task_id: int
    actual_minutes: float
    speed_factor: float
