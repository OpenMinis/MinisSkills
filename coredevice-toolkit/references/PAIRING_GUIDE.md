# 配对文件 (Pairing Record) 获取与安全防护指南

连接 CoreDevice RSD 隧道需要合法的设备配对记录（Pairing File），用于通过苹果底层的 RemotePairing SRP/TLS 身份双向认证。

---

## ⚠️ 重要安全警示 (Security Warning)

> **配对文件属于高危设备凭据**：  
> 配对文件内部包含该设备的 **Ed25519 签名私钥** 与配对凭证，拥有该文件即拥有对设备的开发者级调试权限。
> 
> - **严禁公开发布**：切勿将 `.plist` 上传至 GitHub、公开网盘或不受信任的第三方云同步空间；
> - **文件权限锁定**：强烈建议在 Linux 终端中为配对文件设置仅属主可读写权限：
>   ```bash
>   chmod 600 /path/to/pairing.plist
>   ```
> - **会话保护**：运行日志绝不会打印配对文件私钥与 PSK 密钥内容。

---

## 获取途径 (任选其一)

### 途径 1：从电脑端直接复制（最通用）
如果这台 iPhone 曾经连接过 Mac 或 Windows 电脑并点击过“信任此电脑”：
- **macOS**：配对文件保存在 `/var/db/lockdown/<UDID>.plist`；
- **Windows**：保存在 `%ProgramData%\Apple\Lockdown\<UDID>.plist`；
将该 `.plist` 文件复制到手机内部，建议保存在非云端同步路径（如本地私有目录或工作区），即可直接使用。

---

### 途径 2：通过 SideStore / SideInstaller 免电脑生成（全单机闭环）
如果手机上安装了 **SideStore** 或 **SideInstaller**：
1. 打开应用，按照提示生成本地配对文件；
2. 导出或共享出生成的 `pairing.plist`；
3. 将该文件放置在默认搜索路径下。

---

## 默认自动发现流水线
`coredevice_session.py` 会按以下优先级自动搜索并加载配对文件，无需手动硬编码：
1. 显式传入的文件路径（`pairing_file=...`）；
2. 环境变量 `CDTK_PAIRING_FILE` 指定的路径（兼容 `MINIS_PAIRING_FILE`）；
3. 本地工作区目录：`/var/minis/workspace/*.plist`；
4. 共享存储目录：`/var/minis/shared/*.plist`；
5. 用户挂载目录：`/var/minis/mounts/*/*.plist`。
