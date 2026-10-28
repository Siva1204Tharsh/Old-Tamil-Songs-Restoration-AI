"""
HTTP client for communicating with the FastAPI backend.
"""
from __future__ import annotations

import time
from typing import Any, Optional
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"
TIMEOUT = httpx.Timeout(300.0, connect=10.0)


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)


def upload_audio(file_bytes: bytes, filename: str) -> dict:
    with _client() as c:
        resp = c.post(
            "/audio/upload",
            files={"file": (filename, file_bytes, _guess_mime(filename))},
        )
        resp.raise_for_status()
        return resp.json()


def get_analysis(job_id: str) -> dict:
    with _client() as c:
        resp = c.get(f"/audio/{job_id}/analysis")
        resp.raise_for_status()
        return resp.json()


def start_restoration(job_id: str, settings: dict) -> dict:
    with _client() as c:
        payload = {"settings": settings}
        resp = c.post(f"/audio/{job_id}/restore", json=payload)
        resp.raise_for_status()
        return resp.json()


def get_job_status(job_id: str) -> dict:
    with _client() as c:
        resp = c.get(f"/jobs/{job_id}")
        resp.raise_for_status()
        return resp.json()


def get_result(job_id: str) -> dict:
    with _client() as c:
        resp = c.get(f"/audio/{job_id}/result")
        resp.raise_for_status()
        return resp.json()


def download_audio(job_id: str, fmt: str) -> bytes:
    with _client() as c:
        resp = c.get(f"/audio/{job_id}/download", params={"format": fmt})
        resp.raise_for_status()
        return resp.content


def delete_job(job_id: str) -> dict:
    with _client() as c:
        resp = c.delete(f"/audio/{job_id}")
        resp.raise_for_status()
        return resp.json()


def get_health() -> dict:
    with _client() as c:
        resp = c.get("/health/")
        resp.raise_for_status()
        return resp.json()


def _guess_mime(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mapping = {
        "wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac",
        "m4a": "audio/mp4", "ogg": "audio/ogg", "aiff": "audio/aiff",
    }
    return mapping.get(ext, "application/octet-stream")


def poll_job_until_done(job_id: str, timeout_seconds: int = 3600,
                         poll_interval: float = 2.0,
                         on_update=None) -> dict:
    """
    Poll job status until it reaches a terminal state.
    Calls on_update(job_status_dict) on each update if provided.
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = get_job_status(job_id)
        if on_update:
            on_update(status)
        if status["status"] in ("completed", "failed", "cancelled"):
            return status
        time.sleep(poll_interval)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout_seconds}s")
