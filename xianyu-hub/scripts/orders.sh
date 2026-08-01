#!/bin/sh
# 闲鱼订单查询 — 我买到的
# 用法: orders.sh [-n 数量] [-p 页码] [-t 类型]
# 类型: all(全部) wait_pay(待付款) wait_send(待发货) wait_receive(待收货) refund(退款)

PAGE_SIZE=20; PAGE_NO=1; TAB_TYPE="all"
while [ $# -gt 0 ]; do
  case "$1" in
    -n) PAGE_SIZE="$2"; shift 2 ;;
    -p) PAGE_NO="$2"; shift 2 ;;
    -t) TAB_TYPE="$2"; shift 2 ;;
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

JS_FILE="/tmp/xy_orders_$$.js"
cat > "$JS_FILE" << JSEOF
return new Promise(function(resolve) {
  window.lib.mtop.request({
    api: 'mtop.idle.web.trade.bought.list', v: '1.0',
    data: { pageSize: ${PAGE_SIZE}, pageNo: ${PAGE_NO}, tabType: '${TAB_TYPE}' }
  }).then(function(res) {
    var d = res.data || {};
    var items = (d.items || []).map(function(it) {
      var c = it.commonData || {};
      var head = it.head || {};
      var content = it.content || {};

      // 提取头部信息
      var headItems = (head.headItems || []);
      var sellerName = '';
      headItems.forEach(function(h) { if (h.type === 'TEXT') sellerName = h.content || ''; });

      // 提取商品信息
      var contentItems = (content.contentItems || []);
      var title = '', price = '', picUrl = '';
      contentItems.forEach(function(ci) {
        if (ci.type === 'ITEM_INFO') {
          title = (ci.title || '').replace(/\n/g,' ').substring(0,50);
          price = ci.price || '';
          picUrl = ci.picUrl || '';
        }
      });

      // 提取尾部操作按钮
      var tailItems = ((it.tail || {}).tailItems || []);
      var actions = tailItems.map(function(t) { return t.title || ''; }).filter(function(t) { return t; });

      return {
        orderId:   c.orderIdStr || c.orderId || '',
        itemId:    c.itemId || '',
        title:     title,
        price:     price,
        status:    c.tradeStatusEnum || '',
        seller:    sellerName || (c.seller||{}).nick || '',
        actions:   actions,
        appUrl:    c.orderDetailUrl || ''
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
status_map = {
    'TRADE_CLOSED':'已关闭','TRADE_FINISHED':'已完成','WAIT_BUYER_PAY':'待付款',
    'WAIT_SELLER_SEND_GOODS':'待发货','WAIT_BUYER_CONFIRM_GOODS':'待收货',
    'TRADE_REFUNDING':'退款中','TRADE_SUCCESS':'交易成功'
}
print(f'🛒 我买到的  共{d[\"total\"]}单  第{d[\"page\"]}页')
print('─' * 60)
if not items:
    print('   暂无订单')
for i, it in enumerate(items, 1):
    st = status_map.get(it['status'], it['status'])
    acts = '  '.join(it.get('actions',[])) if it.get('actions') else ''
    print(f'[{i:02d}] ¥{it[\"price\"]}  [{st}]')
    print(f'     {it[\"title\"]}')
    print(f'     👤{it[\"seller\"]}  订单号:{it[\"orderId\"]}')
    if acts: print(f'     🔘 {acts}')
    if it.get('appUrl'): print(f'     📱 {it[\"appUrl\"]}')
    print()
"
