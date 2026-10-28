"""
Audio file loading using FFmpeg for broad format support.
"""
from __future__ import annotations

import subprocess
import tempfile
import numpy as np
from pathlib import Path
from typing import Optional

from app.core.logging import get_logger

logger = get_logger("audio_loader")


class AudioLoadError(Exception):
    pass


def load_audio_ffmpeg(path: Path, target_sr: Optional[int] = None,
                      mono: bool = False) -> tuple[np.ndarray, int]:
    """
    Load audio file using FFmpeg and return (audio_array, sample_rate).
    audio_array shape: (channels, samples) for stereo; (samples,) for mono.
    Preserves stereo unless mono=True is explicitly requested.
    """
    # First probe the file to get native SR and channels
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", str(path),
    ]
    try:
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        import json
        probe_data = json.loads(probe_result.stdout)
        audio_streams = [s for s in probe_data.get("streams", []) if s.get("codec_type") == "audio"]
        if audio_streams:
            native_sr = int(audio_streams[0].get("sample_rate", 44100))
            native_channels = int(audio_streams[0].get("channels", 1))
        else:
            native_sr = 44100
            native_channels = 1
    except Exception:
        native_sr = 44100
        native_channels = 1

    sr = target_sr if target_sr else native_sr
    channels = 1 if mono else native_channels

    # Build ffmpeg command to decode to raw f32le PCM
    cmd = [
        "ffmpeg", "-v", "quiet",
        "-i", str(path),
        "-ac", str(channels),
        "-ar", str(sr),
        "-f", "f32le",
        "-acodec", "pcm_f32le",
        "pipe:1",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            raise AudioLoadError(f"FFmpeg failed: {result.stderr.decode(errors='replace')[:500]}")
        if len(result.stdout) == 0:
            raise AudioLoadError("FFmpeg produced no output. The file may be corrupted.")
    except subprocess.TimeoutExpired:
        raise AudioLoadError("Audio loading timed out.")

    audio_flat = np.frombuffer(result.stdout, dtype=np.float32)
    if channels > 1:
        # Reshape to (samples, channels) then transpose to (channels, samples)
        n_samples = len(audio_flat) // channels
        audio = audio_flat[:n_samples * channels].reshape(n_samples, channels).T
    else:
        audio = audio_flat.copy()

    logger.info(f"Loaded audio: {path.name} | sr={sr} | channels={channels} | "
                f"samples={audio.shape[-1]} | duration={audio.shape[-1]/sr:.2f}s")
    return audio, sr


def save_audio_ffmpeg(audio: np.ndarray, sample_rate: int, output_path: Path,
                      output_format: str = "wav", mp3_bitrate: int = 256) -> Path:
    """
    Export audio array to file using FFmpeg.
    audio: (channels, samples) or (samples,) float32 array in range [-1, 1].
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_format = output_format.lower()

    if audio.ndim == 1:
        channels = 1
        raw = audio.astype(np.float32).tobytes()
    else:
        channels = audio.shape[0]
        raw = audio.T.astype(np.float32).tobytes()  # interleave channels

    # Build ffmpeg output args
    if output_format == "wav":
        output_args = ["-f", "wav", "-acodec", "pcm_s24le"]
    elif output_format == "flac":
        output_args = ["-f", "flac", "-compression_level", "8"]
    elif output_format == "mp3":
        output_args = ["-f", "mp3", "-b:a", f"{mp3_bitrate}k"]
    else:
        raise AudioLoadError(f"Unsupported output format: {output_format}")

    cmd = [
        "ffmpeg", "-y", "-v", "quiet",
        "-f", "f32le",
        "-ac", str(channels),
        "-ar", str(sample_rate),
        "-i", "pipe:0",
    ] + output_args + [str(output_path)]

    try:
        result = subprocess.run(cmd, input=raw, capture_output=True, timeout=300)
        if result.returncode != 0:
            raise AudioLoadError(
                f"FFmpeg export failed: {result.stderr.decode(errors='replace')[:500]}"
            )
    except subprocess.TimeoutExpired:
        raise AudioLoadError("Audio export timed out.")

    logger.info(f"Saved audio: {output_path} | format={output_format} | channels={channels}")
    return output_path
