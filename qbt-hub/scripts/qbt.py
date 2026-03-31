#!/usr/bin/env python3
"""
qBittorrent WebUI Management Tool (v5.0+)

Commands:
  add        Add a download task (.torrent file / https URL / magnet link)
  list       List / filter tasks
  search     Search tasks by name (fuzzy match)
  status     Show global transfer status
  pause      Pause tasks (keyword or 'all')
  resume     Resume tasks (keyword or 'all')
  delete     Delete tasks (--files to also remove local data)
  info       Show task details (file list, trackers)
  limit      Set per-task download/upload speed limit
  speedlimit View/set global speed limits, or toggle turtle mode
  tag        Add tags to tasks
  untag      Remove tags from tasks
  tags       List all tags
  category   Set category for tasks
  categories List all categories
  rename     Rename a task
  move       Change task save path
  recheck    Force recheck task data
  top        Show Top N tasks sorted by size/speed/ratio/etc.
  rss        RSS feed management (list/add/remove/addrule/removerule)

Authentication (priority: CLI args > env vars > defaults):
  Env vars: QBT_HOST / QBT_USER / QBT_PASS
"""

import os, sys, json, argparse, urllib.request, urllib.parse, urllib.error, http.cookiejar, datetime

DEFAULT_HOST = ""
DEFAULT_USER = ""
DEFAULT_PASS = ""

STATUS_MAP = {
    "downloading":        "Downloading",
    "stalledDL":          "Stalled (DL)",
    "uploading":          "Seeding",
    "stalledUP":          "Stalled (UP)",
    "pausedDL":           "Paused (DL)",
    "pausedUP":           "Paused (UP)",
    "queuedDL":           "Queued (DL)",
    "queuedUP":           "Queued (UP)",
    "checkingDL":         "Checking",
    "checkingUP":         "Checking",
    "checkingResumeData": "Checking resume",
    "moving":             "Moving",
    "error":              "Error",
    "missingFiles":       "Missing files",
    "unknown":            "Unknown",
    "metaDL":             "Fetching metadata",
    "forcedDL":           "Forced download",
    "forcedUP":           "Forced seeding",
    "completed":          "Completed",
}

STATUS_ICON = {
    "downloading": "⬇", "stalledDL": "⏸", "uploading": "⬆", "stalledUP": "⏸",
    "pausedDL": "⏹", "pausedUP": "⏹", "queuedDL": "🕐", "queuedUP": "🕐",
    "checkingDL": "🔍", "checkingUP": "🔍", "checkingResumeData": "🔍",
    "moving": "📦", "error": "❌", "missingFiles": "❓", "unknown": "❓",
    "metaDL": "📡", "forcedDL": "⬇", "forcedUP": "⬆", "completed": "✅",
}

def fmt_size(b):
    if b is None: return "?"
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if abs(b) < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"

def fmt_speed(b): return fmt_size(b) + "/s"

def fmt_eta(s):
    if s is None or s < 0 or s >= 8640000: return "inf"
    h, r = divmod(int(s), 3600)
    m, s = divmod(r, 60)
    if h: return f"{h}h{m:02d}m"
    if m: return f"{m}m{s:02d}s"
    return f"{s}s"

def fmt_ts(ts):
    if not ts or ts <= 0: return "-"
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

def sep(n=60): print("-" * n)


class QBTClient:
    def __init__(self, host, username, password):
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _url(self, path): return f"{self.host}/api/v2/{path}"

    def _post(self, path, data=None, files=None):
        url = self._url(path)
        if files:
            boundary = "----qbtboundary" + "x" * 16
            parts = []
            for k, v in (data or {}).items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}'.encode())
            for field, (fname, fbytes, ctype) in files.items():
                parts.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{fname}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
                    + fbytes)
            body = b"\r\n".join(parts) + f"\r\n--{boundary}--\r\n".encode()
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}", "Referer": self.host})
        else:
            body = urllib.parse.urlencode(data or {}).encode()
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": "application/x-www-form-urlencoded", "Referer": self.host})
        try:
            return self.opener.open(req).read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return f"HTTP {e.code}: {e.reason}"

    def _get(self, path, params=None):
        url = self._url(path)
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        req = urllib.request.Request(url, headers={"Referer": self.host})
        try:
            return self.opener.open(req).read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return f"HTTP {e.code}: {e.reason}"

    def _json(self, path, params=None):
        raw = self._get(path, params)
        try:
            return json.loads(raw)
        except Exception:
            print(f"ERROR: failed to parse response: {raw[:200]}")
            return None

    def login(self):
        r = self._post("auth/login", {"username": self.username, "password": self.password})
        if r == "Ok.":
            return True
        print(f"ERROR: login failed: {r}")
        return False

    def torrents(self, filter_status=None, category=None, tag=None, sort=None, reverse=True, limit=None):
        p = {}
        if filter_status and filter_status != "all": p["filter"] = filter_status
        if category: p["category"] = category
        if tag:      p["tag"] = tag
        if sort:     p["sort"] = sort
        if reverse:  p["reverse"] = "true"
        if limit:    p["limit"] = limit
        return self._json("torrents/info", p) or []

    def find(self, keyword):
        kw = keyword.lower()
        return [t for t in self.torrents() if kw in t.get("name", "").lower()]

    def hashes_by_keyword(self, keyword):
        if keyword == "all":
            return "|".join(t["hash"] for t in self.torrents())
        matches = self.find(keyword)
        if not matches:
            print(f'ERROR: no task matched "{keyword}"')
            return None
        return "|".join(t["hash"] for t in matches)

    def add(self, source, savepath=None, category=None, tags=None, paused=False, sequential=False):
        data = {}
        if savepath:   data["savepath"] = savepath
        if category:   data["category"] = category
        if tags:       data["tags"] = tags
        if paused:     data["paused"] = "true"
        if sequential: data["sequentialDownload"] = "true"
        if source.startswith(("http://", "https://", "magnet:")):
            data["urls"] = source
            r = self._post("torrents/add", data)
        else:
            if not os.path.isfile(source):
                print(f"ERROR: file not found: {source}")
                return False
            with open(source, "rb") as f:
                fb = f.read()
            r = self._post("torrents/add", data=data,
                           files={"torrents": (os.path.basename(source), fb, "application/x-bittorrent")})
        if r == "Ok.":
            print("OK: task added successfully")
            return True
        print(f"ERROR: {r}")
        return False

    def pause(self, hashes):      return self._post("torrents/pause",            {"hashes": hashes})
    def resume(self, hashes):     return self._post("torrents/resume",           {"hashes": hashes})
    def recheck(self, hashes):    return self._post("torrents/recheck",          {"hashes": hashes})
    def rename(self, h, name):    return self._post("torrents/rename",           {"hash": h, "name": name})
    def set_location(self, h, l): return self._post("torrents/setLocation",      {"hashes": h, "location": l})
    def set_category(self, h, c): return self._post("torrents/setCategory",      {"hashes": h, "category": c})
    def add_tags(self, h, t):     return self._post("torrents/addTags",          {"hashes": h, "tags": t})
    def remove_tags(self, h, t):  return self._post("torrents/removeTags",       {"hashes": h, "tags": t})
    def set_dl_limit(self, h, l): return self._post("torrents/setDownloadLimit", {"hashes": h, "limit": l})
    def set_ul_limit(self, h, l): return self._post("torrents/setUploadLimit",   {"hashes": h, "limit": l})
    def delete(self, hashes, delete_files=False):
        return self._post("torrents/delete", {"hashes": hashes, "deleteFiles": str(delete_files).lower()})

    def properties(self, h): return self._json("torrents/properties", {"hash": h})
    def files(self, h):      return self._json("torrents/files",      {"hash": h})
    def trackers(self, h):   return self._json("torrents/trackers",   {"hash": h})
    def peers(self, h):
        data = self._json("sync/torrentPeers", {"hash": h, "rid": "0"})
        return data.get("peers", {}) if data else {}

    def get_global_dl_limit(self):    return int(self._get("transfer/downloadLimit") or 0)
    def get_global_ul_limit(self):    return int(self._get("transfer/uploadLimit") or 0)
    def set_global_dl_limit(self, l): return self._post("transfer/setDownloadLimit", {"limit": l})
    def set_global_ul_limit(self, l): return self._post("transfer/setUploadLimit",   {"limit": l})
    def get_alt_speed_state(self):    return self._get("transfer/speedLimitsMode").strip()
    def toggle_alt_speed(self):       return self._post("transfer/toggleSpeedLimitsMode")
    def transfer_info(self):          return self._json("transfer/info") or {}

    def get_categories(self): return self._json("torrents/categories") or {}
    def get_tags(self):       return self._json("torrents/tags") or []
    def add_category(self, name, path=""): return self._post("torrents/createCategory", {"category": name, "savePath": path})
    def remove_categories(self, names):    return self._post("torrents/removeCategories", {"categories": "\n".join(names)})
    def create_tags(self, tags): return self._post("torrents/createTags", {"tags": tags})
    def delete_tags(self, tags): return self._post("torrents/deleteTags", {"tags": tags})

    def rss_items(self):               return self._json("rss/items", {"withData": "false"}) or {}
    def rss_add_feed(self, url, path=""): return self._post("rss/addFeed", {"url": url, "path": path})
    def rss_remove(self, path):        return self._post("rss/removeItem", {"path": path})
    def rss_rules(self):               return self._json("rss/rules") or {}
    def rss_set_rule(self, name, rule): return self._post("rss/setRule", {"ruleName": name, "ruleDef": json.dumps(rule)})
    def rss_remove_rule(self, name):   return self._post("rss/removeRule", {"ruleName": name})


def print_torrent_row(t, idx=None):
    name   = t.get("name", "?")
    state  = t.get("state", "unknown")
    prog   = t.get("progress", 0) * 100
    size   = t.get("size", 0)
    dl     = t.get("dlspeed", 0)
    ul     = t.get("upspeed", 0)
    eta    = t.get("eta", -1)
    cat    = t.get("category", "")
    tags   = t.get("tags", "")
    ratio  = t.get("ratio", 0)
    hash_  = t.get("hash", "")[:8]
    added  = fmt_ts(t.get("added_on"))
    icon   = STATUS_ICON.get(state, "?")
    label  = STATUS_MAP.get(state, state)
    prefix = f"{idx:3}. " if idx is not None else "    "
    display = name if len(name) <= 52 else name[:49] + "..."

    print(f"\n{prefix}{icon} {display}")
    print(f"     {label:<22} {prog:5.1f}%  {fmt_size(size):>10}  added: {added}")
    if state in ("downloading", "stalledDL", "metaDL", "forcedDL"):
        print(f"     DL: {fmt_speed(dl):<14} UL: {fmt_speed(ul):<14} ETA: {fmt_eta(eta)}")
    elif state in ("uploading", "stalledUP", "forcedUP"):
        print(f"     UL: {fmt_speed(ul):<14} ratio: {ratio:.2f}")
    elif state in ("pausedUP", "completed"):
        print(f"     ratio: {ratio:.2f}   UL: {fmt_speed(ul)}")
    meta = []
    if cat:  meta.append(f"cat:{cat}")
    if tags: meta.append(f"tags:{tags}")
    meta.append(f"hash:{hash_}...")
    print(f"     {' | '.join(meta)}")

def print_torrents(torrents, title=""):
    if title:
        sep()
        print(f"  {title}  ({len(torrents)} tasks)")
        sep()
    if not torrents:
        print("  (no tasks)\n")
        return
    for i, t in enumerate(torrents, 1):
        print_torrent_row(t, i)
    print()


def cmd_status(client):
    info = client.transfer_info()
    alt  = client.get_alt_speed_state()
    dl_g = client.get_global_dl_limit()
    ul_g = client.get_global_ul_limit()
    sep(44)
    print("  Global Transfer Status")
    sep(44)
    print(f"  DL Speed    : {fmt_speed(info.get('dl_info_speed', 0))}")
    print(f"  UL Speed    : {fmt_speed(info.get('up_info_speed', 0))}")
    print(f"  DL Total    : {fmt_size(info.get('dl_info_data', 0))}")
    print(f"  UL Total    : {fmt_size(info.get('up_info_data', 0))}")
    print(f"  Connection  : {info.get('connection_status', '?')}")
    print(f"  Turtle mode : {'on' if alt == '1' else 'off'}")
    print(f"  DL limit    : {fmt_speed(dl_g) if dl_g > 0 else 'unlimited'}")
    print(f"  UL limit    : {fmt_speed(ul_g) if ul_g > 0 else 'unlimited'}")
    print()

def cmd_pause(client, keyword):
    hashes = client.hashes_by_keyword(keyword)
    if not hashes: return
    n = len(client.torrents()) if keyword == "all" else len(client.find(keyword))
    client.pause(hashes)
    print(f"OK: paused {n} task(s)")

def cmd_resume(client, keyword):
    hashes = client.hashes_by_keyword(keyword)
    if not hashes: return
    n = len(client.torrents()) if keyword == "all" else len(client.find(keyword))
    client.resume(hashes)
    print(f"OK: resumed {n} task(s)")

def cmd_delete(client, keyword, delete_files):
    matches = client.torrents() if keyword == "all" else client.find(keyword)
    if not matches:
        print(f'ERROR: no task matched "{keyword}"')
        return
    print(f"About to delete {len(matches)} task(s) ({'including' if delete_files else 'excluding'} local files):")
    for t in matches:
        print(f"  - {t['name']}  ({fmt_size(t['size'])})")
    if input("Confirm delete? [y/N] ").strip().lower() != "y":
        print("Cancelled.")
        return
    client.delete("|".join(t["hash"] for t in matches), delete_files)
    print(f"OK: deleted {len(matches)} task(s)")

def cmd_info(client, keyword):
    matches = client.find(keyword)
    if not matches:
        print(f'ERROR: no task matched "{keyword}"')
        return
    t     = matches[0]
    h     = t["hash"]
    prop  = client.properties(h) or {}
    files = client.files(h) or []
    trks  = client.trackers(h) or []
    state = t.get("state", "unknown")

    sep(64)
    print(f"  {t['name']}")
    sep(64)
    print(f"  State       : {STATUS_ICON.get(state,'')} {STATUS_MAP.get(state, state)}")
    print(f"  Progress    : {t.get('progress',0)*100:.1f}%  ({fmt_size(t.get('completed',0))} / {fmt_size(t.get('size',0))})")
    print(f"  Speed       : DL {fmt_speed(t.get('dlspeed',0))}  UL {fmt_speed(t.get('upspeed',0))}")
    print(f"  ETA         : {fmt_eta(t.get('eta',-1))}")
    print(f"  Ratio       : {t.get('ratio',0):.3f}")
    print(f"  Category    : {t.get('category','-') or '-'}")
    print(f"  Tags        : {t.get('tags','-') or '-'}")
    print(f"  Save path   : {prop.get('save_path','?')}")
    print(f"  Added       : {fmt_ts(t.get('added_on'))}")
    print(f"  Completed   : {fmt_ts(t.get('completion_on'))}")
    print(f"  Hash        : {h}")
    print(f"  Peers       : {t.get('num_seeds',0)} seeding / {t.get('num_leechs',0)} leeching")
    if files:
        print(f"\n  Files ({len(files)}):")
        for f in files[:25]:
            prog = f.get("progress", 0) * 100
            print(f"    [{prog:5.1f}%] {fmt_size(f.get('size',0)):>10}  {f.get('name','?')}")
        if len(files) > 25:
            print(f"    ... {len(files)} files total")
    active_trks = [tk for tk in trks if tk.get("status") not in ("Not contacted yet", "Disabled")]
    if active_trks:
        print(f"\n  Trackers ({len(trks)} total):")
        for tk in active_trks[:5]:
            print(f"    [{tk.get('status','?')}]  {tk.get('url','?')[:60]}")
    # peers summary
    peers = client.peers(h)
    if peers:
        seeders  = sum(1 for p in peers.values() if p.get("progress", 0) >= 1.0)
        leechers = len(peers) - seeders
        active   = [p for p in peers.values() if p.get("dl_speed", 0) > 0]
        top_dl   = sorted(peers.values(), key=lambda x: x.get("dl_speed", 0), reverse=True)[:3]
        print(f"\n  Peers ({len(peers)} total — {seeders} seeding / {leechers} leeching):")
        for p in top_dl:
            if p.get("dl_speed", 0) > 0:
                print(f"    {p.get('ip','?'):<18} {p.get('country_code','--')}  {p.get('client','?')[:24]:<26}  DL: {fmt_speed(p.get('dl_speed',0))}")
        if len(peers) > 3:
            print(f"    ... run 'peers' command for full list")
    print()

def cmd_limit(client, keyword, dl, ul):
    matches = client.torrents() if keyword == "all" else client.find(keyword)
    if not matches:
        print(f'ERROR: no task matched "{keyword}"')
        return
    hashes = "|".join(t["hash"] for t in matches)
    if dl is not None:
        client.set_dl_limit(hashes, int(dl * 1024))
        print(f"OK: DL limit for {len(matches)} task(s) -> {f'{dl} KB/s' if dl > 0 else 'unlimited'}")
    if ul is not None:
        client.set_ul_limit(hashes, int(ul * 1024))
        print(f"OK: UL limit for {len(matches)} task(s) -> {f'{ul} KB/s' if ul > 0 else 'unlimited'}")

def cmd_speedlimit(client, dl, ul, toggle_alt):
    if toggle_alt:
        client.toggle_alt_speed()
        state = client.get_alt_speed_state()
        print(f"OK: turtle mode {'enabled' if state == '1' else 'disabled'}")
        return
    if dl is not None:
        client.set_global_dl_limit(int(dl * 1024))
        print(f"OK: global DL limit -> {f'{dl} KB/s' if dl > 0 else 'unlimited'}")
    if ul is not None:
        client.set_global_ul_limit(int(ul * 1024))
        print(f"OK: global UL limit -> {f'{ul} KB/s' if ul > 0 else 'unlimited'}")
    if dl is None and ul is None:
        dl_cur = client.get_global_dl_limit()
        ul_cur = client.get_global_ul_limit()
        alt    = client.get_alt_speed_state()
        print(f"  Global DL limit : {fmt_speed(dl_cur) if dl_cur > 0 else 'unlimited'}")
        print(f"  Global UL limit : {fmt_speed(ul_cur) if ul_cur > 0 else 'unlimited'}")
        print(f"  Turtle mode     : {'on' if alt == '1' else 'off'}")

def cmd_tag(client, keyword, tags):
    matches = client.torrents() if keyword == "all" else client.find(keyword)
    if not matches:
        print(f'ERROR: no task matched "{keyword}"')
        return
    client.add_tags("|".join(t["hash"] for t in matches), tags)
    print(f"OK: added tag(s) [{tags}] to {len(matches)} task(s)")

def cmd_untag(client, keyword, tags):
    matches = client.torrents() if keyword == "all" else client.find(keyword)
    if not matches:
        print(f'ERROR: no task matched "{keyword}"')
        return
    client.remove_tags("|".join(t["hash"] for t in matches), tags)
    print(f"OK: removed tag(s) [{tags}] from {len(matches)} task(s)")

def cmd_tags(client):
    tags = client.get_tags()
    all_torrents = client.torrents()
    if not tags:
        print("(no tags)")
        return
    print(f"\n  Tags ({len(tags)}):")
    for tag in tags:
        count = sum(1 for t in all_torrents if tag in (t.get("tags") or ""))
        print(f"    {tag:<30} {count} task(s)")
    print()

def cmd_category(client, keyword, category):
    matches = client.torrents() if keyword == "all" else client.find(keyword)
    if not matches:
        print(f'ERROR: no task matched "{keyword}"')
        return
    client.set_category("|".join(t["hash"] for t in matches), category)
    print(f"OK: category set to [{category}] for {len(matches)} task(s)")

def cmd_categories(client):
    cats = client.get_categories()
    all_torrents = client.torrents()
    if not cats:
        print("(no categories)")
        return
    print(f"\n  Categories ({len(cats)}):")
    for name, info in cats.items():
        count = sum(1 for t in all_torrents if t.get("category") == name)
        path  = info.get("savePath", "")
        print(f"    {name:<25} {count:>3} task(s)  path: {path or '(default)'}")
    print()

def cmd_rename(client, keyword, new_name):
    matches = client.find(keyword)
    if not matches:
        print(f'ERROR: no task matched "{keyword}"')
        return
    if len(matches) > 1:
        print(f"ERROR: {len(matches)} tasks matched, use a more specific keyword:")
        for t in matches: print(f"  - {t['name']}")
        return
    t = matches[0]
    client.rename(t["hash"], new_name)
    print(f"OK: renamed\n  {t['name']}\n  -> {new_name}")

def cmd_move(client, keyword, path):
    matches = client.torrents() if keyword == "all" else client.find(keyword)
    if not matches:
        print(f'ERROR: no task matched "{keyword}"')
        return
    client.set_location("|".join(t["hash"] for t in matches), path)
    print(f"OK: save path -> [{path}] for {len(matches)} task(s)")

def cmd_recheck(client, keyword):
    matches = client.torrents() if keyword == "all" else client.find(keyword)
    if not matches:
        print(f'ERROR: no task matched "{keyword}"')
        return
    client.recheck("|".join(t["hash"] for t in matches))
    print(f"OK: recheck started for {len(matches)} task(s)")

def cmd_top(client, n, sort_by):
    torrents = client.torrents()
    key_map = {
        "size":     lambda t: t.get("size", 0),
        "dl":       lambda t: t.get("dlspeed", 0),
        "ul":       lambda t: t.get("upspeed", 0),
        "ratio":    lambda t: t.get("ratio", 0),
        "progress": lambda t: t.get("progress", 0),
        "added":    lambda t: t.get("added_on", 0),
    }
    label_map = {"size":"size","dl":"DL speed","ul":"UL speed",
                 "ratio":"ratio","progress":"progress","added":"date added"}
    sorted_list = sorted(torrents, key=key_map.get(sort_by, key_map["size"]), reverse=True)[:n]
    print_torrents(sorted_list, title=f"Top {n} by {label_map.get(sort_by, sort_by)}")

def cmd_peers(client, keyword):
    matches = client.find(keyword)
    if not matches:
        print(f'ERROR: no task matched "{keyword}"')
        return
    t = matches[0]
    peers = client.peers(t["hash"])
    if not peers:
        print("No peers connected.")
        return
    seeders  = [p for p in peers.values() if p.get("progress", 0) >= 1.0]
    leechers = [p for p in peers.values() if p.get("progress", 0) < 1.0]
    sep(100)
    print(f"  Peers for: {t['name'][:60]}")
    print(f"  {len(peers)} total — {len(seeders)} seeding / {len(leechers)} leeching")
    sep(100)
    print(f"  {'IP':<24} {'CC':<4} {'Client':<28} {'DL':>10} {'UL':>10} {'Progress':>9}  Flags")
    sep(100)
    for p in sorted(peers.values(), key=lambda x: x.get("dl_speed", 0), reverse=True):
        ip       = f"{p.get('ip','?')}:{p.get('port','')}"
        cc       = p.get("country_code", "--")
        client_s = p.get("client", "?")[:26]
        dl       = fmt_speed(p.get("dl_speed", 0))
        ul       = fmt_speed(p.get("up_speed", 0))
        progress = f"{p.get('progress', 0)*100:.1f}%"
        flags    = p.get("flags", "")
        print(f"  {ip:<24} {cc:<4} {client_s:<28} {dl:>10} {ul:>10} {progress:>9}  {flags}")
    print()


def cmd_rss(client, action, url, path, rule_name, rule_pattern, rule_category):
    if action == "list":
        items = client.rss_items()
        rules = client.rss_rules()
        sep(50)
        print("  RSS Feeds")
        sep(50)
        def print_node(node, indent=0):
            for k, v in node.items():
                if isinstance(v, dict) and "url" in v:
                    print(f"  {'  '*indent}[feed] {k}  ({v.get('url','?')[:50]})")
                elif isinstance(v, dict):
                    print(f"  {'  '*indent}[dir]  {k}/")
                    print_node(v, indent+1)
        if items: print_node(items)
        else: print("  (no feeds)")
        sep(50)
        print(f"  Auto-download Rules ({len(rules)})")
        sep(50)
        if rules:
            for name, r in rules.items():
                enabled = "[on] " if r.get("enabled") else "[off]"
                print(f"  {enabled} {name}")
                print(f"         must contain : {r.get('mustContain','*')}")
                print(f"         must not     : {r.get('mustNotContain','-') or '-'}")
                print(f"         category     : {r.get('assignedCategory','-') or '-'}")
        else:
            print("  (no rules)")
        print()
    elif action == "add":
        if not url: print("ERROR: --url is required"); return
        client.rss_add_feed(url, path or "")
        print(f"OK: feed added: {url}")
    elif action == "remove":
        if not path: print("ERROR: --path is required"); return
        client.rss_remove(path)
        print(f"OK: removed: {path}")
    elif action == "addrule":
        if not rule_name or not rule_pattern: print("ERROR: --name and --pattern are required"); return
        client.rss_set_rule(rule_name, {
            "enabled": True, "mustContain": rule_pattern, "mustNotContain": "",
            "useRegex": False, "assignedCategory": rule_category or "",
            "savePath": "", "ignoreDays": 0,
        })
        print(f"OK: rule created [{rule_name}]  pattern: {rule_pattern}")
    elif action == "removerule":
        if not rule_name: print("ERROR: --name is required"); return
        client.rss_remove_rule(rule_name)
        print(f"OK: rule deleted: {rule_name}")


def main():
    parser = argparse.ArgumentParser(
        description="qBittorrent WebUI Management Tool (v5.0+)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python3 qbt.py add movie.torrent --category movies
  python3 qbt.py add "magnet:?xt=urn:btih:..." --savepath /data/tv --tags "4K,drama"
  python3 qbt.py list --filter downloading
  python3 qbt.py list --tag 4K --sort size
  python3 qbt.py search ubuntu
  python3 qbt.py status
  python3 qbt.py info ubuntu
  python3 qbt.py pause ubuntu
  python3 qbt.py resume all
  python3 qbt.py delete ubuntu --files
  python3 qbt.py limit ubuntu --dl 500 --ul 100
  python3 qbt.py limit ubuntu --dl 0           # remove limit
  python3 qbt.py speedlimit --dl 2048 --ul 512
  python3 qbt.py speedlimit --alt              # toggle turtle mode
  python3 qbt.py speedlimit                    # show current limits
  python3 qbt.py tag ubuntu --tags "linux,iso"
  python3 qbt.py untag ubuntu --tags "iso"
  python3 qbt.py tags
  python3 qbt.py category ubuntu --cat Linux
  python3 qbt.py categories
  python3 qbt.py rename ubuntu --name "Ubuntu 24.04 LTS"
  python3 qbt.py move ubuntu --path /data/iso
  python3 qbt.py recheck ubuntu
  python3 qbt.py top --n 10 --sort size
  python3 qbt.py top --n 5 --sort dl
  python3 qbt.py rss list
  python3 qbt.py rss add --url "https://example.com/rss"
  python3 qbt.py rss addrule --name "4K shows" --pattern "2160p" --category TV
        """
    )
    parser.add_argument("--host", default=os.environ.get("QBT_HOST", DEFAULT_HOST))
    parser.add_argument("--user", default=os.environ.get("QBT_USER", DEFAULT_USER))
    parser.add_argument("--pass", dest="password", default=os.environ.get("QBT_PASS", DEFAULT_PASS))

    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="Add a download task")
    p.add_argument("source", help=".torrent file, https URL, or magnet link")
    p.add_argument("--savepath")
    p.add_argument("--category")
    p.add_argument("--tags", help="Comma-separated tags")
    p.add_argument("--paused", action="store_true")
    p.add_argument("--sequential", action="store_true")

    p = sub.add_parser("list", help="List tasks")
    p.add_argument("--filter", dest="filter_status", default="all",
        choices=["all","downloading","seeding","completed","paused","active",
                 "inactive","stalled","stalled_downloading","stalled_uploading","errored","resumed"])
    p.add_argument("--category")
    p.add_argument("--tag")
    p.add_argument("--sort", choices=["name","size","progress","dlspeed","upspeed","ratio","added_on"], default="added_on")
    p.add_argument("--asc", action="store_true")

    p = sub.add_parser("search", help="Search tasks by name")
    p.add_argument("keyword")

    sub.add_parser("status", help="Show global transfer status")

    for cmd_name, help_text in [("pause","Pause"), ("resume","Resume"), ("recheck","Recheck")]:
        p = sub.add_parser(cmd_name, help=f"{help_text} tasks (keyword or 'all')")
        p.add_argument("keyword")

    p = sub.add_parser("delete", help="Delete tasks")
    p.add_argument("keyword", help="Name keyword or 'all'")
    p.add_argument("--files", action="store_true", help="Also delete local files")

    p = sub.add_parser("info", help="Show task details")
    p.add_argument("keyword")

    p = sub.add_parser("peers", help="Show peer list for a task")
    p.add_argument("keyword")

    p = sub.add_parser("limit", help="Set per-task speed limit")
    p.add_argument("keyword")
    p.add_argument("--dl", type=float, help="DL limit KB/s (0=unlimited)")
    p.add_argument("--ul", type=float, help="UL limit KB/s (0=unlimited)")

    p = sub.add_parser("speedlimit", help="View/set global speed limits")
    p.add_argument("--dl", type=float)
    p.add_argument("--ul", type=float)
    p.add_argument("--alt", action="store_true", help="Toggle turtle mode")

    p = sub.add_parser("tag", help="Add tags to tasks")
    p.add_argument("keyword")
    p.add_argument("--tags", required=True)

    p = sub.add_parser("untag", help="Remove tags from tasks")
    p.add_argument("keyword")
    p.add_argument("--tags", required=True)

    sub.add_parser("tags", help="List all tags")

    p = sub.add_parser("category", help="Set category for tasks")
    p.add_argument("keyword")
    p.add_argument("--cat", required=True)

    sub.add_parser("categories", help="List all categories")

    p = sub.add_parser("rename", help="Rename a task")
    p.add_argument("keyword")
    p.add_argument("--name", required=True)

    p = sub.add_parser("move", help="Change save path")
    p.add_argument("keyword")
    p.add_argument("--path", required=True)

    p = sub.add_parser("top", help="Show Top N tasks sorted by a field")
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--sort", choices=["size","dl","ul","ratio","progress","added"], default="size")

    p = sub.add_parser("rss", help="RSS feed management")
    p.add_argument("action", choices=["list","add","remove","addrule","removerule"])
    p.add_argument("--url")
    p.add_argument("--path")
    p.add_argument("--name")
    p.add_argument("--pattern")
    p.add_argument("--category")

    args = parser.parse_args()
    client = QBTClient(args.host, args.user, args.password)
    if not client.login(): sys.exit(1)

    cmd = args.cmd
    if   cmd == "add":        client.add(args.source, args.savepath, args.category, args.tags, args.paused, args.sequential)
    elif cmd == "list":
        label_map = {"all":"All","downloading":"Downloading","seeding":"Seeding","completed":"Completed",
                     "paused":"Paused","active":"Active","inactive":"Inactive","stalled":"Stalled","errored":"Errored"}
        label = label_map.get(args.filter_status, args.filter_status)
        if args.category: label += f" / cat:{args.category}"
        if args.tag:      label += f" / tag:{args.tag}"
        ts = client.torrents(args.filter_status, args.category, args.tag, sort=args.sort, reverse=not args.asc)
        print_torrents(ts, title=label)
    elif cmd == "search":     print_torrents(client.find(args.keyword), title=f'Search: "{args.keyword}"')
    elif cmd == "status":     cmd_status(client)
    elif cmd == "pause":      cmd_pause(client, args.keyword)
    elif cmd == "resume":     cmd_resume(client, args.keyword)
    elif cmd == "delete":     cmd_delete(client, args.keyword, args.files)
    elif cmd == "info":       cmd_info(client, args.keyword)
    elif cmd == "peers":      cmd_peers(client, args.keyword)
    elif cmd == "limit":      cmd_limit(client, args.keyword, args.dl, args.ul)
    elif cmd == "speedlimit": cmd_speedlimit(client, args.dl, args.ul, args.alt)
    elif cmd == "tag":        cmd_tag(client, args.keyword, args.tags)
    elif cmd == "untag":      cmd_untag(client, args.keyword, args.tags)
    elif cmd == "tags":       cmd_tags(client)
    elif cmd == "category":   cmd_category(client, args.keyword, args.cat)
    elif cmd == "categories": cmd_categories(client)
    elif cmd == "rename":     cmd_rename(client, args.keyword, args.name)
    elif cmd == "move":       cmd_move(client, args.keyword, args.path)
    elif cmd == "recheck":    cmd_recheck(client, args.keyword)
    elif cmd == "top":        cmd_top(client, args.n, args.sort)
    elif cmd == "rss":        cmd_rss(client, args.action, args.url, args.path, args.name, args.pattern, args.category)

if __name__ == "__main__":
    main()
