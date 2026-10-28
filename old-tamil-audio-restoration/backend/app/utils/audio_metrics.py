"""
Audio metrics and measurement utilities.
"""
from __future__ import annotations

import numpy as np
from typing import Optional
from app.core.logging import get_logger

logger = get_logger("audio_metrics")


def measure_true_peak_dbtp(audio: np.ndarray, sample_rate: int, oversample: int = 4) -> float:
    """
    Measure inter-sample true peak using oversampling (ITU-R BS.1770-4 compliant approach).
    Returns dBTP value.
    """
    try:
        from scipy.signal import resample_poly
        if audio.ndim == 1:
            upsampled = resample_poly(audio, oversample, 1)
        else:
            upsampled = np.stack([
                resample_poly(audio[ch], oversample, 1) for ch in range(audio.shape[0])
            ])
        peak = float(np.max(np.abs(upsampled)))
        if peak <= 0:
            return -120.0
        return float(20 * np.log10(peak))
    except Exception:
        # Fallback: simple peak
        peak = float(np.max(np.abs(audio)))
        if peak <= 0:
            return -120.0
        return float(20 * np.log10(peak))


def measure_rms_db(audio: np.ndarray) -> float:
    """Measure RMS level in dBFS."""
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    if rms <= 0:
        return -120.0
    return float(20 * np.log10(rms))


def measure_integrated_lufs(audio: np.ndarray, sample_rate: int) -> float:
    """
    Measure integrated loudness (LUFS) using a simplified BS.1770-3 K-weighting approach.
    Falls back to RMS-based estimate when pyloudnorm is not available.
    """
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sample_rate)
        if audio.ndim == 1:
            data = audio.astype(np.float64)
        else:
            data = audio.T.astype(np.float64)  # pyloudnorm expects (samples, channels)
        lufs = meter.integrated_loudness(data)
        return float(lufs) if np.isfinite(lufs) else measure_rms_db(audio) - 3.0
    except Exception:
        # Fallback: approximate from RMS with K-weighting offset (~3 dB for music)
        return measure_rms_db(audio) - 3.0


def estimate_noise_floor_db(audio: np.ndarray, sample_rate: int, percentile: float = 10.0) -> float:
    """
    Estimate noise floor by finding the Nth-percentile energy in short frames.
    Uses quiet sections of the recording.
    """
    frame_size = int(sample_rate * 0.05)  # 50 ms frames
    if audio.ndim > 1:
        mono = np.mean(audio, axis=0)
    else:
        mono = audio

    if len(mono) < frame_size:
        return measure_rms_db(mono)

    n_frames = len(mono) // frame_size
    energies = []
    for i in range(n_frames):
        frame = mono[i * frame_size:(i + 1) * frame_size]
        rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
        if rms > 0:
            energies.append(20 * np.log10(rms))

    if not energies:
        return -80.0
    return float(np.percentile(energies, percentile))


def estimate_snr_db(audio: np.ndarray, sample_rate: int) -> float:
    """Estimate SNR as difference between signal RMS and noise floor."""
    signal_db = measure_rms_db(audio)
    noise_floor_db = estimate_noise_floor_db(audio, sample_rate)
    return max(0.0, signal_db - noise_floor_db)


def detect_clipping(audio: np.ndarray, threshold: float = 0.98) -> tuple[bool, float]:
    """
    Detect clipping by counting samples at or near full scale.
    Returns (clipping_detected, fraction_of_samples).
    """
    clipped = np.sum(np.abs(audio) >= threshold)
    fraction = float(clipped) / float(audio.size)
    return fraction > 0.0001, fraction


def detect_silence_fraction(audio: np.ndarray, sample_rate: int,
                             silence_threshold_db: float = -60.0) -> float:
    """Fraction of frames that are below the silence threshold."""
    frame_size = int(sample_rate * 0.02)
    if audio.ndim > 1:
        mono = np.mean(audio, axis=0)
    else:
        mono = audio

    n_frames = len(mono) // frame_size
    if n_frames == 0:
        return 0.0

    silent_count = 0
    threshold_linear = 10 ** (silence_threshold_db / 20)
    for i in range(n_frames):
        frame = mono[i * frame_size:(i + 1) * frame_size]
        rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
        if rms < threshold_linear:
            silent_count += 1

    return float(silent_count) / float(n_frames)


def detect_hum(audio: np.ndarray, sample_rate: int,
               candidates: list[float] = None) -> tuple[bool, Optional[float], Optional[float]]:
    """
    Detect electrical hum (50/60 Hz and harmonics) using FFT peak analysis.
    Returns (hum_detected, hum_frequency_hz, hum_strength_db).
    """
    if candidates is None:
        candidates = [50.0, 60.0, 100.0, 120.0, 150.0, 180.0, 200.0, 240.0]

    if audio.ndim > 1:
        mono = np.mean(audio, axis=0)
    else:
        mono = audio.copy()

    # Use a portion of the signal (up to 10s) for speed
    max_samples = int(sample_rate * 10)
    if len(mono) > max_samples:
        mono = mono[:max_samples]

    fft_size = min(len(mono), sample_rate * 4)
    if fft_size < sample_rate // 2:
        return False, None, None

    window = np.hanning(fft_size)
    spectrum = np.abs(np.fft.rfft(mono[:fft_size] * window)) / (fft_size / 2.0)
    spectrum_db = 20 * np.log10(np.maximum(spectrum, 1e-6))  # Clamped at -120 dBFS

    # Compute baseline floor in the low-frequency band (30 Hz to 400 Hz)
    low_start = max(1, int(30.0 * fft_size / sample_rate))
    low_end = min(len(spectrum_db), int(400.0 * fft_size / sample_rate))
    low_band = spectrum_db[low_start:low_end]
    local_floor = float(np.median(low_band)) if len(low_band) > 0 else -80.0

    best_freq = None
    best_strength = -999.0

    bin_hz = sample_rate / fft_size
    radius = max(2, int(2.0 / bin_hz))

    for cand_freq in candidates:
        idx = int(cand_freq * fft_size / sample_rate)
        if idx >= len(spectrum_db):
            continue
        lo = max(0, idx - radius)
        hi = min(len(spectrum_db), idx + radius + 1)
        peak_db = float(np.max(spectrum_db[lo:hi]))

        # Hum must be audible (above -60 dBFS) and prominent above low-frequency baseline
        strength = peak_db - local_floor
        if peak_db > -60.0 and strength > best_strength:
            best_strength = strength
            best_freq = cand_freq

    hum_threshold = 12.0  # dB above local low-frequency baseline
    if best_strength >= hum_threshold and best_freq is not None:
        return True, best_freq, round(best_strength, 1)
    return False, None, None


def detect_rumble(audio: np.ndarray, sample_rate: int,
                  rumble_cutoff_hz: float = 40.0) -> tuple[bool, Optional[float]]:
    """
    Detect low-frequency rumble by measuring energy below the cutoff frequency.
    Returns (rumble_detected, energy_db).
    """
    if audio.ndim > 1:
        mono = np.mean(audio, axis=0)
    else:
        mono = audio.copy()

    fft_size = min(len(mono), sample_rate * 4)
    spectrum = np.abs(np.fft.rfft(mono[:fft_size]))
    freqs = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)

    low_mask = freqs < rumble_cutoff_hz
    mid_mask = (freqs >= 100.0) & (freqs < 500.0)

    if not np.any(low_mask) or not np.any(mid_mask):
        return False, None

    low_energy = float(np.mean(spectrum[low_mask] ** 2))
    mid_energy = float(np.mean(spectrum[mid_mask] ** 2))

    if mid_energy == 0:
        return False, None

    ratio = 10 * np.log10(max(low_energy / mid_energy, 1e-10))
    energy_db = 20 * np.log10(max(np.sqrt(low_energy), 1e-10))

    # Rumble is suspicious if low-freq energy is comparable to mid-range
    return ratio > -6.0, energy_db


def estimate_click_density(audio: np.ndarray, sample_rate: int) -> float:
    """
    Estimate vinyl click/crackle density using transient detection.
    Returns estimated clicks per second.
    """
    if audio.ndim > 1:
        mono = np.mean(audio, axis=0)
    else:
        mono = audio.copy()

    # Differentiate to emphasize transients
    diff = np.abs(np.diff(mono.astype(np.float64)))
    # Threshold: mean + 6*std of differentiated signal
    mean_d = float(np.mean(diff))
    std_d = float(np.std(diff))
    threshold = mean_d + 6.0 * std_d

    # Find peaks above threshold with minimum separation
    min_gap = int(sample_rate * 0.005)  # 5 ms minimum between clicks
    above = diff > threshold
    prev_trigger = -min_gap - 1
    click_count = 0
    for i, is_above in enumerate(above):
        if is_above and (i - prev_trigger) > min_gap:
            click_count += 1
            prev_trigger = i

    duration_seconds = len(mono) / sample_rate
    return float(click_count) / max(duration_seconds, 1.0)


def compute_frequency_bands(audio: np.ndarray, sample_rate: int) -> list[dict]:
    """Compute average energy in perceptually relevant frequency bands."""
    if audio.ndim > 1:
        mono = np.mean(audio, axis=0)
    else:
        mono = audio.copy()

    fft_size = min(len(mono), sample_rate * 4)
    spectrum = np.abs(np.fft.rfft(mono[:fft_size]))
    freqs = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)

    bands = [
        ("Sub-bass", 20, 60),
        ("Bass", 60, 250),
        ("Low-mid", 250, 500),
        ("Mid", 500, 2000),
        ("Upper-mid", 2000, 4000),
        ("Presence", 4000, 6000),
        ("Brilliance", 6000, 12000),
        ("Air", 12000, min(20000, sample_rate // 2)),
    ]

    result = []
    for name, lo, hi in bands:
        mask = (freqs >= lo) & (freqs < hi)
        if np.any(mask):
            energy = float(np.mean(spectrum[mask] ** 2))
            energy_db = 10 * np.log10(max(energy, 1e-20))
        else:
            energy_db = -120.0
        result.append({
            "band_name": name,
            "center_hz": float((lo + hi) / 2),
            "energy_db": energy_db,
        })

    return result


def compute_quality_score(snr_db: float, clipping_fraction: float,
                           click_density: float, silence_fraction: float) -> tuple[float, str]:
    """Compute an overall quality score (0–100) and label."""
    score = 50.0

    # SNR contribution (0–30 points)
    snr_score = min(30.0, max(0.0, (snr_db - 5.0) * 2.0))
    score += snr_score - 15.0  # normalise around 0

    # Clipping penalty (0–20 points)
    clipping_penalty = min(20.0, clipping_fraction * 2000.0)
    score -= clipping_penalty

    # Click density penalty (0–20 points)
    click_penalty = min(20.0, click_density * 4.0)
    score -= click_penalty

    # Silence penalty
    silence_penalty = min(10.0, max(0.0, silence_fraction - 0.3) * 20.0)
    score -= silence_penalty

    score = max(0.0, min(100.0, score))

    if score >= 70:
        label = "Good"
    elif score >= 45:
        label = "Fair"
    elif score >= 25:
        label = "Poor"
    else:
        label = "Very Poor"

    return score, label
