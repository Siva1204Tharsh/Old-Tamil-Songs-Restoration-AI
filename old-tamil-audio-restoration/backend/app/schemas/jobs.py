"""
Pydantic schemas for job management.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingStage(str, Enum):
    UPLOAD = "upload"
    ANALYSIS = "analysis"
    NOISE_REDUCTION = "noise_reduction"
    MUSIC_PRESERVATION = "music_preservation"
    CLARITY_ENHANCEMENT = "clarity_enhancement"
    LOUDNESS_NORMALIZATION = "loudness_normalization"
    EXPORT = "export"
    DONE = "done"


class JobStageInfo(BaseModel):
    stage: ProcessingStage
    label: str
    progress_pct: float       # 0–100
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    message: Optional[str] = None


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    stages: list[JobStageInfo] = []
    overall_progress: float = 0.0   # 0–100
    current_stage: Optional[ProcessingStage] = None
    error_message: Optional[str] = None
    original_filename: Optional[str] = None
    # Result metadata (populated when completed)
    result_metadata: Optional[dict[str, Any]] = None
    processing_time_seconds: Optional[float] = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    overall_progress: float
    current_stage: Optional[ProcessingStage] = None
    stages: list[JobStageInfo]
    error_message: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    result_metadata: Optional[dict[str, Any]] = None
