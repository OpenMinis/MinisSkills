# 配对记录指南

**中文 | [English](PAIRING_GUIDE.md)**

RSD 隧道靠一份 RemotePairing 记录（`.plist`）完成 SRP / TLS 握手。这份文件相当于设备的开发者级凭据，按下面方式保管。

---

## 格式

`load_pairing()` 只认三个顶层键，缺一个就跳过：

- `identifier` —— 配对标识，同时用作 RSD 握手 UUID
- `private_key` —— Ed25519 私钥
- `public_key` —— Ed25519 公钥

检查候选文件：

```bash
python3 -c "import plistlib;print(sorted(plistlib.load(open('pairing.plist','rb'))))"
```

---

## 获取

在手机上开启「开发者模式」后，用下面任一 App 配对，再导出配对文件：

- **StikPair** —— 配对后从 App 内导出 `.plist`
- **wloc** —— 用户反馈同样能导出，本仓库未复现

导出的文件应当含上面三个键。其它方式（例如在电脑上用 `pymobiledevice3 remote pair`）本仓库没有验证过，需要时自己试。

### 配对记录什么时候会失效

**改锁屏密码**就足以让它失效。设备会丢弃所有在「密码状态不同」时注册过的 host，旧记录验签照样通过，但再也派生不出会话密钥。
iOS 27.3 实测：在设置锁屏密码之前导出的记录，设置密码之后表现为

```
cdtk-doctor 第 6 步: Pair-Verify 已通过，但设备对一切加密请求直接断连（0 字节）
cdtk-install list:  0 bytes read on a total of 9 expected bytes
```

Pair-Verify 只验 host 签名，所以旧记录前 5 步全绿、只在 `createListener` 挂掉。**任何改密码 / 恢复 / 重新配对之后都要重导一份**，
并先确认身份确实变了再怀疑回环：

```bash
python3 -c "import plistlib;print(plistlib.load(open('/root/.cdtk/pairing/rp_pairing_file.plist','rb'))['identifier'])"
```

`identifier` 是稳定 UUID，不是设备 UDID。新导出带的是另一个值，就是旧记录已死的证据 —— 先把旧的收好，再把新的按 `0600` 放进去。

> `lockdown` 记录（`/var/db/lockdown/<UDID>.plist`）不是配对记录：它存的是 `HostCertificate` /
> `HostPrivateKey` / `RootCertificate`，没有上面三个键，放进配对目录也用不了。

---

## 存放位置

`find_pairing_file()` 按这个顺序找：

1. 环境变量 `CDTK_PAIRING_FILE` 指向的文件（推荐）
2. `/root/.cdtk/pairing/*.plist`
3. `/var/minis/workspace/cdtk/*.plist`
4. 当前工作目录（仅当 `CDTK_ALLOW_CWD_PAIRING=1`）

第 3 个是 Minis 里所有会话共享的目录，权限 `0755`；把私钥放进去等于同机其它会话也能读，能不用就不用。
推荐只放在第 1 或第 2 个位置，且保持 `0600`。

---

## 权限

- 权限是 `0600`：直接使用；
- 权限过宽（如 `0644`）：能 `chmod` 就收紧到 `0600`；
- 文件系统忽略 `chmod`：复制到 `/root/.cdtk/pairing/` 再锁 `0600`。

---

## 安全

- 配对记录里是设备签名私钥，拿到它等于拿到开发者级调试权限。不要提交到仓库、不要上传网盘。
- CDTK 不打印私钥和 PSK。`cdtk-install --password` 会把**证书密码**（不是配对私钥）传给 `zsign` 命令行，
  可能短暂出现在 `ps` 里。
- `cdtk-doctor` 默认把设备标识符打码，`--show-udid` 才显示完整值；贴日志前仍建议删掉第 3 节。
