# Agent HTTP API (Built-In APK Server, `127.0.0.1:28080`)

Once the overlay APK starts, it listens on `127.0.0.1:28080` on the device. From a host computer, use `adb forward tcp:<local_port> tcp:28080`; from inside Minis on the phone, connect to `127.0.0.1:28080` directly (or via `agent.sh`). Coordinates default to reference width `ref=540` (height scaled proportionally to the physical screen aspect ratio, e.g. `540x1170` or `540x1176`), matching the default output of `/screenshot` and `/ui`.

| Endpoint | Description |
|---|---|
| `/status` | `{connected,ready,frames,rendered,dropped,decodeErrors,displayId,serviceEnabled,serviceConnected,width,height,closed,closedReason,idleMs,idleLimitMs,humanActive,manualTakeover,stopped,...}` — see `ready` semantics below |
| `/version` | `{ok,app,version,versionCode,scrcpy,protocol,sdk,device}` |
| `/ui` | Read-only virtual display widget tree (requires accessibility service; parameters below) |
| `/screenshot` | Captures the floating card via `TextureView.getBitmap()`. Params: `w=<width(default 540)>`, `scale=0.1~1`, `fmt=png\|jpg\|webp`, `q=30~100` (for jpg/webp). Response header `X-Timing-Ms` reports `capture/scale/encode` latency |
| `/ping` | No-op endpoint used to measure baseline transport overhead |
| `/tap?x=&y=&ref=540` | Tap at `(x, y)` (scaled proportionally from reference width `ref` to the virtual display's native resolution) |
| `/swipe?x1=&y1=&x2=&y2=&ms=300&ref=540` | Swipe from `(x1, y1)` to `(x2, y2)` over `ms` milliseconds |
| `/key?code=4` | Inject Android keycode (`4`=BACK, `3`=HOME, `66`=ENTER, `67`=DEL) |
| `/text?s=hello` | Inject text (ASCII injected character by character; non-ASCII pasted via system clipboard) |
| `/start?pkg=com.android.chrome` | Launch an application on the virtual display |
| `/title?s=Label` | Dynamically update the top-bar task pill on the floating window |
| `/window?x=&y=&w=<dp>` / `hide=1\|0` | Move/resize the floating card; `hide=1` moves it off-screen and makes it untouchable while keeping the virtual display active; `hide=0` restores it |
| `/takeover?on=1\|0` / `/resume` | Toggle human takeover; `/resume` clears human takeover or stopped state |

When the user stationary long-presses the floating card for 1 second (or taps the top-right Stop button), human takeover begins and all control endpoints (`tap`, `swipe`, `key`, `text`, `start`) return **HTTP 423** until the user taps **Hand back to AI** (or `/resume` is called). Pass `force=1` only when the user explicitly instructs the agent to override takeover.

## `ready` / `frames` / `rendered` (`v0.11.0+`)
- `frames`: Number of video **packets** received from the scrcpy stream (used as `ready` in older versions). Receiving packets does not guarantee a visible picture: if the decoder misses the config/keyframe packet or the Surface is not ready, `frames` increments while screenshots remain black.
- `rendered`: Number of frames **actually decoded and released with `render=true`**.
- `ready = connected && rendered > 0` ("at least one frame has been drawn"). `start.sh` requires `ready:true` before succeeding.
- `dropped`: Packets dropped due to decoder input-buffer timeouts (config and keyframe packets retry for up to ~500 ms and send scrcpy `RESET_VIDEO` if still unable to queue). `decodeErrors`: Decoder exception count (details in `error` and logcat tag `SKILLED`).
- When the Surface is destroyed, `rendered` resets to `0` and recovers once a new Surface is attached and rendered.

## `GET /ui` (`v0.12.0+`, Read-Only Widget Tree)
`/status` exposes `displayId` (our virtual display ID), `serviceEnabled`, and `serviceConnected`. `/ui` is read-only: it remains available during human takeover or Stop state and refreshes the idle timer.

| Parameter | Description |
|---|---|
| `display=<id>\|all` | Defaults to our virtual display; `all` lists windows across all displays |
| `ref=540` | Reference coordinate width (same as `/tap`), height scaled proportionally; every node includes `center` |
| `find=<text>` | Case-insensitive substring match against `text`, `contentDescription`, or `resource id`; returns `count=0` when unmatched |
| `clickable=1` `editable=1` `scrollable=1` | Filter by node capability |
| `limit=N` | Maximum nodes returned (default `200`) |
| `format=lines\|json` | Default `lines`: `[25] ImageButton desc="7" id=digit_7 click (6,605)-(134,733) c=(70,669)`; `json` returns `items:[{i,d,p,class,text,desc,id,bounds,center,clickable,...}]` |
| `all=1` | Disable filtering of invisible or uninformative container nodes |

By default, `/ui` skips nodes that are invisible, zero-sized, or lack text/description while not being clickable/editable/scrollable. If the accessibility service is disabled or disconnected, `/ui` returns HTTP 503 (`{"ok":false,"error":..,"serviceEnabled":..,"serviceConnected":..,"hint":"<enable_cmd>"}`, which `agent.sh ui` heals automatically once); if the system call takes longer than 5 s, it returns HTTP 504.
Measured payload sizes (`ref=540`): Calculator `lines` 3.5 KB / `json` 6.3 KB; Settings 4.0 KB / 7.0 KB; Chrome 5.6 KB / 9.5 KB. Median latency: 16 ms.
