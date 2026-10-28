"""FastAPI entry point for the TimeSense milestone-1 API."""

import hashlib
import logging
from functools import lru_cache

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .cache import ResponseCache
from .config import get_settings
from .gemini_client import GeminiExtractor
from .schemas import (
    AnalyzeResponse,
    FeedbackRequest,
    FeedbackResponse,
    TimerStartRequest,
    TimerStartResponse,
)
from .storage import TaskStore

LOGGER = logging.getLogger(__name__)
ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}


@lru_cache
def get_extractor() -> GeminiExtractor:
    """Create the Gemini wrapper lazily so API imports work without a configured key."""
    settings = get_settings()
    return GeminiExtractor(
        settings.gemini_api_key, settings.gemini_model, settings.few_shot_path
    )


@lru_cache
def get_cache() -> ResponseCache:
    """Create the response cache lazily."""
    return ResponseCache(get_settings().cache_db_path)


@lru_cache
def get_store() -> TaskStore:
    """Create the domain store lazily."""
    settings = get_settings()
    return TaskStore(settings.cache_db_path, settings.ema_alpha)


app = FastAPI(title="TimeSense API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)) -> AnalyzeResponse:
    """Upload a PDF/image and return Gemini's validated task estimate."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Upload a PDF, JPEG, PNG, or WebP file.",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    file_hash = hashlib.sha256(content).hexdigest()
    cached = get_cache().get(file_hash)
    if cached:
        extraction_data = {key: value for key, value in cached.items() if key not in {"task_id", "cached"}}
        extraction = AnalyzeResponse.model_validate(extraction_data)
        if extraction.confidence < get_settings().low_confidence_threshold:
            raise HTTPException(
                status_code=422,
                detail="The image is unclear or ambiguous. Please retake the photo or upload a clearer file.",
            )
        task_id, adjusted_minutes = get_store().create_task(extraction)
        return AnalyzeResponse(
            **{
                **extraction.model_dump(),
                "estimated_minutes": round(adjusted_minutes),
                "task_id": task_id,
                "cached": True,
            }
        )

    try:
        extraction = get_extractor().extract(content, file.content_type)
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="Gemini could not produce a valid task estimate. Please try again.",
        ) from error
    except Exception as error:
        LOGGER.exception("Gemini request failed")
        raise HTTPException(
            status_code=503,
            detail="The analysis service is temporarily unavailable. Please try again.",
        ) from error

    task_id, adjusted_minutes = get_store().create_task(extraction)
    result = extraction.model_dump()
    result["estimated_minutes"] = round(adjusted_minutes)
    result["range_low"] = max(
        1, round(extraction.range_low * adjusted_minutes / extraction.estimated_minutes)
    )
    result["range_high"] = round(
        extraction.range_high * adjusted_minutes / extraction.estimated_minutes
    )
    result["task_id"] = task_id
    get_cache().set(file_hash, extraction.model_dump())
    response = AnalyzeResponse(**result)
    if response.confidence < get_settings().low_confidence_threshold:
        raise HTTPException(
            status_code=422,
            detail="The image is unclear or ambiguous. Please retake the photo or upload a clearer file.",
        )
    return response


@app.post("/api/timer/start", response_model=TimerStartResponse)
def start_timer(request: TimerStartRequest) -> TimerStartResponse:
    """Return the duration the frontend should count down."""
    return TimerStartResponse(
        duration_minutes=request.estimated_minutes,
        duration_seconds=request.estimated_minutes * 60,
    )


@app.post("/api/feedback", response_model=FeedbackResponse)
def feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Record actual duration and update the user's EMA speed factor."""
    try:
        factor = get_store().record_feedback(
            request.task_id, request.actual_minutes, request.user_id
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FeedbackResponse(
        task_id=request.task_id,
        actual_minutes=request.actual_minutes,
        speed_factor=round(factor, 4),
    )
