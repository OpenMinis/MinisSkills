# 配对文件 (Pairing Record) 获取指南

连接 CoreDevice RSD 隧道需要合法的设备配对记录（Pairing File），用于通过苹果底层的 RemotePairing SRP/TLS 身份双向认证。

---

## 获取途径 (任选其一)

### 途径 1：从电脑端直接复制（最通用）
如果这台 iPhone 曾经连接过 Mac 或 Windows 电脑并点击过“信任此电脑”：
- **macOS**：配对文件保存在 `/var/db/lockdown/<UDID>.plist`；
- **Windows**：保存在 `%ProgramData%\Apple\Lockdown\<UDID>.plist`；
将该 `.plist` 文件复制到手机内部（例如保存为 `/var/minis/workspace/pairing.plist` 或放入配对目录），即可直接使用。

---

### 途径 2：通过 SideStore / SideInstaller 免电脑生成（全单机闭环）
如果手机上安装了 **SideStore** 或 **SideInstaller**：
1. 打开应用，按照提示生成本地配对文件；
2. 导出或共享出生成的 `pairing.plist`；
3. 将该文件放置在默认搜索路径下。

---

## 默认自动发现路径
`minis_device.py` 会按以下顺序自动搜索并加载配对文件，无需手动硬编码：
1. 显式传入的文件路径；
2. 环境变量 `MINIS_PAIRING_FILE` 指定的路径；
3. `/var/minis/workspace/*.plist`；
4. `/var/minis/mounts/*/*.plist`；
5. SideStore / SideInstaller 导出的配对目录。
