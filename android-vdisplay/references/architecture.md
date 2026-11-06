# 架构与实现要点

## 组件
| 组件 | 运行身份 | 作用 |
|---|---|---|
| scrcpy server (`scrcpy-server.jar`) | adb shell | 创建 **trusted 虚拟屏**（带系统装饰/输入法，默认与主屏同尺寸/dpi），H.264 编码，处理控制消息（触摸/按键/文字/启动 App） |
| Bridge (`skilled-shell.jar`，类 `app.openminis.vdisplay.Bridge`) | adb shell | TCP 桥：连 `@scrcpy_<scid>`（默认 `scid=76646973`，即 `"vdis"`），映射到 `127.0.0.1:<空闲端口>`（27183 起自动选择） |
| `skilled.apk`（包名 `app.openminis.vdisplay`） | 普通 App（悬浮窗 + 只读无障碍服务） | 连桥、解码 H.264 到圆角悬浮窗 `TextureView`（AGSL 呼吸灯流光边框）、处理手势（长按 1 秒接管、双指跟手缩放、边缘吸附折叠）、内置 `UiService` 读取副屏控件树、暴露本机 HTTP 接口(28080) |

## 为什么要 TCP 桥
普通 App 连 shell 进程创建的 abstract socket 会被 SELinux 拒绝（`Permission denied`，已实测），但可以连 `127.0.0.1` TCP。scrcpy server 因此保持零改动。

## 连接顺序
scrcpy 在 `tunnel_forward=true` 下按 **video → control** 顺序 accept，Bridge 与 APK 必须同序连接。流格式：`[dummy 1B][设备名 64B][codec id 4B]`，之后循环 `[12B 帧头 + payload]`；帧头 8B `ptsAndFlags`（bit63 session，bit62 config，bit61 keyframe）+ 4B 长度；session 头为 `flags(4)+w(4)+h(4)`。

## 虚拟屏参数与共存
- `new_display=WxH/dpi vd_system_decorations=true`；`cleanup=false power_off_on_close=false power_on=false stay_awake=false`，退出时不改主屏电源/常亮设置。
- 进程清理只匹配本项目 `scid`（默认 `76646973`）和 `app.openminis.vdisplay.Bridge`，不会误杀用户在电脑上运行的其它 scrcpy 会话。

## 从源码重新构建
仓库 `OpenMinis/scrcpy-skilled`：`scripts/build-scrcpy-server.sh`（本机编译 scrcpy server，手写 AIDL stub，因为 x86 的 aidl 在 ARM 上跑不了）、`scripts/build-apk.sh`。

## 已验证的坑
- shell 往虚拟屏 `am start` 需要虚拟屏带 `PUBLIC`，scrcpy 已带。
- 前台服务必须 5 秒内 `startForeground()`，否则进程被杀、虚拟屏消失。
- `SurfaceView` 无法被 View 的圆角 `Outline` 裁剪，改用 `TextureView` 才能裁出干净圆角并直接 `getBitmap()` 截图。
- `am force-stop` 会让系统从 `enabled_accessibility_services` 中移除本包条目，因此 `start.sh` 每次都会幂等追加。
- `/data/local/tmp` 根目录的 jar 会被系统或其它工具清理，放子目录 `/data/local/tmp/sc/`。
