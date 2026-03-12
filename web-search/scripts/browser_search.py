#!/usr/bin/env python3
"""
browser_search.py - web-search 执行器骨架

能力：
1. 根据 query 自动推断搜索意图
2. 生成多引擎优先级链路
3. 对抓取文本进行 blocked / success 判定
4. 生成下一步执行建议

说明：
- 当前脚本仍不直接调用 browser_use。
- 设计目标是把“路由 + 判定 + 降级规则”固化下来，供 Agent/浏览器执行层复用。
"""

import argparse
import json
import re
import urllib.parse
from typing import Dict, List, Optional

SOURCES: Dict[str, Dict] = {
    "perplexity": {
        "name": "Perplexity",
        "url": "https://www.perplexity.ai/search?q={query}",
        "priority": "P1",
        "needs_login": True,
        "quality": "high",
    },
    "metaso": {
        "name": "秘塔AI",
        "url": "https://metaso.cn/",
        "priority": "P1",
        "needs_login": False,
        "quality": "high",
    },
    "google": {
        "name": "Google",
        "url": "https://www.google.com/search?q={query}",
        "priority": "P2",
        "needs_login": False,
        "quality": "wide",
    },
    "bing": {
        "name": "Bing",
        "url": "https://www.bing.com/search?q={query}",
        "priority": "P2",
        "needs_login": False,
        "quality": "good",
    },
    "brave": {
        "name": "Brave",
        "url": "https://search.brave.com/search?q={query}",
        "priority": "P3",
        "needs_login": False,
        "quality": "good",
    },
    "duckduckgo": {
        "name": "DuckDuckGo",
        "url": "https://html.duckduckgo.com/html/?q={query}",
        "priority": "P4",
        "needs_login": False,
        "quality": "basic",
    },
    "baidu": {
        "name": "百度",
        "url": "https://www.baidu.com/s?wd={query}",
        "priority": "P3",
        "needs_login": False,
        "quality": "zh_strong",
    },
    "sogou": {
        "name": "搜狗",
        "url": "https://www.sogou.com/web?query={query}",
        "priority": "P4",
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

BLOCK_PATTERNS = [
    r"captcha",
    r"验证",
    r"异常流量",
    r"robot",
    r"blocked",
    r"请稍候",
    r"访问受限",
    r"sign in",
    r"登录",
]

WEAK_PATTERNS = [
    r"你想了解什么",
    r"问任何事情",
    r"输入您的密码",
    r"在应用中打开",
    r"欢迎",
]

STRONG_RESULT_PATTERNS = [
    r"链接",
    r"答案",
    r"相关",
    r"引用",
    r"来源",
    r"Search Results",
    r"Web results",
    r"结果",
    r"主流工具对比",
    r"性能排行",
]

DEEP_HINTS = [
    "对比", "比较", "趋势", "分析", "研究", "评测", "排行", "总结", "综述"
]
ZH_HINTS = [
    "中文", "国内", "秘塔", "百度", "搜狗", "中文语境"
]
WEB_HINTS = [
    "官网", "github", "仓库", "原文", "原始", "网站", "链接"
]
PRIVACY_HINTS = [
    "隐私", "匿名", "不追踪", "privacy"
]


def build_url(source: str, query: str) -> str:
    encoded = urllib.parse.quote(query)
    return SOURCES[source]["url"].format(query=encoded)


def infer_intent(query: str, explicit_intent: Optional[str] = None) -> str:
    if explicit_intent:
        return explicit_intent
    q = query.lower()
    if any(k in query for k in PRIVACY_HINTS):
        return "privacy"
    if any(k in query for k in WEB_HINTS):
        return "web"
    if any(k in query for k in ZH_HINTS):
        return "zh_deep"
    if any(k in query for k in DEEP_HINTS):
        return "deep"
    if re.search(r"what|why|how|compare|analysis|research", q):
        return "deep"
    return "general"


def choose_chain(intent: str) -> List[str]:
    return FALLBACK_CHAINS.get(intent, FALLBACK_CHAINS["general"])


def detect_blocked(text: str) -> Dict:
    if not text:
        return {"blocked": True, "matched": ["empty_text"], "reason": "empty_text"}
    low = text.lower()
    matched = [p for p in BLOCK_PATTERNS if re.search(p, low, re.I)]
    weak = [p for p in WEAK_PATTERNS if re.search(p, text, re.I)]
    blocked = bool(matched)
    return {
        "blocked": blocked,
        "matched": matched,
        "weak_signals": weak,
        "reason": matched[0] if matched else None,
    }


def detect_success(text: str, title: str = "", url: str = "") -> Dict:
    if not text or len(text.strip()) < 80:
        return {"success": False, "score": 0, "signals": ["text_too_short"]}

    score = 0
    signals: List[str] = []

    if url and ("search" in url or "?q=" in url or "search-v2" in url):
        score += 1
        signals.append("result_like_url")

    if title and any(k.lower() in title.lower() for k in ["search", "搜索", "Perplexity", "秘塔", "Google", "Bing", "Brave"]):
        score += 1
        signals.append("result_like_title")

    strong = [p for p in STRONG_RESULT_PATTERNS if re.search(p, text, re.I)]
    if strong:
        score += 2
        signals.append("strong_result_patterns")

    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if len(lines) >= 6:
        score += 1
        signals.append("enough_content_lines")

    weak = [p for p in WEAK_PATTERNS if re.search(p, text, re.I)]
    if weak and score < 2:
        return {"success": False, "score": score, "signals": signals + ["homepage_like"]}

    return {"success": score >= 2, "score": score, "signals": signals}


def evaluate_page(text: str, title: str = "", url: str = "") -> Dict:
    blocked = detect_blocked(text)
    success = detect_success(text, title=title, url=url)
    if blocked["blocked"]:
        verdict = "fallback"
        reason = f"blocked:{blocked['reason']}"
    elif success["success"]:
        verdict = "accept"
        reason = "success"
    else:
        verdict = "fallback"
        reason = "weak_or_homepage"
    return {
        "verdict": verdict,
        "reason": reason,
        "blocked": blocked,
        "success": success,
    }


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
        "steps": steps,
    }


def make_next_action(query: str, intent: str, current_source: Optional[str] = None, evaluation: Optional[Dict] = None) -> Dict:
    plan = make_plan(query, intent)
    if current_source is None:
        first = plan["steps"][0]
        return {
            "action": "try_first_engine",
            "source": first["source"],
            "url": first["url"],
            "reason": "start_chain",
        }

    chain = plan["fallback_chain"]
    try:
        idx = chain.index(current_source)
    except ValueError:
        idx = -1

    if evaluation and evaluation.get("verdict") == "accept":
        return {
            "action": "accept_result",
            "source": current_source,
            "reason": evaluation.get("reason", "success"),
        }

    next_idx = idx + 1
    if 0 <= next_idx < len(chain):
        nxt = chain[next_idx]
        return {
            "action": "fallback_to_next_engine",
            "source": nxt,
            "url": build_url(nxt, query),
            "reason": evaluation.get("reason") if evaluation else "fallback",
        }

    return {
        "action": "chain_exhausted",
        "reason": evaluation.get("reason") if evaluation else "no_more_engines",
    }


def main():
    parser = argparse.ArgumentParser(description="web-search 执行器骨架")
    parser.add_argument("query", nargs="?", help="搜索查询")
    parser.add_argument("-i", "--intent", choices=["deep", "zh_deep", "web", "privacy", "general"], help="显式指定搜索意图")
    parser.add_argument("-l", "--list", action="store_true", help="列出搜索源")
    parser.add_argument("-j", "--json", action="store_true", help="JSON 输出")
    parser.add_argument("--eval-text", help="对给定文本做 blocked/success 判定")
    parser.add_argument("--title", default="", help="页面标题")
    parser.add_argument("--url", default="", help="页面URL")
    parser.add_argument("--current-source", help="当前引擎名，用于生成下一步动作")
    args = parser.parse_args()

    if args.list:
        print("可用搜索源：")
        for key, val in SOURCES.items():
            login = "需登录" if val["needs_login"] else "免登录"
            print(f"- {key}: {val['name']} [{val['priority']}] {login}")
        return

    if not args.query and not args.eval_text:
        parser.print_help()
        return

    if args.eval_text is not None:
        result = evaluate_page(args.eval_text, title=args.title, url=args.url)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"判定: {result['verdict']}")
            print(f"原因: {result['reason']}")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    intent = infer_intent(args.query, args.intent)
    plan = make_plan(args.query, intent)
    next_action = make_next_action(args.query, intent, current_source=args.current_source)
    payload = {
        "query": args.query,
        "intent": intent,
        "plan": plan,
        "next_action": next_action,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"查询: {args.query}")
        print(f"推断意图: {intent}")
        print("链路:")
        for step in plan["steps"]:
            login = "需登录" if step["needs_login"] else "免登录"
            print(f"  {step['order']}. {step['name']} [{step['priority']}] - {login}")
            print(f"     {step['url']}")
        print("\n下一步:")
        print(json.dumps(next_action, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
