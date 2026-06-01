#!/usr/bin/env python3
import json, subprocess, html, argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--data',       default='/var/minis/workspace/sleep_report_7d.json')
parser.add_argument('--out-prefix', default='/var/minis/workspace/sleep_report_7d_librsvg')
parser.add_argument('--lang',       default='zh', choices=['zh','en','ja'])
parser.add_argument('--width',  type=int, default=1280)
parser.add_argument('--height', type=int, default=1760)
args = parser.parse_args()

STRINGS = {
    'zh': dict(title='最近一周睡眠周报', suffix='夜有效记录', source_suffix='Apple Health 睡眠阶段 / 血氧',
               avg_sleep='平均睡眠', good_days='达标天数', deep_avg='深睡均值', min_spo2='最低血氧',
               stage_trend='睡眠阶段趋势', recommend='推荐 7h', key_insights='关键洞察', daily_detail='每日明细',
               deep='深睡', core='浅睡', awake='清醒', bedtime='入睡', min_o2='最低氧',
               spo2_section='睡眠期最低血氧', generated='生成时间',
               data_source='数据来源：Apple HealthKit · 仅供健康趋势参考',
               note_duration='低于推荐 7h，优先补时长', note_good='夜有效记录', note_deep='深睡略偏少，恢复不足', note_spo2='建议持续观察',
               ins_duration_t='主问题：睡眠时长不足', ins_bedtime_t='作息偏晚', ins_spo2_t='血氧均值正常，低点需观察',
               ins_bedtime_b_tpl='平均入睡 {bed}，建议先提前到 00:30 前。'),
    'en': dict(title='Weekly Sleep Report', suffix='nights recorded', source_suffix='Apple Health Sleep Stages / SpO2',
               avg_sleep='Avg Sleep', good_days='Goal Days', deep_avg='Avg Deep', min_spo2='Min SpO2',
               stage_trend='Sleep Stage Trend', recommend='Goal 7h', key_insights='Key Insights', daily_detail='Daily Detail',
               deep='Deep', core='Core', awake='Awake', bedtime='Bedtime', min_o2='Min O2',
               spo2_section='Nightly Min SpO2', generated='Generated',
               data_source='Source: Apple HealthKit · For reference only',
               note_duration='Below 7h goal, prioritize sleep', note_good='nights recorded', note_deep='Low deep sleep', note_spo2='Monitor closely',
               ins_duration_t='Issue: Sleep Too Short', ins_bedtime_t='Late Bedtime', ins_spo2_t='SpO2 avg OK, low dips noted',
               ins_bedtime_b_tpl='Avg bedtime {bed}. Aim for before 00:30.'),
    'ja': dict(title='週間睡眠レポート', suffix='夜の有効記録', source_suffix='Apple Health 睡眠ステージ / 血中酸素',
               avg_sleep='平均睡眠', good_days='達成日数', deep_avg='深睡眠平均', min_spo2='最低血中酸素',
               stage_trend='睡眠ステージ推移', recommend='目標 7h', key_insights='重要インサイト', daily_detail='日別明細',
               deep='深睡眠', core='コア', awake='覚醒', bedtime='就寝', min_o2='最低O2',
               spo2_section='夜間最低血中酸素', generated='生成日時',
               data_source='データ：Apple HealthKit · 参考用のみ',
               note_duration='7h未満、まず睡眠時間を確保', note_good='夜の有効記録', note_deep='深睡眠が少ない', note_spo2='継続観察を推奨',
               ins_duration_t='問題：睡眠時間不足', ins_bedtime_t='就寝時刻が遅い', ins_spo2_t='血中酸素平均は正常、低下に注意',
               ins_bedtime_b_tpl='平均就寝 {bed}。00:30前を目標に。'),
}
T = STRINGS[args.lang]

data = json.loads(Path(args.data).read_text())
S, R = data['summary'], data['rows']
W, H = args.width, args.height

# Compute average bedtime from actual data for the insight card
def _avg_bed():
    beds = [r['bed'] for r in R if r.get('bed') and r['bed'] != '—']
    if not beds: return '—'
    # parse HH:MM, convert to float hours adjusted for cross-midnight
    def to_h(s):
        h, m = int(s[:2]), int(s[3:])
        f = h + m/60
        return f + 24 if f < 14 else f
    avg = sum(to_h(b) for b in beds) / len(beds)
    h = int(avg % 24); m = int((avg % 1) * 60)
    return f'{h:02d}:{m:02d}'

avg_bed_str = _avg_bed()
T_bedtime_b = T['ins_bedtime_b_tpl'].format(bed=avg_bed_str)

SVG_PATH = Path(args.out_prefix + '.svg')
PNG_PATH = Path(args.out_prefix + '.png')

COL = {
    'bg0':'#07111f','bg1':'#0b1020','card':'#111827','card2':'#0f172a','line':'#26324a',
    'text':'#f8fafc','muted':'#94a3b8','blue':'#60a5fa','cyan':'#22d3ee','violet':'#a78bfa',
    'amber':'#fbbf24','red':'#fb7185','green':'#34d399','deep':'#2563eb','core':'#22c1c3','rem':'#a78bfa','awake':'#fb923c'
}

def esc(x): return html.escape(str(x))
def icon(name, x, y, size=28, color='currentColor', sw=2.3):
    paths = {
        'moon': '<path d="M12 3a6.6 6.6 0 0 0 8.8 8.8A9 9 0 1 1 12 3Z"/>',
        'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        'heart': '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8Z"/>',
        'droplet': '<path d="M12 2.5S5.5 9.4 5.5 14A6.5 6.5 0 0 0 18.5 14C18.5 9.4 12 2.5 12 2.5Z"/>',
        'alert': '<path d="M10.3 3.9 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
        'bars': '<path d="M3 3v18h18"/><path d="M7 16V9M12 16V5M17 16v-3"/>',
        'activity': '<path d="M22 12h-4l-3 8L9 4l-3 8H2"/>',
        'sparkles': '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"/>'
    }
    return f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>'

def total_cls(v):
    return COL['green'] if v >= 7 else (COL['amber'] if v >= 6 else COL['red'])

def rounded_rect(x,y,w,h,r,fill,stroke='#ffffff22',opacity=1):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" opacity="{opacity}"/>'

def text(x,y,content,size=24,color=None,weight=400,anchor='start',opacity=1):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color or COL["text"]}" font-weight="{weight}" text-anchor="{anchor}" opacity="{opacity}">{esc(content)}</text>'

def metric_card(x,y,w,h,icon_name,title,value,unit,note,color,value_color=None):
    s=[]
    s.append(rounded_rect(x,y,w,h,28,'url(#cardGrad)','#ffffff24'))
    s.append(text(x+24,y+42,title,20,COL['muted'],500))
    s.append(f'<rect x="{x+w-76}" y="{y+22}" width="54" height="54" rx="17" fill="{color}" opacity=".16"/>')
    s.append(icon(icon_name,x+w-63,y+35,28,color))
    # librsvg 对不同字体的数字宽度估算不稳定，使用单个 <text> + tspan 避免单位错位
    s.append(
        f'<text x="{x+24}" y="{y+116}" font-size="50" fill="{value_color or color}" font-weight="850">'
        f'{esc(value)}<tspan font-size="24" fill="{COL["muted"]}" font-weight="650" dx="8">{esc(unit)}</tspan></text>'
    )
    s.append(text(x+24,y+152,note,18,COL['muted'],400))
    return '\n'.join(s)

svg=[]
svg.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#07111f"/><stop offset=".55" stop-color="#0b1020"/><stop offset="1" stop-color="#111827"/></linearGradient>
  <radialGradient id="glowBlue" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#38bdf8" stop-opacity=".55"/><stop offset="1" stop-color="#38bdf8" stop-opacity="0"/></radialGradient>
  <radialGradient id="glowPurple" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#a78bfa" stop-opacity=".45"/><stop offset="1" stop-color="#a78bfa" stop-opacity="0"/></radialGradient>
  <linearGradient id="cardGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity=".105"/><stop offset="1" stop-color="#ffffff" stop-opacity=".035"/></linearGradient>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="28" stdDeviation="28" flood-color="#000000" flood-opacity=".34"/></filter>
  <style><![CDATA[
    text{{font-family:'Noto Sans CJK SC','Noto Sans CJK SC Regular','Noto Sans CJK','PingFang SC',Arial,sans-serif;text-rendering:geometricPrecision}}
  ]]></style>
</defs>
<rect width="100%" height="100%" fill="url(#bg)"/>
<circle cx="1190" cy="180" r="270" fill="url(#glowBlue)"/>
<circle cx="0" cy="1540" r="260" fill="url(#glowPurple)"/>
<g filter="url(#shadow)">
''')
# header
svg.append(text(54,108,T['title'],58,COL['text'],850))
svg.append(text(56,152,f"{S['range']} · {S['days']} {T['suffix']} · {T['source_suffix']}",25,COL['muted'],400))
svg.append(rounded_rect(950,62,270,60,30,'#ffffff12','#ffffff25'))
svg.append(icon('sparkles',972,78,28,'#dbeafe'))
svg.append(text(1016,101,'Sleep Intelligence',22,'#dbeafe',550))

# metrics
mx,my,gap,cw,ch=54,210,20,280,174
cards=[
    ('moon', T['avg_sleep'],  S['avg_total'], 'h', T['note_duration'], COL['blue'],   total_cls(S['avg_total'])),
    ('clock',T['good_days'],  S['good_days'], '',  f"{S['days']} {T['note_good']}",   COL['green'],  COL['green']),
    ('heart',T['deep_avg'],   S['avg_deep'],  'h', T['note_deep'],     COL['violet'], COL['violet']),
    ('droplet',T['min_spo2'], S['min_spo2'],  '%', T['note_spo2'],     COL['red'],    COL['red']),
]
for i,c in enumerate(cards): svg.append(metric_card(mx+i*(cw+gap),my,cw,ch,*c))

# main stage panel
px,py,pw,ph=54,420,1172,520
svg.append(rounded_rect(px,py,pw,ph,36,'url(#cardGrad)','#ffffff24'))
svg.append(icon('bars',px+30,py+29,31,COL['cyan']))
svg.append(text(px+76,py+55,T['stage_trend'],30,COL['text'],760))
chart_x,chart_y,chart_w,chart_h=px+40,py+112,pw-80,320
svg.append(f'<line x1="{chart_x}" y1="{chart_y+chart_h}" x2="{chart_x+chart_w}" y2="{chart_y+chart_h}" stroke="#ffffff24"/>')
target_y=chart_y+chart_h-7/8*chart_h
svg.append(f'<line x1="{chart_x}" y1="{target_y}" x2="{chart_x+chart_w}" y2="{target_y}" stroke="{COL['green']}" stroke-width="2" stroke-dasharray="8 8" opacity=".75"/>')
svg.append(text(chart_x+chart_w-82,target_y-12,T['recommend'],18,'#86efac',500))
bar_w=82; step=chart_w/len(R)
for i,r in enumerate(R):
    cx=chart_x+i*step+step/2-bar_w/2
    svg.append(f'<clipPath id="clip{i}"><rect x="{cx}" y="{chart_y}" width="{bar_w}" height="{chart_h}" rx="26"/></clipPath>')
    svg.append(f'<rect x="{cx}" y="{chart_y}" width="{bar_w}" height="{chart_h}" rx="26" fill="#0f172a" stroke="#ffffff18"/>')
    y=chart_y+chart_h
    for key,col in [('deep',COL['deep']),('core',COL['core']),('rem',COL['rem']),('awake',COL['awake'])]:
        hh=r[key]/8*chart_h; y-=hh
        svg.append(f'<rect clip-path="url(#clip{i})" x="{cx}" y="{y}" width="{bar_w}" height="{hh}" fill="{col}" opacity=".95"/>')
    svg.append(text(cx+bar_w/2,chart_y+chart_h+38,f"{r['total']:.1f}h",21,total_cls(r['total']),780,'middle'))
    svg.append(text(cx+bar_w/2,chart_y+chart_h+68,f"{r['label']} {r['weekday']}",18,COL['muted'],400,'middle'))
legend_items=[('deep',COL['deep'],T['deep']),('core',COL['core'],T['core']),('rem',COL['rem'],'REM'),('awake',COL['awake'],T['awake'])]
lx0,ly2=px+365,py+48
for idx,(name,col,lbl) in enumerate(legend_items):
    gx=lx0+idx*190
    svg.append(f'<circle cx="{gx}" cy="{ly2}" r="7" fill="{col}"/>')
    svg.append(text(gx+16,ly2+7,lbl,19,'#dbeafe',650))

# lower panels
for p in [(54,970,620,620),(698,970,528,620)]: svg.append(rounded_rect(*p[:4],36,'url(#cardGrad)','#ffffff24'))
svg.append(icon('moon',84,1000,31,COL['blue'])); svg.append(text(130,1027,T['daily_detail'],30,COL['text'],760))
row_y=1060
for r in R:
    svg.append(rounded_rect(84,row_y,560,70,22,'#0f172acc','#ffffff18'))
    svg.append(text(104,row_y+31,r['label'],20,COL['text'],760))
    svg.append(text(104,row_y+54,r['weekday'],15,COL['muted']))
    bx,by,bw,bh=198,row_y+28,250,18
    svg.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="9" fill="#243047"/>')
    svg.append(f'<rect x="{bx}" y="{by}" width="{min(bw,r['total']/7*bw)}" height="{bh}" rx="9" fill="url(#barFill)"/>')
    svg.append(f'<defs><linearGradient id="barFill" x1="0" x2="1"><stop offset="0" stop-color="{COL['blue']}"/><stop offset=".55" stop-color="{COL['cyan']}"/><stop offset="1" stop-color="{COL['violet']}"/></linearGradient></defs>')
    svg.append(text(472,row_y+31,r['bed'],19,'#dbeafe',550,'end'))
    svg.append(text(472,row_y+53,T['bedtime'],14,COL['muted'],400,'end'))
    spcol=COL['red'] if r['spo2_min']<90 else (COL['amber'] if r['spo2_min']<95 else COL['green'])
    svg.append(text(620,row_y+31,str(r['spo2_min'])+'%',19,spcol,650,'end'))
    svg.append(text(620,row_y+53,T['min_o2'],14,COL['muted'],400,'end'))
    row_y+=84

svg.append(icon('activity',728,1000,31,COL['violet'])); svg.append(text(774,1027,T['key_insights'],30,COL['text'],760))
ins=[
    ('alert', COL['red'],    T['ins_duration_t'], f"{T['avg_sleep']} {S['avg_total']}h. {T['note_duration']}."),
    ('clock', COL['amber'],  T['ins_bedtime_t'],  T_bedtime_b),
    ('droplet',COL['cyan'],  T['ins_spo2_t'],     f"avg {S['avg_spo2']}%, min {S['min_spo2']}%. {T['note_spo2']}."),
]
y=1060
for ic,col,title,body in ins:
    svg.append(rounded_rect(728,y,468,95,24,'#0f172acc','#ffffff18'))
    svg.append(f'<rect x="{750}" y="{y+20}" width="48" height="48" rx="16" fill="{col}" opacity=".16"/>')
    svg.append(icon(ic,761,y+30,25,col))
    svg.append(text(816,y+38,title,21,COL['text'],760))
    words=list(body); line=''; lines=[]
    for ch in words:
        line+=ch
        if len(line)>=27: lines.append(line); line=''
    if line: lines.append(line)
    for j,ln in enumerate(lines[:2]): svg.append(text(816,y+65+j*18,ln,14,'#cbd5e1',400))
    y+=111
svg.append(text(728,1415,T['spo2_section'],20,'#cbd5e1',500))
cx0,cy0,cw2,ch2=728,1448,468,88
mini_step=cw2/len(R)
for i,r in enumerate(R):
    h=max(18,(r['spo2_min']-85)/15*ch2)
    x=cx0+i*mini_step+20; y=cy0+ch2-h
    col=COL['red'] if r['spo2_min']<90 else COL['blue']
    svg.append(f'<rect x="{x}" y="{y}" width="42" height="{h}" rx="11" fill="{col}" opacity=".9"/>')
    svg.append(text(x+21,y-10,str(r['spo2_min'])+'%',13,'#cbd5e1',500,'middle'))
    svg.append(text(x+21,cy0+ch2+24,r['label'][3:],13,'#64748b',400,'middle'))

from datetime import date as _date
svg.append(rounded_rect(54,1698,340,42,21,'#ffffff0a','#ffffff18'))
svg.append(text(76,1725,f"{T['generated']}: {_date.today()}",17,COL['muted']))
svg.append(text(1226,1725,T['data_source'],17,COL['muted'],400,'end'))
svg.append('</g></svg>')
SVG_PATH.write_text('\n'.join(svg))
subprocess.run(['rsvg-convert', str(SVG_PATH), '-w', str(W), '-h', str(H), '-o', str(PNG_PATH)], check=True)
print(PNG_PATH)
