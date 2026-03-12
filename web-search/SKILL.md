---
name: web-search
description: >
  通用网页搜索技能。通过浏览器自动化使用多个公开搜索引擎，并按搜索意图选择优先级链路。
  当用户提到“网页搜索”“搜索一下”“帮我搜”“网上查一下”“找官网”“找原始网页”或任何需要互联网实时信息的场景时触发。
  本技能主打无需 API key 的浏览器搜索与自动降级切换，适合作为 exa-search / tavily-search 等 API 搜索技能的补位方案。
compatibility: browser_use tool required; Perplexity optional login; no API key required for browser-based engines
chinese_name: 网页搜索引擎路由器
---

# web-search

这是一个**无需 API key** 的网页搜索技能。

它不替代 `exa-search` 或 `tavily-search`：
- 有 API key 时，API 型搜索技能通常更强、更稳；
- 没有 key、key 不可用、或需要直接走公开搜索引擎时，`web-search` 负责提供**浏览器自动化 + 多引擎降级**能力。

## 何时使用

当用户需要以下能力时激活本技能：
- 搜索实时网页信息
- 查官网、原始网页、GitHub 仓库、文档入口
- 搜中文内容或中文语境下的结构化答案
- 指定搜索引擎（Google / Bing / Brave / Perplexity / 秘塔AI）
- 一个搜索引擎失败后自动切换下一个

## 搜索引擎分工

| 引擎 | 入口方式 | 适用场景 | 说明 |
|---|---|---|---|
| Perplexity | `https://www.perplexity.ai/search?q={query}` | 深度问答、对比研究 | 质量最高，需登录一次 |
| 秘塔AI | 首页交互输入 | 中文综述、中文结构化答案 | 中文表现强，适合补位 |
| Google | `https://www.google.com/search?q={query}` | 官网、原始网页、通用网页 | 覆盖最广 |
| Bing | `https://www.bing.com/search?q={query}` | 中文与网页综合检索 | 稳定、常带 AI 摘要 |
| Brave | `https://search.brave.com/search?q={query}` | 隐私优先、备用链路 | 适合作为 fallback |
| DuckDuckGo | `https://html.duckduckgo.com/html/?q={query}` | 轻量搜索、隐私补位 | 可能触发异常页 |
| 百度 | `https://www.baidu.com/s?wd={query}` | 中文网页搜索 | 中文索引强 |
| 搜狗 | `https://www.sogou.com/web?query={query}` | 中文 / 微信生态内容 | 次级中文补位 |

> `Tavily` / `Exa` 属于互补的 API 型能力，不是本技能直接调用的浏览器引擎。

## 按意图选择优先级链路

### 1）深度问答 / 对比研究 / 趋势分析
`Perplexity -> 秘塔AI -> Bing -> Google -> Brave`

### 2）中文检索 / 中文综述 / 国内语境
`秘塔AI -> Perplexity -> 百度 -> Bing -> Google`

### 3）通用网页搜索 / 找官网 / 找原始网页
`Google -> Bing -> Brave -> DuckDuckGo`

### 4）隐私优先检索
`Brave -> DuckDuckGo -> Bing`

## 自动降级条件

当出现以下任一情况时，立即切到下一级：
- 登录失效
- captcha / 验证 / blocked / robot / 异常流量 / 访问受限
- 空结果页
- 被重定向回首页
- 页面结构异常，无法提取有效文本
- 页面里只有输入框，没有实际结果

## 成功判定

满足以下任意两项即可接受当前结果：
- 页面标题或 URL 明显是结果页
- 提取文本非空，且包含有效内容
- 存在结构化答案、结果列表、引用来源、相关问题
- 页面明显不是首页或登录页

## 标准执行流程

1. 从用户请求中推断搜索意图。
2. 选择对应的引擎链路。
3. 打开第一个引擎结果页。
4. 提取页面文本。
5. 判断当前结果是否可接受。
6. 若失败，则切到下一个引擎。
7. 返回首个合格结果；必要时附加第二结果源做交叉验证。

## 标准返回结构

建议上层调用方统一按以下结构理解结果：

```json
{
  "query": "AI 搜索引擎对比 2026",
  "intent": "deep",
  "engine": "perplexity",
  "verdict": "accept",
  "reason": "success",
  "url": "https://www.perplexity.ai/search?q=...",
  "fallback_tried": ["perplexity"],
  "notes": "获得结构化答案与引用来源"
}
```

## 脚本

- `scripts/browser_search.py`
  - 自动推断搜索意图
  - 生成引擎链路
  - 判定 blocked / success
  - 给出下一步动作建议

- `evals/evals.json`
  - 覆盖路由、降级、定位差异等基础场景

## 注意事项

- 优先在有登录态时使用 Perplexity 获取高质量答案。
- 中文结构化答案优先尝试秘塔AI。
- 找官网、找原始网页时优先 Google / Bing。
- Brave / DuckDuckGo 主要承担隐私或备用链路角色。
- 不要把本技能描述成 API 搜索替代品；它是公开搜索引擎的浏览器补位方案。
