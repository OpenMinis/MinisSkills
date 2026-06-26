#!/bin/sh
# 闲鱼收藏管理
# 用法:
#   favorites.sh list [-n 数量] [-p 页码]     查看收藏列表
#   favorites.sh add <商品ID>                 收藏商品
#   favorites.sh remove <商品ID>              取消收藏

ACTION="$1"; shift
case "$ACTION" in
  list|add|remove) ;;
  *) echo "用法: favorites.sh <list|add|remove> [参数]" >&2; exit 1 ;;
esac

PAGE_SIZE=20; PAGE_NO=1; ITEM_ID=""
while [ $# -gt 0 ]; do
  case "$1" in
    -n) PAGE_SIZE="$2"; shift 2 ;;
    -p) PAGE_NO="$2"; shift 2 ;;
    *)  ITEM_ID="$1"; shift ;;
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

JS_FILE="/tmp/xy_fav_$$.js"

if [ "$ACTION" = "list" ]; then
  cat > "$JS_FILE" << JSEOF
return new Promise(function(resolve) {
  window.lib.mtop.request({
    api: 'mtop.taobao.idle.web.favor.item.list', v: '1.0',
    data: { pageSize: ${PAGE_SIZE}, pageNo: ${PAGE_NO} }
  }).then(function(res) {
    var d = res.data || {};
    var items = (d.items || []).map(function(it) {
      return {
        itemId: it.id || it.longItemId || '',
        title: (it.title || '').replace(/\n/g,' ').substring(0,50),
        price: it.price || '',
        area: (it.province || '') + ' ' + (it.city || ''),
        seller: it.userNick || '',
        status: it.offline ? '已下架' : '在售',
        favorTime: it.favorTime || '',
        url: 'https://www.goofish.com/item?id=' + (it.id || it.longItemId || ''),
        appUrl: 'fleamarket://item?id=' + (it.id || it.longItemId || '')
      };
    });
    resolve(JSON.stringify({ ok:true, total:d.totalCount||'0', page:${PAGE_NO}, items:items }));
  }).catch(function(e) {
    resolve(JSON.stringify({ ok:false, error: e.ret ? e.ret.join('; ') : String(e) }));
  });
});
JSEOF
else
  if [ -z "$ITEM_ID" ]; then echo "错误: 请提供商品ID" >&2; exit 1; fi
  OP=$([ "$ACTION" = "add" ] && echo "1" || echo "0")
  cat > "$JS_FILE" << JSEOF
return new Promise(function(resolve) {
  window.lib.mtop.request({
    api: 'mtop.taobao.idle.collect.item', v: '1.0',
    data: { itemId: '${ITEM_ID}', operate: '${OP}' }
  }).then(function(res) {
    resolve(JSON.stringify({ ok:true, result: (res.data||{}).favorResult }));
  }).catch(function(e) {
    resolve(JSON.stringify({ ok:false, error: e.ret ? e.ret.join('; ') : String(e) }));
  });
});
JSEOF
fi

RESULT=$(minis-browser-use execute_js $TAB_ARG --script "$(cat $JS_FILE)" --compact -q 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('text','').strip().split('\n')[0].strip())")
rm -f "$JS_FILE"

if [ -z "$RESULT" ]; then echo "❌ 请求失败" >&2; exit 1; fi

echo "$RESULT" | python3 -c "
import json, sys, datetime
d = json.loads(sys.stdin.read().strip())
if not d.get('ok'): print('❌', d.get('error','')); sys.exit(1)

if 'items' in d:
    print(f'⭐ 收藏列表  共{d[\"total\"]}件  第{d[\"page\"]}页')
    print('─' * 60)
    for i, it in enumerate(d['items'], 1):
        status = '🔴已下架' if it['status']=='已下架' else '🟢在售'
        print(f'[{i:02d}] ¥{it[\"price\"]}  {status}')
        print(f'     {it[\"title\"]}')
        print(f'     📍{it[\"area\"]}  👤{it[\"seller\"]}')
        print(f'     🔗 {it[\"url\"]}')
        print(f'     📱 {it[\"appUrl\"]}')
        print()
else:
    action_name = '收藏' if d.get('result')=='true' else '取消收藏'
    print(f'✅ {action_name}成功')
"
