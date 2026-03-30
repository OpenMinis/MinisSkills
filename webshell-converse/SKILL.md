---
name: webshell-converse
version: 2.0.0
description: >
  通过 HTTP API (http://127.0.0.1:8080) 执行远程 Shell 命令。当用户提到"WebShell"、"http 命令"、
  "127.0.0.1:8080"、"admin123 token"、"远程执行命令"、"Web 终端"、"HTTP shell"时触发。
  无需额外依赖，纯 Python 实现，访问远程 iPadOS/越狱设备 shell。
compatibility: 纯 Python 3，无外部依赖
---

# WebShell Manager

## 快速开始

```bash
# 直接 URL 访问
curl "http://127.0.0.1:8080/?cmd=ls&token=admin123"

# 使用 web-ssh 工具
source ~/.profile && web-ssh "pwd"
```

## 安装 alias

添加到 `~/.profile`：

```bash
web-ssh() { python3 /var/minis/skills/webshell-converse/scripts/web-ssh.py "$@"; }
```

立即生效：`source ~/.profile`

## 使用方式

| 模式 | 命令 | 说明 |
|------|------|------|
| 单次命令 | `web-ssh "ls -la"` | 执行单条命令并返回结果 |
| 命令组合 | `web-ssh "whoami && pwd"` | 多条命令按序执行 |
| 交互模式 | `web-ssh` | 类似 SSH 客户端的交互式会话 |
| URL 直连 | `curl "http://127.0.0.1:8080/?cmd=<url-encoded>&token=admin123"` | 原始 HTTP API |

### 常用示例

```bash
web-ssh "pwd"                      # 当前工作目录
web-ssh "ls -la ~/Documents"       # 列出目录详情
web-ssh "cat file.txt"             # 读取文件内容
web-ssh "grep pattern file"        # 搜索文本
web-ssh "python3 script.py"        # 运行 Python 脚本
```

## API 规格

```
GET http://127.0.0.1:8080/?cmd=<命令>&token=admin123
```

**参数：**
- `cmd`: URL 编码后的 Shell 命令
- `token`: 认证令牌 (默认：admin123)

**响应：**
- HTML 页面，命令输出在 `<pre>` 标签内
- 可用正则 `/\<pre\>(.*?)\<\/pre\>/s` 提取内容

## 限制与注意事项

- ⏱️ **超时**: 30 秒（iOS 系统限制）
- ❌ **不可用命令**: `df`, `top`, `htop` 等部分 iOS 受限命令
- 🎯 **目标系统**: 远程 iPadOS (iPad16,6, M2 芯片)
- 🔐 **安全**: 仅本地 127.0.0.1 可访问

## 脚本说明

**位置**: `/var/minis/skills/webshell-converse/scripts/web-ssh.py`

**功能**:
- URL 编码命令参数
- 解析 HTML 响应提取 `<pre>` 内容
- 支持单次命令和交互模式
- 30 秒超时保护