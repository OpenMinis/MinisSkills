# Surge 本地回环配置指南 (Surge Loopback Guide)

**[English](SURGE_LOOPBACK.md)** | **[中文说明](SURGE_LOOPBACK_zh.md)**

本模块是实现 iOS 免电脑在单机打通 CoreDevice RSD 隧道的网络前置基建之一。

---

## 1. 原理
在正常情况下，普通 App 无法申请专有网络开发扩展权限，因此无法在本地创建开发者专用的 VPN 虚拟网卡。
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

### 方法 B：作为独立模块启用
若使用模块管理，可创建模块内容如下：

```ini
#!name=CoreDevice RSD Local Loopback
#!desc=启用 iOS 单机 CoreDevice RSD 开发者隧道本地回环反射

[General]
tun-included-routes = %APPEND% 10.7.0.1/32
always-raw-tcp-keywords = %APPEND% "Content-Type: application/pairing+tlv8"

[IP Rewrite]
10.7.0.1 = reflect
```

---

## 3. 配置副作用与安全性释疑 (Side Effects Analysis)

1. **`tun-included-routes = 10.7.0.1/32` 的副作用**：
   - **作用**：iOS 常见的默认配置会将 `skip-proxy = 10.0.0.0/8`，导致发往 `10.7.0.1` 的请求被系统底层直接绕过 TUN。添加该单点 `/32` 主机路由仅强制捕获发往 `10.7.0.1` 这一个保留地址的流量；
   - **影响范围**：**严格限制在 10.7.0.1**，对正常的私有局域网（192.168.x.x / 172.16.x.x）、公网互联网流量及其他分流策略组**零干扰、无副作用**。
2. **`always-raw-tcp-keywords = "Content-Type: application/pairing+tlv8"` 的副作用**：
   - **作用**：告诉 Surge 在进行通用 TCP/TLS 流量嗅探时，若报文中含有苹果配对协议特有的 `application/pairing+tlv8` 内容类型，则保持原始二进制 TCP 流透传，不尝试对其进行 MitM 证书解密；
   - **影响范围**：由于常规互联网 HTTPS 流量与网页绝不会使用该专有 Content-Type，因此**绝不影响正常的 HTTPS 抓包、网页解密与脚本重写功能**。

---

## 4. 验证生效
在终端中执行体检医生：
```bash
cdtk-doctor
```
或直接测试端口：
```bash
nc -zv 10.7.0.1 49152
```
若返回 `open` 或成功连接，只说明端口可达；还需 `cdtk-doctor` 的 Pair-Verify 握手检查通过。
