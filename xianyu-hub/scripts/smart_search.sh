#!/bin/sh
# smart_search.sh — 智能搜索：自动关键字增强
# 当闲鱼直接搜索结果为空或极少时，自动补充该商品的常用别称，再重试搜索
#
# 用法:
#   sh scripts/smart_search.sh -k <关键词> [闲鱼 search.sh 其他参数]
#
# 示例:
#   sh scripts/smart_search.sh -k "GTA"
#   sh scripts/smart_search.sh -k "VPN" --city 上海 --max-price 100
#   sh scripts/smart_search.sh -k "gpt plus"

# ── 定位脚本目录（无论从哪里调用都能找到兄弟脚本）────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SEARCH_SH="$SCRIPT_DIR/search.sh"

KEYWORD=""
EXTRA_ARGS=""
MIN_RESULTS=3         # 少于这个数量视为"搜不到"
MAX_RETRY_KW=3        # 最多用几个别称重试

# 解析参数（-k 给 smart_search，其余透传给 search.sh）
while [ $# -gt 0 ]; do
  case "$1" in
    -k) KEYWORD="$2"; shift 2 ;;
    *)  EXTRA_ARGS="$EXTRA_ARGS $1"; shift ;;
  esac
done

if [ -z "$KEYWORD" ]; then
  echo "用法: sh scripts/smart_search.sh -k <关键词> [其他参数]"
  exit 1
fi

url_encode() {
  python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$1"
}

fetch_api() {
  curl -sS \
    -H "Accept: application/json" \
    -H "Referer: https://search-sharp.com/" \
    -H "User-Agent: Mozilla/5.0" \
    "$1"
}

count_results() {
  # 从 search.sh JSON 输出统计条数
  python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    items = d.get('data',{}).get('resultList') or []
    print(len(items))
except:
    print(0)
"
}

echo "🔍 智能搜索：「${KEYWORD}」"
echo "══════════════════════════════════════════════════"

# ── Step 1：先直接搜闲鱼 ─────────────────────────────────────────────
echo ""
echo "▶ Step 1  直接搜索「${KEYWORD}」..."
DIRECT_OUTPUT=$(sh "$SEARCH_SH" -k "$KEYWORD" -n 20 $EXTRA_ARGS 2>&1)
DIRECT_COUNT=$(echo "$DIRECT_OUTPUT" | grep -E '^\[' | wc -l | tr -d ' ')

echo "$DIRECT_OUTPUT"

if [ "$DIRECT_COUNT" -ge "$MIN_RESULTS" ]; then
  echo ""
  echo "✅ 找到 ${DIRECT_COUNT} 条结果，无需关键字增强。"
  exit 0
fi

# ── Step 2：结果不足，查别称 ────────────────────────────
echo ""
echo "⚠️  直接搜索结果较少（${DIRECT_COUNT} 条），启动关键字增强模式..."
echo ""
echo "▶ Step 2  查询「${KEYWORD}」的常用别称（SearchSharp.com）..."

ENCODED=$(url_encode "$KEYWORD")
DARK_RAW=$(fetch_api "https://search-sharp.com/api/products?q=${ENCODED}")

# 提取别称列表
DARK_KEYWORDS=$(python3 - "$DARK_RAW" << 'PYEOF'
import sys, json
data = json.loads(sys.argv[1])
products = data.get('products', [])
if not products:
    sys.exit(0)
seen = set()
results = []
for p in products:
    kws = p.get('keywords') or []
    kws_sorted = sorted(kws, key=lambda k: k.get('up',0) - k.get('down',0), reverse=True)
    for kw in kws_sorted[:6]:
        t = kw['text'].strip()
        if t and t not in seen:
            seen.add(t)
            score = kw.get('up',0) - kw.get('down',0)
            results.append((score, t))
results.sort(reverse=True)
for _, t in results[:10]:
    print(t)
PYEOF
)

if [ -z "$DARK_KEYWORDS" ]; then
  echo "❌ SearchSharp 也没找到「${KEYWORD}」的常用别称记录。"
  echo ""
  echo "💡 建议："
  echo "   1. 换同义词重试，如「${KEYWORD}会员」「${KEYWORD}账号」等"
  echo "   2. 用 sh scripts/alt_keywords.sh --list 浏览热门别称"
  exit 0
fi

echo ""
echo "📖 找到以下别称关键字："
echo "$DARK_KEYWORDS" | while IFS= read -r kw; do
  echo "   • ${kw}"
done

# ── Step 3：逐个别称重试搜索 ─────────────────────────────────────────
echo ""
echo "▶ Step 3  用别称关键字逐一重搜闲鱼..."
echo "══════════════════════════════════════════════════"

RETRY=0
FOUND_ANY=0

echo "$DARK_KEYWORDS" | while IFS= read -r kw; do
  [ -z "$kw" ] && continue
  RETRY=$((RETRY + 1))
  [ "$RETRY" -gt "$MAX_RETRY_KW" ] && break

  echo ""
  echo "🔄 尝试别称 [$RETRY/$MAX_RETRY_KW]：「${kw}」"
  echo "──────────────────────────────────────────────────"
  RETRY_OUTPUT=$(sh "$SEARCH_SH" -k "$kw" -n 15 $EXTRA_ARGS 2>&1)
  RETRY_COUNT=$(echo "$RETRY_OUTPUT" | grep -E '^\[' | wc -l | tr -d ' ')
  echo "$RETRY_OUTPUT"
  if [ "$RETRY_COUNT" -ge 1 ]; then
    echo ""
    echo "✅ 别称「${kw}」找到 ${RETRY_COUNT} 条结果！"
    FOUND_ANY=1
  fi
done

echo ""
echo "══════════════════════════════════════════════════"
echo "💡 提示：更多别称可运行："
echo "   sh scripts/alt_keywords.sh -q \"${KEYWORD}\""
