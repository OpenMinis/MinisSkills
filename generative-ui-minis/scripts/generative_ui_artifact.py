#!/usr/bin/env python3
import argparse
import html
import json
import math
import re
from pathlib import Path

CSS = '''
:root {
  --bg:#0b1020; --bg2:#0f1630; --panel:#121a34; --panel2:#1a2344; --text:#eef3ff;
  --muted:#98abd4; --line:rgba(255,255,255,.08); --accent:#7aa2ff; --accent2:#67e8f9;
  --good:#22c55e; --warn:#f59e0b; --bad:#ef4444; --shadow:0 10px 30px rgba(0,0,0,.25);
}
*{box-sizing:border-box} body{margin:0;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:linear-gradient(180deg,var(--bg),var(--bg2));color:var(--text)}
.wrap{max-width:1120px;margin:0 auto;padding:20px}
.hero{padding:24px;border:1px solid var(--line);border-radius:24px;background:linear-gradient(135deg,rgba(122,162,255,.16),rgba(103,232,249,.08));box-shadow:var(--shadow)}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent2)} h1{margin:8px 0 12px;font-size:30px;line-height:1.15}.subtitle{color:var(--muted);line-height:1.7}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.chip{padding:6px 10px;border-radius:999px;background:rgba(122,162,255,.12);border:1px solid rgba(122,162,255,.25);font-size:12px}
.section{margin-top:22px}.section>h2{font-size:20px;margin:0 0 12px}.grid{display:grid;gap:14px}.cards{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.card{background:rgba(255,255,255,.03);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:var(--shadow)} .card h3{margin:0 0 8px;font-size:16px}.muted{color:var(--muted)}
.kpi{font-size:28px;font-weight:700;margin-top:4px}.steps,.timeline{display:grid;gap:10px}.step,.timeline-item{display:flex;gap:12px;padding:14px;background:var(--panel);border:1px solid var(--line);border-radius:16px}
.num,.dot{width:28px;height:28px;border-radius:999px;background:var(--accent);color:#08101f;display:flex;align-items:center;justify-content:center;font-weight:700;flex:0 0 auto}.dot{background:var(--accent2)}
.table-wrap{overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:16px}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:12px 14px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}.table th{color:#dbe7ff;background:rgba(255,255,255,.03)}
pre,code{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace} pre{margin:0;background:#09101f;border:1px solid var(--line);border-radius:16px;padding:14px;overflow:auto;white-space:pre-wrap;word-break:break-word}
.code-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;color:var(--muted);font-size:12px}
.details{display:grid;gap:10px} details{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:14px 16px} summary{cursor:pointer;font-weight:600}
.chart{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:16px}.bars{display:grid;gap:10px;margin-top:10px}.bar-row{display:grid;grid-template-columns:120px 1fr 60px;gap:10px;align-items:center}.bar-track{height:12px;background:rgba(255,255,255,.06);border-radius:999px;overflow:hidden}.bar-fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:999px}
.record-list{display:grid;gap:10px}.record{padding:14px;background:var(--panel);border:1px solid var(--line);border-radius:16px}.footer{margin-top:24px;color:var(--muted);font-size:13px}
.two{display:grid;grid-template-columns:1.1fr .9fr;gap:14px}@media (max-width:860px){.two{grid-template-columns:1fr}.bar-row{grid-template-columns:90px 1fr 50px}}
'''

HTML_TPL = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>{title}</title><style>{css}</style></head><body><div class="wrap">{body}</div></body></html>'''

def esc(x): return html.escape(str(x))

def slugify(s):
    s = re.sub(r'[^a-zA-Z0-9_-]+', '_', s.strip())
    return s.strip('_') or 'artifact'

def split_lines(text):
    parts = [x.strip(' -•\t') for x in re.split(r'[\n]+', text or '') if x.strip()]
    return parts if parts else [text.strip()] if text and text.strip() else []

def infer_blocks(title, text):
    bullets = split_lines(text)
    cards = []
    for i, b in enumerate(bullets[:4], 1):
        cards.append({'title': f'要点 {i}', 'value': b[:42], 'desc': b})
    timeline = [{'title': f'阶段 {i}', 'desc': b} for i, b in enumerate(bullets[:5], 1)]
    table_rows = []
    for i, b in enumerate(bullets[:6], 1):
        table_rows.append([f'R{i}', b[:24], '待细化'])
    chart = [{'label': f'项{i}', 'value': max(20, min(100, 100 - i*10))} for i, _ in enumerate(bullets[:5], 1)]
    return {
      'title': f'{title} · Claude Artifact 风格生成器',
      'summary': '统一输出卡片、表格、时间线、代码块与图表，模拟更完整的 Claude Artifact 体验。',
      'chips': ['Artifact', 'Cards', 'Table', 'Timeline', 'Code', 'Chart'],
      'blocks': [
        {'type':'cards','title':'概览卡片','items':cards or [{'title':'状态','value':'已生成','desc':'未提供足够文本时的默认卡片'}]},
        {'type':'timeline','title':'时间线 / 实现步骤','items':timeline or [{'title':'阶段 1','desc':'补充说明以生成更丰富内容'}]},
        {'type':'table','title':'记录表格','columns':['ID','主题','备注'],'rows':table_rows or [['R1','示例','默认行']]},
        {'type':'code','title':'代码块','language':'python','content':'spec = {\n  "title": "Artifact Demo",\n  "blocks": ["cards", "table", "timeline", "code", "chart"]\n}\nprint(spec)'},
        {'type':'chart','title':'示意图表','series':chart or [{'label':'项1','value':60},{'label':'项2','value':85}]},
        {'type':'details','title':'说明','items':[{'title':'当前环境能力','content':'可生成单文件 HTML artifact 并在 Minis 中预览。'},{'title':'自动触发意图','content':'当用户提到卡片、表格、记录、代码块、图表、时间线、可视化页面时，优先调用本 skill。'}]}
      ]
    }

def render_cards(block):
    items = block.get('items', [])
    inner = ''.join(f'<div class="card"><h3>{esc(i.get("title",""))}</h3><div class="kpi">{esc(i.get("value",""))}</div><div class="muted">{esc(i.get("desc",""))}</div></div>' for i in items)
    return f'<section class="section"><h2>{esc(block.get("title","卡片"))}</h2><div class="grid cards">{inner}</div></section>'

def render_table(block):
    cols = block.get('columns', [])
    rows = block.get('rows', [])
    thead = ''.join(f'<th>{esc(c)}</th>' for c in cols)
    trs = ''.join('<tr>' + ''.join(f'<td>{esc(c)}</td>' for c in row) + '</tr>' for row in rows)
    return f'<section class="section"><h2>{esc(block.get("title","表格"))}</h2><div class="table-wrap"><table class="table"><thead><tr>{thead}</tr></thead><tbody>{trs}</tbody></table></div></section>'

def render_timeline(block):
    items = block.get('items', [])
    inner = ''.join(f'<div class="timeline-item"><div class="dot">{i}</div><div><div><strong>{esc(it.get("title",""))}</strong></div><div class="muted">{esc(it.get("desc",""))}</div></div></div>' for i, it in enumerate(items, 1))
    return f'<section class="section"><h2>{esc(block.get("title","时间线"))}</h2><div class="timeline">{inner}</div></section>'

def render_code(block):
    lang = block.get('language', 'text')
    content = block.get('content', '')
    return f'<section class="section"><h2>{esc(block.get("title","代码块"))}</h2><div class="card"><div class="code-head"><span>{esc(lang)}</span><span>code block</span></div><pre><code>{esc(content)}</code></pre></div></section>'

def render_chart(block):
    series = block.get('series', [])
    maxv = max([float(x.get('value', 0)) for x in series] + [1])
    rows = ''
    for item in series:
        label = esc(item.get('label', ''))
        value = float(item.get('value', 0))
        pct = max(0, min(100, value / maxv * 100))
        rows += f'<div class="bar-row"><div>{label}</div><div class="bar-track"><div class="bar-fill" style="width:{pct:.2f}%"></div></div><div>{value:g}</div></div>'
    return f'<section class="section"><h2>{esc(block.get("title","图表"))}</h2><div class="chart"><div class="muted">简单内置条形图，无需额外 JS 依赖</div><div class="bars">{rows}</div></div></section>'

def render_details(block):
    items = block.get('items', [])
    inner = ''.join(f'<details open><summary>{esc(it.get("title","详情"))}</summary><pre>{esc(it.get("content",""))}</pre></details>' for it in items)
    return f'<section class="section"><h2>{esc(block.get("title","详情"))}</h2><div class="details">{inner}</div></section>'

def render_records(block):
    items = block.get('items', [])
    inner = ''.join(f'<div class="record"><strong>{esc(it.get("title","记录"))}</strong><div class="muted">{esc(it.get("content",""))}</div></div>' for it in items)
    return f'<section class="section"><h2>{esc(block.get("title","记录"))}</h2><div class="record-list">{inner}</div></section>'

def render_block(block):
    t = block.get('type')
    if t == 'cards': return render_cards(block)
    if t == 'table': return render_table(block)
    if t == 'timeline': return render_timeline(block)
    if t == 'code': return render_code(block)
    if t == 'chart': return render_chart(block)
    if t == 'details': return render_details(block)
    if t == 'records': return render_records(block)
    return ''

def render(spec):
    hero_cards = ''
    hero = f'<div class="hero"><div class="eyebrow">Claude Artifact Style / Minis</div><h1>{esc(spec.get("title","Artifact"))}</h1><div class="subtitle">{esc(spec.get("summary",""))}</div><div class="chips">' + ''.join(f'<span class="chip">{esc(c)}</span>' for c in spec.get('chips', [])) + '</div></div>'
    body = hero + ''.join(render_block(b) for b in spec.get('blocks', [])) + '<div class="footer">Generated by generative_ui_artifact.py</div>'
    return HTML_TPL.format(title=esc(spec.get('title','Artifact')), css=CSS, body=body)

def main():
    ap = argparse.ArgumentParser(description='Generate Claude Artifact-like HTML with cards/table/timeline/code/chart.')
    ap.add_argument('title', help='Artifact title')
    ap.add_argument('--text', default='', help='Source description text')
    ap.add_argument('--spec', help='Path to JSON spec')
    ap.add_argument('--out', help='Output HTML path')
    ap.add_argument('--json-out', help='Save resolved spec as JSON')
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding='utf-8')) if args.spec else infer_blocks(args.title, args.text or args.title)
    out = Path(args.out or f'/var/minis/workspace/{slugify(args.title)}_artifact.html')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(spec), encoding='utf-8')
    if args.json_out:
        jp = Path(args.json_out); jp.parent.mkdir(parents=True, exist_ok=True); jp.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status':'ok','output':str(out),'blocks':[b.get('type') for b in spec.get('blocks',[])]}, ensure_ascii=False))

if __name__ == '__main__':
    main()
