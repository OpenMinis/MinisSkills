#!/bin/sh
# refresh_cookie.sh — 刷新夸克网盘 Cookie
#
# 流程：
#   1. navigate 打开夸克主页，触发 WebView 与服务端 Cookie 交换
#   2. 等待页面加载完成
#   3. get_cookies 提取最新 Cookie 并写入 ~/.quark_hub_cookie
#
# 用法：sh /var/minis/skills/quark-hub/scripts/refresh_cookie.sh

COOKIE_FILE="$HOME/.quark_hub_cookie"

echo "[refresh] 打开夸克主页刷新 Cookie……"
minis-browser-use navigate --url https://pan.quark.cn >/dev/null 2>&1
sleep 3

echo "[refresh] 提取 Cookie……"
ENV_FILE=$(minis-browser-use get_cookies -q 2>/dev/null \
  | python3 -c "import sys,json,re;m=re.search(r'/var/minis/offloads/env_cookies_\S+\.sh',json.load(sys.stdin).get('text',''));print(m.group(0) if m else '')")

if [ -z "$ENV_FILE" ]; then
  echo "[refresh] ❌ 无法提取 Cookie，请确认已在浏览器中登录夸克网盘"
  exit 1
fi

. "$ENV_FILE"

if [ -z "$BROWSER_COOKIE_HEADER" ]; then
  echo "[refresh] ❌ BROWSER_COOKIE_HEADER 为空"
  exit 1
fi

printf '%s' "$BROWSER_COOKIE_HEADER" > "$COOKIE_FILE"
chmod 600 "$COOKIE_FILE"
echo "[refresh] ✅ Cookie 已保存至 $COOKIE_FILE ($(wc -c < "$COOKIE_FILE") bytes)"
