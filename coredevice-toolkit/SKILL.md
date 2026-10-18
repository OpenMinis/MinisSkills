---
name: coredevice-toolkit
description: "iOS 17+ 免电脑、免越狱、免 TestFlight CoreDevice RSD 极客工具链。利用 Surge 本地回环反射 (10.7.0.1=reflect) + Node.js TLS-PSK 桥接 + 纯用户态协议栈 (pmd-pytcp)，在 iPhone 单机内部建立苹果底层开发者通信隧道，提供侧载直装、全屏自动化、桌面整理、系统诊断、沙盒穿透、描述文件管理及崩溃分析全套 CLI 神器。触发词：CoreDevice, RSD, 免电脑侧载, 绕过电脑, minis-phone, minis-install, minis-profile, minis-ctrl, minis-fs, minis-diag, minis-crash, minis-inspect, 隧道, 本地回环。"
---

# CoreDevice RSD 极客工具箱 (iOS 17+ 单机开发者中枢)

本 Skill 将原本必须通过 USB 数据线连接 Mac/Xcode 才能调用的苹果底层开发者特权（CoreDevice RSD 加密隧道），通过 **Surge 本地回环反射 + 纯用户态网络协议栈** 完整搬迁至 iPhone 单机内部。

---

## 一、 前置准备与环境要求

1. **系统版本**：iOS 17.0+（含 iOS 18 / 26+），且在系统【设置 ➡️ 隐私与安全性】中已开启「开发者模式」；
2. **本地回环基建**：Surge 启用 `10.7.0.1 = reflect` 与 `tun-included-routes = 10.7.0.1/32`（详见 [Surge 回环配置指南](references/SURGE_LOOPBACK.md)）；
3. **配对文件**：手机与电脑配对生成的 `.plist` 文件或 SideStore 配对文件（详见 [配对文件指南](references/PAIRING_GUIDE.md)）；
4. **环境依赖**：Node.js、Python 3 及 `pymobiledevice3`、`pmd-pytcp`、`cryptography`。

---

## 二、 架构原理：单机莫比乌斯环 🔌🔄

```
┌────────────────────────────────────────────────────────────────────────┐
│                        iPhone 单机内部 (Non-Jailbroken)                 │
│                                                                        │
│   [ 应用层 / CLI 工具 ]                                                 │
│       │                                                                │
│       ▼                                                                │
│   minis_device.py (MinisDeviceSession 异步上下文管理器)                 │
│       │                                                                │
│       ├── Node.js TLS-PSK 桥接 (解决原生握手缺少 PSK 扩展痛点)          │
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

---

## 三、 专属核心 CLI 工具矩阵

通过本 Skill，系统全局交付 7 大开箱即用的命令行神器：

### 1. `minis-install`（免电脑侧载与自签直装）
- **功能**：自动发现证书（支持本地 P12 / 描述文件）、自动签名（可自定义 App 展现名称与 Bundle ID 避免冲突），并通过底层 `installation_proxy` 原生推流直装进入系统。
- **常用命令**：
  ```bash
  minis-install list                     # 查看全量已安装应用与元数据
  minis-install install app.ipa          # 原生签名并直装 IPA
  minis-install install app.ipa -b com.demo.app -n "小明Pro"  # 多开分身直装
  minis-install uninstall <bundle_id>    # 原生反注册卸载
  ```

### 2. `minis-phone`（iCTRL + 原生自动化合体控制中枢）
- **功能**：将 iCTRL 的“眼与手”（Accessibility 元素树、精准 ref 点击、平滑手势，100% 绕过 `backboardd` 物理认证丢弃锁）与 CoreDevice RSD 的“脑与命脉”（原生进程唤醒、0.1 秒不死鸟自愈保活）深度合体。
- **常用命令**：
  ```bash
  minis-phone status                     # 双通道状态诊断与不死鸟自愈检测
  minis-phone launch <app_name>          # 原生特权调起 App 并准备自动化
  minis-phone tree -f "搜索"              # 抓取当前界面结构化元素树
  minis-phone tap 195 422                # 坐标点击
  minis-phone tap "去结算"                # 智能识别文本并点击
  minis-phone swipe up                   # 原生平滑手势上滑刷视频
  minis-phone shot                       # 截屏并输出预览链接
  ```

### 3. `minis-profile`（免确认静默描述文件管理器）
- **功能**：基于 `com.apple.mobile.MCInstall.shim.remote`，彻底告别 Safari 弹窗 ➡️ 设置 ➡️ 输两遍密码确认的繁琐流程，免跳转一键管理证书与配置。
- **常用命令**：
  ```bash
  minis-profile list                     # 查看当前系统已安装的全部描述文件
  minis-profile install cert.mobileconfig# 协议层直接下发安装描述文件
  minis-profile remove <PayloadIdentifier># 一键静默移除指定描述文件
  ```

### 4. `minis-fs`（系统媒体与应用沙盒穿透管理器）
- **功能**：基于 `house_arrest`（VendContainer）和 `afc`，免越狱穿透第三方自签/开发 App 的私有沙盒，直读直写配置文件与数据库。
- **常用命令**：
  ```bash
  minis-fs media ls /                    # 查看系统相册/媒体分区文件
  minis-fs app ls <bundle_id> /Library   # 查看指定 App 私有沙盒结构
  minis-fs app pull <bundle_id> <remote_path> <local_path> # 导出沙盒文件 (如 SQLite)
  minis-fs app push <bundle_id> <local_path> <remote_path> # 将文件写入沙盒
  ```

### 5. `minis-diag`（电池硬件真实自检与系统日志捕获）
- **功能**：绕过 iOS 模糊算法，读取芯片底层真实电池循环次数、当前物理容量；捕获系统内核 syslog。
- **常用命令**：
  ```bash
  minis-diag hw                          # 输出真实电池循环、物理容量与健康度
  minis-diag log -f "Sandbox" -t 5       # 捕获 5 秒包含关键字的内核实时日志
  ```

### 6. `minis-crash`（系统闪退与崩溃日志透视器）
- **功能**：基于 `com.apple.crashreportcopymobile`，秒级解析系统深处生成的 `.ips` 崩溃日志与调用栈。
- **常用命令**：
  ```bash
  minis-crash list                       # 查看最近系统崩溃与诊断日志
  minis-crash view <ips_file>            # 查看崩溃线程调用栈与异常原因
  minis-crash pull <ips_file>            # 导出崩溃日志至本地
  minis-crash latest [app_name]          # 一键秒级定位最近一次闪退根因
  ```

### 7. `minis-inspect`（WebKit / H5 远程审查与脚本注入）
- **功能**：基于 `com.apple.webinspector.shim.remote`，后台挂载全系统 WebKit 渲染进程，执行 JavaScript。
- **常用命令**：
  ```bash
  minis-inspect list                     # 列出全机正在运行 WebKit 的应用与页面
  minis-inspect eval <page_id> "<code>"  # 向目标网页注入执行 JS 代码
  ```

---

## 四、 代码调用公共库 (Python)

所有自研脚本均可直接复用标准会话库：

```python
import asyncio
from minis_device import MinisDeviceSession

async def main():
    async with MinisDeviceSession() as s:
        # s.rsd 即为握手完毕的 RemoteServiceDiscoveryService 实例
        services = s.rsd.peer_info.get("Services", {})
        print(f"成功连通 CoreDevice RSD 隧道！可用底层服务数: {len(services)}")

asyncio.run(main())
```
