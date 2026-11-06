# Virtual Display Widget Tree (`agent.sh ui`, v0.12.0+)

## Overview (Verified on Pixel 4a, Android 13)
The companion APK includes a read-only accessibility service (`app.openminis.vdisplay/.UiService`) that calls `getWindowsOnAllDisplays()` (API 30+, grouped by `displayId`) to inspect the **virtual display's** window hierarchy. `GET /ui` (wrapped by `agent.sh ui`) only responds to local `127.0.0.1` requests and never writes to disk or uploads data.
- Calculator on the virtual display: 71 nodes, with bounds in the virtual display's coordinate space (`1080x2340`), scaled by `ref=540` so coordinates can be passed directly to `agent.sh tap`. Every node includes its center point `c=(x,y)`.
- Main-screen windows (`SystemUI`, `Minis`, and our floating overlay) live on display `0` and **never leak** into virtual display results. Pass `ui display 0` to inspect the main screen, or `ui all-displays` to list windows across all displays.
- Exposed node properties: `text`, `contentDescription`, `resource id` (short name), `bounds`, and boolean flags (`clickable`, `editable`, `scrollable`, `enabled`, `checked`, `selected`, `focusable`). Verified end-to-end by computing `37 * 42 = 1554` and reading the result purely through `/ui` without taking screenshots.
- Freshness: Some views (such as Calculator's formula `EditText`) cache stale text until refreshed; `UiService` calls `node.refresh()` on every node before reading so returned values are always current.

## Silent Activation via ADB (No Manual Settings Prompt)
`start.sh` and `install.sh` automatically run:
```sh
settings put secure enabled_accessibility_services "<existing>:app.openminis.vdisplay/app.openminis.vdisplay.UiService"
settings put secure accessibility_enabled 1
```
(ADB `shell` holds `WRITE_SECURE_SETTINGS`.) This is **append-only**, idempotent, and leaves other accessibility services untouched. Because `am force-stop` in `stop.sh` / `start.sh` causes Android to drop our service entry (while preserving other services), `start.sh` re-enables our entry on every run and waits for `serviceConnected:true`. If a vendor ROM blocks secure-settings writes, `serviceEnabled` in `/status` remains `false` and `/ui` returns HTTP 503 with a `hint`, at which point the agent should fall back to `shot`.
When idle, the accessibility service uses zero CPU (measured 0 ticks over 15 s, ~50 MB resident, 12 threads).

### Automatic Mid-Session Healing (`v0.12.1+`)
The accessibility service may be lost mid-session if the user toggles it off, `am force-stop` runs, or secure settings are reset (if the process is killed via `am kill`, Android restarts and rebinds it automatically within ~2 s). When `agent.sh ui` or `ui-tap` receives HTTP 503 (`service not enabled`), it **automatically heals the service once and retries**, printing a one-line notice to `stderr`. To avoid fighting the user, auto-healing enforces four guard rails:
1. Only heals inside an active session started by `start.sh` (and before `stop.sh`); never touches system settings outside a session.
2. Rate-limited to at most once every 60 seconds; if the service is turned off again immediately after healing, the user turned it off intentionally and `agent.sh` returns 503 without re-enabling.
3. If the OS rejects the setting write (e.g. strict vendor ROM restrictions), `ui_blocked` is recorded for the rest of the session and `agent.sh` instructs the caller to use `shot`.
4. Running `start.sh` explicitly re-authorizes the session and clears the rate-limit and blocked markers.
**When the agent still receives 503**: Read `hint`; if auto-healing was blocked or rate-limited, do not retry `ui` in a loop — fall back to `shot` and inform the user that "Minis Second Screen" can be enabled manually in Android Accessibility Settings.

## Usage (Recommended)
```sh
sh $SK/agent.sh ui                       # 1 line per node: [25] ImageButton desc="7" id=digit_7 click (6,605)-(134,733) c=(70,669)
sh $SK/agent.sh ui find 7                # Case-insensitive substring match on text/desc/id; count=0 when nothing matches
sh $SK/agent.sh ui clickable | editable | scrollable | json | limit N | display N | all-displays
sh $SK/agent.sh ui-tap 7                 # Exact match preferred; taps only when a single unique target matches; lists candidates when ambiguous
```
When `ui` is empty or insufficient (games, WebView, Flutter, or custom-drawn controls), fall back to `shot` + pixel coordinates. After an action, verify the outcome with `ui find <target>` instead of taking a screenshot after every step.

## Historical Notes (Do Not Waste Calls on These)
- Minis's built-in `android-a11y-cli ui dump --display <ID>`, `--package`, and `ui find --text` all ignore the display parameter and always return the 45 nodes on the main screen (`display 0`).
- Android's `uiautomator dump --display <ID>` likewise ignores `--display` and dumps whichever display currently holds top focus on the main screen.
- Never invoke `android-a11y-cli` or `uiautomator dump` to inspect the virtual display; always use `agent.sh ui`.
