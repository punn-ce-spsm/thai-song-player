import json

import app


def test_missing_config_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "CONFIG_PATH", str(tmp_path / "nope.json"))

    cfg = app.load_config()

    assert cfg == app.DEFAULT_CONFIG
    assert cfg is not app.DEFAULT_CONFIG  # must be a copy, not the shared dict


def test_partial_config_filled_from_defaults(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"threshold": 90}), encoding="utf-8")
    monkeypatch.setattr(app, "CONFIG_PATH", str(p))

    cfg = app.load_config()

    assert cfg["threshold"] == 90
    assert cfg["hotkey"] == app.DEFAULT_CONFIG["hotkey"]
    assert cfg["always_listening"] == app.DEFAULT_CONFIG["always_listening"]


def test_corrupt_config_falls_back_to_defaults(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    p.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(app, "CONFIG_PATH", str(p))

    cfg = app.load_config()

    assert cfg == app.DEFAULT_CONFIG
