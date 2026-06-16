"""
quark_hub.py — 夸克网盘 Minis 版命令行工具

上游来源
--------
基于 ihmily/QuarkPanTool (Apache-2.0)
https://github.com/ihmily/QuarkPanTool
原作者：Hmily，版本 0.0.6

改造说明
--------
1. 登录/Cookie 获取：原项目使用 Playwright 控制 Firefox 浏览器。
   Minis 环境无法运行 Playwright，改用 minis-browser-use CLI 工具
   驱动 Minis 内置 WebView 完成登录，再通过 get_cookies 动作提取
   pan.quark.cn 域下的全部 Cookie（BROWSER_COOKIE_HEADER 变量）并持久化。

2. Cookie 持久化路径：~/.quark_hub_cookie（HOME 目录下，跨会话复用）。
   Cookie 写入不由 Python 脚本负责，由 agent 通过 browser_use 工具完成：
   navigate 打开夸克 → 用户登录 → get_cookies 提取 → shell 写文件。
   脚本只负责读取和校验；失效时以 exit code 10 退出，供 agent 触发登录。

3. 依赖极简：仅使用标准库 + aiohttp（Alpine 原生包，无需 pip 安装）。
   移除了原项目的 playwright / colorama / prettytable / retrying / httpx。
   同步 Cookie 校验用标准库 urllib.request，无任何第三方依赖。

4. 登录分层：
   - 【无需登录】分享链接相关操作（ls-share / tree-share）匿名请求即可，
     stoken 接口本身不校验登录态。
   - 【需要登录】涉及自己网盘的操作（info / ls / save / dl / mkdir）才调用
     ensure_cookie()。

5. 错误处理：全局捕获未处理异常，避免 traceback 中泄露 Cookie / OSS 签名 URL。

6. 下载修复：OSS 下载 headers 不带 Content-Type（否则签名不匹配）。

7. 新增 tree-share 命令：递归展开分享链接的完整文件树。
"""

import asyncio
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

import aiohttp

# ── 常量 ─────────────────────────────────────────────────────────────────────

DOWNLOAD_DIR    = Path.cwd() / "downloads"
COOKIE_FILE     = Path.home() / ".quark_hub_cookie"   # 跨会话复用，权限 600
QUARK_LOGIN_URL = "https://pan.quark.cn"
QUARK_HOME      = "https://pan.quark.cn"
API_BASE        = "https://drive-pc.quark.cn/1/clouddrive"
API_SAVE        = "https://drive.quark.cn/1/clouddrive/share/sharepage/save"

# 夸克 PC 端通用 UA
UA_WEB = (
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 "
    "Core/1.94.225.400 QQBrowser/12.2.5544.400"
)
# Electron 客户端 UA —— /file/download 返回 code=23018 时切换重试（原项目逻辑）
UA_ELECTRON = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) quark-cloud-drive/2.5.56 Chrome/100.0.4896.160 "
    "Electron/18.3.5.12-a038f7b798 Safari/537.36 Channel/pckk_other_ch"
)


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _p() -> dict:
    """公共查询参数。"""
    return {
        "pr": "ucpro", "fr": "pc", "uc_param_str": "",
        "__dt": random.randint(200, 9999),
        "__t": int(time.time() * 1000),
    }

def _h(cookie: str = "", ua: str = UA_WEB) -> dict:
    """构造请求 headers，需要登录的接口传入 cookie。"""
    h = {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/json",
        "Origin": QUARK_HOME,
        "Referer": QUARK_HOME + "/",
    }
    if cookie:
        h["Cookie"] = cookie
    return h

def _fmt_size(b: int) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"

def parse_share_url(url: str) -> tuple[str, str]:
    """从分享链接提取 (pwd_id, password)。"""
    pwd_id = url.split("?")[0].split("/s/")[-1].split("#")[0]
    m = re.search(r"pwd=([^&]+)", url)
    return pwd_id, (m.group(1) if m else "")


# ── Cookie 管理 ───────────────────────────────────────────────────────────────

def load_cookie() -> str:
    """从 ~/.quark_hub_cookie 读取 Cookie，不存在返回空串。"""
    if COOKIE_FILE.exists():
        return COOKIE_FILE.read_text(encoding="utf-8").strip()
    return ""

def save_cookie(cookie_str: str) -> None:
    """保存 Cookie 到 ~/.quark_hub_cookie，权限 600。"""
    COOKIE_FILE.write_text(cookie_str, encoding="utf-8")
    COOKIE_FILE.chmod(0o600)

def _is_cookie_valid(cookie: str) -> bool:
    """
    同步校验 Cookie 有效性（调用 /account/info）。
    使用标准库 urllib.request，无需第三方依赖。
    """
    if not cookie:
        return False
    try:
        req = urllib.request.Request(
            f"{QUARK_HOME}/account/info?fr=pc&platform=pc",
            headers={"User-Agent": UA_WEB, "Cookie": cookie},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return bool(json.loads(resp.read()).get("data"))
    except Exception:
        return False

def ensure_cookie() -> str:
    """
    需要登录的命令统一入口。
    读取 ~/.quark_hub_cookie 并校验有效性；
    无效或不存在时以 exit code 10 退出，供 agent 触发登录流程。
    """
    cookie = load_cookie()
    if cookie and _is_cookie_valid(cookie):
        return cookie
    reason = "Cookie 文件不存在" if not cookie else "Cookie 已失效"
    print(f"[quark-hub] ❌ {reason}，需要登录夸克网盘")
    print(f"[quark-hub] 登录地址：{QUARK_LOGIN_URL}")
    sys.exit(10)  # exit code 10 = 需要登录


# ── 分享链接 API（无需登录）──────────────────────────────────────────────────

async def get_stoken(pwd_id: str, password: str = "") -> str:
    """【无需登录】获取分享页访问令牌 stoken。"""
    async with aiohttp.ClientSession() as s:
        async with s.post(
            f"{API_BASE}/share/sharepage/token",
            json={"pwd_id": pwd_id, "passcode": password},
            params=_p(), headers=_h(), timeout=aiohttp.ClientTimeout(total=30),
        ) as r:
            j = await r.json(content_type=None)
    if j.get("status") != 200 or not j.get("data"):
        raise RuntimeError(f"获取 stoken 失败：{j.get('message', '未知')}")
    return j["data"]["stoken"]

async def get_share_detail(pwd_id: str, stoken: str,
                           pdir_fid: str = "0") -> tuple[bool, list[dict]]:
    """【无需登录】获取分享页文件列表，返回 (is_owner, files)。"""
    files, page = [], 1
    async with aiohttp.ClientSession() as s:
        while True:
            async with s.get(
                f"{API_BASE}/share/sharepage/detail",
                params={**_p(), "pwd_id": pwd_id, "stoken": stoken,
                        "pdir_fid": pdir_fid, "force": "0",
                        "_page": page, "_size": 50,
                        "_sort": "file_type:asc,updated_at:desc"},
                headers=_h(), timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                j = await r.json(content_type=None)
            is_owner = j["data"]["is_owner"]
            total = j["metadata"]["_total"]
            if total < 1:
                return bool(is_owner), []
            for f in j["data"]["list"]:
                files.append({
                    "fid": f["fid"],
                    "file_name": f["file_name"],
                    "dir": f["dir"],
                    "size": f.get("size", 0),
                    "pdir_fid": f["pdir_fid"],
                    "share_fid_token": f["share_fid_token"],
                    "include_items": f.get("include_items", 0),
                })
            if page * 50 >= total:
                return bool(is_owner), files
            page += 1


# ── 网盘 API（需要登录）──────────────────────────────────────────────────────

async def api_user_info(cookie: str) -> dict:
    """【需要登录】查询账号信息。"""
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"{QUARK_HOME}/account/info",
            params={"fr": "pc", "platform": "pc"},
            headers=_h(cookie), timeout=aiohttp.ClientTimeout(total=30),
        ) as r:
            data = await r.json(content_type=None)
    if not data.get("data"):
        raise RuntimeError("Cookie 已过期，请重新登录")
    return data["data"]

async def api_list_all(cookie: str, pdir_fid: str = "0") -> list[dict]:
    """【需要登录】分页列出网盘目录全部文件。"""
    files, page, size = [], 1, 100
    async with aiohttp.ClientSession() as s:
        while True:
            async with s.get(
                f"{API_BASE}/file/sort",
                params={**_p(), "pdir_fid": pdir_fid, "_page": page,
                        "_size": size, "_fetch_total": "1",
                        "_fetch_sub_dirs": "1",
                        "_sort": "file_type:asc,updated_at:desc"},
                headers=_h(cookie), timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                j = await r.json(content_type=None)
            files.extend(j["data"]["list"])
            if page * size >= j["metadata"]["_total"]:
                break
            page += 1
    return files

async def api_save_share(cookie: str, pwd_id: str, stoken: str,
                         fid_list: list[str], token_list: list[str],
                         to_fid: str = "0") -> str:
    """【需要登录】提交转存任务，返回 task_id。"""
    async with aiohttp.ClientSession() as s:
        async with s.post(
            API_SAVE,
            json={"fid_list": fid_list, "fid_token_list": token_list,
                  "to_pdir_fid": to_fid, "pwd_id": pwd_id,
                  "stoken": stoken, "pdir_fid": "0", "scene": "link"},
            params=_p(), headers=_h(cookie),
            timeout=aiohttp.ClientTimeout(total=30),
        ) as r:
            j = await r.json(content_type=None)
    return j["data"]["task_id"]

async def api_poll_task(cookie: str, task_id: str, max_retry: int = 30) -> dict:
    """【需要登录】轮询任务状态直到完成。"""
    async with aiohttp.ClientSession() as s:
        for i in range(max_retry):
            await asyncio.sleep(random.uniform(0.5, 1.2))
            async with s.get(
                f"{API_BASE}/task",
                params={**_p(), "task_id": task_id, "retry_index": i},
                headers=_h(cookie), timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                j = await r.json(content_type=None)
            if j.get("message") == "ok" and j["data"].get("status") == 2:
                return j["data"]
            if j.get("code") == 32003:
                raise RuntimeError("转存失败：网盘容量不足")
    raise RuntimeError(f"任务 {task_id} 超时未完成")

async def api_get_download_urls(cookie: str, fids: list[str]) -> list[dict]:
    """
    【需要登录】获取文件下载直链列表。
    收到 code=23018 时切换 Electron UA 重试一次（原项目逻辑）。
    """
    ua = UA_WEB
    async with aiohttp.ClientSession() as s:
        for attempt in range(2):
            async with s.post(
                f"{API_BASE}/file/download",
                json={"fids": fids},
                params={**_p(), "sys": "win32", "ve": "2.5.56",
                        "ut": "", "guid": ""},
                headers=_h(cookie, ua),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                j = await r.json(content_type=None)
            if j.get("code") == 23018 and attempt == 0:
                ua = UA_ELECTRON
                continue
            if j.get("status") != 200:
                raise RuntimeError(f"获取下载地址失败：{j.get('message')}")
            return j["data"]
    raise RuntimeError("获取下载地址失败（已重试）")

async def api_mkdir(cookie: str, name: str, pdir_fid: str = "0") -> str:
    """【需要登录】创建网盘目录，返回新目录 fid。"""
    async with aiohttp.ClientSession() as s:
        async with s.post(
            f"{API_BASE}/file",
            json={"pdir_fid": pdir_fid, "file_name": name,
                  "dir_path": "", "dir_init_lock": False},
            params=_p(), headers=_h(cookie),
            timeout=aiohttp.ClientTimeout(total=30),
        ) as r:
            j = await r.json(content_type=None)
    if j.get("code") != 0:
        raise RuntimeError(f"创建目录失败：{j.get('message')}")
    return j["data"]["fid"]

def download_file(url: str, save_path: Path, cookie: str) -> None:
    """
    【需要登录】同步流式下载单个文件（适合在线程中调用）。
    下载 URL 指向阿里云 OSS，不能带 Content-Type（签名校验会失败）。
    """
    import urllib.request as _ur
    dl_headers = {
        "User-Agent": UA_WEB,
        "Cookie": cookie,
        "Referer": QUARK_HOME + "/",
    }
    save_path.parent.mkdir(parents=True, exist_ok=True)
    req = _ur.Request(url, headers=dl_headers)
    with _ur.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(save_path, "wb") as f:
            while True:
                chunk = resp.read(512 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {save_path.name}  {done/total*100:.1f}%",
                          end="", flush=True)
    print()


# ── 后台多文件下载（线程 + 进度报告）────────────────────────────────────────

import threading
from collections import deque

class _DLTask:
    """单文件下载任务，记录进度和速度历史。"""
    def __init__(self, name: str, save_path: Path, url: str, cookie: str):
        self.name = name
        self.save_path = save_path
        self.url = url
        self.cookie = cookie
        self.total_size = 0
        self.done_bytes = 0
        self.finished = False
        self.error: Optional[Exception] = None
        # (timestamp, cumulative_bytes) 用于计算过去 1min 均速
        self.speed_history: deque = deque()

    def speed_1min(self) -> float:
        now = time.time()
        while self.speed_history and now - self.speed_history[0][0] > 60:
            self.speed_history.popleft()
        if len(self.speed_history) < 2:
            return 0.0
        t0, b0 = self.speed_history[0]
        t1, b1 = self.speed_history[-1]
        dt = t1 - t0
        return (b1 - b0) / dt if dt > 0.1 else 0.0

    def progress_line(self) -> str:
        pct = f"{self.done_bytes / self.total_size * 100:.1f}%" if self.total_size else "??%"
        done_s  = _fmt_size(self.done_bytes)
        total_s = _fmt_size(self.total_size) if self.total_size else "?"
        spd     = _fmt_size(self.speed_1min()) + "/s"
        if self.finished:
            status = "✅ 完成"
        elif self.error:
            status = f"❌ {self.error}"
        else:
            status = "⬇ 下载中"
        return f"  [{status}] {self.name}  {done_s}/{total_s} ({pct})  1min均速: {spd}"

def _run_dl_task(task: _DLTask) -> None:
    """线程入口：流式下载并更新进度。"""
    import urllib.request as _ur
    dl_headers = {
        "User-Agent": UA_WEB,
        "Cookie": task.cookie,
        "Referer": QUARK_HOME + "/",
    }
    try:
        req = _ur.Request(task.url, headers=dl_headers)
        task.save_path.parent.mkdir(parents=True, exist_ok=True)
        with _ur.urlopen(req, timeout=60) as resp:
            cl = resp.headers.get("Content-Length")
            if cl:
                task.total_size = int(cl)
            with open(task.save_path, "wb") as f:
                while True:
                    chunk = resp.read(512 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    task.done_bytes += len(chunk)
                    now = time.time()
                    task.speed_history.append((now, task.done_bytes))
        task.finished = True
    except Exception as e:
        task.error = e

async def download_files_bg(items: list[dict], save_dir: Path, cookie: str,
                            report_interval: int = 10) -> None:
    """
    后台线程下载多个文件，每隔 report_interval 秒打印一次进度。

    items 格式：[{"file_name": str, "download_url": str}, ...]
    每项可选 "save_name" 覆盖保存文件名。
    打印 download_url（截断到 80 字符）供调试。
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    tasks: list[_DLTask] = []

    for item in items:
        orig_name = item["file_name"]
        save_name = item.get("save_name", orig_name)
        url       = item["download_url"]
        save_path = save_dir / save_name

        print(f"\n📎 {orig_name}  →  {save_name}")
        print(f"   URL: {url[:80]}...")

        tasks.append(_DLTask(save_name, save_path, url, cookie))

    print(f"\n🚀 启动 {len(tasks)} 个后台下载线程...\n")
    threads = []
    for t in tasks:
        th = threading.Thread(target=_run_dl_task, args=(t,), daemon=True)
        th.start()
        threads.append(th)

    start = time.time()
    while True:
        await asyncio.sleep(report_interval)
        elapsed = time.time() - start
        print(f"\n⏱ 已用时 {elapsed:.0f}s  [{time.strftime('%H:%M:%S')}]")
        for t in tasks:
            print(t.progress_line())
        if all(t.finished or t.error for t in tasks):
            break

    for th in threads:
        th.join(timeout=5)

    print("\n" + "=" * 60)
    print("📦 下载结果：")
    for t in tasks:
        if t.finished:
            size = t.save_path.stat().st_size
            print(f"  ✅ {t.save_path.name}  ({_fmt_size(size)})")
        else:
            print(f"  ❌ {t.name}  失败: {t.error}")


# ── 命令实现 ──────────────────────────────────────────────────────────────────

async def cmd_ls_share(share_url: str) -> None:
    """【无需登录】列出分享链接根目录文件（单层）。"""
    pwd_id, password = parse_share_url(share_url)
    tok = await get_stoken(pwd_id, password)
    is_owner, files = await get_share_detail(pwd_id, tok)
    if not files:
        print("（分享为空或已失效）")
        return
    print(f"{'类型':<4} {'大小':>10}  文件名")
    print("-" * 60)
    for f in files:
        t = "目录" if f["dir"] else "文件"
        size = f"({f['include_items']}项)" if f["dir"] else _fmt_size(f["size"])
        print(f"{t:<4} {size:>10}  {f['file_name']}")

async def _tree_walk(pwd_id: str, tok: str, pdir: str = "0", indent: int = 0) -> None:
    _, items = await get_share_detail(pwd_id, tok, pdir)
    for f in items:
        pre = "  " * indent
        if f["dir"]:
            print(f"{pre}📁 {f['file_name']}/  ({f['include_items']}项)")
            await _tree_walk(pwd_id, tok, f["fid"], indent + 1)
        else:
            print(f"{pre}📄 {f['file_name']}  [{_fmt_size(f['size'])}]")

async def cmd_tree_share(share_url: str) -> None:
    """【无需登录】递归展开分享链接完整文件树。"""
    pwd_id, password = parse_share_url(share_url)
    tok = await get_stoken(pwd_id, password)
    print(f"📦 {share_url}\n")
    await _tree_walk(pwd_id, tok)

async def cmd_info(cookie: str) -> None:
    """【需要登录】查看账号信息和容量。"""
    u = await api_user_info(cookie)
    print(f"用户：{u.get('nickname', '未知')}")
    print(f"容量：{_fmt_size(u.get('use_capacity', 0))} / "
          f"{_fmt_size(u.get('total_capacity', 0))}")

async def cmd_ls(cookie: str, pdir_fid: str = "0") -> None:
    """【需要登录】列出网盘目录。"""
    files = await api_list_all(cookie, pdir_fid)
    if not files:
        print("（目录为空）")
        return
    print(f"{'类型':<4} {'大小':>10}  {'fid':<32}  文件名")
    print("-" * 80)
    for f in files:
        t = "目录" if f["dir"] else "文件"
        size = "-" if f["dir"] else _fmt_size(f.get("size", 0))
        print(f"{t:<4} {size:>10}  {f['fid']:<32}  {f['file_name']}")

async def cmd_save(cookie: str, share_url: str, to_fid: str = "0") -> None:
    """
    【需要登录】转存分享链接中的文件到网盘。
    转存前先检查目标目录是否已有同名文件夹/文件，已有则跳过转存直接复用。
    返回实际可用的目标 fid（已有文件所在目录 fid 或转存后的 fid）。
    """
    pwd_id, password = parse_share_url(share_url)
    tok = await get_stoken(pwd_id, password)
    is_owner, share_files = await get_share_detail(pwd_id, tok)
    if is_owner:
        print("[save] 该分享是您自己的文件，无需转存")
        return
    if not share_files:
        print("[save] 分享为空或已失效")
        return

    # ── 转存前检查网盘是否已有同名内容 ──────────────────────────────────────
    share_names = {f["file_name"] for f in share_files}
    existing = await api_list_all(cookie, to_fid)
    existing_map = {f["file_name"]: f for f in existing}
    already = share_names & existing_map.keys()
    if already:
        print(f"[save] ℹ️  网盘目标目录已有相同文件/文件夹，跳过转存：")
        for name in sorted(already):
            f = existing_map[name]
            size_str = "-" if f.get("dir") else _fmt_size(f.get("size", 0))
            print(f"         {name}  ({size_str})  fid={f['fid']}")
        return

    # ── 正式转存 ──────────────────────────────────────────────────────────────
    print(f"[save] 共 {len(share_files)} 个条目，开始转存……")
    task_id = await api_save_share(
        cookie, pwd_id, tok,
        [f["fid"] for f in share_files],
        [f["share_fid_token"] for f in share_files],
        to_fid,
    )
    print(f"[save] 等待任务完成……")
    result = await api_poll_task(cookie, task_id)
    folder = result.get("save_as", {}).get("to_pdir_name", "根目录")
    print(f"[save] ✅ 转存完成，已保存至：{folder}")

async def cmd_dl(cookie: str, share_url_or_fids: str,
                 save_dir: Optional[str] = None,
                 extra_fids: Optional[list[str]] = None,
                 rename_map: Optional[dict[str, str]] = None) -> None:
    """
    【需要登录】下载网盘文件到本地，支持两种模式：

    模式 1 — 分享链接（必须是自己的分享）：
        python3 quark_hub.py dl <分享链接> [本地目录]
    模式 2 — 直接传 fid（不依赖分享链接，适合已在网盘的文件）：
        内部调用时传 extra_fids=[fid1, fid2, ...]

    rename_map: {原文件名: 保存文件名}，可选，用于字幕等重命名。
    使用后台线程下载，每 10s 打印进度和 1min 均速。
    """
    base = Path(save_dir) if save_dir else DOWNLOAD_DIR
    rename_map = rename_map or {}

    if extra_fids:
        # 模式 2：直接 fid
        fids = extra_fids
    else:
        # 模式 1：通过分享链接
        pwd_id, password = parse_share_url(share_url_or_fids)
        tok = await get_stoken(pwd_id, password)
        is_owner, files = await get_share_detail(pwd_id, tok)
        if not is_owner:
            print("[dl] ⚠️  只能下载自己网盘的分享文件，请先 save 转存后再下载")
            return
        file_only = [f for f in files if not f["dir"]]
        if not file_only:
            print("[dl] 没有可直接下载的文件")
            return
        fids = [f["fid"] for f in file_only]

    dl_list = await api_get_download_urls(cookie, fids)
    if not dl_list:
        print("[dl] 未获取到下载地址")
        return

    items = []
    for item in dl_list:
        orig_name = item["file_name"]
        items.append({
            "file_name": orig_name,
            "save_name": rename_map.get(orig_name, orig_name),
            "download_url": item["download_url"],
        })

    print(f"[dl] 共 {len(items)} 个文件，保存至 {base}")
    await download_files_bg(items, base, cookie)

async def cmd_mkdir(cookie: str, name: str, pdir_fid: str = "0") -> None:
    """【需要登录】在网盘中创建目录。"""
    fid = await api_mkdir(cookie, name, pdir_fid)
    print(f"[mkdir] ✅ 已创建：{name}  (fid={fid})")


# ── CLI 入口 ──────────────────────────────────────────────────────────────────

COMMANDS = {
    "ls-share":   (False, "列出分享链接根目录文件列表              🔓 无需登录"),
    "tree-share": (False, "递归展开分享链接完整文件树              🔓 无需登录"),
    "info":       (True,  "查看当前登录账号信息和容量              🔒 需要登录"),
    "ls":         (True,  "列出自己网盘目录                        🔒 需要登录"),
    "save":       (True,  "转存分享链接文件到自己网盘              🔒 需要登录"),
    "dl":         (True,  "下载自己分享的文件到本地               🔒 需要登录"),
    "mkdir":      (True,  "在自己网盘中创建目录                    🔒 需要登录"),
}

def usage() -> None:
    print(f"\n用法：python3 {Path(__file__).name} <命令> [参数]\n")
    print("命令：")
    for cmd, (_, desc) in COMMANDS.items():
        print(f"  {cmd:<14} {desc}")
    print("""
示例：
  python3 quark_hub.py ls-share   "https://pan.quark.cn/s/xxxxxxxx"
  python3 quark_hub.py tree-share "https://pan.quark.cn/s/xxxxxxxx"
  python3 quark_hub.py info
  python3 quark_hub.py ls
  python3 quark_hub.py ls <fid>
  python3 quark_hub.py save "https://pan.quark.cn/s/xxxxxxxx"
  python3 quark_hub.py save "https://pan.quark.cn/s/xxxxxxxx?pwd=1234" <目标fid>
  python3 quark_hub.py dl   "https://pan.quark.cn/s/xxxxxxxx" /var/minis/workspace/
  python3 quark_hub.py mkdir 我的电影
  python3 quark_hub.py mkdir 子目录 <父目录fid>

登录说明：
  Cookie 保存路径：~/.quark_hub_cookie
  登录由 agent 通过 browser_use 完成，脚本仅读取校验。
  若脚本退出码为 10，表示需要登录。
""")

def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        usage()
        return

    cmd = args[0]
    if cmd not in COMMANDS:
        print(f"未知命令：{cmd}")
        usage()
        sys.exit(1)

    # 无需登录的命令
    if cmd == "ls-share":
        if len(args) < 2:
            print("用法：ls-share <分享链接>"); sys.exit(1)
        asyncio.run(cmd_ls_share(args[1]))
        return
    if cmd == "tree-share":
        if len(args) < 2:
            print("用法：tree-share <分享链接>"); sys.exit(1)
        asyncio.run(cmd_tree_share(args[1]))
        return

    # 需要登录的命令
    cookie = ensure_cookie()

    if cmd == "info":
        asyncio.run(cmd_info(cookie))
    elif cmd == "ls":
        asyncio.run(cmd_ls(cookie, args[1] if len(args) > 1 else "0"))
    elif cmd == "save":
        if len(args) < 2:
            print("用法：save <分享链接> [目标fid]"); sys.exit(1)
        asyncio.run(cmd_save(cookie, args[1], args[2] if len(args) > 2 else "0"))
    elif cmd == "dl":
        if len(args) < 2:
            print("用法：dl <分享链接> [本地目录]"); sys.exit(1)
        asyncio.run(cmd_dl(cookie, args[1], args[2] if len(args) > 2 else None))
    elif cmd == "mkdir":
        if len(args) < 2:
            print("用法：mkdir <目录名> [父目录fid]"); sys.exit(1)
        asyncio.run(cmd_mkdir(cookie, args[1], args[2] if len(args) > 2 else "0"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[quark-hub] 已取消")
        sys.exit(130)
    except RuntimeError as e:
        print(f"[quark-hub] ❌ {e}")
        sys.exit(1)
    except Exception as e:
        # 捕获所有未处理异常，避免 traceback 中泄露 Cookie / OSS 签名 URL
        print(f"[quark-hub] ❌ 发生错误：{type(e).__name__}: {e}")
        sys.exit(1)
