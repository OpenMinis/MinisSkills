#!/bin/sh
# 闲鱼我发布的商品列表
# 用法: my_items.sh [-n 数量] [-p 页码]

PAGE_SIZE=20; PAGE_NO=1
while [ $# -gt 0 ]; do
  case "$1" in
    -n) PAGE_SIZE="$2"; shift 2 ;;
    -p) PAGE_NO="$2"; shift 2 ;;
    *)  shift ;;
  esac
done

TAB_ID=$(minis-browser-use list_tabs --compact -q 2>/dev/null | python3 -c "
import json,sys,re
for l in json.load(sys.stdin).get('text','').split('\n'):
  if 'goofish.com' in l:
    m=re.search(r'Tab (\d+)',l)
    if m: sys.stdout.write(m.group(1)); break
")
TAB_ARG=""; [ -n "$TAB_ID" ] && TAB_ARG="--tab-id $TAB_ID"

# 先获取当前用户 ID
USER_ID=$(minis-browser-use execute_js $TAB_ARG \
  --script 'return new Promise(function(r){window.lib.mtop.request({api:"mtop.taobao.idlemessage.pc.loginuser.get",v:"1.0",data:{}}).then(function(res){r((res.data||{}).userId||"")}).catch(function(){r("")})})' \
  --compact -q 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('text','').strip().split('\n')[0].strip())")

if [ -z "$USER_ID" ]; then echo "❌ 获取用户ID失败" >&2; exit 1; fi

JS_FILE="/tmp/xy_myitems_$$.js"
cat > "$JS_FILE" << JSEOF
return new Promise(function(resolve) {
  window.lib.mtop.request({
    api: 'mtop.idle.web.xyh.item.list', v: '1.0',
    data: { pageNumber: ${PAGE_NO}, pageSize: ${PAGE_SIZE}, userId: '${USER_ID}' }
  }).then(function(res) {
    var d = res.data || {};
    var items = (d.cardList || []).map(function(card) {
      var cd = card.cardData || {};
      var dp = cd.detailParams || {};
      var pi = cd.priceInfo || {};
      var price = '';
      if (pi.priceItems) {
        pi.priceItems.forEach(function(p) { if (p.type === 'integer') price = p.text; });
      }
      return {
        itemId:    dp.itemId || cd.id || '',
        title:     (cd.title || '').replace(/\n/g,' ').substring(0,50),
        price:     price || dp.soldPrice || '',
        status:    cd.itemStatus || '',
        url:       'https://www.goofish.com/item?id=' + (dp.itemId || cd.id || ''),
        appUrl:    'fleamarket://item?id=' + (dp.itemId || cd.id || '')
      };
    });
    resolve(JSON.stringify({ ok:true, total:d.totalCount||'0', page:${PAGE_NO}, items:items }));
  }).catch(function(e) {
    resolve(JSON.stringify({ ok:false, error: e.ret ? e.ret.join('; ') : String(e) }));
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

items = d.get('items', [])
status_map = {'0':'在售','1':'已下架','2':'已售出'}
print(f'📤 我发布的  共{d[\"total\"]}件  第{d[\"page\"]}页')
print('─' * 60)
if not items:
    print('   暂无发布')
for i, it in enumerate(items, 1):
    st = status_map.get(str(it.get('status','')), str(it.get('status','')))
    print(f'[{i:02d}] ¥{it[\"price\"]}  [{st}]')
    print(f'     {it[\"title\"]}')
    print(f'     🔗 {it[\"url\"]}')
    print(f'     📱 {it[\"appUrl\"]}')
    print()
"
