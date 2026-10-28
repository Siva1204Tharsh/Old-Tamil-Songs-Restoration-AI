"""
Export service — Stage 7. Writes the restored audio in all requested formats.
"""
from __future__ import annotations

import numpy as np
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.services.audio_loader import save_audio_ffmpeg
from app.schemas.restoration import RestorationSettings

logger = get_logger("export_service")


def export_all_formats(job_id: str, audio: np.ndarray, sr: int,
                       rest_settings: RestorationSettings,
                       original_filename: str) -> dict[str, Path]:
    """
    Export the restored audio to all supported formats.
    Returns a dict mapping format name to output path.
    """
    out_dir = settings.PROCESSED_DIR / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(original_filename).stem
    outputs: dict[str, Path] = {}

    # WAV (primary, lossless)
    wav_path = out_dir / f"{stem}_restored.wav"
    save_audio_ffmpeg(audio, sr, wav_path, output_format="wav")
    outputs["wav"] = wav_path
    logger.info(f"[{job_id}] Exported WAV: {wav_path}")

    # FLAC (lossless compressed)
    flac_path = out_dir / f"{stem}_restored.flac"
    save_audio_ffmpeg(audio, sr, flac_path, output_format="flac")
    outputs["flac"] = flac_path
    logger.info(f"[{job_id}] Exported FLAC: {flac_path}")

    # MP3 (user-selectable bitrate)
    mp3_path = out_dir / f"{stem}_restored.mp3"
    save_audio_ffmpeg(audio, sr, mp3_path, output_format="mp3",
                      mp3_bitrate=rest_settings.mp3_bitrate)
    outputs["mp3"] = mp3_path
    logger.info(f"[{job_id}] Exported MP3 @{rest_settings.mp3_bitrate}kbps: {mp3_path}")

    return outputs


def get_output_path(job_id: str, format_name: str,
                    original_filename: str) -> Path | None:
    """Return the path for a specific output format if it exists."""
    out_dir = settings.PROCESSED_DIR / job_id
    stem = Path(original_filename).stem
    path = out_dir / f"{stem}_restored.{format_name}"
    return path if path.exists() else None
