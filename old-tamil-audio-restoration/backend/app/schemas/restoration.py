"""
Pydantic schemas for restoration settings.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class StrengthLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    OFF = "off"


class RestorationSettings(BaseModel):
    # Noise reduction
    noise_reduction_strength: StrengthLevel = StrengthLevel.LOW
    hiss_reduction: StrengthLevel = StrengthLevel.LOW
    crackle_reduction: StrengthLevel = StrengthLevel.LOW
    hum_removal: bool = True                  # only applied when hum detected
    rumble_reduction: bool = True              # only applied when rumble detected
    # Clarity
    clarity_enhancement: StrengthLevel = StrengthLevel.LOW
    # Loudness normalization
    enable_loudness_normalization: bool = True
    target_lufs: float = Field(default=-16.0, ge=-40.0, le=-6.0)
    true_peak_dbtp: float = Field(default=-1.0, ge=-6.0, le=0.0)
    # Source separation (optional, risky)
    enable_source_separation: bool = False
    # Output
    output_format: str = "wav"
    mp3_bitrate: int = 256
    # Bypass mode
    bypass_restoration: bool = False

    @field_validator("output_format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        allowed = {"wav", "flac", "mp3"}
        if v.lower() not in allowed:
            raise ValueError(f"Output format must be one of {allowed}")
        return v.lower()

    @field_validator("mp3_bitrate")
    @classmethod
    def validate_bitrate(cls, v: int) -> int:
        allowed = {128, 192, 256, 320}
        if v not in allowed:
            raise ValueError(f"MP3 bitrate must be one of {allowed}")
        return v


class RestorationRequest(BaseModel):
    settings: RestorationSettings = RestorationSettings()
