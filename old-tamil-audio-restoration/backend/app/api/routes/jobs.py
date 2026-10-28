"""
Job status API routes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from app.services.job_manager import job_manager
from app.schemas.jobs import JobStatus, JobStatusResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", summary="Get job status and progress", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Return current job status, per-stage progress, and any error details.
    Poll this endpoint to track restoration progress.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        overall_progress=job.overall_progress,
        current_stage=job.current_stage,
        stages=job.stages,
        error_message=job.error_message,
        processing_time_seconds=job.processing_time_seconds,
        result_metadata=job.result_metadata,
    )


@router.get("/", summary="List all jobs")
async def list_jobs():
    """Return a summary of all jobs (for debugging/admin)."""
    jobs = job_manager.list_jobs()
    return [
        {
            "job_id": j.job_id,
            "status": j.status,
            "original_filename": j.original_filename,
            "overall_progress": j.overall_progress,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]
