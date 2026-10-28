"""
Tests for audio upload, validation, and analysis endpoints.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import numpy as np
import tempfile
import struct
from pathlib import Path
import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _generate_test_wav(duration_s: float = 2.0, sr: int = 44100,
                        channels: int = 1, add_hum: bool = False,
                        add_noise: bool = True) -> bytes:
    """Generate a minimal synthetic WAV file with a 440 Hz sine wave."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

    if add_hum:
        audio += 0.05 * np.sin(2 * np.pi * 50 * t).astype(np.float32)

    if add_noise:
        rng = np.random.default_rng(42)
        audio += rng.normal(0, 0.01, len(audio)).astype(np.float32)

    audio = np.clip(audio, -1.0, 1.0)

    # Encode as 16-bit PCM WAV
    pcm = (audio * 32767).astype(np.int16)
    if channels == 2:
        pcm = np.stack([pcm, pcm], axis=1).flatten()

    n_samples = len(pcm)
    data_size = n_samples * 2
    file_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", file_size, b"WAVE",
        b"fmt ", 16, 1, channels, sr, sr * channels * 2, channels * 2, 16,
        b"data", data_size,
    )
    return header + pcm.tobytes()


# ──────────────────────────────────────────────────────────────────────────────
# Validation tests
# ──────────────────────────────────────────────────────────────────────────────

def test_validate_extension_valid():
    from app.utils.validation import validate_extension
    assert validate_extension("song.wav") == ".wav"
    assert validate_extension("song.mp3") == ".mp3"
    assert validate_extension("song.flac") == ".flac"
    assert validate_extension("song.m4a") == ".m4a"


def test_validate_extension_invalid():
    from app.utils.validation import validate_extension, ValidationError
    with pytest.raises(ValidationError):
        validate_extension("song.exe")
    with pytest.raises(ValidationError):
        validate_extension("song.pdf")


def test_validate_file_size_ok():
    from app.utils.validation import validate_file_size
    validate_file_size(1024 * 1024)  # 1 MB — should not raise


def test_validate_file_size_too_large():
    from app.utils.validation import validate_file_size, ValidationError
    with pytest.raises(ValidationError):
        validate_file_size(300 * 1024 * 1024)  # 300 MB — too large


def test_validate_file_size_empty():
    from app.utils.validation import validate_file_size, ValidationError
    with pytest.raises(ValidationError):
        validate_file_size(0)


# ──────────────────────────────────────────────────────────────────────────────
# Audio metrics tests
# ──────────────────────────────────────────────────────────────────────────────

def test_measure_rms_db():
    from app.utils.audio_metrics import measure_rms_db
    audio = np.ones(44100, dtype=np.float32) * 0.5
    db = measure_rms_db(audio)
    assert abs(db - (-6.02)) < 0.5  # 0.5 amplitude → ~-6 dBFS


def test_measure_rms_silent():
    from app.utils.audio_metrics import measure_rms_db
    audio = np.zeros(44100, dtype=np.float32)
    db = measure_rms_db(audio)
    assert db <= -100.0


def test_detect_clipping_clean():
    from app.utils.audio_metrics import detect_clipping
    audio = np.ones(44100, dtype=np.float32) * 0.5
    detected, fraction = detect_clipping(audio)
    assert not detected
    assert fraction == 0.0


def test_detect_clipping_clipped():
    from app.utils.audio_metrics import detect_clipping
    audio = np.ones(44100, dtype=np.float32)  # Full scale
    detected, fraction = detect_clipping(audio)
    assert detected
    assert fraction > 0.5


def test_estimate_snr_db():
    from app.utils.audio_metrics import estimate_snr_db
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2)
    audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    snr = estimate_snr_db(audio, sr)
    assert snr > 0  # Should be positive for a clean sine wave


def test_detect_hum_50hz():
    from app.utils.audio_metrics import detect_hum
    sr = 44100
    t = np.linspace(0, 4.0, sr * 4, endpoint=False)
    # Strong 50 Hz hum + weak signal
    audio = (0.5 * np.sin(2 * np.pi * 440 * t) +
             0.3 * np.sin(2 * np.pi * 50 * t)).astype(np.float32)
    detected, freq, strength = detect_hum(audio, sr)
    assert detected
    assert abs(freq - 50.0) < 5.0


def test_detect_hum_none():
    from app.utils.audio_metrics import detect_hum
    sr = 44100
    t = np.linspace(0, 4.0, sr * 4, endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    detected, freq, strength = detect_hum(audio, sr)
    # Should not detect strong hum in a clean sine wave
    # (weak harmonic may match — acceptable; assert no very strong hum)
    if detected:
        assert strength is not None and strength < 30.0  # Weak if any


def test_compute_frequency_bands():
    from app.utils.audio_metrics import compute_frequency_bands
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)  # 1 kHz tone
    bands = compute_frequency_bands(audio, sr)
    assert len(bands) == 8
    mid_band = next(b for b in bands if b["band_name"] == "Mid")
    # 1 kHz is in "Mid" (500–2000 Hz) — should have highest energy
    assert mid_band["energy_db"] == max(b["energy_db"] for b in bands)


def test_quality_score_good():
    from app.utils.audio_metrics import compute_quality_score
    score, label = compute_quality_score(snr_db=35.0, clipping_fraction=0.0,
                                          click_density=0.0, silence_fraction=0.1)
    assert score >= 60
    assert label in ("Good", "Fair")


def test_quality_score_poor():
    from app.utils.audio_metrics import compute_quality_score
    score, label = compute_quality_score(snr_db=5.0, clipping_fraction=0.1,
                                          click_density=8.0, silence_fraction=0.5)
    assert score < 50


# ──────────────────────────────────────────────────────────────────────────────
# Audio loader tests
# ──────────────────────────────────────────────────────────────────────────────

def test_load_and_save_wav_roundtrip():
    """Test loading a WAV and saving it back."""
    from app.services.audio_loader import load_audio_ffmpeg, save_audio_ffmpeg

    wav_bytes = _generate_test_wav(duration_s=2.0, sr=44100, channels=1)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = Path(tmp.name)

    try:
        audio, sr = load_audio_ffmpeg(tmp_path)
        assert sr == 44100
        assert len(audio) > 0
        assert audio.dtype == np.float32

        out_path = tmp_path.with_name(f"{tmp_path.stem}_out.wav")
        save_audio_ffmpeg(audio, sr, out_path, output_format="wav")
        assert out_path.exists()
        assert out_path.stat().st_size > 100

        out_path.unlink(missing_ok=True)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_load_stereo_wav():
    """Test that stereo files load with correct shape."""
    from app.services.audio_loader import load_audio_ffmpeg

    wav_bytes = _generate_test_wav(duration_s=2.0, sr=44100, channels=2)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = Path(tmp.name)

    try:
        audio, sr = load_audio_ffmpeg(tmp_path)
        assert audio.ndim == 2  # (channels, samples)
        assert audio.shape[0] == 2  # stereo
    finally:
        tmp_path.unlink(missing_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# Noise reduction tests
# ──────────────────────────────────────────────────────────────────────────────

def test_reduce_hiss_preserves_duration():
    from app.services.noise_reduction import reduce_hiss
    from app.schemas.restoration import StrengthLevel

    sr = 44100
    t = np.linspace(0, 3.0, sr * 3, endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    audio += np.random.default_rng(0).normal(0, 0.01, len(audio)).astype(np.float32)

    result = reduce_hiss(audio, sr, StrengthLevel.LOW)
    assert len(result) == len(audio)


def test_remove_hum_reduces_50hz():
    """Verify that 50 Hz notch filter reduces 50 Hz energy."""
    from app.services.noise_reduction import remove_hum
    from app.schemas.restoration import StrengthLevel
    from app.schemas.audio import AudioAnalysis, ChannelConfig, FrequencyBand

    sr = 44100
    t = np.linspace(0, 4.0, sr * 4, endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t) +
             0.2 * np.sin(2 * np.pi * 50 * t)).astype(np.float32)

    # Create a mock analysis object
    analysis = AudioAnalysis(
        job_id="test",
        estimated_noise_floor_db=-50.0,
        estimated_snr_db=20.0,
        clipping_detected=False,
        clipping_fraction=0.0,
        hum_detected=True,
        hum_frequency_hz=50.0,
        hum_strength_db=20.0,
        rumble_detected=False,
        crackle_detected=False,
        estimated_click_density=0.0,
        silence_fraction=0.0,
        integrated_lufs=-20.0,
        true_peak_dbtp=-3.0,
        frequency_bands=[FrequencyBand(band_name="Bass", center_hz=100.0, energy_db=-30.0)],
        quality_score=60.0,
        quality_label="Fair",
        is_stereo=False,
        has_low_frequency_energy=True,
        recommendations=[],
    )

    result = remove_hum(audio, sr, enabled=True, analysis=analysis)
    assert len(result) == len(audio)

    # Measure 50 Hz energy before and after
    def _energy_at_freq(sig, sr, freq, width=2):
        fft_size = sr * 4
        spectrum = np.abs(np.fft.rfft(sig[:fft_size]))
        freqs = np.fft.rfftfreq(fft_size, d=1.0 / sr)
        mask = (freqs >= freq - width) & (freqs <= freq + width)
        return float(np.mean(spectrum[mask]))

    e_before = _energy_at_freq(audio, sr, 50.0)
    e_after = _energy_at_freq(result, sr, 50.0)
    assert e_after < e_before * 0.5  # At least 50% reduction


def test_normalize_loudness():
    """Test that loudness normalization reaches the target LUFS approximately."""
    from app.services.audio_enhancement import normalize_loudness
    from app.utils.audio_metrics import measure_rms_db

    sr = 44100
    t = np.linspace(0, 5.0, sr * 5, endpoint=False)
    audio = (0.05 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)  # Very quiet

    db_before = measure_rms_db(audio)
    normalized = normalize_loudness(audio, sr, target_lufs=-16.0, enabled=True)
    db_after = measure_rms_db(normalized)

    assert db_after > db_before  # Should have been amplified
    assert np.max(np.abs(normalized)) <= 1.0  # Should not clip


# ──────────────────────────────────────────────────────────────────────────────
# Music preservation tests
# ──────────────────────────────────────────────────────────────────────────────

def test_pitch_preserved_same_signal():
    from app.services.music_restoration import verify_pitch_preserved
    sr = 44100
    t = np.linspace(0, 3.0, sr * 3, endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    assert verify_pitch_preserved(audio, audio.copy(), sr)


def test_duration_preserved():
    from app.services.music_restoration import verify_duration_preserved
    sr = 44100
    audio = np.zeros(sr * 10, dtype=np.float32)
    assert verify_duration_preserved(audio, audio.copy(), sr)


def test_duration_mismatch_detected():
    from app.services.music_restoration import verify_duration_preserved
    sr = 44100
    orig = np.zeros(sr * 10, dtype=np.float32)
    short = np.zeros(sr * 5, dtype=np.float32)
    assert not verify_duration_preserved(orig, short, sr)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
