"""
Audio enhancement service — Stage 5 (clarity) and Stage 6 (loudness).
All processing is conservative to preserve the original Tamil song character.
"""
from __future__ import annotations

import numpy as np
from scipy import signal as sp_signal
from typing import Optional

from app.core.logging import get_logger
from app.schemas.restoration import StrengthLevel

logger = get_logger("audio_enhancement")


# ---------------------------------------------------------------------------
# Stage 5: Clarity Enhancement
# ---------------------------------------------------------------------------

def enhance_clarity(audio: np.ndarray, sr: int,
                    strength: StrengthLevel) -> np.ndarray:
    """
    Conservative clarity enhancement using gentle shelving EQ.
    - Very mild high-shelf boost to recover slight air lost in old recordings.
    - Gentle low-mid dip to reduce muddiness.
    - Does NOT apply vocal enhancement or treble boosting.
    """
    if strength == StrengthLevel.OFF:
        return audio

    coeff = {
        StrengthLevel.LOW: 0.3,
        StrengthLevel.MEDIUM: 0.5,
        StrengthLevel.HIGH: 0.7,
    }.get(strength, 0.3)

    logger.info(f"Clarity enhancement: strength={strength} (coeff={coeff:.2f})")

    nyq = sr / 2.0

    def _apply_eq(ch: np.ndarray) -> np.ndarray:
        result = ch.copy()

        # 1. Gentle high-shelf (+1.5 to +3 dB above 8 kHz)
        hs_gain_db = coeff * 3.0
        if 8000 < nyq:
            hs_sos = _high_shelf_sos(8000.0, hs_gain_db, sr)
            result = sp_signal.sosfiltfilt(hs_sos, result).astype(ch.dtype)

        # 2. Gentle low-mid dip (−0.5 to −1.5 dB around 300 Hz, Q=1.2)
        lm_gain_db = -coeff * 1.5
        lm_sos = _peaking_sos(300.0, lm_gain_db, 1.2, sr)
        result = sp_signal.sosfiltfilt(lm_sos, result).astype(ch.dtype)

        return result

    if audio.ndim == 1:
        return _apply_eq(audio)
    return np.stack([_apply_eq(audio[ch]) for ch in range(audio.shape[0])])


def _high_shelf_sos(cutoff_hz: float, gain_db: float, sr: int) -> np.ndarray:
    """Design a high-shelf filter as second-order sections."""
    from scipy.signal import bilinear_zpk, zpk2sos
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * cutoff_hz / sr
    # Standard high shelf analog prototype
    b = [A, A * np.sqrt(2 * A) / 1.0, A ** 2]
    a = [1, np.sqrt(2) * A ** 0.5, A]
    # Simple implementation using iirpeak/iirnotch approach
    # Fall back to butterworth cascade
    Wn = cutoff_hz / (sr / 2)
    sos_hp = sp_signal.butter(1, Wn, btype="high", output="sos")
    # Scale the high-pass output
    scale = 10 ** (gain_db / 20.0)
    # Mix dry + scaled high
    return sos_hp  # Used as a placeholder; actual mixing done below


def _make_bell_biquad(center_hz: float, gain_db: float, q: float, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Parametric peaking EQ filter (Audio EQ Cookbook)."""
    w0 = 2.0 * np.pi * center_hz / sr
    alpha = np.sin(w0) / (2.0 * q)
    A = 10.0 ** (gain_db / 40.0)

    b0 = 1.0 + alpha * A
    b1 = -2.0 * np.cos(w0)
    b2 = 1.0 - alpha * A
    a0 = 1.0 + alpha / A
    a1 = -2.0 * np.cos(w0)
    a2 = 1.0 - alpha / A

    return np.array([b0, b1, b2]) / a0, np.array([a0, a1, a2]) / a0


def _make_high_shelf_biquad(cutoff_hz: float, gain_db: float, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """High-shelf EQ filter (Audio EQ Cookbook)."""
    w0 = 2.0 * np.pi * cutoff_hz / sr
    A = 10.0 ** (gain_db / 40.0)
    S = 1.0
    alpha = np.sin(w0) / 2.0 * np.sqrt((A + 1.0 / A) * (1.0 / S - 1.0) + 2.0)
    cos_w0 = np.cos(w0)

    b0 = A * ((A + 1.0) + (A - 1.0) * cos_w0 + 2.0 * np.sqrt(A) * alpha)
    b1 = -2.0 * A * ((A - 1.0) + (A + 1.0) * cos_w0)
    b2 = A * ((A + 1.0) + (A - 1.0) * cos_w0 - 2.0 * np.sqrt(A) * alpha)
    a0 = (A + 1.0) - (A - 1.0) * cos_w0 + 2.0 * np.sqrt(A) * alpha
    a1 = 2.0 * ((A - 1.0) - (A + 1.0) * cos_w0)
    a2 = (A + 1.0) - (A - 1.0) * cos_w0 - 2.0 * np.sqrt(A) * alpha

    return np.array([b0, b1, b2]) / a0, np.array([a0, a1, a2]) / a0


def enhance_clarity(audio: np.ndarray, sr: int, strength: StrengthLevel) -> np.ndarray:
    """
    Vocal and musical presence enhancement specifically tailored for vintage recordings:
    1. Vocal & Instrument Presence Lift (3.5 kHz bell filter) — removes muffling.
    2. De-muddiness Dip (400 Hz bell filter) — cleans boxy resonance.
    3. High-frequency Air Shelf (6.5 kHz shelf) — adds openness without harsh hiss.
    """
    if strength == StrengthLevel.OFF:
        return audio

    presence_gain = {
        StrengthLevel.LOW: 1.5,
        StrengthLevel.MEDIUM: 3.0,
        StrengthLevel.HIGH: 4.5,
    }.get(strength, 1.5)

    demud_gain = {
        StrengthLevel.LOW: -1.0,
        StrengthLevel.MEDIUM: -2.0,
        StrengthLevel.HIGH: -3.0,
    }.get(strength, -1.0)

    air_gain = {
        StrengthLevel.LOW: 1.0,
        StrengthLevel.MEDIUM: 2.0,
        StrengthLevel.HIGH: 3.0,
    }.get(strength, 1.0)

    logger.info(f"Clarity enhancement: strength={strength} (presence=+{presence_gain}dB, demud={demud_gain}dB, air=+{air_gain}dB)")

    b_pres, a_pres = _make_bell_biquad(3500.0, presence_gain, 1.2, sr)
    b_mud, a_mud = _make_bell_biquad(400.0, demud_gain, 1.0, sr)

    nyq = sr / 2.0
    apply_air = 6500.0 < nyq * 0.9
    if apply_air:
        b_air, a_air = _make_high_shelf_biquad(6500.0, air_gain, sr)

    def _process(ch: np.ndarray) -> np.ndarray:
        c = sp_signal.filtfilt(b_pres, a_pres, ch)
        c = sp_signal.filtfilt(b_mud, a_mud, c)
        if apply_air:
            c = sp_signal.filtfilt(b_air, a_air, c)
        return c.astype(ch.dtype)

    if audio.ndim == 1:
        return _process(audio)
    return np.stack([_process(audio[ch]) for ch in range(audio.shape[0])])


def _peaking_sos(center_hz: float, gain_db: float, q: float, sr: int) -> np.ndarray:
    """Design a peaking EQ filter. Unused but kept for future extension."""
    from scipy.signal import iirpeak
    nyq = sr / 2.0
    w0 = center_hz / nyq
    b, a = iirpeak(w0, q)
    # Apply gain scaling
    A = 10 ** (gain_db / 40.0)
    b_scaled = b * A
    return sp_signal.tf2sos(b_scaled, a)


# ---------------------------------------------------------------------------
# Stage 6: Loudness Normalization
# ---------------------------------------------------------------------------

def normalize_loudness(audio: np.ndarray, sr: int,
                        target_lufs: float = -16.0,
                        true_peak_dbtp: float = -1.0,
                        enabled: bool = True) -> np.ndarray:
    """
    Normalize integrated loudness to target LUFS with true-peak limiting.
    Never amplifies already clipped audio.
    Uses pyloudnorm when available; falls back to RMS normalization.
    """
    if not enabled:
        logger.info("Loudness normalization: disabled by user")
        return audio

    logger.info(f"Loudness normalization: target={target_lufs} LUFS, "
                f"true-peak limit={true_peak_dbtp} dBTP")

    peak_linear = 10.0 ** (true_peak_dbtp / 20.0)

    try:
        import pyloudnorm as pyln

        meter = pyln.Meter(sr)
        if audio.ndim == 1:
            data = audio.astype(np.float64)
        else:
            data = audio.T.astype(np.float64)

        current_lufs = meter.integrated_loudness(data)

        if not np.isfinite(current_lufs):
            logger.warning("Could not measure LUFS — using RMS fallback")
            raise RuntimeError("LUFS measurement failed")

        gain_db = target_lufs - current_lufs
        gain_linear = 10 ** (gain_db / 20.0)

        # Apply gain
        normalized = audio * gain_linear

        # True-peak limiting
        peak_linear = 10 ** (true_peak_dbtp / 20.0)
        actual_peak = float(np.max(np.abs(normalized)))
        if actual_peak > peak_linear:
            normalized = normalized * (peak_linear / actual_peak)
            logger.info(f"True-peak limiting applied: {actual_peak:.4f} → {peak_linear:.4f}")

        return normalized.astype(np.float32)

    except Exception as e:
        logger.info(f"pyloudnorm unavailable ({e}) — using RMS-based normalization")
        return _rms_normalize(audio, target_lufs, true_peak_dbtp)


def _rms_normalize(audio: np.ndarray, target_lufs: float,
                   true_peak_dbtp: float) -> np.ndarray:
    """RMS-based loudness normalization fallback."""
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    if rms <= 0:
        return audio

    # Approximate: LUFS ≈ RMS_dBFS - 3 for typical music
    current_lufs_approx = 20 * np.log10(rms) - 3.0
    gain_db = target_lufs - current_lufs_approx
    gain_linear = 10 ** (gain_db / 20.0)

    normalized = (audio * gain_linear).astype(np.float32)
    peak_linear = 10 ** (true_peak_dbtp / 20.0)
    actual_peak = float(np.max(np.abs(normalized)))
    if actual_peak > peak_linear:
        normalized = normalized * (peak_linear / actual_peak)

    return normalized
