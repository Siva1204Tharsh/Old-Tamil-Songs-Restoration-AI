"""
Waveform and spectrum visualization components using Plotly.
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


def _load_audio_for_display(audio_bytes: bytes, filename: str) -> tuple[np.ndarray, int] | None:
    """Load audio bytes into a numpy array for visualization."""
    try:
        import subprocess, json, tempfile, os
        with tempfile.NamedTemporaryFile(suffix=f"_{filename}", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        # Probe for metadata
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", tmp_path],
            capture_output=True, text=True, timeout=10
        )
        probe_data = json.loads(probe.stdout)
        audio_streams = [s for s in probe_data.get("streams", []) if s.get("codec_type") == "audio"]
        if not audio_streams:
            return None
        sr = int(audio_streams[0].get("sample_rate", 44100))
        channels = int(audio_streams[0].get("channels", 1))

        # Decode to mono f32le for display (downmix if stereo)
        result = subprocess.run(
            ["ffmpeg", "-v", "quiet", "-i", tmp_path,
             "-ac", "1", "-ar", str(min(sr, 44100)),
             "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"],
            capture_output=True, timeout=60
        )
        os.unlink(tmp_path)
        audio = np.frombuffer(result.stdout, dtype=np.float32)
        return audio, min(sr, 44100)
    except Exception:
        return None


def _get_chart_key(prefix: str, user_key: str | None = None) -> str:
    """Return a unique key for st.plotly_chart."""
    if user_key:
        return user_key
    if "_chart_key_counter" not in st.session_state:
        st.session_state._chart_key_counter = 0
    st.session_state._chart_key_counter += 1
    return f"{prefix}_{st.session_state._chart_key_counter}"


def render_waveform(audio_bytes: bytes, filename: str, color: str = "#6C63FF",
                    title: str = "Waveform", key: str | None = None) -> None:
    """Render an interactive waveform plot."""
    result = _load_audio_for_display(audio_bytes, filename)
    if result is None:
        st.warning("Could not render waveform.")
        return

    audio, sr = result

    # Downsample to max 10000 points for display performance
    max_points = 10000
    if len(audio) > max_points:
        step = len(audio) // max_points
        audio_disp = audio[::step]
    else:
        audio_disp = audio

    times = np.linspace(0, len(audio) / sr, len(audio_disp))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=times, y=audio_disp,
        mode="lines",
        line=dict(color=color, width=0.8),
        name="Amplitude",
        fill="tozeroy",
        fillcolor="rgba(108,99,255,0.15)",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(color="#E0E0E0", size=14)),
        xaxis=dict(title="Time (s)", color="#A0A0A0", gridcolor="#2A2A3E"),
        yaxis=dict(title="Amplitude", color="#A0A0A0", gridcolor="#2A2A3E",
                   range=[-1.05, 1.05]),
        paper_bgcolor="#0E0E1A",
        plot_bgcolor="#0E0E1A",
        margin=dict(l=10, r=10, t=40, b=30),
        height=200,
        showlegend=False,
    )
    chart_key = _get_chart_key("waveform", key)
    st.plotly_chart(fig, use_container_width=True, key=chart_key)


def render_spectrum(audio_bytes: bytes, filename: str, color: str = "#00D4AA",
                    title: str = "Frequency Spectrum", key: str | None = None) -> None:
    """Render a frequency spectrum plot."""
    result = _load_audio_for_display(audio_bytes, filename)
    if result is None:
        return

    audio, sr = result

    # Use a portion for spectrum analysis
    seg = audio[:min(len(audio), sr * 30)]
    fft_size = min(len(seg), 65536)
    window = np.hanning(fft_size)
    spectrum = np.abs(np.fft.rfft(seg[:fft_size] * window))
    freqs = np.fft.rfftfreq(fft_size, d=1.0 / sr)

    # Convert to dB and smooth
    spectrum_db = 20 * np.log10(np.maximum(spectrum, 1e-10))
    # Downsample for display
    max_freq = min(20000, sr // 2)
    mask = freqs <= max_freq
    freqs_disp = freqs[mask]
    spectrum_disp = spectrum_db[mask]

    # Log-scale display — bin into 512 points
    if len(freqs_disp) > 512:
        log_freqs = np.logspace(np.log10(max(freqs_disp[1], 20)), np.log10(max_freq), 512)
        spectrum_interp = np.interp(log_freqs, freqs_disp, spectrum_disp)
        freqs_disp = log_freqs
        spectrum_disp = spectrum_interp

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=freqs_disp, y=spectrum_disp,
        mode="lines",
        line=dict(color=color, width=1.5),
        fill="tozeroy",
        fillcolor="rgba(0,212,170,0.1)",
        name="Spectrum",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(color="#E0E0E0", size=14)),
        xaxis=dict(title="Frequency (Hz)", type="log", color="#A0A0A0",
                   gridcolor="#2A2A3E", range=[np.log10(20), np.log10(max_freq)]),
        yaxis=dict(title="Level (dB)", color="#A0A0A0", gridcolor="#2A2A3E"),
        paper_bgcolor="#0E0E1A",
        plot_bgcolor="#0E0E1A",
        margin=dict(l=10, r=10, t=40, b=30),
        height=200,
        showlegend=False,
    )
    chart_key = _get_chart_key("spectrum", key)
    st.plotly_chart(fig, use_container_width=True, key=chart_key)


def render_comparison_waveforms(original_bytes: bytes, restored_bytes: bytes,
                                 orig_filename: str, rest_filename: str,
                                 key_prefix: str = "compare") -> None:
    """Side-by-side waveform comparison."""
    col1, col2 = st.columns(2)
    with col1:
        render_waveform(original_bytes, orig_filename, "#6C63FF", "Original Waveform",
                        key=f"{key_prefix}_orig_waveform")
    with col2:
        render_waveform(restored_bytes, rest_filename, "#00D4AA", "Restored Waveform",
                        key=f"{key_prefix}_rest_waveform")


def render_frequency_band_chart(bands: list[dict], key: str | None = None) -> None:
    """Render a bar chart of frequency band energies."""
    names = [b["band_name"] for b in bands]
    energies = [max(b["energy_db"], -80) for b in bands]

    fig = go.Figure(go.Bar(
        x=names,
        y=energies,
        marker=dict(
            color=energies,
            colorscale="Viridis",
            showscale=False,
        ),
        text=[f"{e:.0f} dB" for e in energies],
        textposition="auto",
    ))
    fig.update_layout(
        title=dict(text="Frequency Band Energy", font=dict(color="#E0E0E0", size=14)),
        xaxis=dict(color="#A0A0A0"),
        yaxis=dict(title="Energy (dB)", color="#A0A0A0", gridcolor="#2A2A3E"),
        paper_bgcolor="#0E0E1A",
        plot_bgcolor="#0E0E1A",
        margin=dict(l=10, r=10, t=40, b=30),
        height=250,
    )
    chart_key = _get_chart_key("freq_band", key)
    st.plotly_chart(fig, use_container_width=True, key=chart_key)
