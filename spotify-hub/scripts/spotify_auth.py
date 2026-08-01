"""
Spotify OAuth 授权脚本。
启动本地 HTTP server 监听回调，打印授权 URL，自动捕获 code 换取 token。
Token 保存至 ~/.config/spotify/cache，包含 refresh_token，永久免登录。

用法：uv run --script --cache-dir /root/.cache/uv spotify_auth.py
"""
# /// script
# requires-python = ">=3.10"
# dependencies = ["spotipy>=2.26.0"]
# ///

import os, threading, urllib.parse, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from spotipy.oauth2 import SpotifyOAuth

SCOPE = " ".join([
    # 播放控制
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "streaming",
    # 音乐库
    "user-library-read",
    "user-library-modify",
    # 歌单
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
    # 用户信息
    "user-read-private",
    "user-read-email",
    # 收听历史 & 推荐
    "user-top-read",
    "user-read-recently-played",
    # 关注
    "user-follow-read",
    "user-follow-modify",
])
REDIRECT_URI = os.environ["SPOTIPY_REDIRECT_URI"]
CACHE_PATH = os.path.expanduser("~/.config/spotify/cache")

parsed = urllib.parse.urlparse(REDIRECT_URI)
PORT = parsed.port or 80
CALLBACK_PATH = parsed.path or "/callback"

os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)

auth_manager = SpotifyOAuth(
    client_id=os.environ["SPOTIPY_CLIENT_ID"],
    client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    cache_path=CACHE_PATH,
    open_browser=False,
)

# 已有有效 token 则跳过
token_info = auth_manager.get_cached_token()
if token_info and not auth_manager.is_token_expired(token_info):
    print("✅ 已有有效 Token，无需重新授权")
    sys.exit(0)

auth_code = None
server_done = threading.Event()

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        if self.path.startswith(CALLBACK_PATH):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            auth_code = params.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>✅ Spotify 授权成功！可以关闭浏览器了 🎉</h2>".encode("utf-8"))
            server_done.set()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

server = HTTPServer(("127.0.0.1", PORT), CallbackHandler)
t = threading.Thread(target=lambda: server.serve_forever())
t.daemon = True
t.start()

auth_url = auth_manager.get_authorize_url()

# 写入文件供外部读取
with open("/tmp/spotify_auth_url.txt", "w") as f:
    f.write(auth_url)

print(f"AUTH_URL={auth_url}", flush=True)
print(f"⏳ 等待授权回调（监听 {REDIRECT_URI}）...", flush=True)

server_done.wait(timeout=120)
server.shutdown()

if auth_code:
    auth_manager.get_access_token(auth_code, as_dict=False, check_cache=False)
    print("✅ 授权成功！Token 已保存至 ~/.config/spotify/cache")
else:
    print("❌ 授权超时，请重试")
    sys.exit(1)
