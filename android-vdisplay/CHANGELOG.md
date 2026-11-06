# 更新说明

> **遇到任何错误，请先更新到最新版再试一次**：重新安装最新的 android-vdisplay 包后运行 `start.sh`，脚本会自动比较设备上 APK 与 skill 自带版本，不一致则重装。查看版本：`sh scripts/agent.sh version`（返回 skill 版本、设备 APK 版本、是否一致）。APK 也可直接查询：`/status` 与 `/version` 接口含 `version`、`versionCode`、`protocol`、`sdk`、`device`。

## 0.12.1
- `agent.sh ui` / `ui-tap` now heal a LOST accessibility service in the middle of a session: on "service not enabled" they re-enable it (append-only) and retry once, with a one-line note on stderr.
  Guard rails: only inside a session we started (between start.sh and stop.sh), at most once per 60 s (if it is switched off again right away, someone meant it), remembered as blocked when the system refuses the write (some vendor ROMs), and an explicit start.sh re-authorises.
- Fixed: a reused `start.sh` did not reset those flags.
- SKILL.md now tells the agent to inform the user before first use that a read-only accessibility service is added through adb.
- Tests: scripts/test/ui-heal.sh (13 checks); ui.sh case [8] updated.

## 0.12.0
- **Second-screen widget tree: `GET /ui` + `agent.sh ui` / `ui-tap`.** New read-only accessibility service `app.openminis.vdisplay/.UiService` reads the virtual display's windows through `getWindowsOnAllDisplays()` (verified on Pixel 4a, Android 13: Calculator on the second screen = 71 nodes, bounds in that display's space, main-screen windows not mixed in). Compact `lines` format (one node per line with centre point) or `json`; filters `find`, `clickable`, `editable`, `scrollable`, `limit`; coordinates in the 540-wide reference space so they go straight to `tap`.
- `/status` adds `displayId`, `serviceEnabled`, `serviceConnected`. Service not enabled -> HTTP 503 with a `hint`.
- `start.sh`/`install.sh` enable the service silently via `settings put secure enabled_accessibility_services` (APPEND only, idempotent, other services untouched; needs WRITE_SECURE_SETTINGS held by adb shell). `am force-stop` removes only our entry, so `start.sh` re-enables it each time.
- Nodes are `refresh()`ed before reading (otherwise EditText text can be stale). Idle service costs no CPU.
- Tests: scripts/test/ui.sh. SKILL.md shortest path now prefers `ui`, falling back to `shot` for games/WebView/Flutter/custom-drawn UI.

## 0.11.0
- **`ready` now means a picture was rendered.** The app counts frames the decoder actually produced (`rendered`); `/status` has `ready = connected && rendered>0`. `frames` keeps its old meaning (packets received) and `dropped`/`decodeErrors` were added. Fixes "ready:true but every screenshot is black".
- **Decoder no longer drops config/keyframes**: input-buffer timeouts are retried (up to ~500 ms) for config and key packets; if one still cannot be queued the app asks the server for a new keyframe (scrcpy RESET_VIDEO). Decoder exceptions are logged with their text. Output is drained on its own thread.
- **Surface ordering**: a video session that arrives before the Surface exists defers decoder start; a re-created TextureView re-attaches the running client to the new Surface instead of tearing the connection down.
- **start.sh self-heals**: after the display is up it waits up to 3 s for `rendered>0`; otherwise it saves logs and rebuilds once (`"healed":true`), then fails with `stage:"render"`.
- **start.sh reuses a healthy display** (`"reused":true`, ~1 s, same display id). `--fresh` / `VDISPLAY_FRESH=1` forces a rebuild. Display ids only increase within a boot; that is normal.
- **Evidence is preserved**: server.log, bridge.log and filtered logcat are copied to `~/.android-vdisplay/logs/<timestamp>/` (last 5) before an automatic restart, on failures, and by `stop.sh`.

## 0.10.0
- Idle auto-close: after 10 minutes with no agent request (status polling counts) and no touch on the window, the second screen exits by itself. The last minute shows a countdown in the title. Change with `IDLE_MIN=<minutes>` on `start.sh`; `IDLE_MIN=0` disables it. `/status` now reports `idleMs`, `idleLimitMs`, `closed` and `closedReason` ("user" or "idle timeout").
- Closing is idempotent (the watchdog could otherwise run it twice).
- start.sh/stop.sh only touch our own server (scid 76646973) and Bridge, never another scrcpy on the phone.
- Tests: scripts/test/idle.sh, idle-touch.sh, coexist.sh, gestures.sh.

## 0.9.0
- **Renamed**: package `app.openminis.vdisplay` (was me.openminis.skilled), skill `android-vdisplay` (was pip-display), state dir ~/.android-vdisplay. Android package names cannot contain hyphens.
- **Cold start 6.5 s → 2.1 s**: start.sh now makes one preflight call and one device-side `up` call (stop → server → bridge → overlay in dependency order with 50 ms polling) instead of ~12 adb round trips with 1 s sleeps. The device-side work itself is ~1.1 s.
- **Per-command overhead roughly halved**: agent.sh calls the forwarded HTTP port directly and only runs the adb health check/forward repair when that fails (tap 598 → ~190 ms over HTTP, ~300 ms end to end).
- **run-app.sh 1.9 s → ~0.4 s**: polls the foreground on the device every 100 ms instead of sleeping 1 s per try; a wrong package name now fails in ~350 ms.
- **Screenshots**: `agent.sh shot <file> [png|jpg|webp] [q]`; jpg is ~2x faster than png and ~4x smaller (540 wide: png 307 ms/236 KB, jpg 173 ms/64 KB).
- Cases not changed: scrcpy server startup (~0.5 s) and PNG encoding of full-size frames (~430 ms) are the remaining floors; `uiautomator dump` still ~2.3 s and cannot target the secondary display.

## 0.7.0
- start.sh reports per-stage timing in its result JSON: {"ms":{"preflight","server","bridge","overlay","ready","total"}}
- Agent API: new /ping (no-op, isolates transport cost); /screenshot adds an X-Timing-Ms header (capture/scale/encode)
- Benchmark: scripts/test/perf.py (+ perf-remote.sh); results in docs/perf-0.7.0.json
- Known limitation: `uiautomator dump --display N` ignores N and follows the focused display, so it cannot target the secondary display

## 0.6.8
- Closing the second screen (×) now fully exits the app process: no lingering background process, threads, or open agent port. Verified: after closing, app pid=none, scrcpy server/bridge gone, virtual display gone, port 28080 closed; starting again works.

## 0.6.7
- Long-press 1s (stationary) is now the ONLY way to take over — light taps, one-finger drags and two-finger pinches never take over, in both AI-working and standby states (8/8 gesture tests pass on Pixel 6)
- Two-finger pinch resizes and follows the fingers (the point under your fingers stays under them); window size clamped to 120dp … 85% of screen
- Buttons, title and hint scale with the window (clamped 0.75–1.15×); all top-bar controls share one height
- Center hint is plain outlined text (no capsule), localized
- Close-screen button (×) in standby, tap twice to confirm; closing ends the virtual display, scrcpy server and bridge
- Localization: English default, 简体中文, 繁體中文, 日本語, 한국어; app name "Minis Second Screen"
- Code comments translated to English

## 0.5.4
- 光晕改为 GPU 着色器（AGSL）一次绘制，每帧零分配，帧耗时约 12ms、无掉帧
- 内部光晕 = 屏幕呼吸灯：原地渐显渐隐，不再移动；向内的渐变用圆润等值线，中间没有直角镂空
- 旋转彩虹边框 + 绕行高光保留
- 右上角停止改为红色圆形图标按钮（无文字）
- AI 操作中：点击画面任意位置接管，拖动画面移动悬浮窗；中央提示随呼吸闪烁
- 标题胶囊带玻璃质感；圆角、默认窗口尺寸略缩小
- run-app.sh 修复 dumpsys 管道导致的卡死；start.sh 等待 server 更久并自动重试一次

## 0.3.6
- 悬浮窗靠近屏幕左右边缘松手 → 自动折叠吸附，只留一个带箭头的小拉手；点拉手展开，拉手可上下拖动
- 画面改用 TextureView，四角真正圆角；标题叠在画面上，不占高度
- 光晕：Siri / Apple Intelligence 风格，彩色柔光团沿边缘游走并向内铺满画面，运动更快；去掉外阴影，保留旋转彩虹边框
- AI 操作中居中显示「立即停止」「接管」两颗等大胶囊（带图标）；接管后显示「交还 AI」；立即停止后 agent 操作返回 423，直到用户点「交还 AI」
- 标题可由 agent 设置：`agent.sh title "正在做什么"`
- 虚拟屏默认与物理主屏同尺寸/dpi；截图与点击统一用参考宽度 540 的坐标（`REF_W` 可改），不用关心实际分辨率
- `start.sh`：自动选空闲端口（27183 被占用不再失败）、等待视频帧到达才返回、失败给出 stage/hint/log、自动比对并升级 APK
- `run-app.sh`：确认 App 真的在副屏前台；`agent.sh shot` 校验 PNG；adb 卡死自动换端口自愈
- `/status` 新增 `ready`、`frames`、`version`、`stopped`；新增 `/version`、`/title`、`/resume`

## 0.1.0
- 首个版本：scrcpy 虚拟屏 + 悬浮窗 + HTTP agent 接口
