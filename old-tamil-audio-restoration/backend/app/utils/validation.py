"""
Audio file validation utilities.
"""
from __future__ import annotations

import hashlib
import mimetypes
import subprocess
import json
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("validation")

EXTENSION_TO_FORMAT = {
    ".wav": "wav", ".wave": "wav",
    ".mp3": "mp3",
    ".flac": "flac",
    ".m4a": "m4a", ".mp4": "m4a",
    ".ogg": "ogg",
    ".aiff": "aiff", ".aif": "aiff",
}


class ValidationError(Exception):
    """Raised when an uploaded file fails validation."""
    def __init__(self, message: str, status_code: int = 422):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def validate_file_size(file_size: int) -> None:
    max_bytes = settings.max_file_size_bytes
    if file_size > max_bytes:
        raise ValidationError(
            f"File size {file_size / 1024 / 1024:.1f} MB exceeds the "
            f"maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB."
        )
    if file_size == 0:
        raise ValidationError("Uploaded file is empty.")


def validate_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in EXTENSION_TO_FORMAT:
        raise ValidationError(
            f"File extension '{suffix}' is not supported. "
            f"Supported: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    return suffix


def probe_audio_file(path: Path) -> dict:
    """Run ffprobe on the file and return stream info."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise ValidationError(
                "Could not read audio file. The file may be corrupted or in an "
                "unsupported format."
            )
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        raise ValidationError("Audio file probe timed out. The file may be corrupted.")
    except json.JSONDecodeError:
        raise ValidationError("Could not parse audio file information.")


def validate_audio_probe(probe_data: dict) -> dict:
    """Extract and validate audio stream info from ffprobe output."""
    streams = probe_data.get("streams", [])
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    if not audio_streams:
        raise ValidationError(
            "No audio stream found in the uploaded file. "
            "Please upload a valid audio file."
        )

    fmt = probe_data.get("format", {})
    audio = audio_streams[0]

    duration = float(fmt.get("duration") or audio.get("duration") or 0)
    if duration <= 0:
        raise ValidationError("Could not determine audio duration. The file may be corrupted.")
    if duration > settings.MAX_DURATION_SECONDS:
        raise ValidationError(
            f"Audio duration {duration/60:.1f} minutes exceeds the maximum "
            f"allowed duration of {settings.MAX_DURATION_SECONDS/60:.0f} minutes."
        )

    sample_rate = int(audio.get("sample_rate", 0))
    if sample_rate < 8000:
        raise ValidationError(
            f"Sample rate {sample_rate} Hz is too low to be a valid audio recording."
        )

    channels = int(audio.get("channels", 0))
    if channels < 1 or channels > 2:
        raise ValidationError(
            f"Only mono and stereo recordings are supported (got {channels} channels)."
        )

    codec = audio.get("codec_name", "unknown")
    bit_depth = audio.get("bits_per_sample") or audio.get("bits_per_raw_sample")

    return {
        "duration": duration,
        "sample_rate": sample_rate,
        "channels": channels,
        "codec": codec,
        "bit_depth": int(bit_depth) if bit_depth else None,
        "format_name": fmt.get("format_name", "unknown"),
        "size": int(fmt.get("size", 0)),
    }


def compute_file_hash(path: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
