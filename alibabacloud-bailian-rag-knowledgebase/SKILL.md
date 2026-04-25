---
name: alibabacloud-bailian-rag-knowledgebase
description: >
  阿里云百炼知识库 RAG 检索与文件上传。当用户提到"知识库""百炼""阿里云知识库""私有文档""我的资料""上传到百炼""搜一下我的文档""知识库里"等任何与私有知识库
  相关的操作时，必须使用此技能。覆盖场景：检索知识库内容（"帮我查一下""搜一下""有没有提到""找一找合同里"
  "内部资料查""知识库里有吗"）、上传文件到知识库（"上传到知识库""添加到百炼""把这个文档传到知识库"）、
  以及任何需要从用户已上传的阿里云百炼文档中获取信息的请求。注意：即使用户没明确说"百炼"
  三个字，只要涉及"我的文档""内部资料""知识库"等私有知识库概念，就应触发此技能。
  Python SDK 实现，支持密集检索+Reranking，文件上传覆盖 20+ 格式含索引自动提交。
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

## 🔑 环境变量配置

### 凭证（AccessKey）
- [设置 ALIBABA_CLOUD_ACCESS_KEY_ID](minis://settings/environments?create_key=ALIBABA_CLOUD_ACCESS_KEY_ID&create_value=)
- [设置 ALIBABA_CLOUD_ACCESS_KEY_SECRET](minis://settings/environments?create_key=ALIBABA_CLOUD_ACCESS_KEY_SECRET&create_value=)

> ⚠️ 流程图直接以 Markdown 图片形式展示给用户，不要用 OCR/描述/分析图片内容，直接发图片即可。

![凭证AccessKey获取流程参考图](https://file.monika.host/Picture/High-definition%20original%20picture/IMG_7391.jpeg)

### 知识库定位
- [设置 DEFAULT_WORKSPACE_ID](minis://settings/environments?create_key=DEFAULT_WORKSPACE_ID&create_value=)
- [设置 DEFAULT_INDEX_ID](minis://settings/environments?create_key=DEFAULT_INDEX_ID&create_value=)

> ⚠️ 流程图直接以 Markdown 图片形式展示给用户，不要用 OCR/描述/分析图片内容，直接发图片即可。

![工作空间和索引ID 获取流程参考图](https://file.monika.host/Picture/High-definition%20original%20picture/IMG_7388.jpeg)

## ⚠️ 未出现问题，禁止检查环境，直接调用即可

### 上传文件到知识库
```bash
python3 scripts/upload_file.py /path/to/file.html
```
自动使用 `DEFAULT_WORKSPACE_ID` 和 `DEFAULT_INDEX_ID` 环境变量。如需指定索引：
```bash
python3 scripts/upload_file.py /path/to/file.html <index_id>
```

**支持格式**：pdf, doc, docx, txt, md, pptx, ppt, html, png, jpg, jpeg, bmp, gif, xls, xlsx, mp3, mp4, mov, avi 等。不支持 .js 等代码文件。

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
