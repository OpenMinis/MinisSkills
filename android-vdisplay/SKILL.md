---
name: android-vdisplay
description: >
  Create an on-device virtual display ("second screen") on an Android phone running Minis via local wireless ADB, render it inside a floating Picture-in-Picture overlay window on the main screen, and let the agent launch apps, inspect the widget tree, take screenshots, and inject touch, swipe, text, and key events while allowing the human user to take over at any time (with automatic HTTP 423 mutual exclusion). Powered by scrcpy-server (trusted virtual display) + a companion overlay APK. Trigger this skill whenever the user mentions "second screen", "virtual display", "virtual screen", "PiP", "picture-in-picture", "floating window automation", "background app automation", "scrcpy virtual display", "operate an app without occupying the main screen", or wants the agent to control Android apps on the same phone with human takeover support.
version: 0.12.2
---

# android-vdisplay: On-Device Virtual Display + Floating PiP Overlay + Agent Control

On the same Android phone: `scrcpy-server` creates a trusted virtual display over local ADB (`shell`), apps run on that virtual display while rendered inside a floating Picture-in-Picture card on the main screen, the agent drives apps via scripts, and the human user can long-press the card to take over at any time.

## Update First When Errors Occur
**Whenever a script fails or behaves unexpectedly, update to the latest version first**: reinstall the latest `android-vdisplay` skill package and run `start.sh`, which automatically checks and upgrades the on-device APK. Run `sh scripts/agent.sh version` to verify version parity. If it still fails after updating, follow the `stage` and `hint` fields in the JSON output.

## Shortest Path (Follow Directly — Do Not Improvise)
```sh
SK=/var/minis/skills/android-vdisplay/scripts
sh $SK/start.sh                        # Auto-install -> pick free port -> start server/bridge/overlay -> wait for rendered frame
sh $SK/run-app.sh com.android.chrome   # Launch app and verify it is in the foreground on the virtual display
sh $SK/agent.sh ui                     # Read widget tree first: 1 node per line with center c=(x,y) in 540-wide coord space
sh $SK/agent.sh ui find 7              # Match by text/desc/id; or run `ui-tap 7` to find and tap in one step
sh $SK/agent.sh tap 270 480            # Tap using c=(x,y) from `ui`; verify with `ui find` afterwards
sh $SK/agent.sh shot /tmp/s.jpg jpg 70 # Fall back to screenshots only when `ui` is empty/insufficient (games, WebView, Flutter, custom UI)
sh $SK/stop.sh                         # Stop and exit cleanly
```
Every command outputs JSON or an explicit `ERR:` message and exits non-zero on failure. Follow the `hint` field in the JSON output directly instead of crafting raw `adb` commands by hand.

## Prerequisites (One-Time)
Android 10+; Alpine requires `adb curl python3` (`apk add android-tools curl python3`); `adb devices` must list the phone itself (via Wireless Debugging — see [references/setup.md](references/setup.md)). When multiple devices are attached, set `export SERIAL=<serial>`; set `export ADB_CONNECT=ip:port` for automatic reconnection. Keep the phone screen unlocked and awake.

## `start.sh` Status & Stages
- **Success**: `{"ok":true,"display":N,"port":P,"reused":false}`. `ok:true` means the **virtual display is created AND the decoder has rendered at least one frame** (`rendered>0`), so it is ready for immediate interaction.
- **Reuse**: If the virtual display for our `scid` is already healthy (APK and server alive, `ready:true`, not closed, matching resolution), `start.sh` reuses it immediately (`"reused":true`, ~1 s, without restarting anything). Force a fresh rebuild with `start.sh --fresh` or `VDISPLAY_FRESH=1`. Display IDs monotonically increase within a boot session — this is standard Android behavior, not a resource leak.
- **Self-healing**: If no frame is rendered within 3 seconds on first start, `start.sh` saves diagnostic logs and rebuilds once automatically (`"healed":true`). If it still fails, it exits with `stage:"render"`. Diagnostic logs are saved under `~/.android-vdisplay/logs/<timestamp>/` (last 5 runs kept; `stop.sh` also saves logs) and reported in `savedLogs`.
- **Failure stages** (`stage` / `hint` / `log`):
  - `adb`: Device disconnected or unauthorized (follow [references/setup.md](references/setup.md)).
  - `server` / `bridge`: Check `log`; retrying once usually resolves transient races.
  - `display`: Typically caused by a locked phone screen or bridge connection failure; unlock the phone and retry.
  - `frames`: Overlay did not receive video packets; verify overlay permission and retry.
  - `render`: Video packets arrived but the decoder rendered no frames (screenshots would be solid black); already retried once — inspect `savedLogs`.

## Core Operations (`agent.sh`)
| Command | Description |
|---|---|
| `status` | `ready:true` = decoder has **rendered a frame** (`rendered>0`); `frames` is packet count only; also reports `dropped`, `decodeErrors`, `port`, `humanActive`, `error` |
| `shot [path] [png\|jpg\|webp] [q]` | Capture screenshot (default width 540); `jpg 70` is recommended for vision inspection to save latency and tokens |
| `ui [find TEXT] [clickable] [editable] [json]` / `ui-tap TEXT` | Read virtual display widget tree (1 line per node with center point); `ui-tap` taps only when a single unique target matches |
| `tap x y` / `swipe x1 y1 x2 y2 [ms]` | Coordinates in the same reference space as `shot` and `ui` (default width 540, proportional height) |
| `key <code>` | `4`=BACK, `3`=HOME, `66`=ENTER, `67`=DEL |
| `text "content"` | Injects ASCII character by character; non-ASCII (e.g. CJK) is pasted automatically via clipboard |
| `title "label"` | Update the top-bar task pill on the floating window so the user sees what the agent is doing |
| `window x=.. y=.. w=<dp>` / `hide` / `show` | Move/resize window; `hide` moves it off-screen while keeping the virtual display running and controllable |
| `version` / `resume` | Check version parity; `resume` clears human takeover / stopped state |

`run-app.sh <package>`: Returns `ok:true` only after verifying the app is in the foreground on the virtual display; otherwise reports the exact reason (not installed vs. did not reach foreground).

## Core Workflow & Rules
1. **Workflow**: `start` -> `run-app` -> loop (`ui` to locate target -> one action -> `ui find` to verify, or `shot` when needed) -> `stop`.
2. **Widget Tree First (`ui`)**: Always prefer `agent.sh ui` to inspect the virtual display's widget tree (0.12.0+, see [references/accessibility.md](references/accessibility.md)); fall back to `shot` only when nodes are empty or missing the target. **Never** run `android-a11y-cli ui dump/find` or `uiautomator dump` for the virtual display — both ignore `--display` and always return main-screen nodes. If `ui` returns HTTP 503 (service disabled), `agent.sh` automatically heals it once; if it still fails, follow `hint` or fall back to `shot` without looping. **Inform the user before first use**: to read the widget tree, `start.sh` appends a read-only accessibility service (`Minis Second Screen`) via ADB without touching other services, and `stop.sh` removes it.
3. **Human Takeover & HTTP 423**:
   - When the user stationary long-presses the floating card for 1 second or taps the top-right Stop button, human takeover begins and all agent control endpoints return **HTTP 423** (`human has control` / `stopped by user`).
   - Upon receiving 423, **never retry in a loop**. Pause immediately, inform the user in chat, and wait until the user taps "Hand back to AI" or asks you to continue. See [references/takeover.md](references/takeover.md).
4. **10-Minute Idle Auto-Close**: After 10 minutes with no agent requests (including `status` polls) and no human touch on the floating window, the virtual display closes automatically (showing a countdown in the title bar during the last minute). Once closed, `/status` is unreachable; run `start.sh` to start a new session. Customize the timeout via `IDLE_MIN=30 sh $SK/start.sh` (`IDLE_MIN=0` disables auto-close). Always run `stop.sh` proactively when finished.
5. **Black Screen Triage**: If screenshots are solid black (identical tiny JPEG byte size) or the floating card stays on "AI standby" with no video, take a **main-screen** screenshot to confirm, then run `stop.sh && start.sh` directly — **do not retry screenshots in a loop**. Since 0.11.0, `start.sh` detects and heals this automatically.

## Progressive Disclosure References
- [references/setup.md](references/setup.md): Local Wireless Debugging pairing and connectivity guide
- [references/takeover.md](references/takeover.md): Floating window gestures (long-press takeover, pinch zoom, edge docking) and HTTP 423 rules
- [references/accessibility.md](references/accessibility.md): Virtual display widget tree (`ui`) design, silent activation, and auto-healing
- [references/agent-api.md](references/agent-api.md): Built-in HTTP API (`127.0.0.1:28080`) endpoints and response schema
- [references/architecture.md](references/architecture.md): `scrcpy-server` + TCP Bridge + APK cross-process architecture

## Known Limitations
Verified on Google Pixel 4a (Android 13) and Pixel 6 (Android 17); virtual display widget tree via `ui` requires ADB `WRITE_SECURE_SETTINGS` (custom-drawn UI / games / Flutter require `shot`); unavailable while the phone is locked; video uses local loopback H.264; non-ASCII text injection overwrites the system clipboard.

## Directory Layout
`scripts/` (`start`, `stop`, `run-app`, `agent`, `install`, `common`, `device-run`), `assets/` (`skilled.apk`, `scrcpy-server.jar` 5.0.1, `skilled-shell.jar`, `VERSION`), `references/`. Source repository: https://github.com/OpenMinis/scrcpy-skilled
