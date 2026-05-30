"""
recognizer.py — Whisper-based Thai speech-to-text.

Accepts a float32 numpy array directly so ffmpeg is never invoked.
Supports a bundled model path for PyInstaller distributions.
"""

import os
import sys
import threading

import numpy as np

_model = None
_model_lock = threading.Lock()


def _model_download_root() -> str | None:
    """
    When running as a PyInstaller bundle, check for a pre-bundled model in
    _MEIPASS/whisper_model/ and return that directory so Whisper skips the
    network download entirely.  Returns None in dev mode (use default cache).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, "whisper_model")
        if os.path.isdir(bundled):
            return bundled
    return None


def get_model():
    """Return the cached Whisper base model, loading it if necessary."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import whisper
                download_root = _model_download_root()
                if download_root:
                    _model = whisper.load_model("base", download_root=download_root)
                else:
                    _model = whisper.load_model("base")
    return _model


def transcribe(audio: np.ndarray) -> tuple[str | None, str | None]:
    """
    Transcribe a float32 audio array using Whisper with Thai forced.

    audio must be float32, 16 kHz, mono, values in [-1.0, 1.0].
    Passing a numpy array bypasses whisper's load_audio() which requires ffmpeg.

    Returns (text, error).
    """
    try:
        model = get_model()
        result = model.transcribe(
            audio,
            language="th",
            task="transcribe",
            fp16=False,      # fp16 not supported on CPU; avoids UserWarning
            verbose=False,
        )
        text = result["text"].strip()
        return (text or None), (None if text else "ถอดความได้ข้อความว่างเปล่า")
    except Exception as e:
        return None, f"Whisper error: {e}"
