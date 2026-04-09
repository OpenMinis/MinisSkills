---
name: exa-search
description: Search the web, read webpages as markdown, and run filtered web retrieval with Exa MCP. Use this skill whenever the user asks for current web information, web research, domain/date/category-filtered search, company or people lookup via search filters, or extracting clean page content from one or more URLs.
---

# Exa Search

Use this skill for Exa MCP web retrieval.

## When to Use
- Current web search
- Web research that needs clean LLM-ready results
- Domain, date, and category filtered search
- Company or people lookup through search filters
- Read full page content from known URLs as markdown

## Preferred Tools
- `web_search_exa`: default search tool
- `web_fetch_exa`: fetch one or more URLs as markdown
- `web_search_advanced_exa`: use only when filters or advanced options are needed

## Workflow
1. Run `list_tools` to confirm what the current server exposes.
2. For most tasks, start with `web_search_exa`.
3. If the user already has URLs, or search results need full content, use `web_fetch_exa`.
4. Use `web_search_advanced_exa` only when the task needs filters such as domains, categories, dates, highlights, summaries, or subpage crawling.
5. Prefer the current tools above as the main operating path.

## Commands
```bash
# Inspect current MCP tools
python3 /var/minis/skills/exa-search/scripts/query.py list_tools

# General search
python3 /var/minis/skills/exa-search/scripts/query.py call_tool web_search_exa '{"query":"latest changes in Exa MCP docs","numResults":5}'

# Fetch page content
python3 /var/minis/skills/exa-search/scripts/query.py call_tool web_fetch_exa '{"urls":["https://exa.ai/docs/reference/exa-mcp"]}'

# Advanced search with filters
python3 /var/minis/skills/exa-search/scripts/query.py call_tool web_search_advanced_exa '{"query":"Exa MCP documentation","includeDomains":["exa.ai"],"numResults":5,"enableHighlights":true}'
```

## Notes
- Base MCP URL: `https://mcp.exa.ai/mcp`
- Do not assume optional tools are enabled in every deployment; verify with `list_tools`.
- If the server exposes only the default tools, use `web_search_exa` + `web_fetch_exa` as the primary path.

## Environment Variables
- `EXA_API_KEY`: optional for basic use, recommended for higher limits and better reliability.
- If missing when needed, prompt the user to [Set EXA_API_KEY](minis://settings/environments?create_key=EXA_API_KEY&create_value=).
