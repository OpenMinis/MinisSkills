#!/usr/bin/env python3
"""
maimai-hub: 脉脉同事圈 & 职言 Feed 抓取脚本
用法:
  python3 maimai.py circle_rank   --env <env_file>
  python3 maimai.py search_company --name 字节跳动 --env <env_file>
  python3 maimai.py gossip_circle  --webcid 9AG14xzt --count 20 --env <env_file>
  python3 maimai.py gossip_circle  --company 蚂蚁集团 --count 20 --env <env_file>
  python3 maimai.py gossip_feed    --tab hot --count 20 --env <env_file>
"""

import sys, os, json, re, argparse, subprocess

BASE = "https://maimai.cn"
UA   = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ── Cookie 加载 ──────────────────────────────────────────────────────────────

def load_env(env_file: str) -> dict:
    """从 offload env 文件读取所有 COOKIE_* 变量"""
    r = subprocess.run(["/bin/sh", "-c", f". {env_file} && env"],
                       capture_output=True, text=True)
    return {k: v for line in r.stdout.splitlines()
            if "=" in line
            for k, v in [line.split("=", 1)]
            if k.startswith("COOKIE_")}

def build_cookie(c: dict) -> str:
    pairs = [
        ("access_token", "COOKIE_ACCESS_TOKEN"),
        ("u",            "COOKIE_U"),
        ("session",      "COOKIE_SESSION"),
        ("csrftoken",    "COOKIE_CSRFTOKEN"),
        ("crystal",      "COOKIE_CRYSTAL"),
        ("cmci9xde",     "COOKIE_CMCI9XDE"),
        ("pmck9xge",     "COOKIE_PMCK9XGE"),
        ("assva6",       "COOKIE_ASSVA6"),
        ("assva5",       "COOKIE_ASSVA5"),
        ("vmce9xdq",     "COOKIE_VMCE9XDQ"),
    ]
    return "; ".join(f"{n}={c[k]}" for n, k in pairs if c.get(k))

# ── HTTP（用 curl，避免 urllib 重定向/SSL 问题）────────────────────────────────

def curl_get(url: str, cookie: str, csrf: str, referer: str = BASE) -> dict | str:
    cmd = [
        "curl", "-s", "--max-redirs", "3",
        "-H", f"Cookie: {cookie}",
        "-H", f"X-CSRF-Token: {csrf}",
        "-H", f"User-Agent: {UA}",
        "-H", f"Referer: {referer}",
        "-H", "Accept: application/json, text/html",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    body = r.stdout
    try:
        return json.loads(body)
    except Exception:
        return body  # HTML fallback

# ── 已知 webcid 缓存 ──────────────────────────────────────────────────────────

KNOWN = {
    "字节跳动": "jYZTTwkX",  "拼多多":   "1cDwhLvjW",
    "腾讯":     "167PEUToR", "vivo":     "rXh584Al",
    "阿里巴巴": "EnT6guJz",  "蚂蚁集团": "9AG14xzt",
    "百度":     "mWqfo5EX",  "美团":     "5DDx3ANi",
    "比亚迪":   "10wsjrj6Q", "理想汽车": "hbMMOznT",
    "中兴通讯": "6auL3z1w",  "小米":     "KvzN4IGA",
    "京东":     "SJdjsQ5S",  "快手":     "RO3MvtaT",
    "海康威视": "1fA6gCc0a", "OPPO":     "USBCoTK6",
    "微软":     "K79dfzQG",  "华为":     "3gFRxlnT",
    "TP-Link":  "9JEDgxMb",  "新华三":   "Zru624cS",
    "长安汽车": "199ePls9E",
}

def find_webcid(name: str, cookie: str, csrf: str) -> str | None:
    for k, v in KNOWN.items():
        if name in k or k in name:
            return v
    # 动态查排行榜
    for item in api_circle_rank("9AG14xzt", cookie, csrf):
        n = item.get("name", "")
        if name in n or n in name:
            return item.get("webcid")
    return None

# ── API ───────────────────────────────────────────────────────────────────────

def api_circle_rank(webcid: str, cookie: str, csrf: str) -> list:
    """同事圈人气排行榜 → [{name, webcid, rank, current_recent_visit}]"""
    url = f"{BASE}/web/gossip/events/circle_rank?webcid={webcid}&u=0&channel=www&version=4.0.0"
    resp = curl_get(url, cookie, csrf, referer=f"{BASE}/company/gossip_discuss?webcid={webcid}")
    if not isinstance(resp, str):
        return []
    m = re.search(r'share_data\s*=\s*JSON\.parse\("(.+?)"\)\s*;', resp)
    if not m:
        return []
    data = json.loads(m.group(1).encode("utf-8").decode("unicode_escape"))
    rank_list = data.get("data", {}).get("page_info", {}).get("rank_list", [])
    result = []
    for item in rank_list:
        try:
            name = item["name"].encode("latin1").decode("utf-8")
        except Exception:
            name = item["name"]
        result.append({**item, "name": name})
    return result

def api_gossip_circle(webcid: str, uid: str, cookie: str, csrf: str, page=0, count=20) -> list:
    """指定公司同事圈帖子"""
    url = (f"{BASE}/groundhog/gossip/v3/feed"
           f"?webcid={webcid}&u={uid}&channel=www&version=4.0.0&page={page}&count={count}")
    resp = curl_get(url, cookie, csrf, referer=f"{BASE}/company/gossip_discuss?webcid={webcid}")
    if isinstance(resp, dict):
        err = resp.get("error_code") or resp.get("error")
        if err:
            return [{"error": resp.get("error_msg", str(err))}]
        return resp.get("data", [])
    return []

def api_gossip_feed(uid: str, cookie: str, csrf: str, tab="hot", page=0, count=20) -> list:
    """全站职言 Feed"""
    url = (f"{BASE}/groundhog/gossip/v3/feed"
           f"?u={uid}&channel=www&version=4.0.0&page={page}&count={count}&tab={tab}")
    resp = curl_get(url, cookie, csrf, referer=f"{BASE}/gossip_list")
    if isinstance(resp, dict):
        return resp.get("data", [])
    return []

def fmt(item: dict) -> dict:
    return {
        "id":      item.get("id"),
        "time":    item.get("time", ""),
        "text":    item.get("text", "").strip(),
        "likes":   item.get("likes", 0),
        "cmts":    item.get("cmts", 0),
        "spreads": item.get("spreads", 0),
        "ip_loc":  item.get("ip_loc", ""),
    }

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["gossip_circle", "gossip_feed", "circle_rank", "search_company"])
    p.add_argument("--webcid",  default="")
    p.add_argument("--company", default="")
    p.add_argument("--name",    default="")
    p.add_argument("--tab",     default="hot", help="hot|new|follow|recommend")
    p.add_argument("--count",   type=int, default=20)
    p.add_argument("--page",    type=int, default=0)
    p.add_argument("--env",     default=os.environ.get("MAIMAI_COOKIE_ENV", ""))
    a = p.parse_args()

    if not a.env:
        sys.exit(json.dumps({"error": "需通过 --env 传入 cookie env 文件路径"}))

    c      = load_env(a.env)
    cookie = build_cookie(c)
    csrf   = c.get("COOKIE_CSRFTOKEN", "")
    uid    = c.get("COOKIE_U", "0")

    if not csrf:
        sys.exit(json.dumps({"error": "Cookie 中缺少 csrftoken，请用桌面版 UA 重新获取"}))

    if a.cmd == "circle_rank":
        rank = api_circle_rank(a.webcid or "9AG14xzt", cookie, csrf)
        print(json.dumps(rank, ensure_ascii=False, indent=2))

    elif a.cmd == "search_company":
        name = a.name or a.company
        webcid = find_webcid(name, cookie, csrf)
        if webcid:
            print(json.dumps({"name": name, "webcid": webcid,
                              "url": f"{BASE}/company/gossip_discuss?webcid={webcid}"},
                             ensure_ascii=False))
        else:
            print(json.dumps({"error": f"未找到「{name}」的 webcid，请直接提供同事圈 URL"}))

    elif a.cmd == "gossip_circle":
        webcid = a.webcid
        if not webcid:
            webcid = find_webcid(a.company, cookie, csrf) if a.company else ""
        if not webcid:
            sys.exit(json.dumps({"error": "请通过 --webcid 或 --company 指定公司"}))
        items = api_gossip_circle(webcid, uid, cookie, csrf, a.page, a.count)
        if items and items[0].get("error"):
            print(json.dumps(items[0], ensure_ascii=False))
        else:
            print(json.dumps([fmt(i) for i in items], ensure_ascii=False, indent=2))

    elif a.cmd == "gossip_feed":
        items = api_gossip_feed(uid, cookie, csrf, a.tab, a.page, a.count)
        print(json.dumps([fmt(i) for i in items], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
