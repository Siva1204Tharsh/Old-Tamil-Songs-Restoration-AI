"""
Audio analysis service — Stage 2 of the restoration pipeline.
"""
from __future__ import annotations

import numpy as np
from pathlib import Path

from app.core.logging import get_logger
from app.services.audio_loader import load_audio_ffmpeg
from app.schemas.audio import (
    AudioMetadata, AudioAnalysis, AudioQualityReport,
    ChannelConfig, FrequencyBand,
)
from app.utils.audio_metrics import (
    measure_integrated_lufs, measure_true_peak_dbtp, measure_rms_db,
    estimate_noise_floor_db, estimate_snr_db,
    detect_clipping, detect_silence_fraction,
    detect_hum, detect_rumble, estimate_click_density,
    compute_frequency_bands, compute_quality_score,
)
from app.utils.validation import probe_audio_file, validate_audio_probe

logger = get_logger("audio_analyzer")


def analyze_audio(job_id: str, original_path: Path, original_filename: str,
                  file_size: int) -> AudioQualityReport:
    """
    Run full audio inspection and return structured quality report.
    """
    logger.info(f"[{job_id}] Starting audio analysis: {original_filename}")

    # Probe with ffprobe for exact metadata
    probe_data = probe_audio_file(original_path)
    probe_info = validate_audio_probe(probe_data)

    channels = probe_info["channels"]
    sample_rate = probe_info["sample_rate"]
    duration = probe_info["duration"]
    channel_config = ChannelConfig.STEREO if channels > 1 else ChannelConfig.MONO

    metadata = AudioMetadata(
        job_id=job_id,
        original_filename=original_filename,
        duration_seconds=duration,
        sample_rate=sample_rate,
        channels=channels,
        channel_config=channel_config,
        bit_depth=probe_info["bit_depth"],
        file_size_bytes=file_size,
        format=probe_info["format_name"],
        codec=probe_info["codec"],
    )

    # Load audio — analyse at native SR; limit to first 120s for speed
    audio, sr = load_audio_ffmpeg(original_path)
    max_analysis_samples = int(sr * 120)
    if audio.ndim > 1:
        audio_seg = audio[:, :max_analysis_samples]
    else:
        audio_seg = audio[:max_analysis_samples]

    # --- Run measurements ---
    integrated_lufs = measure_integrated_lufs(audio_seg, sr)
    true_peak = measure_true_peak_dbtp(audio_seg, sr)
    noise_floor_db = estimate_noise_floor_db(audio_seg, sr)
    snr_db = estimate_snr_db(audio_seg, sr)
    clipping_detected, clipping_fraction = detect_clipping(audio_seg)
    silence_fraction = detect_silence_fraction(audio_seg, sr)
    hum_detected, hum_freq, hum_strength = detect_hum(audio_seg, sr)
    rumble_detected, rumble_energy = detect_rumble(audio_seg, sr)
    click_density = estimate_click_density(audio_seg, sr)
    freq_bands_raw = compute_frequency_bands(audio_seg, sr)
    quality_score, quality_label = compute_quality_score(
        snr_db, clipping_fraction, click_density, silence_fraction
    )

    freq_bands = [FrequencyBand(**b) for b in freq_bands_raw]

    # Low-frequency energy flag
    sub_bass = next((b for b in freq_bands if b.band_name == "Sub-bass"), None)
    has_low_freq = sub_bass is not None and sub_bass.energy_db > -60.0

    # Build recommendations
    recs: list[str] = []
    if snr_db < 20:
        recs.append("High background noise detected — noise reduction recommended.")
    if hum_detected:
        recs.append(f"Electrical hum detected at ~{hum_freq:.0f} Hz — notch filtering recommended.")
    if rumble_detected:
        recs.append("Low-frequency rumble detected — gentle high-pass filter recommended.")
    if click_density > 1.0:
        recs.append(f"Vinyl crackle detected (~{click_density:.1f} clicks/s) — click reduction recommended.")
    if clipping_detected:
        recs.append(f"Audio clipping detected ({clipping_fraction*100:.2f}% of samples) — avoid further amplification.")
    if integrated_lufs < -30:
        recs.append("Recording is quiet — loudness normalization recommended.")
    if not recs:
        recs.append("Recording appears in reasonable condition. Conservative settings are recommended.")

    analysis = AudioAnalysis(
        job_id=job_id,
        estimated_noise_floor_db=noise_floor_db,
        estimated_snr_db=snr_db,
        clipping_detected=clipping_detected,
        clipping_fraction=clipping_fraction,
        hum_detected=hum_detected,
        hum_frequency_hz=hum_freq,
        hum_strength_db=hum_strength,
        rumble_detected=rumble_detected,
        rumble_energy_db=rumble_energy,
        crackle_detected=click_density > 0.5,
        estimated_click_density=click_density,
        silence_fraction=silence_fraction,
        integrated_lufs=integrated_lufs,
        true_peak_dbtp=true_peak,
        frequency_bands=freq_bands,
        quality_score=quality_score,
        quality_label=quality_label,
        is_stereo=channels > 1,
        has_low_frequency_energy=has_low_freq,
        recommendations=recs,
    )

    logger.info(f"[{job_id}] Analysis complete: SNR={snr_db:.1f}dB, LUFS={integrated_lufs:.1f}, "
                f"Quality={quality_label}({quality_score:.0f})")
    return AudioQualityReport(metadata=metadata, analysis=analysis)
