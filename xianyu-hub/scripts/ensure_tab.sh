#!/bin/sh
# ensure_tab.sh
# 确保浏览器有已登录的闲鱼 tab，输出 tab_id。
#
# 流程：
#   1. 检测 set_cookies 是否支持（keep the browser action 策略）
#   2. 支持 → 用缓存 cookie 恢复登录态；不支持 → 提示用户手动登录
#   3. 成功登录后刷新一次 cookie 缓存，供下次使用
#
# Cookie 缓存路径：~/.cache/xianyu_cookies.txt
# 环境变量：
#   TAB_ID  — 若已知 tab_id，跳过自动检测（仍会验证登录态）

COOKIE_CACHE="$HOME/.cache/xianyu_cookies.txt"

# ---------- 辅助：检测某 tab 的登录状态 ----------
check_login() {
  local tid="$1"
  minis-browser-use execute_js --tab-id "$tid" \
    --script 'return window.location.href.includes("passport") ? "not_login" : (window.lib && window.lib.mtop ? "ok" : "loading")' \
    --compact -q 2>/dev/null \
    | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('text','').split('\n')[0].strip())
except Exception:
    print('error')
" 2>/dev/null
}

# ---------- 辅助：扫描所有 tab，找含有闲鱼域名的 tab ----------
find_logged_tab() {
  local raw
  raw=$(minis-browser-use list_tabs --compact -q 2>/dev/null)
  python3 -c "
import json, sys, re
try:
    d = json.loads(sys.argv[1])
    text = d.get('text', '')
    for line in text.split('\n'):
        m = re.search(r'Tab (\d+):.*?(https?://\S+)', line)
        if m:
            tab_id = m.group(1)
            url = m.group(2).rstrip('* ')
            if 'goofish.com' in url or 'xianyu' in url:
                print(tab_id)
                break
except Exception:
    pass
" "$raw" 2>/dev/null
}

# ---------- 辅助：检测当前版本是否支持 set_cookies ----------
# 策略：keep the browser action — 直接调用 set_cookies 传一个空数组，
# 若返回的错误是 'cookies' array is empty 说明支持（功能存在但参数为空）；
# 若返回 unknown action / action not found 类错误则不支持。
check_set_cookies_support() {
  # 通过 CLI help 检测是否支持 set_cookies，比调用更轻量无副作用
  minis-browser-use --help 2>&1 | grep -q 'set_cookies' && echo 'supported' || echo 'unsupported'
}

# ---------- 辅助：从缓存文件读取 cookies，构建 JSON 数组 ----------
build_cookies_json() {
  [ -f "$COOKIE_CACHE" ] || return 1
  python3 -c "
import sys, json, re

HTTPONLY = {'t', 'cookie2', 'sgcookie'}
SECURE   = {'sgcookie'}
path = sys.argv[1]
cookies = []
with open(path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        eq = line.index('=') if '=' in line else -1
        if eq <= 0:
            continue
        name  = line[:eq].strip()
        value = line[eq+1:].strip()
        c = {
            'name':   name,
            'value':  value,
            'domain': '.goofish.com',
            'path':   '/'
        }
        if name in HTTPONLY:
            c['http_only'] = True
        if name in SECURE:
            c['secure'] = True
        cookies.append(c)
print(json.dumps(cookies))
" "$COOKIE_CACHE" 2>/dev/null
}

# ---------- 辅助：导航到闲鱼首页，确保在正确域下 ----------
navigate_to_goofish() {
  local tid="$1"
  if [ -n "$tid" ]; then
    minis-browser-use navigate --tab-id "$tid" --url "https://www.goofish.com/" --compact -q >/dev/null 2>&1
  else
    minis-browser-use navigate --url "https://www.goofish.com/" --compact -q >/dev/null 2>&1
  fi
}

# ---------- 辅助：保存当前 tab 的 cookie 到缓存 ----------
save_cookies() {
  local tid="$1"
  local env_file
  env_file=$(minis-browser-use get_cookies --tab-id "$tid" --compact -q 2>/dev/null \
    | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    text = d.get('text', '')
    for line in text.split('\n'):
        line = line.strip()
        if '/var/minis/offloads/env_cookies_' in line:
            print(line)
            break
except Exception:
    pass
" 2>/dev/null)

  [ -z "$env_file" ] && return 1

  mkdir -p "$(dirname "$COOKIE_CACHE")"
  python3 -c "
import sys, re, os

env_file = sys.argv[1]
cache    = sys.argv[2]

lines = []
try:
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            # export COOKIE_XXX='value'  →  xxx=value
            m = re.match(r\"export COOKIE_(.+?)='(.*)'\$\", line)
            if not m:
                continue
            # 把 COOKIE_ENV_NAME 转回原始 cookie name（仅做小写，'_' 保留）
            # 真实名字由 env name 推断不准确；此处直接存 envname lower 作为 key
            # 但更准确的是存 BROWSER_COOKIE_HEADER 里的原始 name=value
            pass
    # 改用 BROWSER_COOKIE_HEADER 解析
    with open(env_file) as f:
        content = f.read()
    m = re.search(r\"export BROWSER_COOKIE_HEADER='(.+?)'\", content, re.DOTALL)
    if not m:
        sys.exit(1)
    header = m.group(1).replace(\"'\\\\'' \", \"'\")  # unescape shell single-quote
    pairs = [p.strip() for p in header.split(';') if '=' in p.strip()]
    with open(cache, 'w') as out:
        out.write('# Xianyu (goofish.com) Cookies — auto-saved\n')
        for pair in pairs:
            out.write(pair + '\n')
    os.chmod(cache, 0o600)
    print(str(len(pairs)))
except Exception as e:
    sys.exit(1)
" "$env_file" "$COOKIE_CACHE" 2>/dev/null
}

# ============================================================
# 主流程
# ============================================================

# 1. 找到或复用 tab
if [ -n "$TAB_ID" ]; then
  TRY_TAB="$TAB_ID"
else
  TRY_TAB=$(find_logged_tab)
fi

# 2. 检测是否已经登录
if [ -n "$TRY_TAB" ]; then
  STATUS=$(check_login "$TRY_TAB")
  if [ "$STATUS" = "ok" ]; then
    echo "$TRY_TAB"
    exit 0
  fi
fi

# 3. 未登录 — 检测 set_cookies 支持情况
echo "⏳ 检测 set_cookies 支持情况…" >&2
SUPPORT=$(check_set_cookies_support)

if [ "$SUPPORT" = "supported" ]; then
  # ---- 支持 set_cookies：尝试用缓存 cookie 恢复 ----
  echo "✅ 支持 set_cookies，尝试用缓存 Cookie 恢复登录…" >&2

  COOKIES_JSON=$(build_cookies_json)
  if [ -z "$COOKIES_JSON" ] || [ "$COOKIES_JSON" = "[]" ]; then
    echo "⚠️  无 Cookie 缓存，需要手动登录" >&2
    SUPPORT="unsupported"  # 降级走手动登录流程
  else
    # 展示缓存中找到的 cookie 名列表
    echo "📂 缓存 Cookie（$COOKIE_CACHE）：" >&2
    echo "$COOKIES_JSON" | python3 -c "
import json, sys
cookies = json.load(sys.stdin)
for c in cookies:
    httponly = ' [HttpOnly]' if c.get('http_only') else ''
    secure   = ' [Secure]'  if c.get('secure')    else ''
    print(f'   {c[\"name\"]}={c[\"value\"][:12]}...{httponly}{secure}')
print(f'   共 {len(cookies)} 条')
" >&2

    # 先导航到 goofish.com 域（set_cookies 需要页面在目标域下）
    if [ -n "$TRY_TAB" ]; then
      navigate_to_goofish "$TRY_TAB"
      sleep 1
    else
      navigate_to_goofish ""
      sleep 1
      TRY_TAB=$(find_logged_tab)
    fi
    [ -z "$TRY_TAB" ] && TRY_TAB=1  # fallback

    # 注入 cookies — 展示完整 set_cookies 结果
    echo "🍪 正在注入 Cookie（tab $TRY_TAB）…" >&2
    SET_RESULT=$(minis-browser-use set_cookies --tab-id "$TRY_TAB" \
      --cookies "$COOKIES_JSON" --compact -q 2>&1 \
      | python3 -c "
import json, sys
raw = sys.stdin.read()
try:
    d = json.loads(raw)
    print(d.get('text', raw))
except Exception:
    print(raw)
" 2>/dev/null)
    echo "   → $SET_RESULT" >&2

    # 刷新首页验证登录态
    echo "🔄 刷新首页验证登录…" >&2
    navigate_to_goofish "$TRY_TAB"
    sleep 2

    STATUS=$(check_login "$TRY_TAB")
    if [ "$STATUS" = "ok" ]; then
      echo "✅ Cookie 恢复登录成功！" >&2
      # 刷新后重新保存一次 cookie（更新时效）
      SAVED=$(save_cookies "$TRY_TAB")
      [ -n "$SAVED" ] && echo "💾 已更新 Cookie 缓存（$SAVED 条）→ $COOKIE_CACHE" >&2
      echo "$TRY_TAB"
      exit 0
    else
      echo "⚠️  缓存 Cookie 已过期，需要重新登录…" >&2
      SUPPORT="unsupported"  # Cookie 失效，降级走手动登录
    fi
  fi
fi

# ---- 不支持 set_cookies 或 Cookie 已过期：提示手动登录 ----
echo "🐟 请在浏览器中登录闲鱼，最多等待 15 秒…" >&2

# 用 minis-open 把内置浏览器弹到前台给用户操作
minis-open "minis://views/browser" >/dev/null 2>&1

# 同时 navigate 过去
navigate_to_goofish "$TRY_TAB"
[ -z "$TRY_TAB" ] && TRY_TAB=$(find_logged_tab)

# 轮询等待登录完成（每 3s，最多 5 次 = 15s）
i=0
while [ $i -lt 5 ]; do
  sleep 3
  i=$((i + 1))

  [ -z "$TRY_TAB" ] && TRY_TAB=$(find_logged_tab)
  [ -z "$TRY_TAB" ] && continue

  STATUS=$(check_login "$TRY_TAB")
  if [ "$STATUS" = "ok" ]; then
    echo "✅ 登录成功！" >&2

    # 登录成功后立即保存 cookie（供下次 set_cookies 恢复用）
    if [ "$(check_set_cookies_support)" = "supported" ]; then
      SAVED=$(save_cookies "$TRY_TAB")
      [ -n "$SAVED" ] && echo "💾 已保存 Cookie 缓存（$SAVED 条）→ $COOKIE_CACHE" >&2
    fi

    echo "$TRY_TAB"
    exit 0
  fi
done

echo "❌ 等待超时，未检测到登录。请手动登录后重试。" >&2
exit 1
