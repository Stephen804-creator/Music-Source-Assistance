"""Optional local audio analysis. No remote URL fetching is performed here."""
from __future__ import annotations
import io
from typing import Any

MAX_AUDIO_BYTES = 20 * 1024 * 1024

def analyze_audio_bytes(data: bytes, filename: str = "audio") -> dict[str, Any]:
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise ValueError("Audio must be between 1 byte and 20 MB")
    try:
        import librosa
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Audio analysis is optional. Install requirements-audio.txt to enable BPM/key/energy analysis.") from exc
    try:
        y, sr = librosa.load(io.BytesIO(data), sr=22050, mono=True, duration=180)
        if y.size == 0: raise ValueError("No decodable audio samples found")
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        rms = librosa.feature.rms(y=y)[0]
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        profile = chroma.mean(axis=1)
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        return {"filename": filename, "duration_seconds_analyzed": round(float(y.size / sr), 2),
                "bpm_estimate": round(float(np.asarray(tempo).reshape(-1)[0]), 1),
                "key_pitch_class_estimate": note_names[int(np.argmax(profile))],
                "energy_rms": round(float(np.mean(rms)), 5),
                "spectral_centroid_hz": round(float(np.mean(centroid)), 1),
                "analysis_note": "Approximate signal features. Key pitch class does not determine major/minor reliably."}
    except Exception as exc:
        if isinstance(exc, ValueError): raise
        raise ValueError("The uploaded audio could not be decoded or analysed") from exc
