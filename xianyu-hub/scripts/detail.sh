#!/bin/sh
# 闲鱼商品详情查询
# 用法: detail.sh <商品ID>
ITEM_ID="$1"
if [ -z "$ITEM_ID" ]; then echo "用法: detail.sh <商品ID>" >&2; exit 1; fi

# 自动定位闲鱼 tab
TAB_ID=$(minis-browser-use list_tabs --compact -q 2>/dev/null | python3 -c "
import json,sys,re
for l in json.load(sys.stdin).get('text','').split('\n'):
  if 'goofish.com' in l:
    m=re.search(r'Tab (\d+)',l)
    if m: sys.stdout.write(m.group(1)); break
")
TAB_ARG=""
[ -n "$TAB_ID" ] && TAB_ARG="--tab-id $TAB_ID"

JS_FILE="/tmp/xy_detail_$$.js"
cat > "$JS_FILE" << JSEOF
return new Promise(function(resolve) {
  window.lib.mtop.request({
    api: 'mtop.taobao.idle.pc.detail', v: '1.0',
    data: { itemId: "${ITEM_ID}" }
  }).then(function(res) {
    var d = res.data || {};
    var item = d.itemDO || {};
    var seller = d.sellerDO || {};
    var b2c = d.b2cItemDO || {};
    resolve(JSON.stringify({
      ok: true,
      item: {
        itemId:       item.itemId || '',
        title:        item.title || '',
        price:        item.soldPrice || '',
        originalPrice:item.originalPrice || '',
        desc:         item.desc || '',
        stuffStatus:  item.stuffStatus || '',
        quantity:     item.quantity || '1',
        wantCnt:      item.wantCnt || '0',
        browseCnt:    b2c.browseCnt || item.browseCnt || '0',
        collectCnt:   item.collectCnt || '0',
        itemStatus:   item.itemStatusStr || '',
        gmtCreate:    item.gmtCreate || '',
        transportFee: item.transportFee || '',
        defaultPrice: item.defaultPrice || '',
        url:          'https://www.goofish.com/item?id=' + (item.itemId || ''),
        appUrl:       'fleamarket://item?id=' + (item.itemId || '')
      },
      seller: {
        nick:         seller.nick || '',
        sellerId:     seller.sellerId || '',
        city:         seller.city || '',
        signature:    seller.signature || '',
        registerDays: seller.userRegDay || '',
        soldCount:    seller.hasSoldNumInteger || '',
        goodRate:     seller.newGoodRatioRate || '',
        replyRate:    seller.replyRatio24h || '',
        itemCount:    seller.itemCount || '',
        portraitUrl:  seller.portraitUrl || ''
      }
    }));
  }).catch(function(e) {
    resolve(JSON.stringify({ ok: false, error: e.ret ? e.ret.join('; ') : String(e) }));
  });
});
JSEOF

RESULT=$(minis-browser-use execute_js $TAB_ARG --script "$(cat $JS_FILE)" --compact -q 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('text','').strip().split('\n')[0].strip())")
rm -f "$JS_FILE"

if [ -z "$RESULT" ]; then echo "❌ 请求失败" >&2; exit 1; fi

echo "$RESULT" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read().strip())
if not d.get('ok'): print('❌', d.get('error','')); sys.exit(1)
it = d['item']; s = d['seller']
print(f'📦 {it[\"title\"]}')
print(f'   💰 ¥{it[\"price\"]}' + (f'  原价¥{it[\"originalPrice\"]}' if it.get('originalPrice') else ''))
print(f'   📝 {it[\"desc\"][:80]}')
print(f'   📊 {it[\"browseCnt\"]}浏览  ❤️{it[\"wantCnt\"]}想要  ⭐{it[\"collectCnt\"]}收藏')
print(f'   📦 库存{it[\"quantity\"]}  运费{it.get(\"transportFee\",\"包邮\")}')
print(f'   🔗 {it[\"url\"]}')
print(f'   📱 {it[\"appUrl\"]}')
print()
print(f'👤 卖家: {s[\"nick\"]}')
print(f'   📍{s[\"city\"]}  注册{s[\"registerDays\"]}天  售出{s[\"soldCount\"]}件')
print(f'   👍好评率{s[\"goodRate\"]}  💬24h回复率{s[\"replyRate\"]}  📦在售{s[\"itemCount\"]}件')
"
