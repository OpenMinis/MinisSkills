# 副屏控件树（0.12.0 起可读：`agent.sh ui`）

## 现状（Pixel 4a, Android 13 实测）
APK 内置只读无障碍服务 `app.openminis.vdisplay/.UiService`，用 `getWindowsOnAllDisplays()`（API 30+，按 displayId 分组）读取**副屏**窗口树。`GET /ui`（脚本 `agent.sh ui`）只回答 127.0.0.1 的本机请求，不存盘、不上传。
- 计算器在副屏：71 个节点，坐标是副屏坐标系（1080x2340），接口按 `ref=540` 缩放后可直接给 `agent.sh tap`；每个节点附 `c=(x,y)` 中心点。
- 主屏窗口（SystemUI、Minis、悬浮窗）在 display 0，**不会混进**副屏结果；`ui display 0` 才看主屏，`ui all-displays` 列各屏窗口。
- 节点可读：text、contentDescription、resource id（短名）、bounds、clickable/editable/scrollable/enabled/checked/selected/focusable。已验证用 `/ui` 读出 37×42 的结果 1554，无需截图。
- 注意：有些节点（如计算器的显示框）文字在刷新前会是旧值，服务对每个节点先 `refresh()` 再读，所以读到的是当前值。

## 怎么启用（无需用户点设置）
`start.sh` / `install.sh` 自动执行 `settings put secure enabled_accessibility_services <原值>:app.openminis.vdisplay/app.openminis.vdisplay.UiService` + `accessibility_enabled 1`（adb shell 有 WRITE_SECURE_SETTINGS）。**只追加**、幂等、不碰其他服务；`stop.sh`/`start.sh` 里的 `am force-stop` 只会让系统摘掉本服务条目（其他服务保留），所以每次 `start.sh` 都会重新启用并等待 `serviceConnected:true`。仅在 Pixel 4a（Android 13）测过；其他厂商若限制 secure settings，`/status` 的 `serviceEnabled` 会是 false，`/ui` 返回 503 + `hint`，这时退回截图。
闲置时服务零 CPU（实测 15 s 内 0 tick，约 50 MB 常驻，12 线程）；关闭副屏后服务进程可能留着，无害。

### 服务中途丢失怎么办（0.12.1 起自动处理）
服务可能因用户手动关闭、`am force-stop`、设置被重置等原因丢失（实测：删掉设置条目后 `ui` 返回 503；进程被 `am kill` 则系统会自动拉起，无需处理）。`agent.sh ui` / `ui-tap` 遇到「服务未启用」会**自动补回一次并重试**，并在 stderr 打一行说明。为了不和用户对着干，补回有四条限制：
1. 只在本技能启动的会话里补（`start.sh` 之后、`stop.sh` 之前）；会话外绝不改系统设置。
2. 60 秒内最多一次；刚补完又被关掉，说明有人故意关，就不再补，直接报 503。
3. 系统拒绝写入（部分国产 ROM 拦截 `settings put secure`）时，记下 `ui_blocked`，本会话不再尝试，提示改用 `shot`。
4. 重新 `start.sh` 视为重新授权，清掉以上标记。
**agent 看到 503 时**：先看 hint；若提示已无法补回，不要反复重试，退回 `shot` 并告诉用户可在系统「无障碍」里手动开启「Minis 副屏」。

## 用法（推荐）
```sh
sh $SK/agent.sh ui                       # 一行一个节点：[25] ImageButton desc="7" id=digit_7 click (6,605)-(134,733) c=(70,669)
sh $SK/agent.sh ui find 7                # 文字/描述/id 子串匹配（不分大小写）；没有匹配 count=0，不是错误
sh $SK/agent.sh ui clickable | editable | scrollable | json | limit N | display N | all-displays
sh $SK/agent.sh ui-tap 7                 # 精确匹配优先；唯一目标才点；多个不同目标只列出不点
```
`ui` 为空或不够用时（游戏、WebView、Flutter、自绘 UI 常常没有节点）用 `shot` + 像素坐标。操作后用 `ui find <结果框>` 验证即可，不必每步截图。

## 历史实测（别再浪费调用）
- Minis 的 `android-a11y-cli ui dump --display <ID>` / `--package` / `ui find --text` 都忽略 display，永远返回主屏 45 个节点；`ui info` 的 windows 也只有主屏。（Minis 1.16-beta.3 测试时如此。）
- `uiautomator dump --display <ID>` 同样被忽略，返回主屏。
- 不要再试这两个；用 `agent.sh ui`。若 `/ui` 返回 503，按 hint 启用，或用截图。
