"""
Job manager — in-memory job state tracking with thread-safe updates.
Handles status, progress, and metadata for all restoration jobs.
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Any

from app.core.logging import get_logger
from app.schemas.jobs import (
    JobRecord, JobStatus, JobStageInfo, ProcessingStage,
)

logger = get_logger("job_manager")


class JobManager:
    """Thread-safe in-memory job store."""

    def __init__(self, max_concurrent: int = 2):
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.RLock()
        self.max_concurrent = max_concurrent

    def create_job(self, original_filename: str) -> JobRecord:
        """Create and register a new job, returning the job record."""
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        record = JobRecord(
            job_id=job_id,
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
            original_filename=original_filename,
            stages=[],
            overall_progress=0.0,
        )
        with self._lock:
            self._jobs[job_id] = record
        logger.info(f"Job created: {job_id} | file={original_filename}")
        return record

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    def update_status(self, job_id: str, status: JobStatus,
                      error_message: Optional[str] = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status
                job.updated_at = datetime.now(timezone.utc)
                if error_message:
                    job.error_message = error_message
                logger.info(f"Job {job_id}: status → {status}")

    def update_stage(self, job_id: str, stage: ProcessingStage,
                     progress_pct: float, message: Optional[str] = None,
                     completed: bool = False) -> None:
        """Update progress for a specific processing stage."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

            now = datetime.now(timezone.utc)
            # Find or create the stage entry
            existing = next((s for s in job.stages if s.stage == stage), None)
            if existing is None:
                stage_info = JobStageInfo(
                    stage=stage,
                    label=stage.value.replace("_", " ").title(),
                    progress_pct=progress_pct,
                    started_at=now,
                    message=message,
                )
                job.stages.append(stage_info)
            else:
                existing.progress_pct = progress_pct
                existing.message = message
                if completed:
                    existing.completed_at = now

            job.current_stage = stage
            job.updated_at = now

            # Recompute overall progress across all stages
            stage_order = list(ProcessingStage)
            n_stages = len(stage_order)
            stage_idx = stage_order.index(stage) if stage in stage_order else 0
            stage_fraction = (stage_idx + progress_pct / 100.0) / n_stages
            job.overall_progress = round(stage_fraction * 100.0, 1)

    def set_result(self, job_id: str, result_metadata: dict[str, Any],
                   processing_time_seconds: float) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.result_metadata = result_metadata
                job.processing_time_seconds = processing_time_seconds
                job.overall_progress = 100.0
                job.updated_at = datetime.now(timezone.utc)

    def count_active_jobs(self) -> int:
        with self._lock:
            return sum(
                1 for j in self._jobs.values()
                if j.status == JobStatus.PROCESSING
            )

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.info(f"Job deleted: {job_id}")
                return True
            return False

    def list_jobs(self) -> list[JobRecord]:
        with self._lock:
            return list(self._jobs.values())


# Application-level singleton
job_manager = JobManager(max_concurrent=2)
