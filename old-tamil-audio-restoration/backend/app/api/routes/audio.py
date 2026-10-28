"""
Audio upload, analysis, restoration, and download API routes.
"""
from __future__ import annotations

import asyncio
import shutil
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.jobs import JobCreateResponse, JobStatus
from app.schemas.restoration import RestorationRequest, RestorationSettings
from app.services.audio_analyzer import analyze_audio
from app.services.job_manager import job_manager
from app.services.restoration_pipeline import run_restoration_pipeline
from app.utils.validation import (
    ValidationError, validate_extension, validate_file_size,
    probe_audio_file, validate_audio_probe,
)

logger = get_logger("routes.audio")
router = APIRouter(prefix="/audio", tags=["audio"])

# ---------------------------------------------------------------------------
# POST /audio/upload
# ---------------------------------------------------------------------------

@router.post("/upload", summary="Upload an audio file for restoration")
async def upload_audio(file: UploadFile = File(...)):
    """
    Upload and validate an audio file.
    Returns job_id and file metadata.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    try:
        validate_extension(file.filename)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.message)

    # Read and check file size
    content = await file.read()
    try:
        validate_file_size(len(content))
    except ValidationError as e:
        raise HTTPException(status_code=413, detail=e.message)

    # Create job record
    if job_manager.count_active_jobs() >= settings.MAX_CONCURRENT_JOBS:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum concurrent jobs ({settings.MAX_CONCURRENT_JOBS}) reached. "
                   "Please wait for a running job to complete."
        )

    job = job_manager.create_job(file.filename)
    job_id = job.job_id

    # Save original file (never overwrite)
    upload_dir = settings.UPLOADS_DIR / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).name
    dest_path = upload_dir / safe_name

    with open(dest_path, "wb") as f:
        f.write(content)

    # Validate audio content with ffprobe
    try:
        probe_data = probe_audio_file(dest_path)
        probe_info = validate_audio_probe(probe_data)
    except ValidationError as e:
        dest_path.unlink(missing_ok=True)
        job_manager.update_status(job_id, JobStatus.FAILED, e.message)
        raise HTTPException(status_code=422, detail=e.message)

    return {
        "job_id": job_id,
        "status": "queued",
        "original_filename": file.filename,
        "file_size_bytes": len(content),
        "duration_seconds": probe_info["duration"],
        "sample_rate": probe_info["sample_rate"],
        "channels": probe_info["channels"],
        "codec": probe_info["codec"],
        "bit_depth": probe_info["bit_depth"],
        "format": probe_info["format_name"],
        "message": "File uploaded successfully. Call /analysis to inspect the audio.",
    }


# ---------------------------------------------------------------------------
# GET /audio/{job_id}/analysis
# ---------------------------------------------------------------------------

@router.get("/{job_id}/analysis", summary="Get audio quality analysis")
async def get_analysis(job_id: str):
    """Run (or return cached) audio analysis for the uploaded file."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    # Find the original file
    original_path = _find_upload(job_id)
    if not original_path:
        raise HTTPException(status_code=404, detail="Original audio file not found on server.")

    try:
        report = analyze_audio(
            job_id=job_id,
            original_path=original_path,
            original_filename=job.original_filename or original_path.name,
            file_size=original_path.stat().st_size,
        )
        return report.model_dump()
    except Exception as e:
        logger.exception(f"Analysis failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Audio analysis failed: {str(e)}")


# ---------------------------------------------------------------------------
# POST /audio/{job_id}/restore
# ---------------------------------------------------------------------------

@router.post("/{job_id}/restore", summary="Start audio restoration job")
async def start_restoration(job_id: str, request: RestorationRequest,
                             background_tasks: BackgroundTasks):
    """
    Accept restoration settings and start the background processing job.
    Returns immediately with job_id and PROCESSING status.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="This job is already processing.")

    if job.status == JobStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="This job has already completed. "
                            "Create a new upload to re-process.")

    if job_manager.count_active_jobs() >= settings.MAX_CONCURRENT_JOBS:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum concurrent restoration jobs ({settings.MAX_CONCURRENT_JOBS}) reached. "
                   "Please wait for a running job to complete."
        )

    original_path = _find_upload(job_id)
    if not original_path:
        raise HTTPException(status_code=404, detail="Original audio file not found.")

    # Run analysis to pass to pipeline
    try:
        report = analyze_audio(
            job_id=job_id,
            original_path=original_path,
            original_filename=job.original_filename or original_path.name,
            file_size=original_path.stat().st_size,
        )
        analysis = report.analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pre-restoration analysis failed: {e}")

    # Launch background thread (not asyncio task, to avoid GIL conflicts with NumPy)
    def _run():
        try:
            run_restoration_pipeline(
                job_id=job_id,
                original_path=original_path,
                original_filename=job.original_filename or original_path.name,
                analysis=analysis,
                rest_settings=request.settings,
            )
        except Exception as e:
            logger.exception(f"Background restoration failed: {e}")

    thread = threading.Thread(target=_run, daemon=True, name=f"restore-{job_id[:8]}")
    thread.start()

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Restoration started. Poll /jobs/{job_id} for progress.",
    }


# ---------------------------------------------------------------------------
# GET /audio/{job_id}/result
# ---------------------------------------------------------------------------

@router.get("/{job_id}/result", summary="Get restoration result metadata")
async def get_result(job_id: str):
    """Return metadata about the completed restoration."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=202,
            detail=f"Job is not yet complete. Current status: {job.status}"
        )

    return {
        "job_id": job_id,
        "status": job.status,
        "result_metadata": job.result_metadata,
        "processing_time_seconds": job.processing_time_seconds,
    }


# ---------------------------------------------------------------------------
# GET /audio/{job_id}/download
# ---------------------------------------------------------------------------

@router.get("/{job_id}/download", summary="Download restored audio file")
async def download_audio(job_id: str, format: str = "wav"):
    """
    Download the restored audio in the requested format (wav, flac, mp3).
    Never exposes filesystem paths.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=202, detail="Restoration not yet complete.")

    format = format.lower()
    if format not in ("wav", "flac", "mp3"):
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    # Locate the file
    if not job.result_metadata:
        raise HTTPException(status_code=404, detail="Result metadata not found.")

    output_paths = job.result_metadata.get("output_paths", {})
    file_path_str = output_paths.get(format)
    if not file_path_str:
        raise HTTPException(status_code=404, detail=f"Format '{format}' not available.")

    file_path = Path(file_path_str)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found on server.")

    original_stem = Path(job.original_filename or "restored").stem
    download_name = f"{original_stem}_restored.{format}"

    media_types = {
        "wav": "audio/wav",
        "flac": "audio/flac",
        "mp3": "audio/mpeg",
    }

    return FileResponse(
        path=str(file_path),
        media_type=media_types[format],
        filename=download_name,
    )


# ---------------------------------------------------------------------------
# DELETE /audio/{job_id}
# ---------------------------------------------------------------------------

@router.delete("/{job_id}", summary="Delete job files")
async def delete_job(job_id: str):
    """Delete all temporary files and job record for the given job_id."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=409,
                            detail="Cannot delete a job while it is processing.")

    # Remove upload directory
    upload_dir = settings.UPLOADS_DIR / job_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)

    # Remove processed directory
    processed_dir = settings.PROCESSED_DIR / job_id
    if processed_dir.exists():
        shutil.rmtree(processed_dir, ignore_errors=True)

    job_manager.delete_job(job_id)

    return {"job_id": job_id, "deleted": True, "message": "Job and associated files deleted."}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _find_upload(job_id: str) -> Optional[Path]:
    """Find the original uploaded audio file for a job."""
    upload_dir = settings.UPLOADS_DIR / job_id
    if not upload_dir.exists():
        return None
    for ext in settings.ALLOWED_EXTENSIONS:
        candidates = list(upload_dir.glob(f"*{ext}"))
        if candidates:
            return candidates[0]
    # Any file in the directory
    files = list(upload_dir.iterdir())
    return files[0] if files else None
