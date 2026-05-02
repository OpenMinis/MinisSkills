---
name: shortcut-share-file
version: 2.1.0
description: 通过 iOS 快捷指令「极速分享」分享 iCloud Drive 文件。当用户提到"分享文件"、"传文件"、"发文件"、"分享给xxx"、"用快捷指令分享"、"发备份里的文件"等与分享文件相关的操作时触发。支持传递 iCloud Drive 备份目录下的任意文件路径给快捷指令。
---

# 分享文件 — 快捷指令「极速分享」

快捷指令链接：https://www.icloud.com/shortcuts/05320f270ce34b01a728a7bc5f06955c

## 核心原则

- **零处理零检查**：不解压、不列出内容、不查看文件类型、不确认文件存在。直接走分享流程。
- **文件路径**：源文件在 iCloud 映射到 `/var/minis/mounts/iCloud/极速分享/`，参数传 `极速分享/<filename>`（相对路径，不要绝对路径）。

## 工作流程

### A. 测速（优先用记忆缓存）

```
memory_get(keywords="iperf3 测速 上传速度")
```

- 有记录且 24 小时内 → 直接用 `upload_MBs` 值
- 无记录或过期 → 执行：

```
iperf3 -c ping.online.net -t 3 --json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);bps=d['end']['sum_sent']['bits_per_second'];print(f'{bps/8000000:.2f}')"
```

输出为 MB/s（兆字节/秒），立即写入记忆：

```
memory_write(content="## 测速缓存\n- upload_MBs: <值> (<日期>)\n- 有效期为 24 小时")
```

### B. 拷贝文件（如需）并计算时间

如果文件不在 `/var/minis/mounts/iCloud/极速分享/` 下：

```
cp <源文件路径> /var/minis/mounts/iCloud/极速分享/<filename>
```

计算参数后缀：
- **来自 iCloud 其他目录** → `--0S`
- **来自 attachments 等外部来源** → `--<ceil(file_size_MB / upload_MBs * 1.2)>S`（加 20% 余量应对网络波动）

### C. 调用快捷指令

```
apple-open "shortcuts://run-shortcut?name=%E6%9E%81%E9%80%9F%E5%88%86%E4%BA%AB&input=text&text=%E6%9E%81%E9%80%9F%E5%88%86%E4%BA%AB/<filename>--<time>S"
```

## 反馈用户

「快捷指令已启动，完成后链接会自动复制到剪贴板，您可以直接粘贴发送。」

---

## 捆绑资源

- [帮助文档](minis://skills/shortcut-share-file/references/%E5%B8%AE%E5%8A%A9%E6%96%87%E6%A1%A3.md) — 安装步骤、功能概览、使用指南，用户有疑问时提供
