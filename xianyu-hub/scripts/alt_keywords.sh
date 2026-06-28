#!/bin/sh
# alt_keywords.sh — 通过 SearchSharp.com 查询商品在各平台的常用别称
# 用法:
#   sh scripts/alt_keywords.sh -q <搜索词>       # 查询别称
#   sh scripts/alt_keywords.sh --list            # 列出热门商品
#   sh scripts/alt_keywords.sh --id <id>         # 查看某商品全部别称
#   sh scripts/alt_keywords.sh -j                # JSON 输出

# ── 定位脚本目录（无论从哪里调用都能找到兄弟脚本）────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

BASE_URL="https://search-sharp.com"
QUERY=""
PRODUCT_ID=""
LIST_MODE=0
JSON_MODE=0

while [ $# -gt 0 ]; do
  case "$1" in
    -q|--query) QUERY="$2"; shift 2 ;;
    --id)       PRODUCT_ID="$2"; shift 2 ;;
    --list)     LIST_MODE=1; shift ;;
    -j|--json)  JSON_MODE=1; shift ;;
    *) shift ;;
  esac
done

# ── 工具函数 ─────────────────────────────────────────────────────────
url_encode() {
  python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$1"
}

fetch_api() {
  curl -sS \
    -H "Accept: application/json" \
    -H "Referer: https://search-sharp.com/" \
    -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
    "$1"
}

# ── 净分排序取关键词 ──────────────────────────────────────────────────
top_keywords() {
  # 输入: JSON 数组 keywords，按 (up-down) 降序，返回 top 前 N 个
  python3 - "$1" "$2" << 'PYEOF'
import sys, json
data = json.loads(sys.argv[1])
n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
kws = sorted(data, key=lambda k: k.get('up',0) - k.get('down',0), reverse=True)
for kw in kws[:n]:
    score = kw.get('up',0) - kw.get('down',0)
    print(f"  👍{kw.get('up',0)} 👎{kw.get('down',0)} (净分+{score})  {kw['text']}")
PYEOF
}

format_product() {
  python3 - "$1" << 'PYEOF'
import sys, json
p = json.loads(sys.argv[1])
aliases = p.get('aliases') or []
kws = p.get('keywords') or []
kws_sorted = sorted(kws, key=lambda k: k.get('up',0) - k.get('down',0), reverse=True)

print(f"📦 {p['name']}", end="")
if aliases:
    print(f"  (又名: {' / '.join(aliases)})", end="")
print(f"\n   共 {len(kws)} 个别称，按热度排序：")
for i, kw in enumerate(kws_sorted[:10], 1):
    score = kw.get('up',0) - kw.get('down',0)
    bar = "★" * min(score, 5) if score > 0 else ""
    print(f"   {i:02d}. {kw['text']:<20} 👍{kw.get('up',0)} 👎{kw.get('down',0)} {bar}")
PYEOF
}

# ── 列出热门商品 ──────────────────────────────────────────────────────
if [ "$LIST_MODE" = "1" ]; then
  RAW=$(fetch_api "${BASE_URL}/api/products")
  if [ "$JSON_MODE" = "1" ]; then
    echo "$RAW"
    exit 0
  fi
  echo "🔥 SearchSharp 热门商品别称"
  echo "──────────────────────────────────────────────────"
  python3 - "$RAW" << 'PYEOF'
import sys, json
data = json.loads(sys.argv[1])
products = data.get('products', [])
for i, p in enumerate(products, 1):
    kws = p.get('keywords') or []
    top3 = sorted(kws, key=lambda k: k.get('up',0)-k.get('down',0), reverse=True)[:3]
    top3_names = ' / '.join(k['text'] for k in top3)
    print(f"[{i:02d}] ID:{p['id']:<4} {p['name']:<20} → {top3_names}")
PYEOF
  exit 0
fi

# ── 查某商品详情 ──────────────────────────────────────────────────────
if [ -n "$PRODUCT_ID" ]; then
  RAW=$(fetch_api "${BASE_URL}/api/products/${PRODUCT_ID}")
  if [ "$JSON_MODE" = "1" ]; then
    echo "$RAW"
    exit 0
  fi
  echo "🔎 别称详情"
  echo "──────────────────────────────────────────────────"
  python3 - "$RAW" << 'PYEOF'
import sys, json
data = json.loads(sys.argv[1])
p = data.get('product', {})
aliases = p.get('aliases') or []
kws = p.get('keywords') or []
kws_sorted = sorted(kws, key=lambda k: k.get('up',0) - k.get('down',0), reverse=True)
print(f"📦 {p['name']}", end="")
if aliases:
    print(f"  (又名: {' / '.join(aliases)})", end="")
print(f"\n   共 {len(kws)} 个别称：")
for i, kw in enumerate(kws_sorted, 1):
    score = kw.get('up',0) - kw.get('down',0)
    print(f"   {i:02d}. {kw['text']:<25} 净分: +{score} (👍{kw.get('up',0)} 👎{kw.get('down',0)})")
PYEOF
  exit 0
fi

# ── 搜索模式 ──────────────────────────────────────────────────────────
if [ -z "$QUERY" ]; then
  echo "用法: sh scripts/alt_keywords.sh -q <搜索词>"
  echo "      sh scripts/alt_keywords.sh --list"
  echo "      sh scripts/alt_keywords.sh --id <商品ID>"
  exit 1
fi

ENCODED=$(url_encode "$QUERY")
RAW=$(fetch_api "${BASE_URL}/api/products?q=${ENCODED}")

if [ "$JSON_MODE" = "1" ]; then
  echo "$RAW"
  exit 0
fi

echo "🔍 搜索「${QUERY}」的常用别称"
echo "──────────────────────────────────────────────────"

python3 - "$RAW" "$QUERY" << 'PYEOF'
import sys, json
data = json.loads(sys.argv[1])
query = sys.argv[2]
products = data.get('products', [])
if not products:
    print(f"❌ 未找到相关别称")
    print("💡 提示：可用 --list 查看全部热门商品")
    sys.exit(0)

print(f"找到 {len(products)} 个匹配商品：\n")
for p in products:
    aliases = p.get('aliases') or []
    kws = p.get('keywords') or []
    kws_sorted = sorted(kws, key=lambda k: k.get('up',0) - k.get('down',0), reverse=True)
    print(f"📦 【{p['name']}】", end="")
    if aliases:
        print(f"  (又名: {' / '.join(aliases)})", end="")
    print(f"  共{len(kws)}个别称")
    for i, kw in enumerate(kws_sorted[:8], 1):
        score = kw.get('up',0) - kw.get('down',0)
        star = "🔥" if score >= 10 else ("⭐" if score >= 5 else "  ")
        print(f"  {star} {i:02d}. {kw['text']}")
    if len(kws) > 8:
        print(f"       ...还有 {len(kws)-8} 个，用 --id {p['id']} 查看全部")
    print()
PYEOF
