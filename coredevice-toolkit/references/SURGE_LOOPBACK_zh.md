# Surge 本地回环配置

**中文 | [English](SURGE_LOOPBACK.md)**

让 `cdtk-*` 在单机上连到 CoreDevice RSD 的前提：把 `10.7.0.1` 反射回本机。本仓库只验证过这一套配置。

---

## 配置

在 Surge 配置里加三行：

```ini
[General]
tun-included-routes = 10.7.0.1/32
always-raw-tcp-keywords = "Content-Type: application/pairing+tlv8"

[IP Rewrite]
10.7.0.1 = reflect
```

或者直接加载仓库里的模块文件 [`surge/local-loopback.sgmodule`](../surge/local-loopback.sgmodule)（内容是同样三行，
以那个文件为准，这里不再抄一遍）。

三行各自的作用：

- `tun-included-routes = 10.7.0.1/32` —— iOS 默认 `skip-proxy = 10.0.0.0/8` 会绕过 TUN，这条单主机路由把
  `10.7.0.1` 抓回来；
- `10.7.0.1 = reflect` —— 把发往该地址的连接反射回本机；
- `always-raw-tcp-keywords = …pairing+tlv8` —— 配对握手是二进制 TLV，别让 Surge 去做 TLS 解密。

这是额外新增的一条 `/32` 主机路由；其它分流规则、局域网和公网流量不受影响，但 Surge 的其它配置本身仍按你自己的规则生效。

---

## 验证

```bash
cdtk-doctor
```

第 4 步连端口，第 5 步做一次 Pair-Verify 握手 —— 只有第 5 步过了才算通。

`nc -zv 10.7.0.1 49152` 只能证明端口可达，不能证明 `remoted` 在答话。

---

## 注意

- Surge 5.23 以下的版本会静默丢掉 `[IP Rewrite]`：现象是任何端口都秒连，但一个字节也收不到。
- 手机需要连着 Wi-Fi；蜂窝网络下 49152 是关闭的。
- 同一时间只能有一个 VPN 生效。
