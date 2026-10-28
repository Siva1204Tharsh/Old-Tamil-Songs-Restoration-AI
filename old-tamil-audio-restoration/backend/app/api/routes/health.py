"""
Health check API route.
"""
from __future__ import annotations

import subprocess
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", summary="API health check")
async def health_check():
    """Return API health, model availability, and system information."""
    models = {}

    # Check noisereduce
    try:
        import noisereduce
        models["noisereduce"] = {"available": True, "version": getattr(noisereduce, "__version__", "unknown")}
    except ImportError:
        models["noisereduce"] = {"available": False, "note": "Run: pip install noisereduce"}

    # Check librosa
    try:
        import librosa
        models["librosa"] = {"available": True, "version": librosa.__version__}
    except ImportError:
        models["librosa"] = {"available": False, "note": "Run: pip install librosa"}

    # Check scipy
    try:
        import scipy
        models["scipy"] = {"available": True, "version": scipy.__version__}
    except ImportError:
        models["scipy"] = {"available": False}

    # Check numpy
    try:
        import numpy as np
        models["numpy"] = {"available": True, "version": np.__version__}
    except ImportError:
        models["numpy"] = {"available": False}

    # Check ffmpeg
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        ffmpeg_ok = result.returncode == 0
        ffmpeg_ver = result.stdout.split("\n")[0] if ffmpeg_ok else "not found"
    except Exception:
        ffmpeg_ok = False
        ffmpeg_ver = "not found"

    # Check Demucs (optional)
    try:
        import demucs
        models["demucs"] = {
            "available": True,
            "version": getattr(demucs, "__version__", "unknown"),
            "note": "Source separation available",
        }
    except ImportError:
        models["demucs"] = {"available": False, "note": "Optional — install with: pip install demucs"}

    # Check PyTorch (optional)
    try:
        import torch
        models["torch"] = {
            "available": True,
            "version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cuda" if torch.cuda.is_available() else "cpu",
        }
    except ImportError:
        models["torch"] = {"available": False, "note": "Optional — CPU-only mode active"}

    return {
        "status": "healthy",
        "api_version": "1.0.0",
        "ffmpeg": {"available": ffmpeg_ok, "version": ffmpeg_ver},
        "libraries": models,
        "processing_mode": "cpu",
        "note": "GPU acceleration will be used automatically if PyTorch + CUDA are installed.",
    }
