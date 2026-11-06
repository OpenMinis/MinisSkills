# Agent 接口（APK 内置，127.0.0.1:28080）

APK 启动后在设备本机监听。电脑上用 `adb forward tcp:<本机端口> tcp:28080` 访问；设备内的 agent 直接访问 127.0.0.1:28080。坐标默认使用参考宽度 `ref=540`（高度按设备主屏比例等比换算，如 540×1170 / 540×1176），与 `/screenshot` 和 `/ui` 默认输出尺寸一致。

| 路径 | 说明 |
|---|---|
| `/status` | `{connected,ready,frames,rendered,dropped,decodeErrors,displayId,serviceEnabled,serviceConnected,width,height,closed,closedReason,idleMs,idleLimitMs,humanActive,manualTakeover,stopped,...}`，见下方 ready 语义 |
| `/version` | `{ok,app,version,versionCode,scrcpy,protocol,sdk,device}` |
| `/ui` | 只读副屏控件树（需无障碍服务，参数见下方） |
| `/screenshot` | `TextureView.getBitmap()` 抓取小窗画面。参数：`w=宽(默认540)`、`scale=0.1~1`、`fmt=png\|jpg\|webp`、`q=30~100`（jpg/webp 质量）。响应头 `X-Timing-Ms` 给出 capture/scale/encode 耗时 |
| `/ping` | 空操作，用来量传输开销 |
| `/tap?x=&y=&ref=540` | 点击（按参考宽度 `ref` 等比映射到虚拟屏真实分辨率） |
| `/swipe?x1=&y1=&x2=&y2=&ms=300&ref=540` | 滑动 |
| `/key?code=4` | 按键（Android keycode） |
| `/text?s=hello` | 输入文字（ASCII 逐字注入；含非 ASCII 自动走剪贴板粘贴） |
| `/start?pkg=com.android.chrome` | 在虚拟屏启动 App |
| `/title?s=文案` | 动态更新悬浮小窗顶栏任务标题 |
| `/window?x=&y=&w=<dp>` / `hide=1\|0` | 移动/缩放小窗；`hide=1` 移出屏幕且不可触摸（副屏继续运行，agent 仍可操作与截图）；`hide=0` 恢复 |
| `/takeover?on=1\|0` / `/resume` | 人类接管开关；`/resume` 解除用户接管或停止态 |

人类在小窗定点长按 1 秒（或点右上角停止按钮）进入接管，接管期间控制请求（`tap`/`swipe`/`key`/`text`/`start`）返回 HTTP 423，直到用户点击「交还 AI」（或调用 `/resume`）；仅在用户明确要求时才可加 `force=1` 绕过拦截。

## `ready` / `frames` / `rendered`（0.11.0）
- `frames`：从 scrcpy 视频流收到的**数据包**数（旧版 `ready` 的依据）。包到了不代表画面出来了：解码器可能没拿到 config/关键帧，或 Surface 失效，此时 `frames` 持续增长而截图是纯黑。
- `rendered`：解码器**真正输出并以 render=true 释放**的帧数。
- `ready = connected && rendered > 0`，即“已经画出过画面”。`start.sh` 以此为成功标准。
- `dropped`：因解码器输入缓冲超时而丢弃的包数（config/关键帧会重试约 500 ms，仍失败则向 server 发 RESET_VIDEO 要新关键帧）。`decodeErrors`：解码异常次数（原因在 `error` 与 logcat 的 `SKILLED` 标签）。
- Surface 销毁时 `rendered` 归零，新 Surface 绑定并出新画面后恢复。

## `GET /ui`（0.12.0，只读控件树，需无障碍服务）
`/status` 含 `displayId`（本副屏 id）、`serviceEnabled`、`serviceConnected`。`/ui` 只读：人类接管/Stop 期间也可用，并刷新闲置计时。
| 参数 | 说明 |
|---|---|
| `display=<id>\|all` | 默认本副屏；`all` 列出各屏窗口 |
| `ref=540` | 坐标参考宽度（同 /tap），高度按比例；每个节点带 `center` |
| `find=<text>` | 不分大小写子串，匹配 text / contentDescription / resource id；无匹配返回 `count=0` |
| `clickable=1` `editable=1` `scrollable=1` | 过滤 |
| `limit=N` | 默认 200 |
| `format=lines\|json` | 默认 lines：`[25] ImageButton desc="7" id=digit_7 click (6,605)-(134,733) c=(70,669)`；json 为 `items:[{i,d,p,class,text,desc,id,bounds,center,clickable,...}]` |
| `all=1` | 不过滤不可见/无信息节点 |
默认输出跳过不可见、零尺寸、无 text/desc 且不可点击/编辑/滚动的节点。服务未启用/未连接返回 HTTP 503：`{"ok":false,"error":..,"serviceEnabled":..,"serviceConnected":..,"hint":"<启用命令>"}`（`agent.sh ui` 遇到 503 会自动补回一次）；系统调用超过 5 s 返回 504。
实测字节数（540 参考坐标）：计算器 lines 3.5 KB / json 6.3 KB；设置 4.0 / 7.0 KB；Chrome 5.6 / 9.5 KB。延迟中位数 16 ms。
