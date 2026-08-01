#!/bin/sh
# =============================================================
# 闲鱼搜索脚本
#
# 依赖：需要在 Minis 内置浏览器中登录闲鱼（https://www.goofish.com）
#       脚本会自动检测登录状态，未登录时会提示
#
# 用法:
#   xianyu_search.sh -k <关键词> [选项]
#
# 选项:
#   -k, --keyword    <关键词>  搜索关键词（必填）
#   -p, --page       <页码>   页码，默认 1
#   -n, --rows       <数量>   每页数量，默认 20（最大 30）
#   -s, --sort       <排序>   排序方式：
#                               default    综合排序（默认）
#                               price_asc  价格从低到高
#                               price_desc 价格从高到低
#                               time       最新发布
#                               reduce     最新降价
#   --min-price      <价格>   最低价格过滤（元）
#   --max-price      <价格>   最高价格过滤（元）
#   --city           <城市>   按城市过滤（如：北京、上海、广东）
#   --personal-only           只看个人闲置（评价数 ≤10 的卖家）
#   --tab-id         <id>     手动指定浏览器 tab id（默认自动检测）
#   -j, --json                输出原始 JSON
#   -h, --help                显示帮助
#
# 示例:
#   search.sh -k "MacBook Air" -s price_asc -n 10
#   search.sh -k "iPhone15" --min-price 1000 --max-price 3000 --city 上海
#   search.sh -k "iPad" -s time --personal-only
#   search.sh -k "Switch" -s reduce -j
# =============================================================

KEYWORD=""
PAGE=1
ROWS=20
SORT="default"
MIN_PRICE=""
MAX_PRICE=""
CITY=""
PERSONAL_ONLY=false
OUTPUT_JSON=false
TAB_ID=""

while [ $# -gt 0 ]; do
  case "$1" in
    -k|--keyword)      KEYWORD="$2";       shift 2 ;;
    -p|--page)         PAGE="$2";          shift 2 ;;
    -n|--rows)         ROWS="$2";          shift 2 ;;
    -s|--sort)         SORT="$2";          shift 2 ;;
    --min-price)       MIN_PRICE="$2";     shift 2 ;;
    --max-price)       MAX_PRICE="$2";     shift 2 ;;
    --city)            CITY="$2";          shift 2 ;;
    --tab-id)          TAB_ID="$2";        shift 2 ;;
    --personal-only)   PERSONAL_ONLY=true; shift 1 ;;
    -j|--json)         OUTPUT_JSON=true;   shift 1 ;;
    -h|--help)         sed -n '3,37p' "$0"; exit 0 ;;
    *)  [ -z "$KEYWORD" ] && KEYWORD="$1"; shift 1 ;;
  esac
done

if [ -z "$KEYWORD" ]; then
  echo "错误: 请提供搜索关键词（-k <关键词>）" >&2
  exit 1
fi

case "$SORT" in
  price_asc)  SORT_FIELD="price";        SORT_VALUE="asc"  ;;
  price_desc) SORT_FIELD="price";        SORT_VALUE="desc" ;;
  time)       SORT_FIELD="time";         SORT_VALUE="desc" ;;
  reduce)     SORT_FIELD="price_reduce"; SORT_VALUE="desc" ;;
  *)          SORT_FIELD="";             SORT_VALUE=""     ;;
esac

# ---------- 确保有已登录的闲鱼 tab（自动打开 + 检测登录）----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -z "$TAB_ID" ]; then
  TAB_ID=$(sh "$SCRIPT_DIR/ensure_tab.sh") || exit $?
else
  # 已手动指定 tab_id，仍走 ensure_tab 验证登录状态
  TAB_ID=$(TAB_ID="$TAB_ID" sh "$SCRIPT_DIR/ensure_tab.sh") || exit $?
fi
TAB_ARG="--tab-id $TAB_ID"

# ---------- 生成 JS 参数（JSON 安全编码，防注入）----------
KW_JS=$(python3 -c "import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))" "$KEYWORD")
SF_JS=$(python3 -c "import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))" "$SORT_FIELD")
SV_JS=$(python3 -c "import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))" "$SORT_VALUE")
SO_JS=$(python3 -c "import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))" "$SORT")
CI_JS=$(python3 -c "import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))" "$CITY")
MN_JS=$(python3 -c "import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))" "$MIN_PRICE")
MX_JS=$(python3 -c "import json,sys; sys.stdout.write(json.dumps(sys.argv[1]))" "$MAX_PRICE")
PO_JS=$([ "$PERSONAL_ONLY" = "true" ] && echo "true" || echo "false")

# ---------- 把 JS 写到临时文件（避免多行 inline 引号问题）----------
JS_FILE="/tmp/xianyu_search_$$.js"
cat > "$JS_FILE" << JSEOF
return (function() {
  var data = {
    keyword:           ${KW_JS},
    pageNumber:        ${PAGE},
    rowsPerPage:       ${ROWS},
    fromFilter:        false,
    sortField:         ${SF_JS},
    sortValue:         ${SV_JS},
    searchReqFromPage: 'pcSearch'
  };

  return new Promise(function(resolve) {
    window.lib.mtop.request({
      api: 'mtop.taobao.idlemtopsearch.pc.search',
      v: '1.0',
      data: data
    })
    .then(function(res) {
      var list         = (res.data || {}).resultList || [];
      var filterCity   = ${CI_JS};
      var minPrice     = ${MN_JS} !== "" ? parseInt(${MN_JS}) : null;
      var maxPrice     = ${MX_JS} !== "" ? parseInt(${MX_JS}) : null;
      var personalOnly = ${PO_JS};

      var items = list.map(function(item) {
        var main = ((item.data || {}).item || {}).main || {};
        var ex   = main.exContent || {};
        var args = (main.clickParam || {}).args || {};
        var dp   = ex.detailParams || {};
        var price = parseInt(dp.soldPrice || args.price || 0);

        // 评价数 >10 视为商家店铺
        var reviewCount = 0;
        var tagList = ((ex.userFishShopLabel || {}).tagList) || [];
        for (var t = 0; t < tagList.length; t++) {
          var content = (tagList[t].data || {}).content || '';
          var m = content.match(/(\d+)条评价/);
          if (m) { reviewCount = parseInt(m[1]); break; }
        }
        var isShop = reviewCount > 10;

        return {
          itemId:      ex.itemId || args.item_id || '',
          title:       (ex.title || dp.title || '').replace(/\n/g, ' ').replace(/\s+/g, ' ').trim(),
          price:       price,
          oriPrice:    ex.oriPrice || '',
          area:        ex.area || '',
          seller:      ex.userNickName || dp.userNick || '',
          want:        ex.want || '0',
          reviewCount: reviewCount,
          isShop:      isShop,
          publishTime: args.publishTime || '',
          url:         'https://www.goofish.com/item?id=' + (ex.itemId || args.item_id || ''),
          appUrl:      'fleamarket://item?id=' + (ex.itemId || args.item_id || '')
        };
      }).filter(function(i) {
        if (i.price <= 0)                                    return false;
        if (filterCity && i.area.indexOf(filterCity) === -1) return false;
        if (minPrice !== null && i.price < minPrice)         return false;
        if (maxPrice !== null && i.price > maxPrice)         return false;
        if (personalOnly && i.isShop)                        return false;
        return true;
      });

      resolve(JSON.stringify({
        ok:          true,
        keyword:     data.keyword,
        page:        ${PAGE},
        sort:        ${SO_JS},
        city:        filterCity,
        minPrice:    minPrice,
        maxPrice:    maxPrice,
        personalOnly: personalOnly,
        count:       items.length,
        items:       items
      }));
    })
    .catch(function(e) {
      resolve(JSON.stringify({ ok: false, error: String(e) }));
    });
  });
})()
JSEOF

# ---------- 执行 ----------
RESULT=$(minis-browser-use execute_js $TAB_ARG --script "$(cat $JS_FILE)" --compact -q 2>/dev/null \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d.get('text','').strip().split('\n')[0].strip())
")
rm -f "$JS_FILE"

if [ -z "$RESULT" ]; then
  echo "❌ 未收到返回数据，请检查网络或登录状态" >&2
  exit 1
fi

# ---------- 输出 ----------
if [ "$OUTPUT_JSON" = "true" ]; then
  echo "$RESULT" | python3 -c "
import json, sys
print(json.dumps(json.loads(sys.stdin.read().strip()), ensure_ascii=False, indent=2))
"
else
  echo "$RESULT" | python3 -c "
import json, sys, datetime

d = json.loads(sys.stdin.read().strip())
if not d.get('ok'):
    print('❌ 搜索失败:', d.get('error','未知错误'))
    sys.exit(1)

items = d.get('items', [])
sort_map = {'default':'综合','price_asc':'价格↑','price_desc':'价格↓','time':'最新','reduce':'降价'}
tags = []
if d.get('city'):         tags.append('城市:' + d['city'])
if d.get('minPrice'):     tags.append('最低¥' + str(d['minPrice']))
if d.get('maxPrice'):     tags.append('最高¥' + str(d['maxPrice']))
if d.get('personalOnly'): tags.append('仅个人')
tag_str = ('  [' + '  '.join(tags) + ']') if tags else ''

print(f'🔍 \"{d[\"keyword\"]}\"  {sort_map.get(d.get(\"sort\",\"\"), d.get(\"sort\",\"\"))}{tag_str}  共{d[\"count\"]}条')
print('─' * 66)
for i, it in enumerate(items, 1):
    ori   = f' 原{it[\"oriPrice\"]}' if it.get('oriPrice') else ''
    kind  = '🏪' if it.get('isShop') else '👤'
    title = it['title'][:50]
    pub   = ''
    if it.get('publishTime'):
        ts  = int(it['publishTime']) // 1000
        pub = datetime.datetime.fromtimestamp(ts).strftime('%m-%d %H:%M')
    print(f'[{i:02d}] ¥{it[\"price\"]}{ori}')
    print(f'     {title}')
    print(f'     📍{it[\"area\"]}  {kind}({it[\"reviewCount\"]}评){it[\"seller\"]}  ❤️{it.get(\"want\",\"0\")}想  🕐{pub}')
    app_url = 'fleamarket://item?id=' + (it['url'].split('id=')[-1])
    print(f'     🔗 {it[\"url\"]}')
    print(f'     📱 {app_url}')
    print()
"
fi
