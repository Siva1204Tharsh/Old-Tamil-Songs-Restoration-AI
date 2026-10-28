"""
A/B comparison and download results component.
"""
from __future__ import annotations

import streamlit as st
from components.waveform import render_comparison_waveforms, render_spectrum


def render_comparison(original_bytes: bytes, restored_bytes: bytes,
                      orig_filename: str, job_id: str,
                      result_meta: dict, analysis: dict) -> None:
    """
    Render the A/B comparison panel with audio players, waveforms,
    loudness comparison, download buttons, and feedback.
    """
    st.markdown("## 🎵 Restoration Results")

    # ── Audio players ──────────────────────────────────────────────
    st.markdown("### 🎧 Listen & Compare")
    tab_orig, tab_rest, tab_side = st.tabs(["Original", "Restored", "Side by Side"])

    with tab_orig:
        st.markdown("#### Original Recording")
        st.audio(original_bytes, format=f"audio/{orig_filename.rsplit('.', 1)[-1].lower()}")
        render_spectrum(original_bytes, orig_filename, "#6C63FF", "Original Spectrum",
                        key="compare_orig_spectrum")

    with tab_rest:
        st.markdown("#### Restored Recording")
        st.audio(restored_bytes, format="audio/wav")
        render_spectrum(restored_bytes, "restored.wav", "#00D4AA", "Restored Spectrum",
                        key="compare_rest_spectrum")

    with tab_side:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 🎵 Original")
            st.audio(original_bytes, format=f"audio/{orig_filename.rsplit('.', 1)[-1].lower()}")
        with col_b:
            st.markdown("#### ✨ Restored")
            st.audio(restored_bytes, format="audio/wav")
        render_comparison_waveforms(original_bytes, restored_bytes, orig_filename, "restored.wav",
                                    key_prefix="compare")

    st.markdown("---")

    # ── Loudness comparison ────────────────────────────────────────
    st.markdown("### 📊 Quality Comparison")
    c1, c2, c3, c4 = st.columns(4)
    orig_lufs = analysis.get("integrated_lufs", "N/A")
    rest_lufs = result_meta.get("restored_lufs", "N/A")
    orig_tp = analysis.get("true_peak_dbtp", "N/A")
    rest_tp = result_meta.get("restored_true_peak_dbtp", "N/A")
    proc_time = result_meta.get("processing_time_seconds", 0)

    with c1:
        st.metric("Original LUFS", f"{orig_lufs:.1f}" if isinstance(orig_lufs, float) else orig_lufs,
                  delta=f"{rest_lufs - orig_lufs:+.1f}" if isinstance(rest_lufs, float) and isinstance(orig_lufs, float) else None)
    with c2:
        st.metric("Restored LUFS", f"{rest_lufs:.1f}" if isinstance(rest_lufs, float) else rest_lufs)
    with c3:
        st.metric("Original True Peak", f"{orig_tp:.1f} dBTP" if isinstance(orig_tp, float) else orig_tp)
    with c4:
        st.metric("Processing Time", f"{proc_time:.1f}s")

    st.markdown("---")

    # ── Download buttons ───────────────────────────────────────────
    st.markdown("### 💾 Download Restored Audio")
    st.caption("All formats are always exported. Download any or all.")

    from services.api_client import download_audio
    dl_col1, dl_col2, dl_col3 = st.columns(3)

    with dl_col1:
        try:
            wav_bytes = download_audio(job_id, "wav")
            stem = orig_filename.rsplit(".", 1)[0]
            st.download_button(
                label="⬇️ Download WAV (Lossless)",
                data=wav_bytes,
                file_name=f"{stem}_restored.wav",
                mime="audio/wav",
                use_container_width=True,
                key="dl_wav",
            )
        except Exception as e:
            st.error(f"WAV download failed: {e}")

    with dl_col2:
        try:
            flac_bytes = download_audio(job_id, "flac")
            st.download_button(
                label="⬇️ Download FLAC (Lossless)",
                data=flac_bytes,
                file_name=f"{stem}_restored.flac",
                mime="audio/flac",
                use_container_width=True,
                key="dl_flac",
            )
        except Exception as e:
            st.error(f"FLAC download failed: {e}")

    with dl_col3:
        try:
            mp3_bytes = download_audio(job_id, "mp3")
            st.download_button(
                label="⬇️ Download MP3",
                data=mp3_bytes,
                file_name=f"{stem}_restored.mp3",
                mime="audio/mpeg",
                use_container_width=True,
                key="dl_mp3",
            )
        except Exception as e:
            st.error(f"MP3 download failed: {e}")

    st.markdown("---")

    # ── Feedback section ───────────────────────────────────────────
    st.markdown("### 📣 Result Feedback")
    st.markdown("How does the restored audio sound?")

    fb_col1, fb_col2 = st.columns(2)
    with fb_col1:
        if st.button("✅ Original music preserved", key="fb_good", use_container_width=True):
            st.success("Thank you for your feedback! Great to hear the music is preserved.")

    with fb_col2:
        if st.button("⚠️ Music sounds distorted", key="fb_bad", use_container_width=True):
            st.warning(
                "Sorry to hear that. Try re-processing with **Low** strength settings "
                "or enable **Bypass mode** to get the original back. "
                "You can re-upload and adjust the settings."
            )

    st.info(
        "💡 If the restored audio sounds worse, use the **Bypass mode** option in settings "
        "to recover the original, or re-upload with lower restoration strength."
    )
