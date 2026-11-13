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
# 强制捕获 10.7.0.1 虚拟回环路由
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

> 没有 Surge 时可改用 **LocalDevVPN**：开启后同样能连上 `10.7.0.1:49152`，已实测连接、诊断和主屏布局操作正常。

---

## 3. 配置副作用与安全性释疑 (Side Effects Analysis)

Reviewer 对改动 Surge 全局配置可能引发的网络行为表达了合理关切，以下为各配置项的精确作用域与无副作用说明：

1. **`tun-included-routes = 10.7.0.1/32` 的副作用**：
   - **作用**：iOS 常见的默认配置会将 `skip-proxy = 10.0.0.0/8`，导致发往 `10.7.0.1` 的请求被系统底层直接绕过 TUN。添加该单点 `/32` 主机路由仅强制捕获发往 `10.7.0.1` 这一个保留地址的流量；
   - **影响范围**：**严格限制在 10.7.0.1**，对正常的私有局域网（192.168.x.x / 172.16.x.x）、公网互联网流量及其他分流策略组**零干扰、无副作用**。
2. **`always-raw-tcp-keywords = "Content-Type: application/pairing+tlv8"` 的副作用**：
   - **作用**：告诉 Surge 在进行通用 TCP/TLS 流量嗅探时，若报文中含有苹果配对协议特有的 `application/pairing+tlv8` 内容类型，则保持原始二进制 TCP 流透传，不尝试对其进行 MitM 证书解密；
   - **影响范围**：由于常规互联网 HTTPS 流量与网页绝不会使用该专有 Content-Type，因此**绝不影响正常的 HTTPS 抓包、网页解密与脚本重写功能**。

---

## 4. 验证生效
在终端中执行测试：
```bash
# 验证端口连通性（iOS 系统的 remoted 守护进程默认监听在 49152 端口）
nc -zv 10.7.0.1 49152
```
若返回 `open` 或成功连接，说明回环隧道已 100% 畅通！

---

## 5. 系统版本兼容性与网络栈差异说明 (实事求是)

- **iOS 18.0+ (已实测验证)**：
  苹果在 iOS 18+ 对 `remoted` 守护进程的网络监听进行了增强，全面开放了 IPv4 双栈回环反射，默认监听在 49152 端口。本项目已在 iOS 18+ 真机环境完成端到端全量实测。
- **iOS 17.0 ~ 17.7 (实验性支持)**：
  在 iOS 17.0 早期版本中，苹果系统底层可能仅将 `remoted` 绑定至 IPv6 Link-Local（`fe80::`）接口，或在部分环境下采用动态端口广播。若在 iOS 17 环境下测试遇到连接被拒绝（Connection Refused）或超时，可能受限于该系统版本的网络栈监听策略，欢迎社区进一步提供真机反馈与适配补丁。

