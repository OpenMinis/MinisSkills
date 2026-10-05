#!/usr/bin/env python3
"""Shared heuristics for shortcut request preflight tools.

Keyword lists are intentionally bilingual: the English words and the Chinese words are both
matching vocabulary for user prompts (users may write in either language). Do not remove the
Chinese keywords; output text (reasons, questions) is English.
"""

from __future__ import annotations

from dataclasses import dataclass

TASK_FAMILY_KEYWORDS = {
    "records": ["记录", "记", "备忘录", "提醒", "笔记", "写入", "note", "notes", "reminder", "capture", "log", "save", "write", "journal", "memo"],
    "query": ["查询", "查看", "天气", "汇率", "日历", "获取", "查", "calendar", "weather", "search", "query", "lookup", "check", "exchange rate", "fetch"],
    "share": ["分享", "发送", "截图", "照片", "图片", "文件", "share", "send", "screenshot", "photo", "image", "file", "attachment"],
    "jump": ["打开", "跳转", "启动", "进入", "open", "launch", "jump", "scheme", "url", "deep link"],
    "download": ["下载", "视频", "音频", "抖音", "douyin", "tiktok", "youtube", "bilibili", "video", "audio", "download"],
}

HIGH_RISK_KEYWORDS = ["cookie", "登录", "登录态", "爬", "抓取", "反爬", "浏览器", "scrape", "crawl", "login", "session", "anti-bot", "browser"]

KNOWN_FIELDS = {
    "trigger": ["分享菜单", "分享", "剪贴板", "手动", "自动化", "小组件", "siri", "share sheet", "clipboard", "manual", "automation", "widget"],
    "input": ["输入框", "输入", "剪贴板", "链接", "图片", "文件", "分享", "input", "prompt", "clipboard", "link", "url", "image", "file", "share"],
    "target": ["备忘录", "提醒", "笔记", "第三方应用", "文件", "页面", "相册", "照片", "url", "notes", "reminders", "third-party app", "file", "page", "album", "photo"],
    "write_mode": ["追加", "新建", "覆盖", "固定", "选择", "append", "create", "new", "overwrite", "replace", "fixed", "choose"],
    "completion": ["通知", "提示", "打开", "跳转", "结束", "分享", "完成后", "notify", "notification", "alert", "open", "jump", "finish", "share", "when done", "afterwards"],
    "hybrid": ["minis", "外部服务", "第三方", "url scheme", "hybrid", "external service", "third-party"],
}

RECIPES_BY_FAMILY = {
    "records": ["collect_text_then_write", "collect_text_then_choose_destination", "task_then_followup"],
    "query": ["query_then_show"],
    "share": ["share_input_then_process"],
    "jump": ["construct_and_open_uri", "task_then_followup"],
    "download": ["hybrid_launcher"],
}

PATTERNS_BY_FAMILY = {
    "records": ["ask_text", "menu_select", "write_target", "show_notification"],
    "query": ["ask_text", "current_location", "json_request", "show_result"],
    "share": ["share_input", "transform", "share_output"],
    "jump": ["url_encode", "open_target"],
    "download": ["launcher_shortcut", "handoff_result"],
}


@dataclass
class Analysis:
    task_family: str
    route_label: str
    recipes: list[str]
    patterns: list[str]
    missing_dimensions: list[str]
    reasons: list[str]


def _contains_any(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(k.lower() in lower for k in keywords)


def analyze_prompt(prompt: str) -> Analysis:
    scores = {family: 0 for family in TASK_FAMILY_KEYWORDS}
    for family, keywords in TASK_FAMILY_KEYWORDS.items():
        scores[family] = sum(1 for k in keywords if k.lower() in prompt.lower())

    task_family = max(scores, key=scores.get)
    if scores[task_family] == 0:
        task_family = "records"

    reasons: list[str] = []
    if task_family == "download":
        if _contains_any(prompt, HIGH_RISK_KEYWORDS):
            route_label = "not-shortcut-first"
            reasons.append("Involves a download platform together with login state, cookies, web scraping, or a browser dependency")
        else:
            route_label = "shortcut-hybrid"
            reasons.append("Involves downloads or a media platform; better as a Hybrid launcher")
    elif task_family in {"records", "query"}:
        route_label = "shortcut-native"
        reasons.append("Closer to a short foreground flow that native system actions can cover")
    elif task_family in {"share", "jump"}:
        route_label = "shortcut-hybrid" if _contains_any(prompt, ["第三方", "third-party", "uri", "scheme"]) else "shortcut-native"
        reasons.append("May need share input, a URL scheme, or a target jump")
    else:
        route_label = "shortcut-native"
        reasons.append("No special high-risk signal matched; default to native-first")

    missing = [name for name, keys in KNOWN_FIELDS.items() if not _contains_any(prompt, keys)]
    if route_label == "shortcut-native" and "hybrid" in missing:
        missing.remove("hybrid")

    return Analysis(
        task_family=task_family,
        route_label=route_label,
        recipes=RECIPES_BY_FAMILY.get(task_family, ["collect_text_then_write"]),
        patterns=PATTERNS_BY_FAMILY.get(task_family, ["ask_text"]),
        missing_dimensions=missing,
        reasons=reasons,
    )
