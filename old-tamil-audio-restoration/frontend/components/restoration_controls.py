    """
Restoration settings control panel component.
"""
from __future__ import annotations

import streamlit as st


PRESETS = {
    "📼 1970s–1980s Cassette Tape (Recommended)": {
        "noise_reduction_strength": "medium",
        "hiss_reduction": "medium",
        "crackle_reduction": "low",
        "hum_removal": True,
        "rumble_reduction": True,
        "clarity_enhancement": "medium",
        "target_lufs": -16.0,
        "true_peak_dbtp": -1.0,
        "enable_loudness_normalization": True,
    },
    "📻 1950s–1960s Gramophone / 78 RPM (Heavy Noise & Crackle)": {
        "noise_reduction_strength": "medium",
        "hiss_reduction": "high",
        "crackle_reduction": "medium",
        "hum_removal": True,
        "rumble_reduction": True,
        "clarity_enhancement": "high",
        "target_lufs": -16.0,
        "true_peak_dbtp": -1.0,
        "enable_loudness_normalization": True,
    },
    "🎚️ 1980s–1990s Studio / Early Digital (Gentle Polish)": {
        "noise_reduction_strength": "low",
        "hiss_reduction": "low",
        "crackle_reduction": "off",
        "hum_removal": True,
        "rumble_reduction": True,
        "clarity_enhancement": "medium",
        "target_lufs": -15.0,
        "true_peak_dbtp": -1.0,
        "enable_loudness_normalization": True,
    },
    "⚙️ Custom / Manual Adjustments": None,
}


def _on_preset_change():
    chosen = st.session_state.get("selected_preset")
    if chosen and chosen in PRESETS and PRESETS[chosen] is not None:
        for k, v in PRESETS[chosen].items():
            st.session_state[k] = v


def render_restoration_controls() -> dict:
    """
    Render all restoration control widgets and return a settings dict
    suitable for the RestorationSettings API schema.
    """
    st.markdown("### ⚙️ Restoration Settings")

    # ── Era Presets ──────────────────────────────────────────────
    st.markdown("#### 🎯 Quick Era Presets")
    st.caption("Select a preset tuned for your recording era, or fine-tune manually below.")

    if "selected_preset" not in st.session_state:
        st.session_state.selected_preset = "📼 1970s–1980s Cassette Tape (Recommended)"
        _on_preset_change()

    st.selectbox(
        "Select Audio Preset",
        list(PRESETS.keys()),
        key="selected_preset",
        on_change=_on_preset_change,
        help="Presets automatically configure noise reduction, crackle, hum, rumble, and clarity.",
    )

    with st.expander("💡 **Restoration Guide & Suggestions**", expanded=False):
        st.markdown("""
        - **1950s–1960s Gramophone**: Uses higher hiss reduction, click/crackle interpolation, and high vocal presence EQ to un-muffle shellac recordings.
        - **1970s–1980s Cassette**: Balanced AI denoising, 50 Hz hum notch, and warmth enhancement for analog cassette tapes.
        - **Clarity Enhancement**: Applies targeted 3.5 kHz vocal presence lift and 400 Hz boxiness cleanup.
        - **Need more reduction?** Increase *Overall Noise Reduction* to **High** or *Hiss Reduction* to **High**.
        """)

    st.markdown("---")

    # ── Bypass mode ──────────────────────────────────────────────
    bypass = st.checkbox(
        "🔄 Bypass mode — return original decoded audio without restoration",
        value=False,
        key="bypass_restoration",
        help="Useful for testing the pipeline without any processing.",
    )

    if bypass:
        st.info("Bypass mode: the original audio will be decoded and exported without any restoration.")
        return _collect_settings(bypass=True)

    st.markdown("#### 🔊 Noise Reduction")

    col1, col2 = st.columns(2)

    with col1:
        noise_strength = st.selectbox(
            "Overall Noise Reduction",
            ["off", "low", "medium", "high"],
            index=2,
            key="noise_reduction_strength",
            help="AI-based broadband denoising (noisereduce). Medium is optimal for most vintage music.",
        )

        hiss = st.selectbox(
            "Hiss Reduction",
            ["off", "low", "medium", "high"],
            index=2,
            key="hiss_reduction",
            help="Reduces tape hiss and background noise using spectral subtraction.",
        )

        crackle = st.selectbox(
            "Crackle / Click Reduction",
            ["off", "low", "medium", "high"],
            index=1,
            key="crackle_reduction",
            help="Reduces vinyl crackle and random clicks using transient detection and interpolation.",
        )

    with col2:
        hum_removal = st.checkbox(
            "🔇 Hum Removal (50/60 Hz)",
            value=True,
            key="hum_removal",
            help="Removes electrical hum (50/60 Hz mains) using sharp notch filters.",
        )

        rumble_reduction = st.checkbox(
            "🔇 Rumble Reduction (<35 Hz)",
            value=True,
            key="rumble_reduction",
            help="Removes sub-bass turntable rumble and mic thumps while preserving percussion.",
        )

        source_sep = st.checkbox(
            "🎼 Source Separation (Optional)",
            value=False,
            key="enable_source_separation",
            help="⚠️ Experimental: Uses Demucs to separate vocals and instruments. "
                 "May introduce artifacts. Requires Demucs to be installed.",
        )
        if source_sep:
            st.warning("⚠️ Source separation may introduce artifacts. "
                       "Use only if Demucs is installed and you accept the risk.")

    st.markdown("#### ✨ Clarity & Loudness")

    col3, col4 = st.columns(2)

    with col3:
        clarity = st.selectbox(
            "Clarity Enhancement",
            ["off", "low", "medium", "high"],
            index=1,
            key="clarity_enhancement",
            help="Gentle EQ boost above 8 kHz and subtle mid reduction. "
                 "Preserves natural warmth.",
        )

    with col4:
        norm_enabled = st.checkbox(
            "Loudness Normalization",
            value=True,
            key="enable_loudness_normalization",
            help="Normalizes integrated loudness to the target LUFS with true-peak limiting.",
        )

    if norm_enabled:
        target_lufs = st.slider(
            "Target Loudness (LUFS)",
            min_value=-30.0,
            max_value=-9.0,
            value=-16.0,
            step=0.5,
            key="target_lufs",
            help="-16 LUFS is a good starting point. Use -14 for streaming services.",
        )
        true_peak = st.slider(
            "True-Peak Limit (dBTP)",
            min_value=-6.0,
            max_value=-0.1,
            value=-1.0,
            step=0.1,
            key="true_peak_dbtp",
            help="Maximum allowable inter-sample peak level.",
        )
    else:
        target_lufs = -16.0
        true_peak = -1.0

    st.markdown("#### 💾 Output Format")

    col5, col6 = st.columns(2)
    with col5:
        output_format = st.selectbox(
            "Primary Output Format",
            ["wav", "flac", "mp3"],
            index=0,
            key="output_format",
            help="WAV and FLAC are lossless. All three formats are always exported.",
        )
    with col6:
        mp3_bitrate = st.selectbox(
            "MP3 Bitrate",
            [128, 192, 256, 320],
            index=2,
            key="mp3_bitrate",
            help="Higher bitrate = better quality for MP3 export.",
        )

    # Reset button
    if st.button("🔄 Restore Default Settings", key="reset_settings"):
        keys = ["noise_reduction_strength", "hiss_reduction", "crackle_reduction",
                "hum_removal", "rumble_reduction", "enable_source_separation",
                "clarity_enhancement", "enable_loudness_normalization",
                "target_lufs", "true_peak_dbtp", "output_format", "mp3_bitrate",
                "bypass_restoration"]
        for k in keys:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    return _collect_settings(bypass=False)


def _collect_settings(bypass: bool = False) -> dict:
    """Collect current widget values into a settings dict."""
    if bypass:
        return {"bypass_restoration": True, "output_format": "wav", "mp3_bitrate": 256}

    return {
        "noise_reduction_strength": st.session_state.get("noise_reduction_strength", "medium"),
        "hiss_reduction": st.session_state.get("hiss_reduction", "medium"),
        "crackle_reduction": st.session_state.get("crackle_reduction", "low"),
        "hum_removal": st.session_state.get("hum_removal", True),
        "rumble_reduction": st.session_state.get("rumble_reduction", True),
        "enable_source_separation": st.session_state.get("enable_source_separation", False),
        "clarity_enhancement": st.session_state.get("clarity_enhancement", "medium"),
        "enable_loudness_normalization": st.session_state.get("enable_loudness_normalization", True),
        "target_lufs": st.session_state.get("target_lufs", -16.0),
        "true_peak_dbtp": st.session_state.get("true_peak_dbtp", -1.0),
        "output_format": st.session_state.get("output_format", "wav"),
        "mp3_bitrate": st.session_state.get("mp3_bitrate", 320),
        "bypass_restoration": False,
    }
