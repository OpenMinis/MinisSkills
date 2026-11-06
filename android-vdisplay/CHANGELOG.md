# Changelog

> **Update first when you hit any error**: Reinstall the latest `android-vdisplay` package and run `start.sh`. The script compares the installed APK version against the bundled skill version and upgrades automatically when they differ. Check version parity with `sh scripts/agent.sh version` (or query `/status` and `/version` directly for `version`, `versionCode`, `protocol`, `sdk`, and `device`).

## 0.12.1 (script fixes, no APK change)
- Fixed `start.sh` failing on the first run after a fresh install (APK not installed): the preflight fields are now labelled (`V= J= P= R=`) so an empty version no longer shifts the port/jar fields; the port is validated.
- Fixed `agent.sh` always exiting 0: control commands now exit non-zero on `{"ok":false,...}` (e.g. HTTP 423 `human has control`) or a transport failure.
- `device-run.sh` now passes `display_ime_policy=local` (override with `IME_POLICY=fallback`) so the soft keyboard shows on the second screen instead of the main screen.
- Reported by a user on Xiaomi 24122RKC7C / Android 17 / HyperOS.

## 0.12.1
- `agent.sh ui` / `ui-tap` now heal a LOST accessibility service in the middle of a session: on "service not enabled" they re-enable it (append-only) and retry once, with a one-line note on stderr.
  Guard rails: only inside a session we started (between `start.sh` and `stop.sh`), at most once per 60 s (if it is switched off again right away, someone meant it), remembered as blocked when the system refuses the write (some vendor ROMs), and an explicit `start.sh` re-authorizes.
- Fixed: a reused `start.sh` did not reset those flags.
- `SKILL.md` now instructs the agent to inform the user before first use that a read-only accessibility service is added through ADB.
- Tests: `scripts/test/ui-heal.sh` (13 checks); `ui.sh` case [8] updated.

## 0.12.0
- **Second-screen widget tree: `GET /ui` + `agent.sh ui` / `ui-tap`.** New read-only accessibility service `app.openminis.vdisplay/.UiService` reads the virtual display's windows through `getWindowsOnAllDisplays()` (verified on Pixel 4a, Android 13: Calculator on the second screen = 71 nodes, bounds in that display's space, main-screen windows not mixed in). Compact `lines` format (one node per line with center point) or `json`; filters `find`, `clickable`, `editable`, `scrollable`, `limit`; coordinates in the 540-wide reference space so they go straight to `tap`.
- `/status` adds `displayId`, `serviceEnabled`, `serviceConnected`. Service not enabled -> HTTP 503 with a `hint`.
- `start.sh` / `install.sh` enable the service silently via `settings put secure enabled_accessibility_services` (APPEND only, idempotent, other services untouched; needs `WRITE_SECURE_SETTINGS` held by ADB shell). `am force-stop` removes only our entry, so `start.sh` re-enables it each time.
- Nodes are `refresh()`ed before reading (otherwise `EditText` text can be stale). Idle service costs no CPU.
- Tests: `scripts/test/ui.sh`. `SKILL.md` shortest path now prefers `ui`, falling back to `shot` for games/WebView/Flutter/custom-drawn UI.

## 0.11.0
- **`ready` now means a picture was rendered.** The app counts frames the decoder actually produced (`rendered`); `/status` has `ready = connected && rendered>0`. `frames` keeps its old meaning (packets received) and `dropped`/`decodeErrors` were added. Fixes "ready:true but every screenshot is black".
- **Decoder no longer drops config/keyframes**: input-buffer timeouts are retried (up to ~500 ms) for config and key packets; if one still cannot be queued the app asks the server for a new keyframe (scrcpy `RESET_VIDEO`). Decoder exceptions are logged with their text. Output is drained on its own thread.
- **Surface ordering**: a video session that arrives before the Surface exists defers decoder start; a re-created `TextureView` re-attaches the running client to the new Surface instead of tearing the connection down.
- **`start.sh` self-heals**: after the display is up it waits up to 3 s for `rendered>0`; otherwise it saves logs and rebuilds once (`"healed":true`), then fails with `stage:"render"`.
- **`start.sh` reuses a healthy display** (`"reused":true`, ~1 s, same display id). `--fresh` / `VDISPLAY_FRESH=1` forces a rebuild. Display IDs only increase within a boot; that is normal.
- **Evidence is preserved**: `server.log`, `bridge.log` and filtered `logcat` are copied to `~/.android-vdisplay/logs/<timestamp>/` (last 5) before an automatic restart, on failures, and by `stop.sh`.

## 0.10.0
- Idle auto-close: after 10 minutes with no agent request (`status` polling counts) and no touch on the window, the second screen exits by itself. The last minute shows a countdown in the title. Change with `IDLE_MIN=<minutes>` on `start.sh`; `IDLE_MIN=0` disables it. `/status` now reports `idleMs`, `idleLimitMs`, `closed` and `closedReason` ("user" or "idle timeout").
- Closing is idempotent (the watchdog could otherwise run it twice).
- `start.sh` / `stop.sh` only touch our own server (`scid` `76646973`) and Bridge, never another scrcpy on the phone.
- Tests: `scripts/test/idle.sh`, `idle-touch.sh`, `coexist.sh`, `gestures.sh`.

## 0.9.0
- **Renamed**: package `app.openminis.vdisplay` (was `me.openminis.skilled`), skill `android-vdisplay` (was `pip-display`), state dir `~/.android-vdisplay`. Android package names cannot contain hyphens.
- **Cold start 6.5 s -> 2.1 s**: `start.sh` now makes one preflight call and one device-side `up` call (stop -> server -> bridge -> overlay in dependency order with 50 ms polling) instead of ~12 ADB round trips with 1 s sleeps. The device-side work itself is ~1.1 s.
- **Per-command overhead roughly halved**: `agent.sh` calls the forwarded HTTP port directly and only runs the ADB health check/forward repair when that fails (`tap` 598 -> ~190 ms over HTTP, ~300 ms end to end).
- **`run-app.sh` 1.9 s -> ~0.4 s**: polls the foreground on the device every 100 ms instead of sleeping 1 s per try; a wrong package name now fails in ~350 ms.
- **Screenshots**: `agent.sh shot <file> [png|jpg|webp] [q]`; jpg is ~2x faster than png and ~4x smaller (540 wide: png 307 ms/236 KB, jpg 173 ms/64 KB).
- Cases not changed: scrcpy server startup (~0.5 s) and PNG encoding of full-size frames (~430 ms) are the remaining floors; `uiautomator dump` still ~2.3 s and cannot target the secondary display.

## 0.7.0
- `start.sh` reports per-stage timing in its result JSON: `{"ms":{"preflight","server","bridge","overlay","ready","total"}}`
- Agent API: new `/ping` (no-op, isolates transport cost); `/screenshot` adds an `X-Timing-Ms` header (`capture/scale/encode`)
- Benchmark: `scripts/test/perf.py` (+ `perf-remote.sh`); results in `docs/perf-0.7.0.json`
- Known limitation: `uiautomator dump --display N` ignores `N` and follows the focused display, so it cannot target the secondary display

## 0.6.8
- Closing the second screen (`x`) now fully exits the app process: no lingering background process, threads, or open agent port. Verified: after closing, app pid=none, scrcpy server/bridge gone, virtual display gone, port 28080 closed; starting again works.

## 0.6.7
- Long-press 1 s (stationary) is now the ONLY way to take over — light taps, one-finger drags and two-finger pinches never take over, in both AI-working and standby states (8/8 gesture tests pass on Pixel 6)
- Two-finger pinch resizes and follows the fingers (the point under your fingers stays under them); window size clamped to 120dp ... 85% of screen
- Buttons, title and hint scale with the window (clamped 0.75-1.15x); all top-bar controls share one height
- Center hint is plain outlined text (no capsule), localized
- Close-screen button (`x`) in standby, tap twice to confirm; closing ends the virtual display, scrcpy server and bridge
- Localization: English default, Simplified Chinese, Traditional Chinese, Japanese, Korean; app name "Minis Second Screen"
- Code comments translated to English

## 0.5.4
- Glow effect rewritten as a single-pass AGSL GPU shader with zero per-frame allocations (~12 ms frame time, zero dropped frames)
- Inner glow acts as a breathing light: fades in and out in place with a rounded distance field (no harsh rectangular hollow in the center)
- Rotating rainbow border and orbiting highlight retained
- Top-right Stop button changed to a red circular icon button (no text label)
- While AI is acting: tapping the card takes over, dragging moves the floating window, and the center prompt pulses with the breathing light
- Title pill given a frosted-glass style; corner radius and default window size slightly reduced
- `run-app.sh` fixed a hang caused by `dumpsys` pipe closure; `start.sh` waits longer for the server and retries once automatically

## 0.3.6
- Releasing the floating window near the left or right screen edge automatically docks and collapses it into a small arrow pull-tab; tapping the tab expands it, and the tab can be dragged vertically
- Video surface switched to `TextureView` for true rounded-corner clipping; title bar overlays the video without adding extra height
- Glow effect styled after Siri / Apple Intelligence with colorful soft light blobs travelling along the edges; outer shadow removed in favor of a rotating rainbow border
- Two equal-sized capsule buttons ("Stop" and "Take over", with icons) centered while AI is acting; shows "Hand back to AI" during takeover; after Stop, agent actions return HTTP 423 until the user taps "Hand back to AI"
- Agent can dynamically update the title via `agent.sh title "Task description"`
- Virtual display defaults to the physical main screen's resolution and DPI; screenshots and taps use a unified 540-wide reference coordinate system (`REF_W` configurable)
- `start.sh`: automatically selects a free port (no longer fails when 27183 is busy), waits for video frames before returning, outputs `stage`/`hint`/`log` on failure, and auto-upgrades the APK when versions mismatch
- `run-app.sh`: verifies the target app is actually in the foreground on the virtual display; `agent.sh shot` validates image headers; stuck ADB server automatically heals by switching ports
- `/status` adds `ready`, `frames`, `version`, `stopped`; added `/version`, `/title`, and `/resume`

## 0.1.0
- Initial release: scrcpy virtual display + floating PiP overlay + HTTP agent API
