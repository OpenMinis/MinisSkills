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

## 推荐存储路径与自动发现规则

为防止私钥被其他自动化 Agent 或外部云同步盘随意检索泄露，本工具链已彻底废除全盘盲目搜索，仅支持以下安全发现顺序：

1. **显式传入的文件路径**（如 `cdtk-install --pairing /path/to/pairing.plist`）；
2. **环境变量 `CDTK_PAIRING_FILE`** 指定的路径（推荐在个人环境变量中配置）；
3. **专属工作区隔离子目录**：`/var/minis/workspace/cdtk/*.plist`。

> ⚠️ **严防泄露注意**：
> - **切勿** 将配对文件直接丢在 `/var/minis/shared`、`/var/minis/mounts/`（外部网盘/iCloud）等容易被多端自动同步或全盘遍历的目录；
> - 配对文件**必须**执行 `chmod 600`，若权限包含同机其他用户可读（Group/Other readable），底座将主动拦截拒绝启动。
