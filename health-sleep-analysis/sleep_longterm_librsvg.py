#!/usr/bin/env python3
"""Half-year (26 weeks) or full-year (12 months) sleep trend.
Design language matches sleep_report_librsvg.py.
"""
import argparse, json, html, subprocess
from pathlib import Path
from datetime import datetime, timedelta, date
from collections import defaultdict

parser = argparse.ArgumentParser()
parser.add_argument('--period',     default='halfyear', choices=['halfyear','year'])
parser.add_argument('--sleep',      default='/var/minis/workspace/sleep_raw.json')
parser.add_argument('--spo2',       default='/var/minis/workspace/spo2_raw.json')
parser.add_argument('--out-prefix', default='/var/minis/workspace/sleep_longterm')
parser.add_argument('--lang',       default='zh', choices=['zh','en','ja'])
args = parser.parse_args()

DAYS = 185 if args.period == 'halfyear' else 370

STR = {
    'zh': dict(
        title_half='最近半年睡眠趋势', title_year='最近一年睡眠趋势',
        sub_half='26周聚合', sub_year='12个月聚合',
        suffix='夜有效记录', source='Apple Health 睡眠阶段 / 血氧',
        avg_sleep='平均睡眠', good_rate='达标率', deep_avg='深睡均值', min_spo2='最低血氧',
        note_sleep='月均睡眠时长', note_good='≥7h 占比', note_deep='深睡恢复', note_spo2='睡眠期最低点',
        stage_title='睡眠阶段趋势', recommend='目标 7h',
        deep='深睡', core='浅睡', awake='清醒',
        spo2_title='血氧趋势（最低值）', warn_line='95%',
        avg_lbl='均值', min_lbl='最低',
        bed_title='入睡时间趋势', warn_01='01:00',
        sum_title='汇总', goal_lbl='达标', spo2_lbl='SpO2',
        conclusion='结论', generated='生成时间',
        data_source='数据来源：Apple HealthKit · 仅供健康趋势参考',
    ),
    'en': dict(
        title_half='6-Month Sleep Trend', title_year='1-Year Sleep Trend',
        sub_half='26-week aggregation', sub_year='12-month aggregation',
        suffix='nights', source='Apple Health Sleep Stages / SpO2',
        avg_sleep='Avg Sleep', good_rate='Goal Rate', deep_avg='Avg Deep', min_spo2='Min SpO2',
        note_sleep='Monthly avg', note_good='≥7h rate', note_deep='Deep recovery', note_spo2='Sleep SpO2 low',
        stage_title='Sleep Stage Trend', recommend='Goal 7h',
        deep='Deep', core='Core', awake='Awake',
        spo2_title='SpO2 Trend (min)', warn_line='95%',
        avg_lbl='avg', min_lbl='min',
        bed_title='Bedtime Trend', warn_01='01:00',
        sum_title='Summary', goal_lbl='Goal', spo2_lbl='SpO2',
        conclusion='Summary', generated='Generated',
        data_source='Source: Apple HealthKit · For reference only',
    ),
    'ja': dict(
        title_half='直近半年の睡眠トレンド', title_year='直近1年の睡眠トレンド',
        sub_half='26週集計', sub_year='12ヶ月集計',
        suffix='夜', source='Apple Health 睡眠ステージ / 血中酸素',
        avg_sleep='平均睡眠', good_rate='達成率', deep_avg='深睡眠平均', min_spo2='最低血中酸素',
        note_sleep='月間平均', note_good='≥7h 達成率', note_deep='深睡眠回復', note_spo2='睡眠中最低値',
        stage_title='睡眠ステージ推移', recommend='目標 7h',
        deep='深睡眠', core='コア', awake='覚醒',
        spo2_title='血中酸素推移（最低値）', warn_line='95%',
        avg_lbl='平均', min_lbl='最低',
        bed_title='就寝時刻推移', warn_01='01:00',
        sum_title='サマリー', goal_lbl='達成', spo2_lbl='SpO2',
        conclusion='まとめ', generated='生成日時',
        data_source='データ：Apple HealthKit · 参考用のみ',
    ),
}
T = STR[args.lang]
TITLE    = T['title_half'] if args.period == 'halfyear' else T['title_year']
SUBTITLE = T['sub_half']   if args.period == 'halfyear' else T['sub_year']

COL = {
    'text':'#f8fafc','muted':'#94a3b8','blue':'#60a5fa','cyan':'#22d3ee',
    'violet':'#a78bfa','amber':'#fbbf24','red':'#fb7185','green':'#34d399',
    'deep':'#2563eb','core':'#22c1c3','rem':'#a78bfa','awake':'#fb923c',
}

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
    da = f' stroke-dasharray="{dash}"' if dash else ''
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{da}/>'

ICON_PATHS = {
    'moon':     '<path d="M12 3a6.6 6.6 0 0 0 8.8 8.8A9 9 0 1 1 12 3Z"/>',
    'clock':    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    'bars':     '<path d="M3 3v18h18"/><path d="M7 16V9M12 16V5M17 16v-3"/>',
    'droplet':  '<path d="M12 2.5S5.5 9.4 5.5 14A6.5 6.5 0 0 0 18.5 14C18.5 9.4 12 2.5 12 2.5Z"/>',
    'activity': '<path d="M22 12h-4l-3 8L9 4l-3 8H2"/>',
    'sparkles': '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"/>',
    'calendar': '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
}
def icon(name,x,y,size=28,color='currentColor',sw=2.2):
    return (f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICON_PATHS[name]}</svg>')

def val_color(v): return COL['green'] if v>=7 else (COL['amber'] if v>=6 else COL['red'])
def pct_color(p): return COL['green'] if p>=0.7 else (COL['amber'] if p>=0.5 else COL['red'])

# ── Parse data ────────────────────────────────────────────────────────────────
def parse_dt(s): return datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S')
def sleep_date(dt): return (dt-timedelta(days=1)).date() if dt.hour<14 else dt.date()
def hm(dt): return dt.hour+dt.minute/60

STAGE_MAP = {'asleepDeep':'Deep','asleepREM':'REM','asleepCore':'Core','awake':'Awake','inBed':None}

samples    = json.load(open(args.sleep)).get('samples',[])
spo2_samps = json.load(open(args.spo2)).get('samples',[])

nights = defaultdict(lambda: defaultdict(float))
bed_h  = {}
for s in samples:
    raw = s.get('stage') or s.get('value') or s.get('sleepStage','')
    stg = STAGE_MAP.get(raw)
    ss  = s.get('startDate') or s.get('start')
    ee  = s.get('endDate')   or s.get('end')
    if not ss or not ee: continue
    a=parse_dt(ss); b=parse_dt(ee); n=sleep_date(a)
    if stg: nights[n][stg] += (b-a).total_seconds()/3600
    af=hm(a); af=af+24 if af<14 else af
    bed_h[n]=min(bed_h.get(n,af),af)

spo2_by = defaultdict(list)
for s in spo2_samps:
    v=s.get('percentage') or s.get('value')
    if isinstance(v,(int,float)) and v>50:
        spo2_by[sleep_date(parse_dt(s['date']))].append(float(v))

valid = sorted([d for d in nights if sum(nights[d].values())>1])[-DAYS:]
if not valid: raise SystemExit('No sleep data.')

# ── Bucket aggregation ────────────────────────────────────────────────────────
USE_WEEKS = (args.period=='halfyear')
def bucket_key(d):
    if USE_WEEKS:
        iso=d.isocalendar(); return f'{iso[0]}-W{iso[1]:02d}'
    return d.strftime('%Y-%m')

def bucket_label(key):
    if USE_WEEKS:
        y,w=int(key[:4]),int(key[6:])
        mon=date.fromisocalendar(y,w,1)
        return f'{mon.month}/{mon.day}'
    y,m=int(key[:4]),int(key[5:])
    return {'zh':f'{m}月','en':['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m],'ja':f'{m}月'}[args.lang]

bkt_days=defaultdict(list)
for d in valid: bkt_days[bucket_key(d)].append(d)
bkt_keys=sorted(bkt_days.keys())

def _avg(xs): return sum(xs)/len(xs) if xs else 0

buckets=[]
for key in bkt_keys:
    ds=bkt_days[key]
    totals=[sum(nights[d].values()) for d in ds]
    sp_min=[min(spo2_by[d]) for d in ds if spo2_by.get(d)]
    beds=[bed_h[d] for d in ds if d in bed_h]
    buckets.append(dict(
        key=key, label=bucket_label(key), n=len(ds),
        avg_total=_avg(totals),
        avg_deep =_avg([nights[d].get('Deep',0) for d in ds]),
        avg_core =_avg([nights[d].get('Core',0) for d in ds]),
        avg_rem  =_avg([nights[d].get('REM',0)  for d in ds]),
        avg_awake=_avg([nights[d].get('Awake',0) for d in ds]),
        good_rate=sum(1 for t in totals if t>=7)/len(totals) if totals else 0,
        spo2_min =min(sp_min) if sp_min else None,
        spo2_avg =_avg(sp_min) if sp_min else None,
        avg_bed  =_avg(beds) if beds else None,
    ))

nb=len(buckets)
g_avg  =_avg([b['avg_total'] for b in buckets])
g_deep =_avg([b['avg_deep']  for b in buckets])
g_rate =_avg([b['good_rate'] for b in buckets])
g_spmin=min((b['spo2_min'] for b in buckets if b['spo2_min'] is not None),default=None)
range_lbl=f"{valid[0].strftime('%Y/%m/%d')} – {valid[-1].strftime('%Y/%m/%d')}"

# ── Layout ────────────────────────────────────────────────────────────────────
W=1280; PAD=54; CW=W-PAD*2; GAP=24

METRIC_H =174
STAGE_H  =500   # panel card height; bars confined inside with chartClip
SPO2_H   =340
BED_H    =320
ROW_H    =62
rows_per_col=(nb+1)//2
SUM_H    =rows_per_col*ROW_H+110
CONCL_H  =108
FOOTER_H =60

y_hdr    =170
y_metrics=y_hdr+10
y_stage  =y_metrics+METRIC_H+GAP
y_spo2   =y_stage +STAGE_H +GAP
y_bed    =y_spo2  +SPO2_H  +GAP
y_sum    =y_bed   +BED_H   +GAP
y_concl  =y_sum   +SUM_H   +GAP
y_footer =y_concl +CONCL_H +GAP
TOTAL_H  =y_footer+FOOTER_H+50

# ── SVG ───────────────────────────────────────────────────────────────────────
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
<circle cx="1150" cy="220" r="300" fill="url(#glowBlue)"/>
<circle cx="80"   cy="{TOTAL_H-200}" r="280" fill="url(#glowPurple)"/>
<g filter="url(#shadow)">
''')

# Header
svg.append(txt(PAD,108,TITLE,54,COL['text'],850))
svg.append(txt(PAD,152,f'{range_lbl} · {len(valid)} {T["suffix"]} · {SUBTITLE} · {T["source"]}',22,COL['muted']))
svg.append(rct(920,60,306,56,28,'#ffffff12','#ffffff25'))
svg.append(icon('sparkles',940,76,26,'#dbeafe'))
svg.append(txt(976,97,'Sleep Intelligence',20,'#dbeafe',550))

# Metric cards
MCW,MCH,MGAP=272,METRIC_H,18
METRICS=[
    ('moon',    T['avg_sleep'],f'{g_avg:.1f}',           'h', T['note_sleep'],val_color(g_avg),  val_color(g_avg)),
    ('activity',T['good_rate'],f'{g_rate*100:.0f}',      '%', T['note_good'], pct_color(g_rate), pct_color(g_rate)),
    ('clock',   T['deep_avg'], f'{g_deep:.1f}',          'h', T['note_deep'], COL['violet'],     COL['violet']),
    ('droplet', T['min_spo2'], f'{g_spmin:.1f}' if g_spmin else '—','%',T['note_spo2'],COL['red'],COL['red']),
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

LEGEND=[( T['deep'],'deep'),(T['core'],'core'),('REM','rem'),(T['awake'],'awake')]
for i,(lbl,key) in enumerate(LEGEND):
    gx=PAD+380+i*195
    svg.append(f'<circle cx="{gx}" cy="{y_stage+44}" r="7" fill="{COL[key]}"/>')
    svg.append(txt(gx+16,y_stage+51,lbl,18,'#dbeafe',650))

# Chart area inside panel — reserve 56px at bottom for rotated labels
CHART_PAD_TOP=80; CHART_PAD_BOT=56
cx=PAD+60; cy=y_stage+CHART_PAD_TOP
chart_w=CW-120
chart_h=STAGE_H-CHART_PAD_TOP-CHART_PAD_BOT

# chartClip: hard boundary — bars CANNOT overflow top or sides
svg.append(f'<clipPath id="chartClip">'
           f'<rect x="{cx}" y="{cy}" width="{chart_w}" height="{chart_h}"/>'
           f'</clipPath>')

svg.append(line(cx,cy+chart_h,cx+chart_w,cy+chart_h))  # baseline
target_y=cy+chart_h-7/9*chart_h
svg.append(line(cx,target_y,cx+chart_w,target_y,COL['green'],2,'8 6'))
svg.append(txt(cx+chart_w-72,target_y-10,T['recommend'],16,'#86efac',500))

bar_gap=5
bw=max(6,(chart_w-(nb-1)*bar_gap)/nb)

# All bars inside chartClip group
svg.append('<g clip-path="url(#chartClip)">')
for i,b in enumerate(buckets):
    bx=cx+i*(bw+bar_gap); by=cy+chart_h
    for key,col in [('avg_deep',COL['deep']),('avg_core',COL['core']),('avg_rem',COL['rem']),('avg_awake',COL['awake'])]:
        hh=b[key]/9*chart_h
        by-=hh
        svg.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{hh:.1f}" rx="3" fill="{col}" opacity=".93"/>')
svg.append('</g>')

# Date labels outside chartClip (below baseline), rotated -45°
for i,b in enumerate(buckets):
    lx=cx+i*(bw+bar_gap)+bw/2
    ly=cy+chart_h+14
    svg.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="12" fill="{COL["muted"]}"'
               f' text-anchor="end" transform="rotate(-45 {lx:.1f} {ly:.1f})">{esc(b["label"])}</text>')

# ── Panel 2: SpO2 ─────────────────────────────────────────────────────────────
svg.append(rct(PAD,y_spo2,CW,SPO2_H,36,'url(#cardGrad)','#ffffff24'))
svg.append(icon('droplet',PAD+30,y_spo2+28,30,COL['blue']))
svg.append(txt(PAD+74,y_spo2+52,T['spo2_title'],28,COL['text'],760))

ax=cx; ay=y_spo2+88; aw=chart_w; ah=SPO2_H-130
# clipPath for SpO2 chart area — prevents bars/circles from escaping panel
svg.append(f'<clipPath id="spo2Clip"><rect x="{ax}" y="{ay}" width="{aw}" height="{ah}"/></clipPath>')
svg.append(line(ax,ay+ah,ax+aw,ay+ah))
svg.append(line(ax,ay,ax,ay+ah,'#ffffff18'))
for pct in [90,95,100]:
    gy=ay+ah-(pct-85)/15*ah
    svg.append(line(ax,gy,ax+aw,gy,'#ffffff15',1,'5 4'))
    svg.append(txt(ax-8,gy+5,str(pct),14,COL['muted'],400,'end'))
svg.append(line(ax,ay+ah-(95-85)/15*ah,ax+aw,ay+ah-(95-85)/15*ah,COL['amber'],1.5,'7 5'))
svg.append(txt(ax+aw+8,ay+ah-(95-85)/15*ah+5,T['warn_line'],13,COL['amber']))

# x positions: evenly distribute across full chart width
pts=[]
step = aw/max(1,nb-1) if nb>1 else 0
for i,b in enumerate(buckets):
    if b['spo2_min'] is None: continue
    bx=ax+i*step; by2=ay+ah-(b['spo2_min']-85)/15*ah
    bh2=ay+ah-by2; col=COL['red'] if b['spo2_min']<90 else COL['blue']
    pts.append((bx,by2,b,col))

svg.append('<g clip-path="url(#spo2Clip)">')
for bx,by2,b,col in pts:
    bh2=ay+ah-by2
    svg.append(f'<rect x="{bx-bw/2:.1f}" y="{by2:.1f}" width="{bw:.1f}" height="{bh2:.1f}" rx="3" fill="{col}" opacity=".3"/>')
for (x1,y1,_,__),(x2,y2,_,__) in zip(pts,pts[1:]):
    svg.append(line(x1,y1,x2,y2,COL['blue'],2.5))
for bx,by2,b,col in pts:
    svg.append(f'<circle cx="{bx:.1f}" cy="{by2:.1f}" r="5" fill="{col}"/>')
svg.append('</g>')

spo2_avgs=[b['spo2_avg'] for b in buckets if b['spo2_avg']]
sp_stat=(f'{T["avg_lbl"]} {_avg(spo2_avgs):.1f}%  ·  {T["min_lbl"]} {g_spmin:.1f}%' if g_spmin else '')
svg.append(txt(ax,ay+ah+28,sp_stat,18,COL['muted']))

# ── Panel 3: Bedtime ──────────────────────────────────────────────────────────
svg.append(rct(PAD,y_bed,CW,BED_H,36,'url(#cardGrad)','#ffffff24'))
svg.append(icon('clock',PAD+30,y_bed+28,30,COL['violet']))
svg.append(txt(PAD+74,y_bed+52,T['bed_title'],28,COL['text'],760))

bax=cx; bay=y_bed+88; baw=chart_w; bah=BED_H-130
BASE=22
def to_ax(h): return (h-BASE)%24
def ax_fmt(v): return f'{int((BASE+v)%24):02d}:00'

svg.append(line(bax,bay+bah,bax+baw,bay+bah))
svg.append(line(bax,bay,bax,bay+bah,'#ffffff18'))
for tick in range(0,13,2):
    ty2=bay+tick/12*bah
    svg.append(line(bax,ty2,bax+baw,ty2,'#ffffff12',1,'4 4'))
    svg.append(txt(bax-8,ty2+5,ax_fmt(tick),13,COL['muted'],400,'end'))
warn_v=to_ax(1)/12*bah
svg.append(line(bax,bay+warn_v,bax+baw,bay+warn_v,COL['red'],1.5,'7 5'))
svg.append(txt(bax+baw+8,bay+warn_v+5,T['warn_01'],13,COL['red']))

bed_pts=[]
for i,b in enumerate(buckets):
    if b['avg_bed'] is None: continue
    bh_n=b['avg_bed']%24; v=to_ax(bh_n)/12*bah
    px2=bax+i*(baw/max(1,nb-1)); py2=bay+v
    bed_pts.append((px2,py2,b))
for (x1,y1,_),(x2,y2,_) in zip(bed_pts,bed_pts[1:]):
    svg.append(line(x1,y1,x2,y2,COL['violet'],2.5))
for px2,py2,b in bed_pts:
    svg.append(f'<circle cx="{px2:.1f}" cy="{py2:.1f}" r="5" fill="{COL["violet"]}"/>')

# ── Panel 4: Summary table ────────────────────────────────────────────────────
svg.append(rct(PAD,y_sum,CW,SUM_H,36,'url(#cardGrad)','#ffffff24'))
svg.append(icon('calendar',PAD+30,y_sum+28,30,COL['amber']))
svg.append(txt(PAD+74,y_sum+52,T['sum_title'],28,COL['text'],760))

half_cw=(CW-20)//2
for i,b in enumerate(buckets):
    col_idx=i//rows_per_col; row_idx=i%rows_per_col
    rx=PAD+col_idx*(half_cw+20); ry=y_sum+80+row_idx*ROW_H
    svg.append(rct(rx,ry,half_cw,ROW_H-8,18,'#0f172acc','#ffffff18'))
    svg.append(txt(rx+14,ry+ROW_H-20,b['label'],17,COL['text'],700))
    svg.append(txt(rx+110,ry+ROW_H-20,f"{b['avg_total']:.1f}h",17,val_color(b['avg_total']),700))
    svg.append(txt(rx+210,ry+ROW_H-20,f"{b['good_rate']*100:.0f}% {T['goal_lbl']}",15,pct_color(b['good_rate']),500))
    svg.append(txt(rx+360,ry+ROW_H-20,
                   f"{T['spo2_lbl']} {b['spo2_min']:.0f}%" if b['spo2_min'] else '',
                   15,COL['red'] if b['spo2_min'] and b['spo2_min']<90 else COL['muted'],400))

# ── Conclusion ────────────────────────────────────────────────────────────────
svg.append(rct(PAD,y_concl,CW,CONCL_H,30,'#0f172acc','#ffffff1e'))
spo2_ok=g_spmin is None or g_spmin>=90
conc={'zh':f"均值 {g_avg:.1f}h · 达标率 {g_rate*100:.0f}% · 深睡均值 {g_deep:.1f}h"+('· 血氧低点正常' if spo2_ok else f' · 血氧最低 {g_spmin:.1f}% ⚠'),
      'en':f"{g_avg:.1f}h avg · {g_rate*100:.0f}% goal · Deep {g_deep:.1f}h"+(' · SpO2 OK' if spo2_ok else f' · SpO2 min {g_spmin:.1f}% ⚠'),
      'ja':f"平均 {g_avg:.1f}h · 達成率 {g_rate*100:.0f}% · 深睡眠 {g_deep:.1f}h"+('· SpO2 正常' if spo2_ok else f' · 最低 {g_spmin:.1f}% ⚠')}[args.lang]
svg.append(txt(PAD+22,y_concl+44,T['conclusion'],26,COL['text'],800))
svg.append(txt(PAD+22,y_concl+82,conc,20,'#cbd5e1'))

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
