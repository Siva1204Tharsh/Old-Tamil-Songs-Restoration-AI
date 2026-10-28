"""
Main restoration pipeline orchestrator.
Coordinates all stages of audio restoration while maintaining musical integrity.
"""
from __future__ import annotations

import time
import numpy as np
from pathlib import Path
from typing import Optional, Callable

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.restoration import RestorationSettings, StrengthLevel
from app.schemas.audio import AudioAnalysis
from app.schemas.jobs import ProcessingStage, JobStatus
from app.services.audio_loader import load_audio_ffmpeg, save_audio_ffmpeg
from app.services.noise_reduction import (
    reduce_hiss, remove_rumble, remove_hum, reduce_crackle, ai_denoise,
)
from app.services.music_restoration import (
    verify_pitch_preserved, verify_duration_preserved, apply_source_separation,
)
from app.services.audio_enhancement import enhance_clarity, normalize_loudness
from app.services.export_service import export_all_formats
from app.services.job_manager import job_manager
from app.utils.audio_metrics import (
    measure_integrated_lufs, measure_true_peak_dbtp, measure_rms_db,
)

logger = get_logger("restoration_pipeline")

CHUNK_DURATION_S = 30.0
CHUNK_OVERLAP_S = 1.0


def run_restoration_pipeline(
    job_id: str,
    original_path: Path,
    original_filename: str,
    analysis: AudioAnalysis,
    rest_settings: RestorationSettings,
) -> dict:
    """
    Full restoration pipeline. Run in a background thread.
    Returns result metadata dict.
    """
    start_time = time.time()
    logger.info(f"[{job_id}] Restoration pipeline started")

    def stage_cb(stage: ProcessingStage, pct: float, msg: Optional[str] = None,
                 done: bool = False):
        job_manager.update_stage(job_id, stage, pct, msg, completed=done)

    try:
        job_manager.update_status(job_id, JobStatus.PROCESSING)

        # ---------------------------------------------------------------
        # Stage 1: Load audio
        # ---------------------------------------------------------------
        stage_cb(ProcessingStage.UPLOAD, 0, "Loading audio...")
        audio, sr = load_audio_ffmpeg(original_path)
        original_audio = audio.copy()  # Keep reference for verification
        stage_cb(ProcessingStage.UPLOAD, 100, "Audio loaded", done=True)

        # Bypass mode — return original decoded audio
        if rest_settings.bypass_restoration:
            logger.info(f"[{job_id}] Bypass mode — skipping restoration")
            outputs = export_all_formats(job_id, audio, sr, rest_settings, original_filename)
            stage_cb(ProcessingStage.EXPORT, 100, "Export complete", done=True)
            stage_cb(ProcessingStage.DONE, 100, "Bypass mode — original audio returned", done=True)
            result = _build_result_metadata(job_id, audio, sr, outputs, start_time)
            job_manager.set_result(job_id, result, result["processing_time_seconds"])
            job_manager.update_status(job_id, JobStatus.COMPLETED)
            return result

        # ---------------------------------------------------------------
        # Stage 2: Analysis (already done upstream, passed in)
        # ---------------------------------------------------------------
        stage_cb(ProcessingStage.ANALYSIS, 100, "Analysis complete", done=True)

        # ---------------------------------------------------------------
        # Stage 3: Noise Reduction
        # ---------------------------------------------------------------
        stage_cb(ProcessingStage.NOISE_REDUCTION, 0, "Starting noise reduction...")

        audio = _process_in_chunks(
            audio, sr, original_filename,
            fn=lambda chunk: _noise_reduction_chain(chunk, sr, rest_settings, analysis),
            stage=ProcessingStage.NOISE_REDUCTION,
            stage_cb=stage_cb,
        )

        stage_cb(ProcessingStage.NOISE_REDUCTION, 100, "Noise reduction complete", done=True)

        # ---------------------------------------------------------------
        # Stage 4: Optional source separation
        # ---------------------------------------------------------------
        stage_cb(ProcessingStage.MUSIC_PRESERVATION, 0, "Music preservation checks...")

        if rest_settings.enable_source_separation:
            stage_cb(ProcessingStage.MUSIC_PRESERVATION, 20, "Running source separation...")
            audio = apply_source_separation(audio, sr, rest_settings,
                                            progress_cb=lambda m: stage_cb(
                                                ProcessingStage.MUSIC_PRESERVATION, 50, m))

        # Verify pitch and timing integrity
        if not verify_pitch_preserved(original_audio, audio, sr):
            logger.warning(f"[{job_id}] Pitch integrity check: minor pitch variance detected between original and restored audio")

        if not verify_duration_preserved(original_audio, audio, sr):
            logger.warning(f"[{job_id}] Duration mismatch — trimming to original length")
            orig_len = original_audio.shape[-1]
            if audio.ndim > 1:
                audio = audio[:, :orig_len]
            else:
                audio = audio[:orig_len]

        stage_cb(ProcessingStage.MUSIC_PRESERVATION, 100, "Music preserved", done=True)

        # ---------------------------------------------------------------
        # Stage 5: Clarity enhancement
        # ---------------------------------------------------------------
        stage_cb(ProcessingStage.CLARITY_ENHANCEMENT, 0, "Enhancing clarity...")
        audio = enhance_clarity(audio, sr, rest_settings.clarity_enhancement)
        stage_cb(ProcessingStage.CLARITY_ENHANCEMENT, 100, "Clarity enhanced", done=True)

        # ---------------------------------------------------------------
        # Stage 6: Loudness normalization
        # ---------------------------------------------------------------
        stage_cb(ProcessingStage.LOUDNESS_NORMALIZATION, 0, "Normalizing loudness...")
        audio = normalize_loudness(
            audio, sr,
            target_lufs=rest_settings.target_lufs,
            true_peak_dbtp=rest_settings.true_peak_dbtp,
            enabled=rest_settings.enable_loudness_normalization,
        )
        stage_cb(ProcessingStage.LOUDNESS_NORMALIZATION, 100, "Loudness normalized", done=True)

        # ---------------------------------------------------------------
        # Stage 7: Export
        # ---------------------------------------------------------------
        stage_cb(ProcessingStage.EXPORT, 0, "Exporting restored audio...")
        outputs = export_all_formats(job_id, audio, sr, rest_settings, original_filename)
        stage_cb(ProcessingStage.EXPORT, 100, "Export complete", done=True)
        stage_cb(ProcessingStage.DONE, 100, "Restoration complete", done=True)

        result = _build_result_metadata(job_id, audio, sr, outputs, start_time)
        job_manager.set_result(job_id, result, result["processing_time_seconds"])
        job_manager.update_status(job_id, JobStatus.COMPLETED)

        logger.info(f"[{job_id}] Restoration complete in "
                    f"{result['processing_time_seconds']:.1f}s")
        return result

    except Exception as e:
        elapsed = time.time() - start_time
        logger.exception(f"[{job_id}] Restoration failed after {elapsed:.1f}s: {e}")
        job_manager.update_status(job_id, JobStatus.FAILED, error_message=str(e))
        raise


def _noise_reduction_chain(audio: np.ndarray, sr: int,
                            settings_: RestorationSettings,
                            analysis: AudioAnalysis) -> np.ndarray:
    """Apply the full noise reduction chain to a chunk."""
    # 3a: Hiss
    if settings_.hiss_reduction != StrengthLevel.OFF:
        audio = reduce_hiss(audio, sr, settings_.hiss_reduction,
                            noise_floor_db=analysis.estimated_noise_floor_db)

    # 3b: Rumble
    if settings_.rumble_reduction:
        audio = remove_rumble(audio, sr, settings_.rumble_reduction, analysis)

    # 3c: Hum
    if settings_.hum_removal:
        audio = remove_hum(audio, sr, settings_.hum_removal, analysis)

    # 3d: Crackle
    if settings_.crackle_reduction != StrengthLevel.OFF:
        audio = reduce_crackle(audio, sr, settings_.crackle_reduction, analysis)

    # 3e: AI denoise (only when noise_reduction_strength is not OFF)
    if settings_.noise_reduction_strength != StrengthLevel.OFF:
        audio = ai_denoise(audio, sr, settings_.noise_reduction_strength)

    return audio


def _process_in_chunks(
    audio: np.ndarray, sr: int, filename: str,
    fn: Callable, stage: ProcessingStage,
    stage_cb: Callable,
) -> np.ndarray:
    """
    Process audio in overlapping chunks with crossfade to avoid seams.
    Falls back to full processing if audio is short enough.
    """
    chunk_samples = int(CHUNK_DURATION_S * sr)
    overlap_samples = int(CHUNK_OVERLAP_S * sr)

    total_samples = audio.shape[-1]

    if total_samples <= chunk_samples * 2:
        # Short file — process in one pass
        stage_cb(stage, 50, "Processing...")
        return fn(audio)

    logger.info(f"Chunked processing: {total_samples/sr:.1f}s | "
                f"chunk={CHUNK_DURATION_S}s | overlap={CHUNK_OVERLAP_S}s")

    hop = chunk_samples - overlap_samples
    starts = []
    curr = 0
    while curr < total_samples:
        starts.append(curr)
        if curr + chunk_samples >= total_samples:
            break
        curr += hop
        if curr + chunk_samples > total_samples and curr < total_samples:
            last = max(0, total_samples - chunk_samples)
            if last not in starts:
                starts.append(last)
            break

    n_chunks = len(starts)
    result = np.zeros_like(audio, dtype=np.float32)
    weight = np.zeros(total_samples, dtype=np.float32)

    for i, start in enumerate(starts):
        end = min(start + chunk_samples, total_samples)
        pct = (i / n_chunks) * 100.0
        stage_cb(stage, pct, f"Processing chunk {i+1}/{n_chunks}...")

        if audio.ndim > 1:
            chunk = audio[:, start:end]
        else:
            chunk = audio[start:end]

        chunk_processed = fn(chunk)
        chunk_len = end - start

        # Trapezoidal window with smooth linear ramps at overlaps
        w = np.ones(chunk_len, dtype=np.float32)
        act_overlap = min(overlap_samples, chunk_len // 2)
        if start > 0 and act_overlap > 0:
            w[:act_overlap] = np.linspace(0.0, 1.0, act_overlap, dtype=np.float32)
        if end < total_samples and act_overlap > 0:
            w[-act_overlap:] = np.linspace(1.0, 0.0, act_overlap, dtype=np.float32)

        if audio.ndim > 1:
            result[:, start:end] += chunk_processed * w[np.newaxis, :]
            weight[start:end] += w
        else:
            result[start:end] += chunk_processed * w
            weight[start:end] += w

    weight = np.maximum(weight, 1e-6)
    if audio.ndim > 1:
        result /= weight[np.newaxis, :]
    else:
        result /= weight

    return result


def _build_result_metadata(job_id: str, audio: np.ndarray, sr: int,
                            outputs: dict, start_time: float) -> dict:
    """Build the result metadata dictionary."""
    elapsed = time.time() - start_time
    lufs = measure_integrated_lufs(audio, sr)
    true_peak = measure_true_peak_dbtp(audio, sr)
    duration = audio.shape[-1] / sr
    channels = 1 if audio.ndim == 1 else audio.shape[0]

    return {
        "job_id": job_id,
        "processing_time_seconds": round(elapsed, 2),
        "restored_duration_seconds": round(duration, 3),
        "restored_sample_rate": sr,
        "restored_channels": channels,
        "restored_lufs": round(lufs, 2),
        "restored_true_peak_dbtp": round(true_peak, 2),
        "available_formats": list(outputs.keys()),
        "output_paths": {fmt: str(path) for fmt, path in outputs.items()},
    }
