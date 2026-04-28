---
name: alibabacloud-bailian-rag-knowledgebase
description: >
  阿里云百炼知识库 RAG 检索与文件上传。当用户明确提到"百炼""阿里云知识库""百炼知识库"等与百炼服务相关的操作时，使用此技能。覆盖场景：检索已配置的百炼知识库内容、上传文件到百炼知识库。
---

# 阿里云百炼 RAG 知识库检索 (Python版)

## 📁 可用脚本

所有脚本位于 `scripts/` 目录：

| 脚本 | 用途 | 参数 | 备注 |
|------|------|------|------|
| `check_env.py` | **环境检查** — 验证凭证、SDK、API连通性 | 无参数 | 无异常禁止使用 |
| `quick_retrieve.py` | **快速检索**（推荐） | `<query> [top_k]` | 自动读取 env 中的 workspace/index ID |
| `retrieve.py` | 完整检索 | `workspaceId indexId query [top_k]` | 自定义 workspace + index，支持 reranking |
| `upload_file.py` | **上传文件到知识库** | `<文件路径> [index_id]` | 完整 4 步流程：租约→上传→AddFile→入索引 |

## ⚠️ 隐私声明

使用此技能前，请了解以下数据处理方式：

- **检索操作**：用户查询和返回的文档片段、文件名、文件路径会发送至阿里云百炼服务
- **上传操作**：选定的整个本地文件会上传至阿里云 OSS 存储
- **数据保留**：数据按阿里云百炼服务条款保留

如不同意上述条款，请勿使用此技能。

## 🚀 使用方法

### 默认检索（推荐）
```bash
python3 scripts/quick_retrieve.py "你的查询" 10
```
自动使用环境变量中的 `DEFAULT_WORKSPACE_ID` 和 `DEFAULT_INDEX_ID`。

### 指定工作空间和知识库
```bash
python3 scripts/retrieve.py <workspaceId> <indexId> "你的查询" 10
```

## 🔧 依赖安装

### 方式 1：使用虚拟环境（推荐）
```bash
cd /var/minis/skills/alibabacloud-bailian-rag-knowledgebase
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 方式 2：使用 Alpine 原生包（iSH/Minis 环境）
```bash
apk add py3-requests
pip install alibabacloud-bailian20231229 alibabacloud-tea-openapi alibabacloud-tea-util
```

> ⚠️ 避免全局安装 Python 包。使用虚拟环境或 Alpine 原生包可防止污染系统环境。

## 🔑 环境变量配置

### 凭证（AccessKey）
- [设置 ALIBABA_CLOUD_ACCESS_KEY_ID](minis://settings/environments?create_key=ALIBABA_CLOUD_ACCESS_KEY_ID&create_value=)
- [设置 ALIBABA_CLOUD_ACCESS_KEY_SECRET](minis://settings/environments?create_key=ALIBABA_CLOUD_ACCESS_KEY_SECRET&create_value=)

> 获取 AccessKey：登录 [阿里云控制台](https://ram.aliyun.com/manage/ak) → 访问控制 → 用户 → 创建 AccessKey

### 知识库定位
- [设置 DEFAULT_WORKSPACE_ID](minis://settings/environments?create_key=DEFAULT_WORKSPACE_ID&create_value=)
- [设置 DEFAULT_INDEX_ID](minis://settings/environments?create_key=DEFAULT_INDEX_ID&create_value=)

> 获取工作空间和索引 ID：登录 [阿里云百炼控制台](https://bailian.console.aliyun.com/) → 工作空间 → 知识库 → 复制相应 ID

## ⚠️ 未出现问题，禁止检查环境，直接调用即可

### 上传文件到知识库

> ⚠️ **用户确认**：上传前，请确认你同意将整个文件发送至阿里云 OSS 存储。

```bash
python3 scripts/upload_file.py /path/to/file.html
```
自动使用 `DEFAULT_WORKSPACE_ID` 和 `DEFAULT_INDEX_ID` 环境变量。如需指定索引：
```bash
python3 scripts/upload_file.py /path/to/file.html <index_id>
```

**支持格式**：pdf, doc, docx, txt, md, pptx, ppt, html, png, jpg, jpeg, bmp, gif, xls, xlsx, mp3, mp4, mov, avi 等。

**文件限制**：
- 最大文件大小：100 MB
- 文件路径必须在允许的目录内：`/var/minis/`, `/tmp/`, 用户主目录
- 不支持代码文件（.js, .py 等）

**上传流程**：`ApplyFileUploadLease → PUT OSS → AddFile → SubmitIndexAddDocumentsJob`

| 现象 | 原因 | 解决 |
|------|------|------|
| 凭证缺失报错 | 未设置 AccessKey | 检查 `ALIBABA_CLOUD_ACCESS_KEY_ID` / `_SECRET` |
| 403 NoWorkspacePermissions | 权限不足或 ID 错误 | 检查 RAM 授权 & 百炼控制台权限；或先用 `list_indices.py <workspaceId>` 验证 ID 是否有效 |
| 连接超时 | 网络问题 | 确认 `ALIBABA_CLOUD_REGION` 正确（默认 cn-beijing） |

## 💡 提示
- 返回结果为 JSON，按 `score` 降序排列，优先关注高分片段
- 多知识库时合并结果并去重
- 凭证通过环境变量传递，不要在脚本中硬编码
