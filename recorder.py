"""
recorder.py — Microphone recording with silence detection.

Returns a float32 numpy array (16 kHz, mono) directly so the caller can pass
it straight to Whisper — no temp WAV file, no ffmpeg dependency.
"""

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
MAX_DURATION_SEC = 5.0
SILENCE_THRESHOLD = 0.015       # RMS amplitude below this = silence
SILENCE_STOP_SEC = 1.5          # Stop after this many seconds of silence (post-speech)
MIN_SPEECH_SEC = 0.4            # Must detect this much speech before silence-stop triggers
NO_SPEECH_TIMEOUT_SEC = 3.0     # Abort if no speech detected within this time


def _rms(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))


def record_audio() -> tuple[np.ndarray | None, str | None]:
    """
    Record from the default microphone.

    Returns (audio, error_message).
    audio is a float32 numpy array at 16 kHz in [-1.0, 1.0], ready for Whisper.
    On failure, audio is None and error_message describes what went wrong.
    """
    max_chunks = int(MAX_DURATION_SEC * SAMPLE_RATE / CHUNK_SIZE)
    silence_stop_chunks = int(SILENCE_STOP_SEC * SAMPLE_RATE / CHUNK_SIZE)
    min_speech_chunks = int(MIN_SPEECH_SEC * SAMPLE_RATE / CHUNK_SIZE)
    no_speech_timeout_chunks = int(NO_SPEECH_TIMEOUT_SEC * SAMPLE_RATE / CHUNK_SIZE)

    frames: list[np.ndarray] = []
    speech_chunks = 0
    consecutive_silence = 0

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=CHUNK_SIZE,
        ) as stream:
            for i in range(max_chunks):
                data, _ = stream.read(CHUNK_SIZE)
                frames.append(data.copy())

                chunk_rms = _rms(data)
                is_speech = chunk_rms > SILENCE_THRESHOLD

                if is_speech:
                    speech_chunks += 1
                    consecutive_silence = 0
                else:
                    consecutive_silence += 1

                # Abort early: no speech at all for too long
                if speech_chunks == 0 and i >= no_speech_timeout_chunks:
                    return None, "ไม่ได้ยินเสียงพูด กรุณาลองใหม่"

                # Stop early: speech detected, then silence
                if speech_chunks >= min_speech_chunks and consecutive_silence >= silence_stop_chunks:
                    break

    except sd.PortAudioError as e:
        msg = str(e)
        if any(kw in msg.lower() for kw in ("denied", "permission", "not permitted")):
            settings_path = "System Settings → Privacy & Security → Microphone"
            return None, (
                f"ไมโครโฟนถูกปฏิเสธ — กรุณาเปิดสิทธิ์ใน\n{settings_path}"
            )
        return None, f"PortAudio error: {msg}"
    except Exception as e:
        return None, f"Recording error: {e}"

    if not frames:
        return None, "ไม่ได้บันทึกเสียง"

    audio = np.concatenate(frames, axis=0).squeeze()
    audio = np.clip(audio, -1.0, 1.0).astype(np.float32)
    return audio, None
