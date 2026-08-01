#!/usr/bin/env python3
"""
quark_share_ls.py — 快速查看夸克分享链接文件列表

🔓 无需登录，直接运行。

用法：
  python3 quark_share_ls.py <分享链接>
  python3 quark_share_ls.py <分享链接> --tree   # 递归展开完整树

示例：
  python3 quark_share_ls.py "https://pan.quark.cn/s/6095134522b4"
  python3 quark_share_ls.py "https://pan.quark.cn/s/6095134522b4?pwd=1234" --tree
"""

import asyncio, random, re, sys, time
import aiohttp

API_BASE = "https://drive-pc.quark.cn/1/clouddrive"
UA = ("Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 "
      "Core/1.94.225.400 QQBrowser/12.2.5544.400")
HEADERS = {"User-Agent": UA, "Referer": "https://pan.quark.cn/"}

def _p():
    return {"pr": "ucpro", "fr": "pc", "uc_param_str": "",
            "__dt": random.randint(200, 9999), "__t": int(time.time() * 1000)}

def parse(url):
    pwd_id = url.split("?")[0].split("/s/")[-1].split("#")[0]
    m = re.search(r"pwd=([^&]+)", url)
    return pwd_id, (m.group(1) if m else "")

async def stoken(pwd_id, pwd=""):
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{API_BASE}/share/sharepage/token",
                          json={"pwd_id": pwd_id, "passcode": pwd},
                          params=_p(), headers=HEADERS,
                          timeout=aiohttp.ClientTimeout(total=30)) as r:
            j = await r.json(content_type=None)
    if j.get("status") != 200:
        raise RuntimeError(f"链接无效或已失效：{j.get('message')}")
    return j["data"]["stoken"]

async def detail(pwd_id, tok, pdir="0"):
    files, page = [], 1
    async with aiohttp.ClientSession() as s:
        while True:
            async with s.get(f"{API_BASE}/share/sharepage/detail",
                             params={**_p(), "pwd_id": pwd_id, "stoken": tok,
                                     "pdir_fid": pdir, "force": "0",
                                     "_page": page, "_size": 50,
                                     "_sort": "file_type:asc,updated_at:desc"},
                             headers=HEADERS,
                             timeout=aiohttp.ClientTimeout(total=30)) as r:
                j = await r.json(content_type=None)
            total = j["metadata"]["_total"]
            if total < 1:
                return bool(j["data"]["is_owner"]), []
            files.extend(j["data"]["list"])
            if page * 50 >= total:
                return bool(j["data"]["is_owner"]), files
            page += 1

def fmt(b):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"

def print_flat(files, is_owner):
    tag = "（你的文件）" if is_owner else ""
    print(f"\n共 {len(files)} 个条目 {tag}\n")
    print(f"{'类型':<4} {'大小':>10}  文件名")
    print("-" * 60)
    for f in files:
        t = "目录" if f["dir"] else "文件"
        size = f"({f.get('include_items',0)}项)" if f["dir"] else fmt(f.get("size", 0))
        print(f"{t:<4} {size:>10}  {f['file_name']}")

async def walk(pwd_id, tok, pdir="0", indent=0):
    _, items = await detail(pwd_id, tok, pdir)
    for f in items:
        pre = "  " * indent
        if f["dir"]:
            print(f"{pre}📁 {f['file_name']}/  ({f.get('include_items',0)}项)")
            await walk(pwd_id, tok, f["fid"], indent + 1)
        else:
            print(f"{pre}📄 {f['file_name']}  [{fmt(f.get('size', 0))}]")

async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    url = sys.argv[1]
    tree_mode = "--tree" in sys.argv

    pwd_id, password = parse(url)
    tok = await stoken(pwd_id, password)

    if tree_mode:
        print(f"📦 {url}\n")
        await walk(pwd_id, tok)
    else:
        is_owner, files = await detail(pwd_id, tok)
        print_flat(files, is_owner)

asyncio.run(main())
