"""
matcher.py — Fuzzy matching of a Thai query against a library of song names.
"""

import os
import json

from thefuzz import fuzz, process as fuzz_process

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".opus"}


def load_songs(song_folder: str, songs_json_path: str | None = None) -> dict[str, str]:
    """
    Build a mapping of {display_name: absolute_filepath}.

    Priority:
      1. Files found directly in song_folder (stem → path).
      2. songs.json overrides / additions (spoken_name → filename in song_folder).
    """
    songs: dict[str, str] = {}

    if song_folder and os.path.isdir(song_folder):
        for filename in os.listdir(song_folder):
            stem, ext = os.path.splitext(filename)
            if ext.lower() in AUDIO_EXTENSIONS:
                songs[stem] = os.path.join(song_folder, filename)

    # Overlay songs.json mappings
    if songs_json_path and os.path.isfile(songs_json_path):
        try:
            with open(songs_json_path, "r", encoding="utf-8") as f:
                mapping: dict[str, str] = json.load(f)
            # Resolve song_folder once for traversal checks
            safe_root = os.path.realpath(song_folder) if song_folder else ""
            for spoken_name, filename in mapping.items():
                if not song_folder or not isinstance(filename, str):
                    continue
                # Skip JSON-comment style keys (e.g. "_comment", "_example1")
                if spoken_name.startswith("_"):
                    continue
                filepath = os.path.join(song_folder, filename)
                # Guard against path traversal (e.g. "../../etc/passwd")
                if safe_root and not os.path.realpath(filepath).startswith(safe_root + os.sep):
                    continue
                if os.path.isfile(filepath):
                    songs[spoken_name] = filepath
        except (json.JSONDecodeError, OSError):
            pass  # Corrupted songs.json — ignore silently

    return songs


def find_best_match(
    query: str,
    songs: dict[str, str],
    threshold: int = 70,
) -> tuple[str | None, str | None, int]:
    """
    Fuzzy-match query against song display names.

    Returns (matched_name, filepath, score).
    If no match above threshold, matched_name and filepath are None.
    """
    if not songs or not query:
        return None, None, 0

    names = list(songs.keys())

    # Use token_set_ratio for better Thai partial-match handling
    result = fuzz_process.extractOne(
        query,
        names,
        scorer=fuzz.token_set_ratio,
    )

    if result is None:
        return None, None, 0

    matched_name, score = result[0], result[1]

    if score >= threshold:
        return matched_name, songs[matched_name], score

    return None, None, score
