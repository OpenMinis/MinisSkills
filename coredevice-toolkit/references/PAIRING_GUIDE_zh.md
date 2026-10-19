# 设备配对记录指南与安全规范

**[English](PAIRING_GUIDE.md)** | **[中文说明](PAIRING_GUIDE_zh.md)**

连接 CoreDevice RSD 隧道需要一份有效的 remote pairing record（`.plist`），
用于通过 Apple RemotePairing 的 SRP/TLS 握手。

---

## ⚠️ 重要安全警告

> **配对记录包含高度敏感的设备凭据**：
> 配对文件里有设备的 **Ed25519 签名私钥** 和配对令牌。任何拿到这个文件的人，
> 都拥有该设备的开发者级调试权限。
>
> - **绝不公开**：不要上传到 GitHub、公共网盘或不可信的同步服务；
> - **严格权限**：只允许属主读写：
>   ```bash
>   chmod 600 /path/to/pairing.plist
>   ```
> - **会话保护**：CDTK 不打印配对私钥或 PSK。注意 `cdtk-install --password`
>   会把证书密码传给 `zsign` 的命令行，因此该密码（不是配对私钥）可能短暂
>   出现在 `ps` 中。

---

## 必需格式

`load_pairing()` 只读取三个顶层键：

```text
identifier   (字符串)
private_key  (bytes / data)
public_key   (bytes / data)
```

缺少任意一个，`find_pairing_file()` 都会跳过该文件。

可以这样检查候选文件：

```bash
python3 -c "import plistlib;print(sorted(plistlib.load(open('pairing.plist','rb')).keys()))"
```

---

## 获取配对记录（二选一）

### 方法 1：SideStore / SideInstaller（设备内生成）
如果设备上装有 **SideStore** 或 **SideInstaller**：
1. 打开 App，按提示生成本地配对文件；
2. 导出生成的 `pairing.plist`；
3. 放入 CDTK 支持的搜索路径（见下文）。

这是最简单的路径，且格式正确。

---

### 方法 2：在电脑上用 `pymobiledevice3` 生成
用 USB 连接 iPhone，在电脑上执行：

```bash
pip install pymobiledevice3
pymobiledevice3 remote pair
```

把生成的 `.plist` 传到设备。使用前确认它包含
`identifier`、`private_key`、`public_key` 三个键。

---

### 不支持：macOS 的 `lockdown` 记录
`/var/db/lockdown/<UDID>.plist` 是 **lockdown** 记录
（`HostCertificate`、`HostPrivateKey`、`RootCertificate` 等），
不含 `identifier` / `private_key` / `public_key`，CDTK 无法使用。
不要把它复制进配对目录。

---

## 安全存放路径与搜索顺序

CDTK 按以下顺序查找：

1. **显式 CLI 参数**（如 `cdtk-install --pairing /path/to/pairing.plist`）；
2. **环境变量 `CDTK_PAIRING_FILE`**；
3. **私有沙盒**：`/root/.cdtk/pairing/*.plist`；
4. **专用工作区目录**：`/var/minis/workspace/cdtk/*.plist`。

默认**不搜索**当前工作目录。确实需要时，设置
`CDTK_ALLOW_CWD_PAIRING=1`。

> ⚠️ **权限要求**：
> 配对文件权限过宽（`0644`）时，CDTK 会尝试收紧到 `0600`。
> 如果底层文件系统忽略 `chmod`（部分外接/共享目录），文件会被复制到
> `/root/.cdtk/pairing/` 并设为 `0600`。
