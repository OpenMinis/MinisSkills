---
name: shortcut-share-file
version: 2.1.1
description: 通过 iOS 快捷指令「极速分享」分享 iCloud Drive 文件。当用户提到"分享文件"、"传文件"、"发文件"、"分享给xxx"、"用快捷指令分享"、"发备份里的文件"等与分享文件相关的操作时触发。支持传递 iCloud Drive 备份目录下的任意文件路径给快捷指令。
---

# 分享文件 — 快捷指令「极速分享」

快捷指令链接：https://www.icloud.com/shortcuts/d044e04806a24ee18bb7360f8b3f802a

## 核心原则

- **零处理零检查**：不解压、不列出内容、不查看文件类型、不确认文件存在。直接走分享流程。
- **文件路径**：源文件在 iCloud 映射到 `/var/minis/mounts/iCloud/极速分享/`，参数传 `极速分享/<filename>`（相对路径，不要绝对路径）。
- **不需要时间参数**：上传完成先由本机监控确认，触发快捷指令时不传任何时间参数。

## 工作流程

### A. 拷贝文件（如需）

如果文件不在 `/var/minis/mounts/iCloud/极速分享/` 下：

```
cp <源文件路径> /var/minis/mounts/iCloud/极速分享/<filename>
```

- **从外部拷贝进来** → 继续执行 B（等待上传完成）
- **原本就在极速分享目录中** → 跳过 B，直接进入 C（已就位即已传输完成）

### B. 等待上传完成（仅新拷贝的文件需要）

刚拷贝进来的文件用监控脚本等待上传真正完成（检测 ctime 跳变信号）：

```
bash /var/minis/skills/shortcut-share-file/scripts/icloud_upload_watch.sh "极速分享/<filename>"
```

- 输出 `UPLOAD_OK` → 进入 C
- 输出 `TIMEOUT`（默认 600 秒）→ 重试一次；仍超时则告知用户「上传似乎未完成」，询问是否仍要触发
- 命令超时请设为脚本超时值（默认 600s）加缓冲；超大文件需更大

### C. 触发快捷指令

```
apple-open "shortcuts://run-shortcut?name=%E6%9E%81%E9%80%9F%E5%88%86%E4%BA%AB&input=text&text=%E6%9E%81%E9%80%9F%E5%88%86%E4%BA%AB/<filename>"
```

快捷指令无需等待，直接生成链接。

## 反馈用户

「上传已完成 ✓ 快捷指令已启动，链接稍后会自动复制到剪贴板，直接粘贴即可发送。」

---

## 捆绑资源

- [帮助文档](minis://skills/shortcut-share-file/references/%E5%B8%AE%E5%8A%A9%E6%96%87%E6%A1%A3.md) — 安装步骤、功能概览、使用指南，用户有疑问时提供
- [scripts/icloud_upload_watch.sh](minis://skills/shortcut-share-file/scripts/icloud_upload_watch.sh) — 上传完成监控脚本（ctime 信号）
