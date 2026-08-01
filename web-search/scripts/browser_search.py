#!/usr/bin/env python3
"""
browser_search.py - 多引擎搜索优先级与自动降级策略配置脚本
说明：该脚本当前负责输出搜索计划与降级链路，不直接调用 browser_use。
后续可由 Agent 按本脚本生成的计划执行浏览器自动化。
"""

import argparse
import json
import urllib.parse
from typing import Dict, List

SOURCES: Dict[str, Dict] = {
    "perplexity": {
        "name": "Perplexity",
        "url": "https://www.perplexity.ai/search?q={query}",
        "priority": "P1",
        "category": ["deep", "zh_deep"],
        "needs_login": True,
        "quality": "high",
    },
    "metaso": {
        "name": "秘塔AI",
        "url": "https://metaso.cn/",
        "priority": "P1",
        "category": ["deep", "zh", "zh_deep"],
        "needs_login": False,
        "quality": "high",
    },
    "google": {
        "name": "Google",
        "url": "https://www.google.com/search?q={query}",
        "priority": "P2",
        "category": ["web", "zh", "general"],
        "needs_login": False,
        "quality": "wide",
    },
    "bing": {
        "name": "Bing",
        "url": "https://www.bing.com/search?q={query}",
        "priority": "P2",
        "category": ["deep", "web", "zh", "general"],
        "needs_login": False,
        "quality": "good",
    },
    "brave": {
        "name": "Brave",
        "url": "https://search.brave.com/search?q={query}",
        "priority": "P3",
        "category": ["privacy", "web", "general"],
        "needs_login": False,
        "quality": "good",
    },
    "duckduckgo": {
        "name": "DuckDuckGo",
        "url": "https://html.duckduckgo.com/html/?q={query}",
        "priority": "P4",
        "category": ["privacy", "web", "general"],
        "needs_login": False,
        "quality": "basic",
    },
    "baidu": {
        "name": "百度",
        "url": "https://www.baidu.com/s?wd={query}",
        "priority": "P3",
        "category": ["zh", "web"],
        "needs_login": False,
        "quality": "zh_strong",
    },
    "sogou": {
        "name": "搜狗",
        "url": "https://www.sogou.com/web?query={query}",
        "priority": "P4",
        "category": ["zh", "web"],
        "needs_login": False,
        "quality": "zh_basic",
    },
}

FALLBACK_CHAINS: Dict[str, List[str]] = {
    "deep": ["perplexity", "metaso", "bing", "google", "brave"],
    "zh_deep": ["metaso", "perplexity", "baidu", "bing", "google"],
    "web": ["google", "bing", "brave", "duckduckgo"],
    "privacy": ["brave", "duckduckgo", "bing"],
    "general": ["perplexity", "metaso", "google", "bing", "brave"],
}

BLOCK_SIGNS = [
    "captcha", "验证", "异常流量", "robot", "blocked", "请稍候", "访问受限"
]


def build_url(source: str, query: str) -> str:
    encoded = urllib.parse.quote(query)
    return SOURCES[source]["url"].format(query=encoded)


def choose_chain(intent: str) -> List[str]:
    return FALLBACK_CHAINS.get(intent, FALLBACK_CHAINS["general"])


def make_plan(query: str, intent: str) -> Dict:
    chain = choose_chain(intent)
    steps = []
    for idx, source in enumerate(chain, start=1):
        steps.append({
            "order": idx,
            "source": source,
            "name": SOURCES[source]["name"],
            "url": build_url(source, query),
            "needs_login": SOURCES[source]["needs_login"],
            "priority": SOURCES[source]["priority"],
        })
    return {
        "query": query,
        "intent": intent,
        "fallback_chain": chain,
        "block_signs": BLOCK_SIGNS,
        "steps": steps,
        "success_rule": [
            "结果页非首页",
            "文本非空且包含结果内容",
            "存在结构化答案/链接列表/引用来源中的任意一种",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="多引擎搜索优先级计划生成器")
    parser.add_argument("query", nargs="?", help="搜索查询")
    parser.add_argument("-i", "--intent", default="general", choices=["deep", "zh_deep", "web", "privacy", "general"], help="搜索意图")
    parser.add_argument("-l", "--list", action="store_true", help="列出所有搜索源")
    parser.add_argument("-j", "--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    if args.list:
        print("可用搜索源：")
        for key, val in SOURCES.items():
            print(f"- {key}: {val['name']} ({val['priority']})")
        return

    if not args.query:
        parser.print_help()
        return

    plan = make_plan(args.query, args.intent)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(f"查询: {plan['query']}")
        print(f"意图: {plan['intent']}")
        print("降级链路:")
        for step in plan["steps"]:
            login = "需登录" if step["needs_login"] else "免登录"
            print(f"  {step['order']}. {step['name']} [{step['priority']}] - {login}")
            print(f"     {step['url']}")
        print("\n遇到以下情况自动切换下一级:")
        for sign in plan["block_signs"]:
            print(f"- {sign}")

if __name__ == "__main__":
    main()
