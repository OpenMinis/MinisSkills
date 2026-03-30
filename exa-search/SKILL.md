---
name: exa-search
description: Search the web, code, companies, and people using Exa's AI-powered search engine. Use this skill whenever the user asks to search for current information, find code examples, research a company, find professional profiles, or perform deep research on a complex topic. This skill is superior to basic web search as it provides clean, LLM-ready content and specialized search modes.
---

# Exa Search Skill

This skill provides access to Exa's AI-powered search capabilities via their hosted MCP server.

## When to Use
- **Web Search**: For current events, facts, or general knowledge.
- **Code Context**: To find documentation, API usage, or code examples from GitHub, Stack Overflow, etc.
- **Company Research**: To get business insights, news, and metadata about any company.
- **People Search**: To find professional profiles and contact info.
- **Deep Research**: For complex questions that require multiple searches and synthesis (takes 15s - 3min).
- **Crawling**: To extract full text content from a specific known URL.

## Available Tools

The skill provides the following tools via the `scripts/query.py` script:

- `web_search_exa`: General web search.
- `web_search_advanced_exa`: Search with filters (domain, date, category).
- `get_code_context_exa`: Targeted programming and documentation search.
- `company_research_exa`: Research companies.
- `people_search_exa`: Find professional profiles.
- `crawling_exa`: Extract content from a URL.
- `deep_researcher_start`: Start a long-running research task.
- `deep_researcher_check`: Get results from a research task.

## Usage Guide

### Calling a Tool
Use the `scripts/query.py` script to interact with Exa:

```bash
# List all available tools and their schemas
python3 /var/minis/skills/exa-search/scripts/query.py list_tools

# Search the web
python3 /var/minis/skills/exa-search/scripts/query.py call_tool web_search_exa '{"query": "latest news about SpaceX Starship"}'

# Search for code examples
python3 /var/minis/skills/exa-search/scripts/query.py call_tool get_code_context_exa '{"query": "React server components example"}'

# Perform deep research
# 1. Start the research
python3 /var/minis/skills/exa-search/scripts/query.py call_tool deep_researcher_start '{"instructions": "Research the impact of Llama 3 on the open source AI ecosystem"}'
# 2. Get the researchId from the output, then poll for results
python3 /var/minis/skills/exa-search/scripts/query.py call_tool deep_researcher_check '{"researchId": "..."}'
```

### Parameters Reference

#### web_search_exa
- `query` (string, required): The search query.
- `numResults` (number): Default 8.
- `livecrawl` (string): 'fallback' (default) or 'preferred'.

#### get_code_context_exa
- `query` (string, required): Programming question or API name.
- `tokensNum` (number): 1000-50000, default 5000.

#### deep_researcher_start
- `instructions` (string, required): Detailed research question.
- `model` (string): 'exa-research-fast' (default), 'exa-research', or 'exa-research-pro'.

## Environment Variables
- `EXA_API_KEY`: Required. If not set, prompt the user to [Set EXA_API_KEY](minis://settings/environments?create_key=EXA_API_KEY&create_value=).
