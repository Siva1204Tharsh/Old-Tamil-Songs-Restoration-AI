"""
Old Tamil Songs Restoration AI — Streamlit Frontend
Main application entry point.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import streamlit as st

# Add frontend to sys.path so imports work regardless of working directory
_FRONTEND_DIR = Path(__file__).parent
if str(_FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(_FRONTEND_DIR))

# ─────────────────────────────────────────────
# Page configuration (MUST be first st call)
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Old Tamil Songs Restoration AI",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "Old Tamil Songs Restoration AI — Restore vintage Tamil music while preserving its original sound.",
    },
)

# ─────────────────────────────────────────────
# Custom CSS — dark premium theme
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* Root overrides */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: linear-gradient(135deg, #0A0A14 0%, #0E0E1A 50%, #12121F 100%);
    color: #E0E0E0;
}

/* Hide default header/footer */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Hero section */
.hero-container {
    text-align: center;
    padding: 40px 20px 20px;
    background: linear-gradient(180deg, rgba(108,99,255,0.1) 0%, transparent 100%);
    border-radius: 20px;
    margin-bottom: 30px;
    border: 1px solid rgba(108,99,255,0.2);
}

.hero-title {
    font-size: 2.8rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6C63FF 0%, #00D4AA 50%, #F59E0B 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.2;
    margin-bottom: 10px;
}

.hero-subtitle {
    font-size: 1.1rem;
    color: #A0A0B0;
    font-weight: 400;
    margin-bottom: 6px;
}

.hero-tamil {
    font-size: 1.4rem;
    color: #F59E0B;
    font-weight: 600;
    letter-spacing: 0.05em;
}

/* Cards */
.card {
    background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%);
    border: 1px solid rgba(108,99,255,0.25);
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 16px;
    transition: border-color 0.3s ease;
}

.card:hover {
    border-color: rgba(108,99,255,0.5);
}

/* Status badges */
.status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.05em;
}

.badge-queued { background: rgba(245,158,11,0.15); color: #F59E0B; border: 1px solid #F59E0B; }
.badge-processing { background: rgba(108,99,255,0.15); color: #6C63FF; border: 1px solid #6C63FF; }
.badge-completed { background: rgba(0,212,170,0.15); color: #00D4AA; border: 1px solid #00D4AA; }
.badge-failed { background: rgba(239,68,68,0.15); color: #EF4444; border: 1px solid #EF4444; }

/* Progress stages */
.stage-row {
    display: flex;
    align-items: center;
    padding: 8px 0;
    gap: 12px;
    font-size: 0.9rem;
}

.stage-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}

.stage-done { background: #00D4AA; }
.stage-active { background: #6C63FF; animation: pulse 1.5s infinite; }
.stage-pending { background: #3A3A5C; }

@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(1.2); }
}

/* Streamlit component overrides */
.stButton > button {
    background: linear-gradient(135deg, #6C63FF 0%, #4F46E5 100%);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    padding: 0.6rem 1.5rem;
    transition: all 0.3s ease;
    font-family: 'Inter', sans-serif;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #7C73FF 0%, #6057F5 100%);
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(108,99,255,0.4);
}

.stDownloadButton > button {
    background: linear-gradient(135deg, #00D4AA 0%, #00A388 100%) !important;
    color: #0A0A14 !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
}

.stSelectbox > div > div {
    background: #1A1A2E;
    border: 1px solid rgba(108,99,255,0.3);
    border-radius: 8px;
    color: #E0E0E0;
}

.stSlider > div > div > div > div {
    background: #6C63FF;
}

.stCheckbox > label {
    color: #E0E0E0;
}

/* File uploader */
.stFileUploader > div {
    background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%);
    border: 2px dashed rgba(108,99,255,0.4);
    border-radius: 14px;
    transition: border-color 0.3s ease;
}

.stFileUploader > div:hover {
    border-color: rgba(108,99,255,0.8);
}

/* Metrics */
[data-testid="metric-container"] {
    background: #1A1A2E;
    border: 1px solid rgba(108,99,255,0.2);
    border-radius: 10px;
    padding: 12px;
}

[data-testid="stMetricLabel"] { color: #A0A0B0 !important; font-size: 0.8rem !important; }
[data-testid="stMetricValue"] { color: #E0E0E0 !important; font-weight: 700 !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0E0E1A 0%, #12121F 100%);
    border-right: 1px solid rgba(108,99,255,0.2);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #1A1A2E;
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
}

.stTabs [data-baseweb="tab"] {
    color: #A0A0B0;
    border-radius: 8px;
    font-weight: 500;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #6C63FF 0%, #4F46E5 100%) !important;
    color: white !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: #1A1A2E !important;
    border: 1px solid rgba(108,99,255,0.2) !important;
    border-radius: 8px !important;
    color: #E0E0E0 !important;
}

/* Info/warning/success boxes */
.stAlert {
    border-radius: 10px;
}

/* Progress bar */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #6C63FF 0%, #00D4AA 100%);
}

/* Horizontal separator */
hr {
    border: none;
    border-top: 1px solid rgba(108,99,255,0.15);
    margin: 20px 0;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Session state initialization
# ─────────────────────────────────────────────
def init_session_state():
    defaults = {
        "job_id": None,
        "upload_meta": None,
        "analysis": None,
        "analysis_metadata": None,
        "original_bytes": None,
        "original_filename": None,
        "restored_bytes": None,
        "job_status": None,
        "result_meta": None,
        "processing_complete": False,
        "backend_online": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # Reset chart key counter for each script rerun
    st.session_state._chart_key_counter = 0


init_session_state()


# ─────────────────────────────────────────────
# Import services (after path setup)
# ─────────────────────────────────────────────
from services.api_client import (
    upload_audio, get_analysis, start_restoration,
    get_job_status, get_result, download_audio, get_health,
)
from components.audio_player import render_analysis_report
from components.restoration_controls import render_restoration_controls
from components.comparison import render_comparison
from components.waveform import render_waveform


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 10px 0 20px;">
        <span style="font-size: 2.5rem;">🎵</span>
        <div style="color: #6C63FF; font-weight: 700; font-size: 1.1rem; margin-top: 6px;">Tamil Music</div>
        <div style="color: #A0A0B0; font-size: 0.8rem;">Restoration AI</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Backend health check
    if st.button("🔄 Check Backend Status", use_container_width=True):
        try:
            health = get_health()
            st.session_state.backend_online = True
            st.success("✅ Backend is online")
            with st.expander("Library Status", expanded=True):
                libs = health.get("libraries", {})
                for lib, info in libs.items():
                    avail = info.get("available", False)
                    icon = "✅" if avail else "❌"
                    ver = info.get("version")
                    ver_str = f" `v{ver}`" if ver else ""
                    dev = info.get("device")
                    dev_str = f" ({dev.upper()})" if dev else ""
                    st.markdown(f"{icon} **{lib}**{ver_str}{dev_str}")
        except Exception as e:
            st.session_state.backend_online = False
            st.error(f"❌ Backend offline: {e}")

    if st.session_state.backend_online is True:
        st.markdown('<span class="status-badge badge-completed">Backend Online</span>',
                    unsafe_allow_html=True)
    elif st.session_state.backend_online is False:
        st.markdown('<span class="status-badge badge-failed">Backend Offline</span>',
                    unsafe_allow_html=True)
        st.markdown("""
        **Start the backend:**
        ```
        ./scripts/start_backend.sh
        ```
        """)

    st.markdown("---")

    # Navigation info
    st.markdown("""
    **Workflow:**
    1. 📁 Upload your song
    2. 🔍 Review quality analysis
    3. ⚙️ Set restoration options
    4. 🚀 Start restoration
    5. 🎧 Compare & download

    **Supported formats:**
    WAV · MP3 · FLAC · M4A · OGG · AIFF
    """)

    st.markdown("---")

    # Reset session
    if st.button("🗑️ Start Over (New Song)", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key not in ("backend_online",):
                del st.session_state[key]
        st.rerun()

    st.markdown("""
    <div style="text-align: center; color: #3A3A5C; font-size: 0.75rem; margin-top: 20px;">
        Old Tamil Songs Restoration AI<br>
        v1.0.0 · CPU-compatible
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Hero Header
# ─────────────────────────────────────────────
st.markdown("""
<div class="hero-container">
    <div class="hero-title">🎵 Old Tamil Songs Restoration AI</div>
    <div class="hero-subtitle">Restore vintage Tamil music while preserving its original sound</div>
    <div class="hero-tamil">பழைய தமிழ் இசையை மீட்டெடுப்போம்</div>
    <div style="color: #6A6A8A; font-size: 0.8rem; margin-top: 8px;">
        Recordings from the 1940s–1990s · Preserves melody, tempo, pitch & musical identity
    </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Section 1: Upload
# ─────────────────────────────────────────────
st.markdown("## 📁 Upload Your Song")

uploaded_file = st.file_uploader(
    "Drag and drop an audio file, or click to browse",
    type=["wav", "mp3", "flac", "m4a", "ogg", "aiff", "aif"],
    key="audio_upload",
    help="Maximum 200 MB · Maximum 30 minutes · WAV, MP3, FLAC, M4A, OGG, AIFF supported",
)

if uploaded_file and (
    st.session_state.original_filename != uploaded_file.name
    or st.session_state.original_bytes is None
):
    # New file uploaded — reset downstream state
    st.session_state.update({
        "job_id": None, "upload_meta": None, "analysis": None,
        "analysis_metadata": None, "restored_bytes": None,
        "job_status": None, "result_meta": None, "processing_complete": False,
        "original_filename": uploaded_file.name,
        "original_bytes": uploaded_file.read(),
    })

    with st.spinner("📤 Uploading and validating..."):
        try:
            resp = upload_audio(st.session_state.original_bytes, uploaded_file.name)
            st.session_state.job_id = resp["job_id"]
            st.session_state.upload_meta = resp
            st.success(f"✅ **{uploaded_file.name}** uploaded successfully!")
        except Exception as e:
            st.error(f"❌ Upload failed: {e}")
            st.stop()

if st.session_state.upload_meta:
    meta = st.session_state.upload_meta
    m1, m2, m3, m4 = st.columns(4)
    dur = meta.get("duration_seconds", 0)
    mins, secs = divmod(int(dur), 60)
    with m1:
        st.metric("Duration", f"{mins}:{secs:02d}")
    with m2:
        st.metric("Sample Rate", f"{meta.get('sample_rate', 0):,} Hz")
    with m3:
        st.metric("Channels", "Stereo" if meta.get("channels", 1) > 1 else "Mono")
    with m4:
        sz = meta.get("file_size_bytes", 0)
        st.metric("File Size", f"{sz/1024/1024:.1f} MB")

    st.markdown("**🎧 Original Audio Player**")
    st.audio(st.session_state.original_bytes,
             format=f"audio/{uploaded_file.name.rsplit('.', 1)[-1].lower()}"
             if uploaded_file else "audio/wav")


# ─────────────────────────────────────────────
# Section 2: Audio Analysis
# ─────────────────────────────────────────────
if st.session_state.job_id and not st.session_state.analysis:
    st.markdown("---")
    st.markdown("## 🔍 Audio Quality Analysis")

    if st.button("🔍 Analyse Recording Quality", key="btn_analyse",
                 use_container_width=False):
        with st.spinner("🔬 Analysing audio quality... (this may take 10–30 seconds)"):
            try:
                report = get_analysis(st.session_state.job_id)
                st.session_state.analysis = report.get("analysis", {})
                st.session_state.analysis_metadata = report.get("metadata", {})
                st.rerun()
            except Exception as e:
                st.error(f"❌ Analysis failed: {e}")

if st.session_state.analysis:
    st.markdown("---")
    st.markdown("## 🔍 Audio Quality Report")
    render_analysis_report(
        analysis=st.session_state.analysis,
        metadata=st.session_state.analysis_metadata or {},
        audio_bytes=st.session_state.original_bytes,
        filename=st.session_state.original_filename or "audio.wav",
    )


# ─────────────────────────────────────────────
# Section 3: Restoration Settings + Process
# ─────────────────────────────────────────────
if st.session_state.job_id and not st.session_state.processing_complete:
    st.markdown("---")
    rest_settings = render_restoration_controls()

    st.markdown("---")
    st.markdown("## 🚀 Start Restoration")

    if not st.session_state.analysis:
        st.info("💡 Tip: Run the audio analysis above before restoring for best results.")

    col_btn, col_warn = st.columns([1, 2])
    with col_btn:
        start_btn = st.button("🎵 Restore Song", key="btn_restore",
                              use_container_width=True)
    with col_warn:
        if rest_settings.get("noise_reduction_strength") == "high":
            st.warning("⚠️ High noise reduction may remove musical details. Consider 'Low' first.")

    if start_btn:
        with st.spinner("🚀 Starting restoration job..."):
            try:
                resp = start_restoration(st.session_state.job_id, rest_settings)
                st.session_state.job_status = "processing"
                st.success("✅ Restoration started! Monitoring progress...")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to start restoration: {e}")


# ─────────────────────────────────────────────
# Section 4: Progress Monitoring
# ─────────────────────────────────────────────
if st.session_state.job_id and st.session_state.job_status == "processing" and not st.session_state.processing_complete:
    st.markdown("---")
    st.markdown("## ⚙️ Processing Progress")

    progress_placeholder = st.empty()
    stage_placeholder = st.empty()

    # Poll until done
    max_polls = 900  # 30 min at 2s intervals
    for poll_n in range(max_polls):
        try:
            status_data = get_job_status(st.session_state.job_id)
        except Exception as e:
            st.error(f"Could not fetch job status: {e}")
            break

        job_status = status_data.get("status", "unknown")
        overall_pct = status_data.get("overall_progress", 0)
        current_stage = status_data.get("current_stage", "")
        stages = status_data.get("stages", [])

        with progress_placeholder.container():
            status_emoji = {"queued": "⏳", "processing": "⚙️", "completed": "✅", "failed": "❌"}.get(job_status, "🔄")
            st.markdown(f"**Status: {status_emoji} {job_status.title()}** — {overall_pct:.0f}% complete")
            st.progress(overall_pct / 100.0)

        with stage_placeholder.container():
            if stages:
                for stage in stages:
                    pct = stage.get("progress_pct", 0)
                    label = stage.get("label", "")
                    msg = stage.get("msg", "") or stage.get("message", "")
                    is_done = stage.get("completed_at") is not None
                    icon = "✅" if is_done else ("⚙️" if pct > 0 else "⏳")
                    st.markdown(f"{icon} **{label}** — {pct:.0f}% {f'({msg})' if msg else ''}")

        if job_status == "completed":
            st.session_state.processing_complete = True
            st.session_state.job_status = "completed"
            # Fetch result
            try:
                result = get_result(st.session_state.job_id)
                st.session_state.result_meta = result.get("result_metadata", {})
            except Exception:
                pass
            # Download WAV for in-browser comparison
            try:
                st.session_state.restored_bytes = download_audio(st.session_state.job_id, "wav")
            except Exception:
                pass
            st.rerun()
            break

        elif job_status == "failed":
            err = status_data.get("error_message", "Unknown error")
            st.error(f"❌ Restoration failed: {err}")
            st.info("Please adjust settings and try again, or contact support.")
            st.session_state.job_status = "failed"
            break

        time.sleep(2)
        if poll_n % 15 == 14:
            st.rerun()


# ─────────────────────────────────────────────
# Section 5: Results & Comparison
# ─────────────────────────────────────────────
if st.session_state.processing_complete and st.session_state.restored_bytes:
    st.markdown("---")
    render_comparison(
        original_bytes=st.session_state.original_bytes,
        restored_bytes=st.session_state.restored_bytes,
        orig_filename=st.session_state.original_filename or "original.wav",
        job_id=st.session_state.job_id,
        result_meta=st.session_state.result_meta or {},
        analysis=st.session_state.analysis or {},
    )
