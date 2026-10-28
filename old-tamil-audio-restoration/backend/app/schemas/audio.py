"""
Pydantic schemas for audio-related request/response models.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AudioFormat(str, Enum):
    WAV = "wav"
    FLAC = "flac"
    MP3 = "mp3"


class MP3Bitrate(int, Enum):
    B128 = 128
    B192 = 192
    B256 = 256
    B320 = 320


class ChannelConfig(str, Enum):
    MONO = "mono"
    STEREO = "stereo"


class AudioMetadata(BaseModel):
    job_id: str
    original_filename: str
    duration_seconds: float
    sample_rate: int
    channels: int
    channel_config: ChannelConfig
    bit_depth: Optional[int] = None
    file_size_bytes: int
    format: str
    codec: Optional[str] = None


class FrequencyBand(BaseModel):
    band_name: str
    center_hz: float
    energy_db: float


class AudioAnalysis(BaseModel):
    job_id: str
    # Noise estimates
    estimated_noise_floor_db: float
    estimated_snr_db: float
    # Clipping
    clipping_detected: bool
    clipping_fraction: float          # 0.0–1.0
    # Hum
    hum_detected: bool
    hum_frequency_hz: Optional[float] = None
    hum_strength_db: Optional[float] = None
    # Rumble
    rumble_detected: bool
    rumble_energy_db: Optional[float] = None
    # Clicks & crackle
    crackle_detected: bool
    estimated_click_density: float    # clicks/second estimate
    # Silence / gaps
    silence_fraction: float           # 0.0–1.0
    # Loudness
    integrated_lufs: float
    true_peak_dbtp: float
    # Frequency distribution
    frequency_bands: list[FrequencyBand]
    # Overall quality
    quality_score: float              # 0–100
    quality_label: str
    # Flags
    is_stereo: bool
    has_low_frequency_energy: bool
    recommendations: list[str]


class AudioQualityReport(BaseModel):
    metadata: AudioMetadata
    analysis: AudioAnalysis
