#!/usr/bin/env python3
"""Tavily Search 轻量调用脚本"""

import argparse
import json
import os

from tavily import TavilyClient


def main():
    p = argparse.ArgumentParser()
    p.add_argument("query", help="Search query")
    p.add_argument("--max", type=int, default=5, help="max results")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument(
        "--include-answer",
        action="store_true",
        help="在文本输出中显示 API 返回的 answer 字段（若存在）",
    )
    args = p.parse_args()

    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise SystemExit("TAVILY_API_KEY not set. Please set it in environments.")

    client = TavilyClient(api_key=key)
    data = client.search(query=args.query, max_results=args.max)

    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if args.include_answer and data.get("answer"):
        print(f"answer: {data.get('answer')}\n")

    for item in data.get("results", []):
        print(f"- {item.get('title')}")
        print(f"  URL: {item.get('url')}")
        snippet = (item.get('content') or "").replace("\n", " ")
        print(f"  摘要: {snippet[:180]}")


if __name__ == "__main__":
    main()
