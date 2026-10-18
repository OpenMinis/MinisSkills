# Surge 本地回环配置指南 (Local Device Loopback)

本模块是实现 iOS 17+ 免电脑、免 TestFlight VPN 权限在单机打通 CoreDevice RSD 隧道的**最核心前置基建**。

---

## 1. 原理
在正常情况下，普通 App 无法申请 `com.apple.developer.networking.networkextension` 专有开发包权限，因此无法在本地创建开发者专用的 VPN 虚拟网卡。
而 Surge 具备顶级的本地网络重写与 TUN 捕获能力。我们通过将目标 IP `10.7.0.1` 设置为 `reflect`（本地回环反射），并在 TUN 路由中强制捕获该 IP，从而在 iPhone 内部构建了一条“把原本插在电脑上的虚拟数据线插回手机自己”的无损通信环路。

---

## 2. Surge 配置方法

### 方法 A：在主配置文件中追加 (推荐)
打开 Surge 配置文件（如 `Default.conf`），在相应段落中添加以下行：

```ini
[General]
# 包含本地配对回环 IP（确保不被 skip-proxy 绕过）
tun-included-routes = 10.7.0.1/32

# 保持原生配对协议走原始 TCP，不进行 TLS 劫持
always-raw-tcp-keywords = "Content-Type: application/pairing+tlv8"

[IP Rewrite]
# 将发往 10.7.0.1 的所有请求在系统网络栈内反射回环
10.7.0.1 = reflect
```

### 方法 B：作为独立模块启用 (CoreDevice-Loopback.sgmodule)
创建并安装以下 Surge 模块：

```ini
#!name=CoreDevice RSD 本地回环反射
#!desc=免电脑、免 TestFlight 专享 VPN，在 iOS 单机建立 CoreDevice RSD 极客通信隧道

[General]
tun-included-routes = %APPEND% 10.7.0.1/32
always-raw-tcp-keywords = %APPEND% "Content-Type: application/pairing+tlv8"

[IP Rewrite]
10.7.0.1 = reflect
```

---

## 3. 验证生效
在终端中执行测试：
```bash
# 验证端口连通性（iOS 系统的 remoted 守护进程默认监听在 49152 端口）
nc -zv 10.7.0.1 49152
```
若返回 `open` 或成功连接，说明回环隧道已 100% 畅通！
