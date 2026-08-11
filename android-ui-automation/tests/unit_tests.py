#!/usr/bin/env python3
"""Unit tests for android-ui-automation skill scripts (no device needed)."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

passed = failed = 0

import re
def re_compiled():
    return re.compile("播.*曲")

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}  {detail}")

def _raises(exc, fn_, *a, **kw):
    try:
        fn_(*a, **kw)
        return False
    except exc:
        return True

# ---------- find_node.py ----------
from find_node import score_node, find, node_text

print("== find_node.score_node ==")
node = {"text": "Circles – Post Malone", "contentDesc": "歌曲", "clickable": True}
node2 = {"text": "", "contentDesc": "暂停", "clickable": True}
node3 = {"text": "播放页", "contentDesc": "", "clickable": False}

check("exact text+desc concatenated → substring 70",
      score_node(node, "circles – post malone", None) == 70)
check("exact match when no contentDesc → 110",
      score_node({"text": "Circles – Post Malone", "clickable": True}, "circles – post malone", None) == 110)
check("substring match scores 60+10", score_node(node, "circles", None) == 70)
check("contentDesc exact 100+10", score_node(node2, "暂停", None) == 110)
check("non-clickable fragment 30", score_node(node3, "暂停播放页", None) == 30)
check("no match returns -1", score_node(node, "不存在的词", None) == -1)
check("regex match",
      score_node({"text": "播放歌曲", "clickable": True}, "播.*曲", re_compiled()) == 110)
check("empty text returns -1", score_node({"text": "", "clickable": True}, "x", None) == -1)

check("node_text joins text+desc",
      node_text(node) == "Circles – Post Malone 歌曲")

# ---------- find() with fake dump ----------
import find_node as fn
fn.dump_tree = lambda: [
    {"nodeId": "001", "text": "Circles – Post Malone", "contentDesc": "歌曲", "clickable": True},
    {"nodeId": "002", "text": "搜索", "contentDesc": "", "clickable": True},
    {"nodeId": "003", "text": "推荐", "contentDesc": "", "clickable": False},
]
r = find("circles", top_k=3)
check("find ranks best match first", r and r[0]["nodeId"] == "001" and r[0]["score"] == 70)
r2 = find("搜索")
check("find exact + clickable", r2 and r2[0]["score"] == 110)
r3 = find("无此节点")
check("find no match returns []", r3 == [])

# ---------- open_deep_link.py ----------
from open_deep_link import build_search_url, open_url, open_and_verify
print("== open_deep_link.build_search_url ==")
cases = [
    ("spotify", "Uptown Funk", "spotify://search/Uptown%20Funk"),
    ("youtube", "cats", "youtube://search/cats"),
    ("bilibili", "测试 视频", "bilibili://search/%E6%B5%8B%E8%AF%95%20%E8%A7%86%E9%A2%91"),
    ("weixin", "张三", "weixin://search/%E5%BC%A0%E4%B8%89"),
]
for app, q, want in cases:
    got = build_search_url(app, q)
    check(f"{app} '{q}' → {want}", got == want, f"got {got}")

check("build_search_url never raises for unknown scheme",
      build_search_url("nope", "x") == "nope://search/x")
check("open_and_verify rejects URL without scheme (ValueError)",
      _raises(ValueError, open_and_verify, "not-a-deep-link"))

# ---------- tap_and_verify.py ----------
from tap_and_verify import verify_marker, tap_and_verify
print("== tap_and_verify.verify_marker ==")
# fake _node_text to simulate a marker appearing
import tap_and_verify as tv
tv._node_text = lambda: ["暂停", "Circles – Post Malone 歌曲"]
check("verify marker 暂停 → True", verify_marker("暂停", timeout=0.5) is True)
tv._node_text = lambda: ["播放", "Circles – Post Malone 歌曲"]
check("verify marker 暂停 (absent) → False", verify_marker("暂停", timeout=0.5) is False)

def _raises(exc, fn_, *a, **kw):
    try:
        fn_(*a, **kw)
        return False
    except exc:
        return True

print("\n结果: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)