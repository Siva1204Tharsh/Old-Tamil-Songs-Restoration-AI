"""
API endpoint tests using httpx TestClient.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import struct
import numpy as np
import pytest
from fastapi.testclient import TestClient


def _make_wav(duration_s: float = 2.0, sr: int = 44100) -> bytes:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    pcm = (audio * 32767).astype(np.int16)
    n_samples = len(pcm)
    data_size = n_samples * 2
    file_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", file_size, b"WAVE",
        b"fmt ", 16, 1, 1, sr, sr * 2, 2, 16,
        b"data", data_size,
    )
    return header + pcm.tobytes()


@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


def test_health_check(client):
    resp = client.get("/api/v1/health/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "ffmpeg" in data
    assert "libraries" in data


def test_upload_valid_wav(client):
    wav_bytes = _make_wav()
    resp = client.post(
        "/api/v1/audio/upload",
        files={"file": ("test_song.wav", wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["original_filename"] == "test_song.wav"
    assert data["sample_rate"] == 44100
    assert data["channels"] == 1


def test_upload_unsupported_extension(client):
    resp = client.post(
        "/api/v1/audio/upload",
        files={"file": ("song.exe", b"not audio", "application/octet-stream")},
    )
    assert resp.status_code == 422


def test_upload_empty_file(client):
    resp = client.post(
        "/api/v1/audio/upload",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert resp.status_code == 413


def test_upload_then_analysis(client):
    wav_bytes = _make_wav(duration_s=3.0)
    upload_resp = client.post(
        "/api/v1/audio/upload",
        files={"file": ("analysis_test.wav", wav_bytes, "audio/wav")},
    )
    assert upload_resp.status_code == 200
    job_id = upload_resp.json()["job_id"]

    analysis_resp = client.get(f"/api/v1/audio/{job_id}/analysis")
    assert analysis_resp.status_code == 200
    data = analysis_resp.json()

    assert "analysis" in data
    assert "metadata" in data
    analysis = data["analysis"]
    assert "estimated_snr_db" in analysis
    assert "integrated_lufs" in analysis
    assert "quality_score" in analysis
    assert 0 <= analysis["quality_score"] <= 100


def test_job_not_found(client):
    resp = client.get("/api/v1/jobs/nonexistent-job-id")
    assert resp.status_code == 404


def test_delete_job(client):
    wav_bytes = _make_wav()
    upload_resp = client.post(
        "/api/v1/audio/upload",
        files={"file": ("delete_test.wav", wav_bytes, "audio/wav")},
    )
    job_id = upload_resp.json()["job_id"]
    del_resp = client.delete(f"/api/v1/audio/{job_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True


def test_full_restoration_bypass(client):
    """
    Test a full bypass restoration job (no actual DSP processing).
    Bypass mode returns the decoded original audio.
    """
    import time

    wav_bytes = _make_wav(duration_s=2.0)
    upload_resp = client.post(
        "/api/v1/audio/upload",
        files={"file": ("bypass_test.wav", wav_bytes, "audio/wav")},
    )
    assert upload_resp.status_code == 200
    job_id = upload_resp.json()["job_id"]

    restore_resp = client.post(
        f"/api/v1/audio/{job_id}/restore",
        json={"settings": {"bypass_restoration": True, "output_format": "wav", "mp3_bitrate": 256}},
    )
    assert restore_resp.status_code == 200

    # Poll until done (max 60s)
    deadline = time.time() + 60
    status = "processing"
    while time.time() < deadline and status not in ("completed", "failed"):
        time.sleep(1)
        status_resp = client.get(f"/api/v1/jobs/{job_id}")
        status = status_resp.json()["status"]

    assert status == "completed", f"Job did not complete: {status}"

    # Download result
    dl_resp = client.get(f"/api/v1/audio/{job_id}/download", params={"format": "wav"})
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] in ("audio/wav", "audio/x-wav")
    assert len(dl_resp.content) > 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
