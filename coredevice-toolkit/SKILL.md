---
name: coredevice-toolkit
description: "iOS 免电脑、免越狱 CoreDevice RSD 极客工具链 (CDTK)。利用 Surge / Loon / Stash / Shadowrocket / Egern / WireGuard 本地回环反射 (10.7.0.1=reflect) + Node.js TLS-PSK 桥接 + 纯用户态协议栈 (pmd-pytcp)，在 iPhone 单机内部建立苹果底层开发者通信隧道，提供本地开发侧载、原生进程调度、硬件诊断、沙盒管理、描述文件管理、环境自检体检及崩溃透视全套 CLI 工具。触发词：coredevice-toolkit, cdtk, cdtk-doctor, cdtk-install, cdtk-ctrl, cdtk-profile, cdtk-fs, cdtk-diag, cdtk-crash, cdtk-inspect, CoreDevice RSD。"
compatibility: "iOS 18.0+ (Verified), iOS 17.x (Experimental), Node.js, Python 3.10+, Surge / Loon / Stash / Shadowrocket / Egern / WireGuard"
---

# CoreDevice RSD 极客工具箱 (iOS 单机开发者中枢)

本 Skill 将原本必须通过 USB 数据线连接 Mac/Xcode 才能调用的苹果底层开发者特权（CoreDevice RSD 加密隧道），通过 **VPN 本地回环反射 (支持主流代理与 WireGuard) + 纯用户态网络协议栈** 完整搬迁至 iPhone 单机内部。

---

## 一、 前置准备与环境要求

1. **系统版本**：
   - **已实测验证 (Verified)**：iOS 18.0+（包含当前真机环境）；
   - **实验性支持 (Experimental)**：iOS 17.0 ~ 17.7（因部分小版本系统 remoted 守护进程可能仅监听 IPv6 Link-Local 或存在端口漂移，欢迎社区测试反馈）；
   - 需在系统【设置 ➡️ 隐私与安全性】中开启「开发者模式」；
2. **本地回环基建 (全面支持主流网络工具与免费 WireGuard)**：
   - 适配 **Surge、Loon、Stash (Clash)、Shadowrocket (小火箭)、Egern (小松鼠)** 以及免购买商业软件的官方开源 **WireGuard**；
   - 启用 `10.7.0.1/32` 回环反射（详见 [Surge 本地回环指南](references/SURGE_LOOPBACK_zh.md)）；
3. **配对文件**：手机与电脑配对生成的 `.plist` 文件或 SideStore 配对文件（详见 [配对文件指南](references/PAIRING_GUIDE.md)）；
4. **一键初始化**：在终端运行 `sh /var/minis/skills/coredevice-toolkit/scripts/setup.sh`，脚本自动采用 Alpine 预编译二进制 + 纯 Python 解压模式，0 编译 10 秒内完成安装并将全套 CLI 注册至全局路径。

---

## 二、 架构原理：单机莫比乌斯环 🔌🔄

```
┌────────────────────────────────────────────────────────────────────────┐
│                        iPhone 单机内部 (Non-Jailbroken)                 │
│                                                                        │
│   [ 应用层 / CLI 工具: cdtk-* ]                                         │
│       │                                                                │
│       ▼                                                                │
│   coredevice_session.py (CoreDeviceSession 异步上下文管理器)            │
│       │                                                                │
│       ├── Node.js TLS-PSK 桥接 (通过 stdin 安全投递 PSK，0 命令行泄露) │
│       ▼                                                                │
│   pmd-pytcp (纯用户态 TCP/IP 协议栈，无 root 免虚拟网卡拨号)            │
│       │                                                                │
│       ▼                                                                │
│   发往 10.7.0.1:49152 (目标：本地开发者配对服务)                         │
│       │                                                                │
│       ▼                                                                │
│   Surge IP Rewrite (10.7.0.1 = reflect 本地反射回环)                   │
│       │                                                                │
│       ▼                                                                │
│   iOS 系统内核守护进程: remoted / launchd (85 大官方 Remote Services)   │
└────────────────────────────────────────────────────────────────────────┘
```

### 依赖与上游 API 说明
- **用户态协议栈 (`UserspaceTun` & `UserspaceDialPlane`)**：iOS 环境下无 root 权限，无法创建内核级虚拟网卡（`utun` 设备节点）。本工具链采用 `pymobiledevice3` 原生提供的 `remote.userspace_tunnel` 与 `pmd-pytcp`（纯 Python 实现的 L2 协议栈），在内存中虚拟出 TCP/IP 握手层，实现非越狱环境下的用户态直接通信。
- **环境依赖版本**：
  - `python3` (>=3.10)
  - `nodejs` (>=18.0)
  - `pymobiledevice3` (>=11.34.0)
  - `pmd-pytcp` (>=0.1.0)
  - `cryptography` (>=41.0.0)

---

## 三、 专属核心 CLI 工具矩阵 (`cdtk-*`)

安装后可在终端直接调用以下 10 大全局命令行神器：

### 0. `cdtk-doctor`（环境体检医生与故障自愈诊断）
- **功能**：一键秒级检测系统运行时（Node.js / Python3）、核心协议栈、配对凭据与安全权限、本地回环网络通道及真机亮屏状态，对未通过项给出具体的复制粘贴解决指令。
- **常用命令**：
  ```bash
  cdtk-doctor                           # 一键体检并输出诊断建议与修复指令
  ```

### 1. `cdtk-install`（免电脑开发侧载与自签直装）
- **功能**：自动动态发现本地证书与描述文件、自动签名（支持自定义 App 展现名称与 Bundle ID 避免冲突），并通过底层 `installation_proxy` 原生推流直装进入系统。
- **常用命令**：
  ```bash
  cdtk-install list                     # 查看全量已安装应用与元数据
  cdtk-install install app.ipa          # 原生签名并直装 IPA
  cdtk-install install app.ipa -b com.demo.app -n "测试分身" -y # 多开分身直装
  cdtk-install uninstall <bundle_id> -y # 原生反注册卸载
  ```

### 2. `cdtk-ctrl`（原生应用生命周期与硬件触控控制）
- **功能**：基于 `com.apple.coredevice.appservice` 与 `dtuhidd`，免无障碍权限直接拉起/保活前后台 App，列出全系统 400+ 正在运行的进程，枚举物理触控/按键设备。
- **常用命令**：
  ```bash
  cdtk-ctrl launch <bundle_id>          # 原生拉起任意 App (如 com.apple.Preferences)
  cdtk-ctrl procs                       # 列出系统前后台正在运行的全部 App 进程
  cdtk-ctrl hid-list                    # 枚举底层硬件输入设备 (触摸屏/键盘/按键)
  cdtk-ctrl tap <x> <y>                 # 向物理屏幕注入底层硬件级触控点击
  cdtk-ctrl swipe <x1> <y1> <x2> <y2>   # 注入底层硬件级滑动轨迹
  ```

### 3. `cdtk-profile`（免确认静默描述文件管理器）
- **功能**：基于 `com.apple.mobile.MCInstall.shim.remote`，彻底告别 Safari 弹窗 ➡️ 设置 ➡️ 输两遍密码确认的繁琐流程，免跳转一键管理证书与配置。
- **常用命令**：
  ```bash
  cdtk-profile list                     # 查看当前系统已安装的全部描述文件
  cdtk-profile install cert.mobileconfig -y # 协议层直接下发安装描述文件
  cdtk-profile remove <PayloadIdentifier> -y # 静默移除指定的描述文件
  ```

### 4. `cdtk-fs`（免越狱应用沙盒穿透与媒体管理）
- **功能**：基于 `house_arrest`（沙盒软禁穿透服务）与 `afc`，免越狱穿透自签与开发 App 沙盒完整文件系统（`Documents`、`Library`、`tmp`），导出内部 SQLite 数据库，管理系统媒体分区。
- **常用命令**：
  ```bash
  cdtk-fs app ls <bundle_id> [/path]    # 查看应用沙盒内部完整目录树
  cdtk-fs app pull <bid> <rem> <loc>    # 提取沙盒文件 (如导出 App 内部数据库)
  cdtk-fs media ls [/path]              # 查看系统媒体分区 (相册/下载/图书)
  cdtk-fs media pull <rem> <loc>        # 从媒体分区拉取文件
  ```

### 5. `cdtk-diag`（硬件真实健康度与系统实时内核日志）
- **功能**：基于 `diagnostics_relay` 与 `syslog_relay`，绕过应用层伪装，直读电池出厂设计容量、真实循环次数与电芯电压，实时监听系统内核与沙盒级实时运行日志。
- **常用命令**：
  ```bash
  cdtk-diag hw                          # 读取真实电池硬件报告 (循环/容量/序列号)
  cdtk-diag log -f "CoreDevice" -t 10   # 实时监听 10 秒包含关键字的系统内核日志
  ```

### 6. `cdtk-crash`（系统深处崩溃与闪退日志透视器）
- **功能**：基于 `crashreportcopymobile` 协议，免电脑秒级拉取系统 `.ips` 崩溃与诊断日志，结构化解析异常代码（EXC_BAD_ACCESS）、终止原因与触发线程调用栈。
- **常用命令**：
  ```bash
  cdtk-crash list                       # 查看最近系统全量崩溃与 Jetsam 诊断日志
  cdtk-crash view <filename.ips>        # 结构化深度解析异常码与崩溃线程栈
  cdtk-crash pull <filename.ips>        # 导出原始崩溃日志到本地分析
  cdtk-crash latest [app_name]          # 一键速查最近一次闪退日志
  ```

### 7. `cdtk-inspect`（全局 WebKit / H5 / 小程序运行时穿透与 JS 注入）
- **功能**：基于 `com.apple.webinspector.shim.remote` 协议，跨进程穿透探测全系统活跃 WebKit 视窗，支持单机向目标页面注入任意 JavaScript 脚本执行、一键提取 Cookies 与 LocalStorage 存储凭据、以及远程控制页面跳转。
- **常用命令**：
  ```bash
  cdtk-inspect list                     # 列出全机所有开放调试的 Web 页面与 ID
  cdtk-inspect eval <page_id> "<js>"    # 向目标页面注入执行 JavaScript 脚本
  cdtk-inspect dump <page_id>           # 一键提取该页面的 Cookies 与 LocalStorage
  cdtk-inspect nav <page_id> <url>      # 控制目标页面跳转到指定网址
  ```

### 8. `cdtk-springboard`（主屏图标与文件夹原子级编排）
- **功能**：基于 `com.apple.springboard.iconstate` 协议，免越狱提取、备份、编排与热恢复 iOS 桌面主屏图标和文件夹布局。
- **常用命令**：
  ```bash
  cdtk-springboard get -o layout.plist  # 导出当前真实主屏布局 Plist 备份
  cdtk-springboard set layout.plist     # 一键热应用新桌面布局配置
  ```

### 9. `cdtk-proc`（iOS 原生进程特权与 Jetsam 内存查杀豁免中枢）
- **功能**：基于 DVT Instruments（`com.apple.instruments.dtservicehub`）与 `processcontrol` 核心服务，免电脑、免越狱为指定 App 申请内核级 Jetsam 内存查杀豁免（Memory Limit Waived），彻底杜绝虚拟机、大模型与后台重型任务因内存超限闪退；支持向底层进程注入系统控制信号。
- **常用命令**：
  ```bash
  cdtk-proc mem <bundle_id | pid>       # 一键豁免应用内存上限，彻底防杀后台
  cdtk-proc signal <bid | pid> stop     # 向底层进程注入暂停信号 (SIGSTOP)
  cdtk-proc signal <bid | pid> cont     # 恢复进程运行 (SIGCONT)
  ```

---

## 四、 安全规范与凭据防护机制 🛡️

1. **AI / 自动化调用最高安全准则 (Mandatory Safety Rule)**：
   - **绝对禁止静默执行修改**：在未向用户发起询问并获得明确聊天答复许可前，**严禁**执行任何安装/移除描述文件（`cdtk-profile install/remove`）、安装/卸载应用（`cdtk-install install/uninstall`）或覆写应用沙盒文件操作！
   - 只有在获得用户明确授权后，方可在命令行中附加 `-y / --yes` 执行。若无 `-y`，CLI 进程将主动输出阻断提示并安全退出（退出码 1）；
2. **配对文件（Private Key）强隔离与权限阻断**：
   - 配对文件 `.plist` 包含设备的 Ed25519 签名私钥，相当于全权设备信任凭据；
   - **禁止全盘盲目搜索**：工具链仅允许从显式参数、`CDTK_PAIRING_FILE` 或专用工作区目录 `/var/minis/workspace/cdtk/*.plist` 读取；
   - **强制权限拦截**：严禁加载权限过宽（Group / Other 可读）的配对文件！若文件权限不符合 `chmod 600`（属主独占只读/读写），底座将主动抛出 `PermissionError` 拒绝启动并提供阻断修复指引；
3. **进程间通信（IPC）零泄露与防僵尸回收**：
   - TLS-PSK 预共享密钥全部经由标准输入（`stdin`）安全传递给 Node 桥接进程，严禁通过命令行参数（`argv`）传递，避免系统进程表（`ps`）泄露；
   - Node 代理子进程监听 `stdin.on('close')` 与 `SIGTERM`，在父进程异常断开或退出时联动自动自毁；
   - 本地 Unix Domain Socket 部署在严格受限的 `0700` 专用私有临时目录中，会话生命周期结束后自动进行物理级清理。

---

## 五、 常见问题与排障指南 (Troubleshooting & FAQ) 💡

### Q1: 依赖安装时报错 `error: [Errno 2] No such file or directory: 'gcc'` 或 `Failed building wheel for sslpsk-pmd3`？
- **原因**：Alpine Linux (musllinux) 在 PyPI 上缺少该包的预编译 wheel，常规 pip 会尝试在本地调用 gcc 编译 C 扩展。但本工具链底层 TLS-PSK 握手完全由内置的 **Node.js 桥接 (`tls_psk_proxy.js`)** 接管，纯 Python 运行时**压根无需也不导入 `sslpsk-pmd3`**。
- **一键免编译解决（强烈推荐）**：无需安装 gcc，直接使用 Alpine 预编译库并以 `--no-deps` 跳过无用依赖即可秒级就绪：
  ```bash
  # 1. 安装 Alpine 预编译系统库 (1秒完成)
  apk add py3-cryptography py3-requests py3-pillow py3-psutil py3-tqdm py3-wsproto py3-hyperframe py3-packaging
  # 2. 免编译安装核心协议栈
  pip install --no-cache-dir --no-deps "pymobiledevice3>=11.34.0" pmd-pytcp
  # 3. 运行一键初始化
  sh /var/minis/skills/coredevice-toolkit/scripts/setup.sh
  ```
- **备选方案（本地完整编译）**：若确实需要本地完整构建，请先安装编译链：`apk add build-base gcc python3-dev openssl-dev` 后重试。

### Q2: 为什么安装依赖时一直在加载中、耗时很久？
- **原因**：通常是因为 pip 正在手机端模拟编译 C 模块。直接使用上述 Q1 的「免编译命令」，避开源码编译，10 秒内即可全部装好。

