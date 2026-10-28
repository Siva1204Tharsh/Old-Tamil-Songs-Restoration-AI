# 🎵 Old Tamil Songs Restoration AI

> **Restore vintage Tamil music while preserving its original sound.**
>
> Recordings from the 1940s–1990s — removes noise, hiss, hum, and crackle while preserving
> the original melody, vocalist's voice, tempo, pitch, and musical arrangement.

---

## ✨ Features

| Feature | Details |
|---|---|
| **Upload formats** | WAV, MP3, FLAC, M4A, OGG, AIFF |
| **Audio analysis** | SNR, LUFS, true-peak, hum detection, rumble, click density, clipping, frequency bands |
| **Noise reduction** | Spectral hiss reduction, notch hum removal, Butterworth rumble filter, click/crackle interpolation, AI denoising (noisereduce) |
| **Music safety** | Pitch & duration integrity checks — reverts on failure |
| **Clarity** | Conservative shelving EQ only |
| **Loudness** | BS.1770-compatible LUFS normalization with true-peak limiting |
| **Output** | WAV (lossless PCM), FLAC (lossless), MP3 (128–320 kbps) |
| **A/B comparison** | Side-by-side waveform, spectrum, and audio player |
| **CPU compatible** | No GPU required |
| **Optional GPU** | Automatic when PyTorch + CUDA are installed |

---

## 🏗️ Architecture

```
old-tamil-audio-restoration/
├── frontend/                    # Streamlit UI
│   ├── app.py                   # Main application
│   ├── components/
│   │   ├── audio_player.py      # Quality report display
│   │   ├── waveform.py          # Plotly visualizations
│   │   ├── restoration_controls.py  # Settings panel
│   │   └── comparison.py        # A/B comparison + downloads
│   └── services/
│       └── api_client.py        # FastAPI HTTP client
├── backend/
│   └── app/
│       ├── main.py              # FastAPI app entry point
│       ├── api/routes/
│       │   ├── audio.py         # Upload, restore, download endpoints
│       │   ├── jobs.py          # Job status polling
│       │   └── health.py        # Health check
│       ├── core/
│       │   ├── config.py        # All settings (Pydantic)
│       │   └── logging.py       # Structured logging
│       ├── schemas/
│       │   ├── audio.py         # AudioMetadata, AudioAnalysis
│       │   ├── restoration.py   # RestorationSettings
│       │   └── jobs.py          # JobRecord, JobStatus
│       ├── services/
│       │   ├── audio_loader.py         # FFmpeg-backed loader/exporter
│       │   ├── audio_analyzer.py       # Stage 2: quality analysis
│       │   ├── noise_reduction.py      # Stage 3: hiss, hum, rumble, crackle, AI
│       │   ├── music_restoration.py    # Stage 4: pitch/duration checks, Demucs
│       │   ├── audio_enhancement.py    # Stage 5 + 6: clarity EQ + LUFS norm
│       │   ├── export_service.py       # Stage 7: WAV/FLAC/MP3 export
│       │   ├── restoration_pipeline.py # Orchestrator
│       │   └── job_manager.py          # Thread-safe job state
│       └── utils/
│           ├── validation.py    # File/codec validation (ffprobe)
│           └── audio_metrics.py # SNR, LUFS, peak, hum, rumble, clicks
├── storage/
│   ├── uploads/                 # Original uploaded files (by job_id/)
│   ├── processed/               # Restored outputs (by job_id/)
│   └── temporary/               # Scratch space
├── tests/
│   ├── test_audio_upload.py     # Unit tests (metrics, loader, DSP)
│   └── test_api.py              # API integration tests
├── scripts/
│   ├── start_backend.sh         # Launch FastAPI
│   └── start_frontend.sh        # Launch Streamlit
├── venv/                        # Python virtual environment
├── .env.example                 # Environment variable template
└── README.md
```

---

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Check Python (3.10+ required)
python3 --version

# Check FFmpeg (required)
ffmpeg -version
```

If FFmpeg is missing:
```bash
sudo apt-get install ffmpeg          # Ubuntu/Debian
brew install ffmpeg                  # macOS
```

### 2. Set up the virtual environment

```bash
cd /path/to/old-tamil-audio-restoration

# Create venv
python3 -m venv venv
source venv/bin/activate

# Install all dependencies
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

### 3. Configure environment (optional)

```bash
cp .env.example .env
# Edit .env to change defaults if needed
```

### 4. Start the backend

```bash
./scripts/start_backend.sh
# FastAPI: http://127.0.0.1:8000
# API docs: http://127.0.0.1:8000/docs
```

### 5. Start the frontend (new terminal)

```bash
./scripts/start_frontend.sh
# Streamlit: http://127.0.0.1:8501
```

---

## 🎛️ Restoration Pipeline

```
Stage 1: Upload & Validation (ffprobe)
   ↓
Stage 2: Audio Inspection (SNR, LUFS, hum, rumble, clicks, clipping)
   ↓
Stage 3: Noise Reduction
   ├── 3a: Spectral subtraction hiss reduction
   ├── 3b: Butterworth high-pass rumble filter (30 Hz)
   ├── 3c: Notch filter hum removal (50/60 Hz harmonics)
   ├── 3d: Transient interpolation click/crackle removal
   └── 3e: AI broadband denoising (noisereduce)
   ↓
Stage 4: Music Preservation checks
   ├── Pitch integrity verification (autocorrelation)
   ├── Duration verification
   └── [Optional] Demucs source separation
   ↓
Stage 5: Clarity Enhancement (conservative shelving EQ)
   ↓
Stage 6: Loudness Normalization (-16 LUFS default, true-peak limit)
   ↓
Stage 7: Export (WAV + FLAC + MP3)
```

### Conservative defaults
- All strength levels default to **Low**.
- Hum & rumble filters only activate when **detected** in the recording.
- Source separation is **disabled by default** (risky for music).
- Pitch/duration checks **revert** to original audio if integrity fails.

---

## ⚙️ Configuration

All settings are adjustable via `.env` or the Streamlit UI.

| Variable | Default | Description |
|---|---|---|
| `MAX_FILE_SIZE_MB` | 200 | Upload limit |
| `MAX_DURATION_SECONDS` | 1800 | Max audio duration (30 min) |
| `MAX_CONCURRENT_JOBS` | 2 | Concurrent processing limit |
| `DEFAULT_TARGET_LUFS` | -16.0 | Loudness normalization target |
| `DEFAULT_TRUE_PEAK_DBTP` | -1.0 | True-peak ceiling |
| `LOG_LEVEL` | INFO | Logging verbosity |

---

## 🧪 Running Tests

```bash
source venv/bin/activate
cd old-tamil-audio-restoration

# Unit tests (no API server required)
pytest tests/test_audio_upload.py -v

# API integration tests (backend must be running)
pytest tests/test_api.py -v

# All tests
pytest tests/ -v
```

---

## 📦 Optional Dependencies

### GPU acceleration (PyTorch)
```bash
# CPU-only (lighter):
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# With CUDA (if NVIDIA GPU available):
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Source separation (Demucs — 600 MB+ download)
```bash
pip install demucs
# Model downloads automatically on first use (~600 MB)
```
> ⚠️ Source separation is optional and disabled by default. It may introduce
> artifacts in complex musical recordings. Test carefully before use.

### Better LUFS measurement (pyloudnorm)
```bash
pip install pyloudnorm
```
If not installed, an RMS-based approximation is used as fallback.

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/audio/upload` | Upload audio file |
| `GET` | `/api/v1/audio/{job_id}/analysis` | Quality analysis |
| `POST` | `/api/v1/audio/{job_id}/restore` | Start restoration |
| `GET` | `/api/v1/jobs/{job_id}` | Job status + progress |
| `GET` | `/api/v1/audio/{job_id}/result` | Restoration metadata |
| `GET` | `/api/v1/audio/{job_id}/download?format=wav` | Download output |
| `DELETE` | `/api/v1/audio/{job_id}` | Delete job files |
| `GET` | `/api/v1/health/` | API & library health |

Full interactive documentation: **http://127.0.0.1:8000/docs**

---

## ⚠️ Important Notes

- **This tool restores — it does not create.** No generative AI is used to reconstruct music.
- **Stronger denoising = more musical risk.** Always start with Low settings.
- **Source separation is experimental.** Demucs may introduce artifacts.
- **Up-converting sample rate does not restore lost information.** The original sample rate is preserved.
- **Clipped audio cannot be fully restored.** Avoid further amplification if clipping is detected.
- The default -16 LUFS target may not suit every recording — adjust per song.

---

## 🧵 Performance Notes

- Long recordings are processed in **30-second overlapping chunks** with crossfade blending to avoid audible seams.
- AI models are loaded **once per server start**, not per request.
- Maximum **2 concurrent jobs** by default (configurable).
- All processing is **CPU-compatible** — no NVIDIA GPU required.
- GPU acceleration is used automatically if PyTorch + CUDA are installed.

---

## 📜 License

MIT License — see `LICENSE` file.

---

*பழைய தமிழ் இசையை மீட்டெடுப்போம் — Let us restore old Tamil music.*
