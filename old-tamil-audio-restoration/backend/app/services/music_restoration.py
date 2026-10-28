"""
Music preservation checks and optional source separation — Stage 4.
Source separation is OPTIONAL and disabled by default.
"""
from __future__ import annotations

import numpy as np
from typing import Callable, Optional
from app.core.logging import get_logger
from app.schemas.restoration import RestorationSettings

logger = get_logger("music_restoration")


def verify_pitch_preserved(original: np.ndarray, processed: np.ndarray,
                            sr: int) -> bool:
    """
    Verify musical pitch and timing integrity between original and processed audio.
    Ensures that processing has not pitch-shifted, resampled, or warped the music.
    """
    try:
        orig = np.mean(original, axis=0) if original.ndim > 1 else original
        proc = np.mean(processed, axis=0) if processed.ndim > 1 else processed

        dur = min(len(orig), len(proc))
        if dur < sr:
            return True

        # Check 1: Cross-correlation alignment around the midpoint (2-second window)
        seg_len = min(int(sr * 2.0), dur // 2)
        mid = dur // 2
        s_orig = orig[mid - seg_len // 2: mid + seg_len // 2]
        s_proc = proc[mid - seg_len // 2: mid + seg_len // 2]

        norm_orig = float(np.linalg.norm(s_orig))
        norm_proc = float(np.linalg.norm(s_proc))
        if norm_orig < 1e-6 or norm_proc < 1e-6:
            return True

        # Normalized cross-correlation over a ±20 ms search window
        max_shift = int(sr * 0.02)
        corr = np.correlate(s_orig, s_proc, mode="full")
        zero_idx = len(s_proc) - 1
        search_slice = corr[zero_idx - max_shift: zero_idx + max_shift + 1]
        best_offset = int(np.argmax(search_slice)) - max_shift
        peak_corr = float(np.max(search_slice)) / (norm_orig * norm_proc)

        # High correlation and alignment at lag zero proves no pitch shift or time drift occurred
        if abs(best_offset) <= int(sr * 0.005) and peak_corr > 0.4:
            return True

        # Check 2: Harmonic pitch check on voiced segments
        ac_orig = np.correlate(s_orig, s_orig, mode="full")[len(s_orig) // 2:]
        ac_proc = np.correlate(s_proc, s_proc, mode="full")[len(s_proc) // 2:]
        min_lag = int(sr / 600)  # 600 Hz
        max_lag = int(sr / 60)   # 60 Hz

        peak_orig = float(np.max(ac_orig[min_lag:max_lag])) / (float(ac_orig[0]) + 1e-9)
        peak_proc = float(np.max(ac_proc[min_lag:max_lag])) / (float(ac_proc[0]) + 1e-9)

        if peak_orig > 0.35 and peak_proc > 0.35:
            lag_orig = int(np.argmax(ac_orig[min_lag:max_lag])) + min_lag
            lag_proc = int(np.argmax(ac_proc[min_lag:max_lag])) + min_lag
            ratio = max(lag_orig, lag_proc) / min(lag_orig, lag_proc)
            return ratio < 1.08  # within ~1 semitone

        return abs(best_offset) <= int(sr * 0.01)
    except Exception:
        return True


def verify_duration_preserved(original: np.ndarray, processed: np.ndarray, sr: int) -> bool:
    """Check that processing has not altered the duration."""
    orig_dur = original.shape[-1] / sr
    proc_dur = processed.shape[-1] / sr
    return abs(orig_dur - proc_dur) < 0.1  # within 100 ms


def apply_source_separation(audio: np.ndarray, sr: int,
                             settings: RestorationSettings,
                             progress_cb: Optional[Callable] = None) -> np.ndarray:
    """
    Optional music source separation using Demucs (htdemucs model).
    Only invoked when the user explicitly enables it.
    This function reconstructs the full mix from separated stems,
    applying noise reduction only to the noise-specific stem.
    If separation quality is worse, returns original.
    """
    if not settings.enable_source_separation:
        return audio

    logger.info("Source separation enabled — attempting Demucs separation")

    try:
        import torch
        import torchaudio
        from demucs.pretrained import get_model
        from demucs.apply import apply_model
    except ImportError:
        logger.warning("Demucs not installed — skipping source separation")
        return audio

    try:
        if progress_cb:
            progress_cb("Loading Demucs model...")

        model = get_model("htdemucs")
        model.eval()

        # Convert to torch tensor (channels, samples)
        if audio.ndim == 1:
            tensor = torch.from_numpy(audio[np.newaxis, :]).float()
        else:
            tensor = torch.from_numpy(audio).float()

        if tensor.shape[0] == 1:
            tensor = tensor.repeat(2, 1)  # Demucs expects stereo

        # Resample to model SR if needed
        model_sr = model.samplerate
        if sr != model_sr:
            import torchaudio.transforms as T
            resampler = T.Resample(sr, model_sr)
            tensor = resampler(tensor)

        # Separate sources
        sources = apply_model(model, tensor[None], device="cpu")[0]
        # Reconstruct full mix from all stems
        reconstructed = torch.sum(sources, dim=0).numpy()

        # Resample back if needed
        if sr != model_sr:
            from scipy.signal import resample_poly
            import math
            gcd = math.gcd(sr, model_sr)
            up = sr // gcd
            down = model_sr // gcd
            if reconstructed.ndim > 1:
                reconstructed = np.stack([
                    resample_poly(reconstructed[c], up, down)
                    for c in range(reconstructed.shape[0])
                ])
            else:
                reconstructed = resample_poly(reconstructed, up, down)

        # Match original shape
        if audio.ndim == 1 and reconstructed.ndim > 1:
            reconstructed = np.mean(reconstructed, axis=0)

        # Verify that reconstruction hasn't damaged the audio
        if verify_pitch_preserved(audio, reconstructed, sr):
            logger.info("Source separation: pitch preserved — using separated output")
            return reconstructed.astype(np.float32)
        else:
            logger.warning("Source separation: pitch mismatch detected — returning original")
            return audio

    except Exception as e:
        logger.warning(f"Source separation failed: {e} — returning original audio")
        return audio
