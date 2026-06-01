#!/usr/bin/env python3
"""30-day monthly sleep trend rendered via rsvg-convert.
Design language matches sleep_report_librsvg.py.

Usage:
  python3 sleep_month_trend_librsvg.py --days 30 --lang zh \\
      --sleep /tmp/sleep_raw.json --spo2 /tmp/spo2_raw.json \\
      --out-prefix /tmp/sleep_month_trend
"""
import argparse, json, html, subprocess
from pathlib import Path
from datetime import datetime, timedelta, date
from collections import defaultdict

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--days',       type=int, default=30)
parser.add_argument('--sleep',      default='/var/minis/workspace/sleep_raw.json')
parser.add_argument('--spo2',       default='/var/minis/workspace/spo2_raw.json')
parser.add_argument('--out-prefix', default='/var/minis/workspace/sleep_month_trend')
parser.add_argument('--lang',       default='zh', choices=['zh','en','ja'])
args = parser.parse_args()

# ── Localisation ──────────────────────────────────────────────────────────────
STR = {
    'zh': dict(
        title='最近一个月睡眠趋势', suffix='夜有效记录', source='Apple Health 睡眠阶段 / 血氧',
        avg_sleep='平均睡眠', good_days='达标天数', deep_avg='深睡均值', min_spo2='最低血氧',
        note_sleep='月均睡眠时长', note_good='≥7h 的夜数', note_deep='深睡恢复', note_spo2='睡眠期最低点',
        stage_title='睡眠阶段趋势', recommend='推荐 7h',
        deep='深睡', core='浅睡', awake='清醒',
        spo2_title='血氧趋势', warn_line='95% 警戒',
        avg_lbl='均值', min_lbl='最低',
        week_title='周汇总', goal_lbl='达标',
        conclusion_title='月度结论',
        short='本月睡眠时长偏短', ok='本月睡眠时长基本达标',
        spo2_bad='；出现低于90%的血氧低点，建议持续观察',
        spo2_ok='；血氧低点未见明显危险信号',
        generated='生成时间',
        data_source='数据来源：Apple HealthKit · 仅供健康趋势参考',
    ),
    'en': dict(
        title='Monthly Sleep Trend', suffix='nights recorded', source='Apple Health Sleep Stages / SpO2',
        avg_sleep='Avg Sleep', good_days='Goal Days', deep_avg='Avg Deep', min_spo2='Min SpO2',
        note_sleep='Monthly avg', note_good='≥7h nights', note_deep='Deep recovery', note_spo2='Sleep SpO2 low',
        stage_title='Sleep Stage Trend', recommend='Goal 7h',
        deep='Deep', core='Core', awake='Awake',
        spo2_title='SpO2 Trend', warn_line='95% alert',
        avg_lbl='avg', min_lbl='min',
        week_title='Weekly Summary', goal_lbl='Goal',
        conclusion_title='Monthly Summary',
        short='Sleep duration below goal this month', ok='Sleep duration on target this month',
        spo2_bad='; SpO2 dropped below 90%, monitor closely',
        spo2_ok='; no dangerous SpO2 lows detected',
        generated='Generated',
        data_source='Source: Apple HealthKit · For reference only',
    ),
    'ja': dict(
        title='月間睡眠トレンド', suffix='夜の有効記録', source='Apple Health 睡眠ステージ / 血中酸素',
        avg_sleep='平均睡眠', good_days='達成日数', deep_avg='深睡眠平均', min_spo2='最低血中酸素',
        note_sleep='月間平均', note_good='≥7h の夜数', note_deep='深睡眠回復', note_spo2='睡眠中最低値',
        stage_title='睡眠ステージ推移', recommend='目標 7h',
        deep='深睡眠', core='コア', awake='覚醒',
        spo2_title='血中酸素推移', warn_line='95% 警戒',
        avg_lbl='平均', min_lbl='最低',
        week_title='週間サマリー', goal_lbl='達成',
        conclusion_title='月間まとめ',
        short='今月の睡眠時間は目標未達', ok='今月の睡眠時間は概ね達成',
        spo2_bad='；90%未満の低下あり、継続観察を推奨',
        spo2_ok='；危険な血中酸素低下は見られない',
        generated='生成日時',
        data_source='データ：Apple HealthKit · 参考用のみ',
    ),
}
T = STR[args.lang]

# ── Colours ───────────────────────────────────────────────────────────────────
COL = {
    'text':'#f8fafc','muted':'#94a3b8','blue':'#60a5fa','cyan':'#22d3ee',
    'violet':'#a78bfa','amber':'#fbbf24','red':'#fb7185','green':'#34d399',
    'deep':'#2563eb','core':'#22c1c3','rem':'#a78bfa','awake':'#fb923c',
}

# ── SVG helpers ───────────────────────────────────────────────────────────────
def esc(x): return html.escape(str(x))
def txt(x,y,s,size=22,color=None,weight=400,anchor='start'):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color or COL["text"]}"'
            f' font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')
def rct(x,y,w,h,r,fill,stroke='#ffffff22'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"/>'
def tspan_unit(x,y,val,unit,vsize,vcolor,usize,ucolor,weight=850):
    return (f'<text x="{x}" y="{y}" font-size="{vsize}" fill="{vcolor}" font-weight="{weight}">'
            f'{esc(val)}<tspan font-size="{usize}" fill="{ucolor}" dx="6">{esc(unit)}</tspan></text>')
def line(x1,y1,x2,y2,color='#ffffff25',sw=1,dash=''):
    da=f' stroke-dasharray="{dash}"' if dash else ''
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{da}/>'

ICON_PATHS = {
    'moon':     '<path d="M12 3a6.6 6.6 0 0 0 8.8 8.8A9 9 0 1 1 12 3Z"/>',
    'clock':    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    'bars':     '<path d="M3 3v18h18"/><path d="M7 16V9M12 16V5M17 16v-3"/>',
    'droplet':  '<path d="M12 2.5S5.5 9.4 5.5 14A6.5 6.5 0 0 0 18.5 14C18.5 9.4 12 2.5 12 2.5Z"/>',
    'activity': '<path d="M22 12h-4l-3 8L9 4l-3 8H2"/>',
    'sparkles': '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"/>',
}
def icon(name,x,y,size=28,color='currentColor',sw=2.2):
    return (f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICON_PATHS[name]}</svg>')

def val_color(v): return COL['green'] if v>=7 else (COL['amber'] if v>=6 else COL['red'])

# ── Parse data ────────────────────────────────────────────────────────────────
def parse_dt(s): return datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S')
def sleep_date(dt): return (dt-timedelta(days=1)).date() if dt.hour<14 else dt.date()
def hm(dt): return dt.hour+dt.minute/60

STAGE_MAP = {'asleepDeep':'Deep','asleepREM':'REM','asleepCore':'Core','awake':'Awake','inBed':None}

sleep_raw  = json.load(open(args.sleep))
spo2_raw   = json.load(open(args.spo2))
samples    = sleep_raw.get('samples', sleep_raw)
spo2_samps = spo2_raw.get('samples', spo2_raw)

nights = defaultdict(lambda: defaultdict(float))
bed_h  = {}; wake_h = {}

for s in samples:
    raw = s.get('stage') or s.get('value') or s.get('sleepStage','')
    stg = STAGE_MAP.get(raw)
    ss  = s.get('startDate') or s.get('start')
    ee  = s.get('endDate')   or s.get('end')
    if not ss or not ee: continue
    a=parse_dt(ss); b=parse_dt(ee); n=sleep_date(a)
    dur=(b-a).total_seconds()/3600
    if stg: nights[n][stg]+=dur
    af=hm(a); af=af+24 if af<14 else af
    bf=hm(b); bf=bf+24 if bf<14 else bf
    bed_h[n] =min(bed_h.get(n,af),af)
    wake_h[n]=max(wake_h.get(n,bf),bf)

spo2_by = defaultdict(list)
for s in spo2_samps:
    v=s.get('percentage') or s.get('value')
    if isinstance(v,(int,float)) and v>50:
        spo2_by[sleep_date(parse_dt(s['date']))].append(float(v))

valid = sorted([d for d in nights if sum(nights[d].values())>1])[-args.days:]
if not valid: raise SystemExit('No sleep data.')

rows=[]
for d in valid:
    st=nights[d]; total=sum(st.values()); sp=spo2_by.get(d,[])
    rows.append(dict(
        date=d, label=d.strftime('%m/%d'),
        total=total,
        deep=st.get('Deep',0), core=st.get('Core',0),
        rem=st.get('REM',0),   awake=st.get('Awake',0),
        spo2_mean=sum(sp)/len(sp) if sp else None,
        spo2_min =min(sp) if sp else None,
        bed =bed_h.get(d),
    ))

def _avg(xs): return sum(xs)/len(xs) if xs else 0
avg_total = _avg([r['total'] for r in rows])
avg_deep  = _avg([r['deep']  for r in rows])
avg_rem   = _avg([r['rem']   for r in rows])
spmins    = [r['spo2_min']  for r in rows if r['spo2_min']  is not None]
spmeans   = [r['spo2_mean'] for r in rows if r['spo2_mean'] is not None]
good      = sum(1 for r in rows if r['total']>=7)
range_lbl = f"{rows[0]['label']}–{rows[-1]['label']}"

# weekly buckets for summary
weeks=[]
for i in range(0,len(rows),7):
    chunk=rows[i:i+7]
    weeks.append((chunk[0]['label']+'–'+chunk[-1]['label'],
                  _avg([r['total'] for r in chunk]),
                  sum(1 for r in chunk if r['total']>=7)))

# ── Layout ────────────────────────────────────────────────────────────────────
W=1280; PAD=54; CW=W-PAD*2; GAP=24
nb=len(rows)

METRIC_H  =174
STAGE_H   =520   # taller to accommodate rotated labels on 30 bars
SPO2_H    =330
WEEK_H    =len(weeks)*72+100
CONCL_H   =120
FOOTER_H  =60

y_metrics =170
y_stage   =y_metrics+METRIC_H+GAP
y_spo2    =y_stage +STAGE_H +GAP
y_week    =y_spo2  +SPO2_H  +GAP
y_concl   =y_week  +WEEK_H  +GAP
y_footer  =y_concl +CONCL_H +GAP
TOTAL_H   =y_footer+FOOTER_H+50

svg=[]
svg.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{TOTAL_H}" viewBox="0 0 {W} {TOTAL_H}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#07111f"/><stop offset=".55" stop-color="#0b1020"/><stop offset="1" stop-color="#111827"/>
  </linearGradient>
  <linearGradient id="cardGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity=".105"/><stop offset="1" stop-color="#ffffff" stop-opacity=".035"/>
  </linearGradient>
  <radialGradient id="glowBlue" cx="50%" cy="50%" r="50%">
    <stop offset="0" stop-color="#38bdf8" stop-opacity=".5"/><stop offset="1" stop-color="#38bdf8" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="glowPurple" cx="50%" cy="50%" r="50%">
    <stop offset="0" stop-color="#a78bfa" stop-opacity=".4"/><stop offset="1" stop-color="#a78bfa" stop-opacity="0"/>
  </radialGradient>
  <filter id="shadow"><feDropShadow dx="0" dy="20" stdDeviation="24" flood-color="#000" flood-opacity=".3"/></filter>
  <style><![CDATA[text{{font-family:'Noto Sans CJK SC','Noto Sans CJK','PingFang SC',Arial,sans-serif;text-rendering:geometricPrecision}}]]></style>
</defs>
<rect width="100%" height="100%" fill="url(#bg)"/>
<circle cx="1150" cy="200" r="300" fill="url(#glowBlue)"/>
<circle cx="80"   cy="{TOTAL_H-200}" r="280" fill="url(#glowPurple)"/>
<g filter="url(#shadow)">
''')

# Header
svg.append(txt(PAD,108,T['title'],54,COL['text'],850))
svg.append(txt(PAD,152,f'{range_lbl} · {len(rows)} {T["suffix"]} · {T["source"]}',22,COL['muted']))
svg.append(rct(920,60,306,56,28,'#ffffff12','#ffffff25'))
svg.append(icon('sparkles',940,76,26,'#dbeafe'))
svg.append(txt(976,97,'Sleep Intelligence',20,'#dbeafe',550))

# Metric cards
MCW,MCH,MGAP=272,METRIC_H,18
METRICS=[
    ('moon',    T['avg_sleep'],f'{avg_total:.1f}','h', T['note_sleep'],val_color(avg_total),val_color(avg_total)),
    ('clock',   T['good_days'],str(good),         '',  f"{len(rows)} {T['note_good']}",COL['green'],COL['green']),
    ('activity',T['deep_avg'], f'{avg_deep:.1f}', 'h', T['note_deep'], COL['violet'],   COL['violet']),
    ('droplet', T['min_spo2'], f'{min(spmins):.1f}' if spmins else '—','%',T['note_spo2'],COL['red'],COL['red']),
]
for i,(ic,title,val,unit,note,color,vc) in enumerate(METRICS):
    mx,my=PAD+i*(MCW+MGAP),y_metrics
    svg.append(rct(mx,my,MCW,MCH,26,'url(#cardGrad)','#ffffff24'))
    svg.append(txt(mx+22,my+40,title,19,COL['muted'],500))
    svg.append(f'<rect x="{mx+MCW-66}" y="{my+18}" width="50" height="50" rx="16" fill="{color}" opacity=".16"/>')
    svg.append(icon(ic,mx+MCW-56,my+27,26,color))
    svg.append(tspan_unit(mx+22,my+108,val,unit,46,vc,22,COL['muted']))
    svg.append(txt(mx+22,my+142,note,16,COL['muted']))

# ── Panel 1: Stage trend ──────────────────────────────────────────────────────
svg.append(rct(PAD,y_stage,CW,STAGE_H,36,'url(#cardGrad)','#ffffff24'))
svg.append(icon('bars',PAD+30,y_stage+28,30,COL['cyan']))
svg.append(txt(PAD+74,y_stage+52,T['stage_title'],28,COL['text'],760))

LEGEND=[(T['deep'],'deep'),(T['core'],'core'),('REM','rem'),(T['awake'],'awake')]
for i,(lbl,key) in enumerate(LEGEND):
    gx=PAD+380+i*195
    svg.append(f'<circle cx="{gx}" cy="{y_stage+44}" r="7" fill="{COL[key]}"/>')
    svg.append(txt(gx+16,y_stage+51,lbl,18,'#dbeafe',650))

CHART_PAD_TOP=80; CHART_PAD_BOT=70   # 70px for rotated labels
cx=PAD+60; cy=y_stage+CHART_PAD_TOP
chart_w=CW-120; chart_h=STAGE_H-CHART_PAD_TOP-CHART_PAD_BOT

# Global clip — prevents overflow in all directions
svg.append(f'<clipPath id="stageClip"><rect x="{cx}" y="{cy}" width="{chart_w}" height="{chart_h}"/></clipPath>')

svg.append(line(cx,cy+chart_h,cx+chart_w,cy+chart_h))
target_y=cy+chart_h-7/9*chart_h
svg.append(line(cx,target_y,cx+chart_w,target_y,COL['green'],2,'8 6'))
svg.append(txt(cx+chart_w-72,target_y-10,T['recommend'],16,'#86efac',500))

bar_gap=4
bw=max(6,(chart_w-(nb-1)*bar_gap)/nb)

svg.append('<g clip-path="url(#stageClip)">')
for i,r in enumerate(rows):
    bx=cx+i*(bw+bar_gap); by=cy+chart_h
    for key,col in [('deep',COL['deep']),('core',COL['core']),('rem',COL['rem']),('awake',COL['awake'])]:
        hh=r[key]/9*chart_h; by-=hh
        svg.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{hh:.1f}" rx="2" fill="{col}" opacity=".93"/>')
svg.append('</g>')

# Rotated date labels — outside stageClip, below baseline
for i,r in enumerate(rows):
    lx=cx+i*(bw+bar_gap)+bw/2; ly=cy+chart_h+14
    svg.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="11" fill="{COL["muted"]}"'
               f' text-anchor="end" transform="rotate(-45 {lx:.1f} {ly:.1f})">{esc(r["label"][3:])}</text>')

# ── Panel 2: SpO2 trend ───────────────────────────────────────────────────────
svg.append(rct(PAD,y_spo2,CW,SPO2_H,36,'url(#cardGrad)','#ffffff24'))
svg.append(icon('droplet',PAD+30,y_spo2+28,30,COL['blue']))
svg.append(txt(PAD+74,y_spo2+52,T['spo2_title'],28,COL['text'],760))

ax=cx; ay=y_spo2+88; aw=chart_w; ah=SPO2_H-130
# clipPath for SpO2 chart area
svg.append(f'<clipPath id="spo2Clip"><rect x="{ax}" y="{ay}" width="{aw}" height="{ah}"/></clipPath>')
svg.append(line(ax,ay+ah,ax+aw,ay+ah))
svg.append(line(ax,ay,ax,ay+ah,'#ffffff18'))
for pct in [90,95,100]:
    gy=ay+ah-(pct-85)/15*ah
    svg.append(line(ax,gy,ax+aw,gy,'#ffffff15',1,'5 4'))
    svg.append(txt(ax-8,gy+5,str(pct),14,COL['muted'],400,'end'))
svg.append(line(ax,ay+ah-(95-85)/15*ah,ax+aw,ay+ah-(95-85)/15*ah,COL['amber'],1.5,'7 5'))
svg.append(txt(ax+aw+8,ay+ah-(95-85)/15*ah+5,T['warn_line'],13,COL['amber']))

# min SpO2 line — clipped to chart bounds
pts=[]
step=aw/max(1,nb-1) if nb>1 else 0
for i,r in enumerate(rows):
    if r['spo2_min'] is None: continue
    bx=ax+i*step; by2=ay+ah-(r['spo2_min']-85)/15*ah
    col=COL['red'] if r['spo2_min']<90 else COL['blue']
    pts.append((bx,by2,r,col))
svg.append('<g clip-path="url(#spo2Clip)">')
for (x1,y1,_,__),(x2,y2,_,__) in zip(pts,pts[1:]):
    svg.append(line(x1,y1,x2,y2,COL['blue'],2.5))
for bx,by2,r,col in pts:
    svg.append(f'<circle cx="{bx:.1f}" cy="{by2:.1f}" r="5" fill="{col}"/>')
svg.append('</g>')

sp_stat=f'{T["avg_lbl"]} {_avg(spmeans):.1f}%  ·  {T["min_lbl"]} {min(spmins):.1f}%' if spmins else ''
svg.append(txt(ax,ay+ah+28,sp_stat,18,COL['muted']))

# ── Panel 3: Weekly summary ───────────────────────────────────────────────────
svg.append(rct(PAD,y_week,CW,WEEK_H,36,'url(#cardGrad)','#ffffff24'))
svg.append(icon('activity',PAD+30,y_week+28,30,COL['violet']))
svg.append(txt(PAD+74,y_week+52,T['week_title'],28,COL['text'],760))

for i,(lab,av,gd) in enumerate(weeks):
    ry=y_week+80+i*72
    svg.append(rct(PAD+20,ry,CW-40,60,20,'#0f172acc','#ffffff18'))
    svg.append(txt(PAD+40,ry+37,lab,20,COL['text'],700))
    svg.append(txt(PAD+40+340,ry+37,f'{av:.1f}h',20,val_color(av),760))
    svg.append(txt(PAD+40+460,ry+37,f'{gd} {T["goal_lbl"]}',18,COL['green'] if gd>=5 else COL['amber'],500))

# ── Conclusion banner ─────────────────────────────────────────────────────────
svg.append(rct(PAD,y_concl,CW,CONCL_H,30,'#0f172acc','#ffffff1e'))
summary = T['ok'] if avg_total>=7 else T['short']
spo2_note = T['spo2_bad'] if spmins and min(spmins)<90 else T['spo2_ok']
conc = f'{summary}：{T["avg_lbl"]} {avg_total:.1f}h，{good}/{len(rows)} {T["note_good"]}。深睡 {avg_deep:.1f}h，REM {avg_rem:.1f}h{spo2_note}。' if args.lang=='zh' else \
       f'{summary}: avg {avg_total:.1f}h, {good}/{len(rows)} {T["note_good"]}, Deep {avg_deep:.1f}h, REM {avg_rem:.1f}h{spo2_note}.' if args.lang=='en' else \
       f'{summary}：平均 {avg_total:.1f}h、{good}/{len(rows)} {T["note_good"]}。深睡眠 {avg_deep:.1f}h、REM {avg_rem:.1f}h{spo2_note}。'
svg.append(txt(PAD+22,y_concl+46,T['conclusion_title'],26,COL['text'],800))
svg.append(txt(PAD+22,y_concl+86,conc,19,'#cbd5e1'))

# ── Footer ────────────────────────────────────────────────────────────────────
svg.append(rct(PAD,y_footer,310,40,20,'#ffffff0a','#ffffff18'))
svg.append(txt(PAD+18,y_footer+26,f"{T['generated']}: {date.today()}",16,COL['muted']))
svg.append(txt(W-PAD,y_footer+26,T['data_source'],16,COL['muted'],400,'end'))
svg.append('</g></svg>')

svg_path=Path(args.out_prefix+'.svg')
png_path=Path(args.out_prefix+'.png')
svg_path.write_text('\n'.join(svg))
subprocess.run(['rsvg-convert',str(svg_path),'-w',str(W),'-o',str(png_path)],check=True)
print(png_path)
