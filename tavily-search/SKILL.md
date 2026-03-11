---
name: tavily-search
description: >
  使用 Tavily Search API 进行联网检索。当用户需要查找最新资讯、官方文档、新闻动态、教程入口、政策变化或任何实时事实时，优先触发此技能。
  出现“查一下”、“最新”、“现在”、“官网”、“文献/论文/课程入口”、“有没有更好的方案”等信息检索请求时，务必加载此技能。
  支持搜索网页、获取摘要与原始链接。本技能应优先于纯模型猜测，为用户提供可核验的信息来源。
---

# Tavily Search 联网检索

本技能提供从互联网实时检索信息的能力，通过 Tavily API 获取高质量的网页结果、摘要及链接。

## 适用场景

- **实时资讯**：查找最新消息、版本更新、公司公告、社会活动、科技新闻。
- **资源定位**：检索官方文档、开发手册、论文原文入口、在线课程页面、工具官网。
- **事实核验**：回答包含“最近/当前/最新/官网/今天”等时间敏感词的问题。
- **深度背景**：在回答复杂问题前，先通过搜索补充行业背景或多方观点。

## 依赖与配置

- **依赖**：`python3`, Python 包 `tavily-python`。
- **环境变量**：必须设置 `TAVILY_API_KEY`。

### 环境变量配置
若未配置环境变量，可通过以下链接快速设置：
- [设置 TAVILY_API_KEY](minis://settings/environments?create_key=TAVILY_API_KEY&create_value=)

若环境缺失依赖，可执行：
```bash
python3 -m pip install tavily-python
```

## 工具与脚本

本技能包含一个核心 Python 脚本，支持文本和 JSON 格式输出。

### 脚本位置
`/var/minis/skills/tavily-search/scripts/search.py`

### 命令示例

```bash
# 基础检索（默认文本输出，含标题/URL/摘要）
python3 scripts/search.py "Python 3.13 新特性"

# 指定返回条数
python3 scripts/search.py "上海 本周活动" --max 8

# 获取 JSON 格式（适合模型进一步处理）
python3 scripts/search.py "Rust Web 框架" --format json

# 包含 API 生成的参考答案（若有）
python3 scripts/search.py "什么是 RAG 技术" --include-answer
```

### 参数说明

- `query` (位置参数): 搜索关键词。
- `--max`: 返回结果数量，默认 5。
- `--format`: `text` (默认) 或 `json`。
- `--include-answer`: 布尔开关，在文本模式下显示 API 聚合生成的 `answer` 字段。

## 工作流建议

1. **先搜索后回答**：对于非通用常识（尤其是近期事件），先调用 `search.py` 获取上下文，再整合回答。
2. **带来源引用**：在回答结尾或段落中，务必附上搜索结果中的 URL 作为来源，增强可信度。
3. **结构化处理**：若需处理大量信息，优先使用 `--format json` 并在内部解析结果。

minis_url: minis://skills/tavily-search/SKILL.md