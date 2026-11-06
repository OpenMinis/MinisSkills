# Architecture & Implementation Notes

## Components
| Component | Execution Identity | Role |
|---|---|---|
| `scrcpy-server` (`scrcpy-server.jar`) | ADB `shell` | Creates a **trusted virtual display** (with system decorations and IME, matching the main screen's resolution/DPI by default), encodes H.264, and handles control messages (touch, key, text, app launch) |
| Bridge (`skilled-shell.jar`, class `app.openminis.vdisplay.Bridge`) | ADB `shell` | TCP bridge: connects to `@scrcpy_<scid>` (default `scid=76646973`, ASCII `"vdis"`) and exposes it on `127.0.0.1:<free_port>` (auto-selected starting at `27183`) |
| `skilled.apk` (package `app.openminis.vdisplay`) | Normal App (Overlay + Read-Only Accessibility Service) | Connects to Bridge, decodes H.264 into a rounded `TextureView` card with AGSL breathing-light border, handles gestures (1 s long-press takeover, two-finger midpoint-anchored pinch zoom, edge docking), runs `UiService` to read the virtual display's widget tree, and serves the local HTTP API (`127.0.0.1:28080`) |

## Why a TCP Bridge Is Required
On Android, untrusted apps are blocked by SELinux (`Permission denied`) from connecting to abstract UNIX domain sockets created by the `shell` user, whereas loopback TCP connections to `127.0.0.1` are permitted. Using a lightweight TCP bridge in `shell` context allows `scrcpy-server.jar` to remain 100% unmodified.

## Connection Ordering & Wire Protocol
When `tunnel_forward=true`, `scrcpy-server` accepts connections sequentially in **video -> control** order; both Bridge and the APK must connect in that exact order. Stream format: `[dummy 1B][device_name 64B][codec_id 4B]`, followed by repeating `[12B frame_header + payload]` packets (`8B ptsAndFlags` with bit 63 = session, bit 62 = config, bit 61 = keyframe + `4B length`; session header is `flags(4)+w(4)+h(4)`).

## Virtual Display Parameters & Coexistence
- `new_display=WxH/dpi vd_system_decorations=true`; `cleanup=false power_off_on_close=false power_on=false stay_awake=false` so exiting never locks the physical screen or alters stay-awake settings.
- Process cleanup matches only our specific `scid` (default `76646973`) and `app.openminis.vdisplay.Bridge`, leaving any other `scrcpy` sessions started by the user untouched.

## Rebuilding from Source
Source repository `OpenMinis/scrcpy-skilled`:
- `scripts/build-scrcpy-server.sh`: Compiles `scrcpy-server` on-device using handwritten AIDL stubs (since Google's `x86_64` `aidl` binary cannot run directly on ARM64).
- `scripts/build-apk.sh`: Compiles resources, Java sources, and DEX for `skilled.apk` and `skilled-shell.jar`.

## Verified Pitfalls
- Launching activities onto a virtual display from `shell` requires the virtual display to carry the `PUBLIC` flag (included by `scrcpy-server`).
- A foreground service started via `am start-foreground-service` must call `startForeground()` within 5 seconds or Android kills the process and destroys the virtual display.
- `SurfaceView` punches through the window and ignores view-hierarchy rounded `Outline` clipping; `TextureView` is required for clean rounded corners and direct `getBitmap()` screenshots.
- `am force-stop` causes Android to remove our entry from `enabled_accessibility_services`, so `start.sh` idempotently appends it on every launch.
- Files placed directly under `/data/local/tmp/*.jar` may be cleaned up unexpectedly; store runtime artifacts in `/data/local/tmp/sc/`.
