"""
Core noise reduction service — Stage 3 of the restoration pipeline.
All DSP operations preserve original pitch, tempo, and musical character.
"""
from __future__ import annotations

import numpy as np
from typing import Callable, Optional
from scipy import signal as sp_signal

from app.core.logging import get_logger
from app.schemas.restoration import StrengthLevel
from app.schemas.audio import AudioAnalysis

logger = get_logger("noise_reduction")


# ---------------------------------------------------------------------------
# Helper: strength -> numeric coefficient
# ---------------------------------------------------------------------------

def _strength_to_coeff(level: StrengthLevel, off: float = 0.0,
                        low: float = 0.3, medium: float = 0.55,
                        high: float = 0.75) -> float:
    mapping = {
        StrengthLevel.OFF: off,
        StrengthLevel.LOW: low,
        StrengthLevel.MEDIUM: medium,
        StrengthLevel.HIGH: high,
    }
    return mapping.get(level, low)


# ---------------------------------------------------------------------------
# Stage 3a: Broadband hiss reduction using spectral subtraction
# ---------------------------------------------------------------------------

def reduce_hiss(audio: np.ndarray, sr: int, strength: StrengthLevel,
                noise_floor_db: float = -50.0,
                progress_cb: Optional[Callable] = None) -> np.ndarray:
    """
    Conservative spectral subtraction-based hiss reduction.
    Works per-channel to preserve stereo image.
    """
    if strength == StrengthLevel.OFF:
        return audio

    coeff = _strength_to_coeff(strength, low=0.35, medium=0.60, high=0.85)
    logger.info(f"Hiss reduction: strength={strength} (coeff={coeff:.2f})")

    def _process_channel(ch: np.ndarray) -> np.ndarray:
        n_fft = 2048
        hop = n_fft // 4

        # STFT via scipy
        f, t, Zxx = sp_signal.stft(ch, fs=sr, nperseg=n_fft, noverlap=n_fft - hop, window='hann')
        magnitudes = np.abs(Zxx)
        phase = np.angle(Zxx)

        # Estimate noise profile from quietest 5% frames
        frame_energies = np.sum(magnitudes ** 2, axis=0)
        n_noise_frames = max(1, int(0.05 * Zxx.shape[1]))
        noise_frame_indices = np.argsort(frame_energies)[:n_noise_frames]
        noise_spectrum = np.mean(magnitudes[:, noise_frame_indices], axis=1, keepdims=True)

        # Spectral subtraction with oversubtraction factor
        alpha = 1.0 + coeff * 2.0   # oversubtraction factor
        beta = 0.005                 # spectral floor (prevents musical noise)

        mag_sub = magnitudes - alpha * noise_spectrum
        mag_sub = np.maximum(mag_sub, beta * noise_spectrum)

        # Reconstruct via scipy ISTFT
        Zxx_proc = mag_sub * np.exp(1j * phase)
        _, out = sp_signal.istft(Zxx_proc, fs=sr, nperseg=n_fft, noverlap=n_fft - hop, window='hann')
        return out[:len(ch)].astype(np.float32)

    return _apply_per_channel(audio, _process_channel)


# ---------------------------------------------------------------------------
# Stage 3b: Low-frequency rumble removal
# ---------------------------------------------------------------------------

def remove_rumble(audio: np.ndarray, sr: int, enabled: bool,
                  analysis: AudioAnalysis) -> np.ndarray:
    """
    High-pass Butterworth filter to remove low-frequency rumble, turntable wow,
    and sub-audible DC noise while preserving tabla and mridangam bass.
    """
    if not enabled:
        return audio

    cutoff_hz = 35.0  # Safe highpass — musical instruments and vocal fundamentals are >65 Hz
    logger.info(f"Rumble removal: highpass at {cutoff_hz} Hz")

    nyq = sr / 2.0
    sos = sp_signal.butter(2, cutoff_hz / nyq, btype="high", output="sos")
    return _apply_filter_per_channel(audio, lambda ch: sp_signal.sosfiltfilt(sos, ch))


# ---------------------------------------------------------------------------
# Stage 3c: Electrical hum removal (notch filters)
# ---------------------------------------------------------------------------

def remove_hum(audio: np.ndarray, sr: int, enabled: bool,
               analysis: AudioAnalysis) -> np.ndarray:
    """
    Targeted notch filters at hum frequency and its harmonics.
    Defaults to 50 Hz (standard Indian/vintage mains frequency) if not detected.
    """
    if not enabled:
        return audio

    fundamental = float(analysis.hum_frequency_hz) if (analysis.hum_detected and analysis.hum_frequency_hz) else 50.0
    harmonics = [fundamental * i for i in range(1, 6)
                 if fundamental * i < sr / 2 - 10]

    logger.info(f"Hum removal: notching at {[f'{h:.0f}' for h in harmonics]} Hz")

    nyq = sr / 2.0
    result = audio.copy()

    for freq in harmonics:
        q = 35.0 if freq == fundamental else 20.0  # narrow notch
        b, a = sp_signal.iirnotch(freq / nyq, q)
        result = _apply_filter_per_channel(result, lambda ch, b=b, a=a: sp_signal.filtfilt(b, a, ch))

    return result


# ---------------------------------------------------------------------------
# Stage 3d: Vinyl click and crackle reduction
# ---------------------------------------------------------------------------

def reduce_crackle(audio: np.ndarray, sr: int, strength: StrengthLevel,
                   analysis: AudioAnalysis) -> np.ndarray:
    """
    Click and vinyl crackle reduction using transient detection and interpolation.
    """
    if strength == StrengthLevel.OFF:
        return audio

    # Lower sigma multiplier detects and removes more clicks/crackles
    coeff = _strength_to_coeff(strength, low=6.0, medium=4.5, high=3.2)
    logger.info(f"Crackle reduction: strength={strength} (threshold_sigma={coeff:.1f})")

    def _declick_channel(ch: np.ndarray) -> np.ndarray:
        """Replace detected click samples with interpolated values."""
        out = ch.copy()
        diff = np.abs(np.diff(ch.astype(np.float64)))
        mu = float(np.mean(diff))
        sigma = float(np.std(diff))
        threshold = mu + coeff * sigma

        # Find click positions
        above = diff > threshold
        click_positions = np.where(above)[0]

        if len(click_positions) == 0:
            return out

        # Merge nearby clicks into regions
        regions = []
        if len(click_positions):
            start = click_positions[0]
            end = click_positions[0]
            for pos in click_positions[1:]:
                if pos - end <= int(sr * 0.003):  # merge if within 3 ms
                    end = pos
                else:
                    regions.append((start, end + 2))
                    start = pos
                    end = pos
            regions.append((start, end + 2))

        # Replace each region with cubic interpolation
        for s, e in regions:
            s = max(0, s - 1)
            e = min(len(out) - 1, e + 1)
            pre_idx = max(0, s - 8)
            post_idx = min(len(out) - 1, e + 8)
            if post_idx - pre_idx < 4:
                continue
            xp = np.array([pre_idx, post_idx])
            yp = np.array([float(ch[pre_idx]), float(ch[post_idx])])
            xi = np.arange(s, e + 1)
            # Linear interpolation (safe, no ringing)
            out[s:e + 1] = np.interp(xi, xp, yp).astype(ch.dtype)

        return out

    return _apply_per_channel(audio, _declick_channel)


# ---------------------------------------------------------------------------
# Stage 3e: AI-based broadband denoising (noisereduce)
# ---------------------------------------------------------------------------

def ai_denoise(audio: np.ndarray, sr: int, strength: StrengthLevel,
               progress_cb: Optional[Callable] = None) -> np.ndarray:
    """
    Music-aware broadband denoising using noisereduce.
    noisereduce uses non-negative matrix factorisation / Wiener filter
    which is gentler than spectral gating and better preserves harmonics.
    Only applied at user request; OFF by default maps to this function's
    strength=LOW which is very conservative.
    """
    if strength == StrengthLevel.OFF:
        return audio

    try:
        import noisereduce as nr
    except ImportError:
        logger.warning("noisereduce not installed — skipping AI denoise stage")
        return audio

    prop_decrease = _strength_to_coeff(strength, low=0.50, medium=0.75, high=0.90)
    logger.info(f"AI denoise: prop_decrease={prop_decrease:.2f}")

    def _denoise_channel(ch: np.ndarray) -> np.ndarray:
        try:
            return nr.reduce_noise(
                y=ch.astype(np.float32),
                sr=sr,
                prop_decrease=prop_decrease,
                stationary=False,          # adaptive to recording's noise
                freq_mask_smooth_hz=500,   # gentle smoothing preserves harmonics
                n_std_thresh_stationary=1.5,
                use_torch=False,           # CPU-safe
            ).astype(ch.dtype)
        except Exception as e:
            logger.warning(f"noisereduce failed on channel: {e}")
            return ch

    return _apply_per_channel(audio, _denoise_channel)


# ---------------------------------------------------------------------------
# Internal STFT/ISTFT helpers
# ---------------------------------------------------------------------------

def _stft(x: np.ndarray, n_fft: int, hop: int, window: np.ndarray) -> np.ndarray:
    """Compute STFT, return complex spectrogram (freq_bins, n_frames)."""
    _, _, z = sp_signal.stft(x, nperseg=n_fft, noverlap=n_fft - hop, window='hann')
    return z


def _istft(spec: np.ndarray, n_fft: int, hop: int, window: np.ndarray, length: int) -> np.ndarray:
    """Reconstruct signal from complex spectrogram using scipy istft."""
    _, out = sp_signal.istft(spec, nperseg=n_fft, noverlap=n_fft - hop, window='hann')
    return out[:length].astype(np.float32)


def _apply_per_channel(audio: np.ndarray, fn: Callable) -> np.ndarray:
    """Apply fn to each channel independently."""
    if audio.ndim == 1:
        return fn(audio)
    result = np.stack([fn(audio[ch]) for ch in range(audio.shape[0])])
    return result


def _apply_filter_per_channel(audio: np.ndarray, fn: Callable) -> np.ndarray:
    """Apply a filter function per channel, preserving shape."""
    return _apply_per_channel(audio, fn)
