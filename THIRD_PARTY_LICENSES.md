# Third-Party Licenses

Thai Song Player is licensed under the [MIT License](LICENSE). It depends on the
following third-party packages, which are **installed at runtime on the user's
machine** (via `pip`) and are **not redistributed** as part of this repository.

| Package | License | Notes |
|---|---|---|
| openai-whisper | MIT | Local speech-to-text. Model weights are also MIT. |
| thefuzz | MIT | Fuzzy matching (backed by rapidfuzz). |
| rapidfuzz | MIT | Matching backend (transitive via thefuzz). |
| sounddevice | MIT | Microphone capture. |
| Pillow | HPND (permissive, MIT-style) | Tray icon rendering. |
| numpy | BSD-3-Clause | Audio buffers. |
| scipy | BSD-3-Clause | Audio array helpers. |
| torch | BSD-3-Clause | Whisper runtime. |
| **mutagen** | **GPL-2.0-or-later** | Audio container/format detection. |
| **pystray** | **LGPL-3.0** | Menu-bar / system-tray icon. |
| **pynput** | **LGPL-3.0** | Global hotkey. |

## Copyleft note

This project's **own source code is MIT**. Because the project is distributed as
**source only** — users install the dependencies themselves with `pip install` —
the copyleft dependencies above do not impose their terms on this repository's
code (the combined work is assembled on the user's machine).

**If you build and distribute a bundled binary** (for example a PyInstaller
`.app`), you would then be *redistributing* the GPL-2.0 (`mutagen`) and LGPL-3.0
(`pystray`, `pynput`) libraries together with this code. In that case the bundled
distribution must comply with those licenses (e.g. it could not be released under
the MIT license alone). To keep a bundled build fully permissive, replace
`mutagen` with a minimal built-in format sniffer and confirm the LGPL components
remain replaceable.

Each package's full license text is available in its own distribution and at its
project homepage. This file is a convenience summary, not legal advice.
