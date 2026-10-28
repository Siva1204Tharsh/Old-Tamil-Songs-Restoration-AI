"""
Audio quality analysis display component.
"""
from __future__ import annotations

import streamlit as st
from components.waveform import render_waveform, render_spectrum, render_frequency_band_chart


def render_analysis_report(analysis: dict, metadata: dict,
                            audio_bytes: bytes, filename: str) -> None:
    """Display the full audio quality report."""

    quality_score = analysis.get("quality_score", 0)
    quality_label = analysis.get("quality_label", "Unknown")

    # Quality score header
    score_color = (
        "#00D4AA" if quality_score >= 70
        else "#F59E0B" if quality_score >= 45
        else "#EF4444"
    )

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%);
        border: 1px solid {score_color};
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    ">
        <div style="display: flex; align-items: center; gap: 16px;">
            <div style="
                font-size: 2.5rem;
                font-weight: 800;
                color: {score_color};
                font-family: 'Inter', sans-serif;
            ">{quality_score:.0f}</div>
            <div>
                <div style="color: {score_color}; font-size: 1.1rem; font-weight: 600;">
                    {quality_label} Quality
                </div>
                <div style="color: #A0A0A0; font-size: 0.85rem;">Overall Recording Score (0–100)</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Metadata and measurements
    col1, col2, col3, col4 = st.columns(4)
    dur = metadata.get("duration_seconds", 0)
    mins, secs = divmod(int(dur), 60)

    with col1:
        st.metric("Duration", f"{mins}:{secs:02d}")
        st.metric("Sample Rate", f"{metadata.get('sample_rate', 0):,} Hz")
    with col2:
        st.metric("Channels", "Stereo" if metadata.get("channels", 1) > 1 else "Mono")
        st.metric("Bit Depth", f"{metadata.get('bit_depth', 'N/A')} bit" if metadata.get("bit_depth") else "N/A")
    with col3:
        lufs = analysis.get("integrated_lufs", 0)
        st.metric("Loudness", f"{lufs:.1f} LUFS")
        snr = analysis.get("estimated_snr_db", 0)
        st.metric("Estimated SNR", f"{snr:.1f} dB")
    with col4:
        tp = analysis.get("true_peak_dbtp", 0)
        st.metric("True Peak", f"{tp:.1f} dBTP")
        nf = analysis.get("estimated_noise_floor_db", 0)
        st.metric("Noise Floor", f"{nf:.1f} dB")

    st.markdown("---")

    # Detected issues
    st.markdown("#### 🔍 Detected Issues")
    cols = st.columns(5)
    issues = [
        ("🎙️ Hiss/Noise", analysis.get("estimated_snr_db", 99) < 25),
        ("⚡ Hum", analysis.get("hum_detected", False)),
        ("📻 Rumble", analysis.get("rumble_detected", False)),
        ("💿 Crackle", analysis.get("crackle_detected", False)),
        ("🔴 Clipping", analysis.get("clipping_detected", False)),
    ]
    for col, (label, detected) in zip(cols, issues):
        with col:
            color = "#EF4444" if detected else "#00D4AA"
            icon = "⚠️" if detected else "✅"
            st.markdown(f"""
            <div style="
                background: #1A1A2E;
                border: 1px solid {color};
                border-radius: 8px;
                padding: 10px;
                text-align: center;
                font-size: 0.8rem;
                color: {color};
            ">
                {icon} {label}<br>
                <span style="font-weight: 600;">{"Detected" if detected else "Clear"}</span>
            </div>
            """, unsafe_allow_html=True)

    # Hum details
    if analysis.get("hum_detected") and analysis.get("hum_frequency_hz"):
        st.caption(f"⚡ Hum frequency: ~{analysis['hum_frequency_hz']:.0f} Hz "
                   f"(strength: {analysis.get('hum_strength_db', 0):.1f} dB above noise floor)")

    # Crackle details
    if analysis.get("crackle_detected"):
        cd = analysis.get("estimated_click_density", 0)
        st.caption(f"💿 Click density: ~{cd:.1f} clicks/second")

    # Clipping details
    if analysis.get("clipping_detected"):
        cf = analysis.get("clipping_fraction", 0)
        st.caption(f"🔴 Clipping: {cf*100:.2f}% of samples at or near full scale")

    st.markdown("---")

    # Waveform and spectrum
    st.markdown("#### 📊 Waveform & Spectrum")
    wc1, wc2 = st.columns(2)
    with wc1:
        render_waveform(audio_bytes, filename, "#6C63FF", "Original Waveform", key="analysis_waveform")
    with wc2:
        render_spectrum(audio_bytes, filename, "#F59E0B", "Frequency Spectrum", key="analysis_spectrum")

    # Frequency bands
    bands = analysis.get("frequency_bands", [])
    if bands:
        render_frequency_band_chart(bands, key="analysis_freq_bands")

    # Recommendations
    recs = analysis.get("recommendations", [])
    if recs:
        st.markdown("#### 💡 Recommendations")
        for rec in recs:
            st.markdown(f"- {rec}")
