"""
app.py — Thai Song Player: cross-platform system tray app.

macOS hotkey: Cmd+Shift+Space  (or custom value in config.json)
Windows hotkey: Ctrl+Shift+Space (or custom value in config.json)
→ record → transcribe → match → play
"""

import json
import os
import subprocess
import sys
import threading
import time

import pystray
from PIL import Image, ImageDraw

import matcher
import player
import recognizer
import recorder

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SONGS_PATH = os.path.join(BASE_DIR, "songs.json")

# ---------------------------------------------------------------------------
# State → tray icon color mapping
# ---------------------------------------------------------------------------
STATE_COLORS = {
    "idle":       "#22c55e",   # green
    "listening":  "#ef4444",   # red
    "processing": "#f59e0b",   # amber
    "playing":    "#3b82f6",   # blue
}

DEFAULT_CONFIG: dict = {
    "song_folder": "",
    "threshold": 70,
    "hotkey": "<cmd>+<shift>+<space>",
    "always_listening": False,
}

# Recorder/recognizer messages that mean "no speech this cycle" — these are
# expected in always-listening mode, so we suppress their notifications.
_SILENT_CYCLE_MARKERS = (
    "ไม่ได้ยินเสียงพูด",
    "ไม่ได้บันทึกเสียง",
    "ถอดความได้ข้อความว่างเปล่า",
)


def _is_silent_cycle_error(err: str | None) -> bool:
    return bool(err) and any(m in err for m in _SILENT_CYCLE_MARKERS)

# Cooldown after a real recording failure (mic denied / device busy) while in
# always-listening mode, so the loop can't retry tightly and spin the audio
# subsystem. Does not apply to normal silent (no-speech) cycles.
_ALWAYS_LISTEN_ERROR_COOLDOWN_SEC = 3.0

# ---------------------------------------------------------------------------
# Tray icon helpers
# ---------------------------------------------------------------------------

def _make_tray_image(color: str) -> Image.Image:
    """Create a 64×64 filled circle PIL image for the system tray."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=color)
    return img


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Security helper
# ---------------------------------------------------------------------------

def _applescript_safe(text: str) -> str:
    """Sanitize text for safe interpolation into an AppleScript string literal.

    Drops all control characters (including newlines and tabs), escapes
    backslashes, then escapes double quotes — in that order — so attacker-
    influenced text cannot break out of the surrounding string literal.
    """
    printable = "".join(ch for ch in text if ch >= " ")
    return printable.replace("\\", "\\\\").replace('"', '\\"')


# ---------------------------------------------------------------------------
# Platform helpers: notifications & folder picker
# ---------------------------------------------------------------------------

def notify(subtitle: str, message: str) -> None:
    """Send a system notification (non-blocking).

    The dynamic subtitle/message (which may include attacker-influenced text
    such as song names or transcripts) are passed as arguments to an
    ``on run`` handler rather than interpolated into the script source, so
    they are always treated as inert data and cannot inject AppleScript.
    """
    def _do():
        subprocess.run(
            [
                "osascript",
                "-e", "on run {subtitleArg, messageArg}",
                "-e", (
                    'display notification messageArg '
                    'with title "Thai Song Player" subtitle subtitleArg'
                ),
                "-e", "end run",
                subtitle, message,
            ],
            check=False,
        )
    threading.Thread(target=_do, daemon=True).start()


def pick_folder(prompt: str = "เลือกโฟลเดอร์เพลง:") -> str | None:
    """Show a native folder picker dialog. Returns path or None."""
    script = f"""
tell application "System Events"
    activate
end tell
try
    set folderPath to choose folder with prompt "{_applescript_safe(prompt)}"
    return POSIX path of folderPath
on error
    return ""
end try
"""
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    path = result.stdout.strip()
    return path.rstrip("/") if path else None


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class ThaiSongPlayerApp:

    def __init__(self):
        self.config = load_config()
        self._songs: dict[str, str] = {}
        self._state = "idle"
        self._state_lock = threading.Lock()
        self._quit_event = threading.Event()

        self._tray_icon = pystray.Icon(
            "ThaiSongPlayer",
            _make_tray_image(STATE_COLORS["idle"]),
            "Thai Song Player",
            menu=self._build_menu(),
        )

        self._reload_songs()
        self._setup_hotkey()

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Start Listening", self._on_listen_clicked),
            pystray.MenuItem("Stop Playback", self._on_stop_clicked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Always Listening",
                self._on_toggle_always_listening,
                checked=lambda item: bool(self.config.get("always_listening")),
            ),
            pystray.MenuItem("Set Song Folder…", self._on_set_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

    def _on_toggle_always_listening(self, icon, item):
        self.config["always_listening"] = not bool(self.config.get("always_listening"))
        save_config(self.config)

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _preload_model(self):
        try:
            recognizer.get_model()
        except Exception as e:
            print(f"[whisper] Failed to preload model: {e}", file=sys.stderr)

    def _reload_songs(self):
        folder = self.config.get("song_folder", "")
        self._songs = matcher.load_songs(folder, SONGS_PATH)

    def _setup_hotkey(self):
        try:
            from pynput import keyboard as kb
            hotkey_str = self.config.get("hotkey", DEFAULT_CONFIG["hotkey"])

            def on_activate():
                self._trigger_listen()

            self._hotkey_listener = kb.GlobalHotKeys({hotkey_str: on_activate})
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
        except Exception as e:
            hint = "เปิดสิทธิ์ใน System Settings → Privacy & Security → Accessibility"
            print(
                f"[hotkey] Could not register global hotkey"
                f" {self.config.get('hotkey')!r}: {e}\n{hint}",
                file=sys.stderr,
            )
            notify("Hotkey ไม่ทำงาน", hint)

    # ------------------------------------------------------------------
    # State management (thread-safe)
    # ------------------------------------------------------------------

    def _set_state(self, state: str):
        color = STATE_COLORS.get(state, STATE_COLORS["idle"])
        new_icon = _make_tray_image(color)
        with self._state_lock:
            self._state = state
            self._tray_icon.icon = new_icon

    def _get_state(self) -> str:
        with self._state_lock:
            return self._state

    def _try_claim_listening(self) -> bool:
        """
        Atomically claim the listening state. Returns True if claimed.
        Allowed transitions: idle → listening, playing → listening (interrupt).
        Refuses if already listening/processing (can't double-start).
        """
        new_icon = _make_tray_image(STATE_COLORS["listening"])
        interrupted_playback = False
        with self._state_lock:
            if self._state in ("idle", "playing"):
                interrupted_playback = (self._state == "playing")
                self._state = "listening"
                self._tray_icon.icon = new_icon
                claimed = True
            else:
                claimed = False
        if interrupted_playback:
            player.stop()
        return claimed

    # ------------------------------------------------------------------
    # Menu / hotkey callbacks
    # ------------------------------------------------------------------

    def _on_listen_clicked(self, icon, item):
        self._trigger_listen()

    def _on_stop_clicked(self, icon, item):
        # Only act when actually playing; don't clobber an in-flight listen/processing.
        if self._get_state() == "playing":
            player.stop()
            self._set_state("idle")

    def _on_set_folder(self, icon, item):
        folder = pick_folder("เลือกโฟลเดอร์เพลง (Select your songs folder):")
        if folder:
            self.config["song_folder"] = folder
            save_config(self.config)
            self._reload_songs()
            count = len(self._songs)
            notify("โฟลเดอร์เพลง", f"พบ {count} เพลงใน {os.path.basename(folder)}")

    def _on_quit(self, icon, item):
        player.stop()
        self._quit_event.set()
        icon.stop()

    # ------------------------------------------------------------------
    # Core listen → transcribe → match → play pipeline
    # ------------------------------------------------------------------

    def _trigger_listen(self):
        """Entry point from both the menu item and the global hotkey."""
        if not self._try_claim_listening():
            return  # Already listening or processing

        if not self.config.get("song_folder"):
            self._set_state("idle")
            notify("ไม่พบโฟลเดอร์", "กรุณาเลือกโฟลเดอร์เพลงก่อน")
            return

        threading.Thread(target=self._pipeline, daemon=True).start()

    def _pipeline(self):
        always_on = bool(self.config.get("always_listening"))

        # --- 1. Record -------------------------------------------------------
        audio, error = recorder.record_audio()

        if error or audio is None:
            if not (always_on and _is_silent_cycle_error(error)):
                notify("บันทึกเสียงล้มเหลว", error or "ไม่ทราบสาเหตุ")
                if always_on:
                    # Hold the (already-claimed) listening state during the
                    # cooldown so the always-listening poll loop can't re-enter
                    # and spin on a persistent failure. Normal silent cycles
                    # skip this and retry promptly.
                    time.sleep(_ALWAYS_LISTEN_ERROR_COOLDOWN_SEC)
            self._set_state("idle")
            return

        # --- 2. Transcribe ---------------------------------------------------
        self._set_state("processing")
        text, error = recognizer.transcribe(audio)

        if error or not text:
            self._set_state("idle")
            if not (always_on and _is_silent_cycle_error(error)):
                notify("ถอดความล้มเหลว", error or "ไม่ได้ยินเสียงพูดชัดเจน")
            return

        if os.environ.get("THAI_SONG_DEBUG"):
            print(f"[whisper] transcribed: {text!r}")

        # --- 3. Match --------------------------------------------------------
        self._reload_songs()
        try:
            threshold = max(0, min(100, int(self.config.get("threshold", 70))))
        except (TypeError, ValueError):
            threshold = 70
        name, filepath, score = matcher.find_best_match(text, self._songs, threshold)

        if not filepath:
            self._set_state("idle")
            notify("ไม่พบเพลง", f'"{text}" — ลองพูดใหม่อีกครั้ง')
            return

        # --- 4. Play ---------------------------------------------------------
        success, error = player.play(filepath)

        if success:
            self._set_state("playing")
            notify("กำลังเล่น", f"{name}  ({score}%)")
        else:
            self._set_state("idle")
            notify("เล่นเพลงล้มเหลว", error or "ไม่สามารถเล่นไฟล์ได้")

    # ------------------------------------------------------------------
    # Playback polling (background thread, replaces rumps.Timer)
    # ------------------------------------------------------------------

    def _poll_playback(self):
        while not self._quit_event.is_set():
            if self._get_state() == "playing" and not player.is_playing():
                self._set_state("idle")
            # Continuous-listening mode: kick off a new listen whenever we
            # return to idle. A folder must be configured first.
            if (
                self.config.get("always_listening")
                and self._get_state() == "idle"
                and self.config.get("song_folder")
            ):
                self._trigger_listen()
            time.sleep(1)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self):
        def _setup(icon):
            icon.visible = True
            # Start background threads after tray icon is up
            threading.Thread(target=self._poll_playback, daemon=True).start()
            threading.Thread(target=self._preload_model, daemon=True).start()
            # First-launch: prompt for song folder after a short delay
            if not self.config.get("song_folder"):
                threading.Thread(target=self._first_launch_prompt, daemon=True).start()

        self._tray_icon.run(_setup)

    def _first_launch_prompt(self):
        time.sleep(1.5)
        notify("Thai Song Player", "ยินดีต้อนรับ! กรุณาเลือกโฟลเดอร์เพลงของคุณ")
        time.sleep(2.0)
        self._on_set_folder(None, None)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ThaiSongPlayerApp().run()


if __name__ == "__main__":
    main()
