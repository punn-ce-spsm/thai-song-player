"""
player.py — macOS audio playback via the afplay subprocess.

Handles the common case where a file has the wrong extension by detecting
the actual container format via mutagen and creating a corrected temp symlink.
"""

import os
import secrets
import subprocess
import tempfile
import threading

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
_proc: subprocess.Popen | None = None   # afplay process
_current_file: str | None = None
_temp_file: str | None = None           # temp symlink for extension fix
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Format detection (replaces macOS-only 'file' command)
# ---------------------------------------------------------------------------

def _detect_extension(filepath: str) -> str:
    """Return the correct file extension based on actual container format."""
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(filepath)
        if audio is None:
            return os.path.splitext(filepath)[1].lower()
        ext_map = {
            "MP4":  ".m4a",
            "FLAC": ".flac",
            "OGG":  ".ogg",
            "MP3":  ".mp3",
            "WAVE": ".wav",
            "AIFF": ".aiff",
        }
        return ext_map.get(type(audio).__name__, os.path.splitext(filepath)[1].lower())
    except Exception:
        return os.path.splitext(filepath)[1].lower()


def _resolve_play_path(filepath: str) -> tuple[str, str | None]:
    """
    Return (play_path, temp_file_to_cleanup).
    If the declared extension doesn't match the actual format, create a
    temp symlink with the correct extension (zero-copy, no admin needed).
    """
    declared_ext = os.path.splitext(filepath)[1].lower()
    actual_ext = _detect_extension(filepath)

    if declared_ext == actual_ext or not actual_ext:
        return filepath, None

    tmp_name = os.path.join(
        tempfile.gettempdir(),
        f"thai_song_{secrets.token_hex(8)}{actual_ext}",
    )
    # Symlink: zero-copy, fast; no admin required on macOS
    os.symlink(os.path.abspath(filepath), tmp_name)
    return tmp_name, tmp_name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def play(filepath: str) -> tuple[bool, str | None]:
    """
    Play an audio file. Stops any currently playing audio first.
    Returns (success, error_message).
    """
    global _proc, _current_file, _temp_file
    try:
        play_path, tmp = _resolve_play_path(filepath)
        with _lock:
            _stop_locked()
            _proc = subprocess.Popen(
                ["afplay", play_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            _current_file = filepath
            _temp_file = tmp
        return True, None
    except Exception as e:
        return False, str(e)


def stop() -> None:
    """Stop any currently playing audio."""
    with _lock:
        _stop_locked()


def _stop_locked() -> None:
    """Must be called with _lock held."""
    global _proc, _current_file, _temp_file
    if _proc is not None:
        try:
            _proc.terminate()
            _proc.wait(timeout=2)
        except Exception:
            try:
                _proc.kill()
            except Exception:
                pass
        _proc = None

    _current_file = None
    _cleanup_temp()


def _cleanup_temp() -> None:
    """Remove the temp file if one exists. Must be called with _lock held."""
    global _temp_file
    if _temp_file and os.path.exists(_temp_file):
        try:
            os.unlink(_temp_file)
        except OSError:
            pass
    _temp_file = None


def is_playing() -> bool:
    """Return True if audio is currently playing."""
    global _proc
    with _lock:
        if _proc is None:
            return False
        ret = _proc.poll()
        if ret is not None:
            _proc = None
            _cleanup_temp()
            return False
        return True


def get_current_file() -> str | None:
    return _current_file
