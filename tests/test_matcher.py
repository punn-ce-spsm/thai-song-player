import json
import os

import matcher


def _make_song(dirpath, name):
    path = os.path.join(dirpath, name)
    with open(path, "wb") as f:
        f.write(b"\x00")  # contents irrelevant for matching
    return path


def test_load_songs_indexes_audio_by_stem(tmp_path):
    d = str(tmp_path)
    _make_song(d, "Tonight.mp3")
    _make_song(d, "Wings.flac")
    _make_song(d, "notes.txt")  # non-audio ignored

    songs = matcher.load_songs(d)

    assert set(songs.keys()) == {"Tonight", "Wings"}
    assert songs["Tonight"].endswith("Tonight.mp3")


def test_find_best_match_above_threshold(tmp_path):
    d = str(tmp_path)
    path = _make_song(d, "คืนนี้.mp3")
    songs = matcher.load_songs(d)

    name, filepath, score = matcher.find_best_match("คืนนี้", songs, threshold=70)

    assert name == "คืนนี้"
    assert filepath == path
    assert score >= 70


def test_find_best_match_below_threshold_returns_none(tmp_path):
    d = str(tmp_path)
    _make_song(d, "Tonight.mp3")
    songs = matcher.load_songs(d)

    name, filepath, score = matcher.find_best_match("zzzzz", songs, threshold=95)

    assert name is None
    assert filepath is None


def test_find_best_match_empty_inputs():
    assert matcher.find_best_match("", {}, 70) == (None, None, 0)
    assert matcher.find_best_match("anything", {}, 70) == (None, None, 0)


def test_songs_json_path_traversal_is_rejected(tmp_path):
    d = str(tmp_path)
    _make_song(d, "Wings.mp3")
    songs_json = tmp_path / "songs.json"
    songs_json.write_text(
        json.dumps({"evil": "../../../../etc/passwd", "ok": "Wings.mp3"}),
        encoding="utf-8",
    )

    songs = matcher.load_songs(d, str(songs_json))

    assert "evil" not in songs
    assert "ok" in songs


def test_songs_json_comment_keys_skipped(tmp_path):
    d = str(tmp_path)
    _make_song(d, "Wings.mp3")
    songs_json = tmp_path / "songs.json"
    songs_json.write_text(
        json.dumps({"_comment": "ignore me", "real": "Wings.mp3"}),
        encoding="utf-8",
    )

    songs = matcher.load_songs(d, str(songs_json))

    assert "_comment" not in songs
    assert "real" in songs


def test_directory_scan_rejects_symlink_escaping_folder(tmp_path):
    # A symlink inside the song folder pointing OUTSIDE must not be indexed,
    # while a normal audio file in the folder still is.
    song_dir = tmp_path / "songs"
    song_dir.mkdir()
    outside = tmp_path / "outside.mp3"
    outside.write_bytes(b"\x00")
    _make_song(str(song_dir), "Real.mp3")
    os.symlink(str(outside), str(song_dir / "evil.mp3"))

    songs = matcher.load_songs(str(song_dir))

    assert "Real" in songs
    assert "evil" not in songs


def test_oversized_songs_json_is_ignored(tmp_path):
    d = str(tmp_path)
    _make_song(d, "Wings.mp3")
    songs_json = tmp_path / "songs.json"
    # Build a valid-but-oversized (>1 MB) mapping; it must be skipped, not parsed.
    big = {f"name{i}": "Wings.mp3" for i in range(60000)}
    songs_json.write_text(json.dumps(big), encoding="utf-8")
    assert songs_json.stat().st_size > 1_000_000

    songs = matcher.load_songs(d, str(songs_json))

    # Directory scan still works; the oversized overlay is ignored.
    assert "Wings" in songs
    assert "name0" not in songs
