---
name: web-search
description: >
  通用网页搜索技能，通过浏览器自动化使用多个搜索引擎，并根据搜索意图选择优先级链路。
  支持：Perplexity、秘塔AI、Google、Bing、Brave、DuckDuckGo、百度、Sogou、Tavily。
  当用户提到"网页搜索"、"搜索一下"、"帮我搜"、"网上查一下"、"搜索引擎"，或需要从互联网获取实时信息时触发。
compatibility: browser_use tool required; optional login for Perplexity; no API key required for browser-based engines
---

# web-search

Use browser automation to search the web through multiple engines, then fall back automatically when one engine is blocked, logged out, or returns poor results.

## When to use

Activate this skill when the user wants:
- real-time web search
- search engine results instead of model memory
- Chinese web search or structured AI answers
- engine-specific search (Google / Bing / Brave / Perplexity / 秘塔AI)
- fallback behavior across multiple search engines

## Search engines

| Engine | URL pattern | Strength | Notes |
|---|---|---|---|
| Perplexity | `https://www.perplexity.ai/search?q={query}` | Highest answer quality | Needs login once |
| 秘塔AI | `https://metaso.cn/` | Strong Chinese results | Home page interaction may be needed |
| Google | `https://www.google.com/search?q={query}` | Best general web coverage | Stable fallback |
| Bing | `https://www.bing.com/search?q={query}` | Good Chinese + AI summary | Stable fallback |
| Brave | `https://search.brave.com/search?q={query}` | Privacy-friendly | Good backup |
| DuckDuckGo | `https://html.duckduckgo.com/html/?q={query}` | Lightweight privacy search | May show anomaly pages |
| 百度 | `https://www.baidu.com/s?wd={query}` | Strong Chinese index | Use for Chinese web results |
| 搜狗 | `https://www.sogou.com/web?query={query}` | Chinese / WeChat-heavy results | Secondary Chinese backup |
| Tavily | API-based | Agent-oriented | Requires API key |

## Intent-based priority chains

Choose the search chain by user intent.

### Deep research / comparison / trend analysis
`Perplexity -> 秘塔AI -> Bing -> Google -> Brave`

### Chinese search / Chinese summary / local context
`秘塔AI -> Perplexity -> 百度 -> Bing -> Google`

### General web search / official site / original page lookup
`Google -> Bing -> Brave -> DuckDuckGo`

### Privacy-first search
`Brave -> DuckDuckGo -> Bing`

## Fallback rules

Immediately switch to the next engine when any of these happens:
- login expired
- captcha / verification / blocked / robot / abnormal traffic
- empty result page
- redirected back to the home page
- page structure is broken and no useful text can be extracted
- only input box is visible with no actual results

## Success criteria

Treat a search as successful when at least two of these are true:
- the page title or URL clearly indicates a result page
- extracted text is non-empty and contains meaningful results
- there are structured answers, result lists, citations, or related questions
- the content is clearly not just the search homepage

## Execution flow

1. Infer search intent from the user request.
2. Select the matching priority chain.
3. Try the first engine.
4. Extract text with browser tools.
5. Check success criteria.
6. If blocked or poor, switch to the next engine.
7. Return the first good result, and optionally add a second source for comparison.

## Scripts

- `scripts/browser_search.py` — generate engine priority plans and fallback chains
- `evals/evals.json` — prompt coverage for the main routing scenarios

## Notes

- Prefer Perplexity for best answer quality when login is valid.
- Prefer 秘塔AI for Chinese structured answers.
- Prefer Google/Bing for finding original pages and official websites.
- Use Brave/DuckDuckGo as privacy-oriented backups.
- Do not rely on a single engine; fallback is part of the skill design.
