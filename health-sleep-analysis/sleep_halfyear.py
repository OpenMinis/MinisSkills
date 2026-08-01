#!/usr/bin/env python3
"""
sleep_halfyear.py — 半年 / 长期睡眠趋势可视化
用法: cd /path/to/workdir && python3 sleep_halfyear.py
输入: sleep_raw.json, spo2_raw.json（当前目录）
输出: sleep_halfyear.png（当前目录）
"""

import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
from matplotlib.gridspec import GridSpec
from datetime import datetime, timedelta, date
from collections import defaultdict
import os, sys

# ── 字体 ──────────────────────────────────────────────────────
def setup_font():
    cjk_paths = [
        '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/noto-cjk/NotoSansCJKsc-Regular.otf',
        '/usr/share/fonts/noto/NotoSansCJK-Regular.ttc',
    ]
    for p in cjk_paths:
        if os.path.exists(p):
            fm.fontManager.addfont(p)
            prop = fm.FontProperties(fname=p)
            plt.rcParams['font.family'] = prop.get_name()
            return
    plt.rcParams['font.family'] = 'sans-serif'

setup_font()
plt.rcParams.update({'font.size': 10, 'axes.unicode_minus': False})

# ── 常量 ──────────────────────────────────────────────────────
STAGE_META = {
    'asleepDeep': {'label': '深睡眠', 'color': '#2D6A9F'},
    'asleepREM':  {'label': 'REM',    'color': '#6A5ACD'},
    'asleepCore': {'label': '浅睡眠', 'color': '#5BA4CF'},
    'awake':      {'label': '清醒',   'color': '#F4A261'},
}
STAGE_ORDER = ['asleepDeep', 'asleepREM', 'asleepCore', 'awake']

# ── 日期归属（凌晨0-14点归前一天）─────────────────────────────
def sleep_date(dt: datetime) -> date:
    if dt.hour < 14:
        return (dt - timedelta(days=1)).date()
    return dt.date()

def parse_dt(s):
    return datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S')

# ── 加载睡眠数据 ───────────────────────────────────────────────
def load_sleep(path):
    data = json.load(open(path))
    samples = data.get('samples', data) if isinstance(data, dict) else data
    by_day = defaultdict(lambda: defaultdict(float))
    bed_times = defaultdict(list)
    wake_times = defaultdict(list)
    for s in samples:
        v = s.get('value', '')
        if v == 'inBed':
            continue
        start = parse_dt(s.get('startDate', s.get('start', '')))
        end   = parse_dt(s.get('endDate', s.get('end', '')))
        dur   = (end - start).total_seconds() / 3600
        if dur <= 0:
            continue
        day = sleep_date(start)
        if v in STAGE_META:
            by_day[day][v] += dur
        # 入睡/起床时间（只记非awake）
        if v != 'awake':
            bed_times[day].append(start)
            wake_times[day].append(end)
    return by_day, bed_times, wake_times

# ── 加载血氧数据 ───────────────────────────────────────────────
def load_spo2(path):
    data = json.load(open(path))
    samples = data.get('samples', data) if isinstance(data, dict) else data
    by_day = defaultdict(list)
    for s in samples:
        try:
            dt = parse_dt(s.get('startDate', s.get('date', '')))
        except:
            continue
        val = s.get('percentage', s.get('value', None))
        if val is None:
            continue
        val = float(val)
        if val > 1:
            val = val  # already %
        else:
            val = val * 100
        if val < 70 or val > 100:
            continue
        day = sleep_date(dt)
        by_day[day].append(val)
    return by_day

# ── 时间轴辅助（以22:00为基准）────────────────────────────────
BASE_H = 22
def to_axis(h):
    return (h - BASE_H) % 24
def axis_fmt(v, pos=None):
    h = int((BASE_H + v) % 24)
    return f'{h:02d}:00'

# ── 7日滚动均值 ────────────────────────────────────────────────
def rolling_mean(vals, w=7):
    out = []
    for i in range(len(vals)):
        sl = [v for v in vals[max(0, i-w+1):i+1] if v is not None]
        out.append(np.mean(sl) if sl else None)
    return out

# ── 月度汇总 ───────────────────────────────────────────────────
def monthly_summary(days, by_day, spo2_by_day):
    from collections import OrderedDict
    months = OrderedDict()
    for d in days:
        key = (d.year, d.month)
        if key not in months:
            months[key] = {'days': [], 'spo2': []}
        months[key]['days'].append(d)
        if d in spo2_by_day and spo2_by_day[d]:
            months[key]['spo2'].extend(spo2_by_day[d])
    return months

# ══════════════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════════════
SLEEP_PATH = 'sleep_raw.json'
SPO2_PATH  = 'spo2_raw.json'
OUT_PATH   = 'sleep_halfyear.png'

by_day, bed_times, wake_times = load_sleep(SLEEP_PATH)
spo2_by_day = load_spo2(SPO2_PATH)

# 过滤：总睡眠 >= 1h 的天
valid_days = sorted([
    d for d, stages in by_day.items()
    if sum(stages.values()) >= 1.0
])

if not valid_days:
    print("没有有效睡眠数据", file=sys.stderr)
    sys.exit(1)

print(f"有效睡眠天数: {len(valid_days)} 天")
print(f"日期范围: {valid_days[0]} ~ {valid_days[-1]}")

# 取最近 185 天
if len(valid_days) > 185:
    valid_days = valid_days[-185:]

days = valid_days
xs = [datetime(d.year, d.month, d.day) for d in days]

# ── 各阶段时长序列 ──────────────────────────────────────────
stage_vals = {k: [by_day[d].get(k, 0) for d in days] for k in STAGE_ORDER}
total_sleep = [sum(by_day[d].get(k, 0) for k in ['asleepDeep','asleepREM','asleepCore']) for d in days]

# ── 血氧序列 ──────────────────────────────────────────────────
spo2_mean = [np.mean(spo2_by_day[d]) if spo2_by_day.get(d) else None for d in days]
spo2_min  = [min(spo2_by_day[d]) if spo2_by_day.get(d) else None for d in days]
spo2_mean_roll = rolling_mean(spo2_mean)
total_roll = rolling_mean(total_sleep)

# ── 入睡/起床时间 ─────────────────────────────────────────────
bed_h, wake_h = [], []
for d in days:
    if bed_times[d]:
        bh = min(bed_times[d]).hour + min(bed_times[d]).minute/60
        bed_h.append(to_axis(bh))
    else:
        bed_h.append(None)
    if wake_times[d]:
        wh = max(wake_times[d]).hour + max(wake_times[d]).minute/60
        wake_h.append(to_axis(wh))
    else:
        wake_h.append(None)

bed_roll  = rolling_mean(bed_h)
wake_roll = rolling_mean(wake_h)

# ── 月度汇总 ──────────────────────────────────────────────────
months = monthly_summary(days, by_day, spo2_by_day)

# ══════════════════════════════════════════════════════════════
# 绘图
# ══════════════════════════════════════════════════════════════
BG = '#0F1117'
GRID_C = '#2A2D3A'
TEXT_C = '#E0E0E0'
ACCENT = '#4FC3F7'

fig = plt.figure(figsize=(18, 22), facecolor=BG)
gs = GridSpec(4, 2, figure=fig,
              hspace=0.42, wspace=0.25,
              left=0.06, right=0.97, top=0.95, bottom=0.04)

ax1 = fig.add_subplot(gs[0, :])   # 睡眠堆叠柱
ax2 = fig.add_subplot(gs[1, :])   # 血氧趋势
ax3 = fig.add_subplot(gs[2, :])   # 入睡/起床时间
ax4 = fig.add_subplot(gs[3, 0])   # 月度平均
ax5 = fig.add_subplot(gs[3, 1])   # 月度血氧箱线

def style_ax(ax, title):
    ax.set_facecolor('#181B27')
    ax.tick_params(colors=TEXT_C, labelsize=9)
    ax.set_title(title, color=TEXT_C, fontsize=12, fontweight='bold', pad=8)
    ax.spines[:].set_color(GRID_C)
    ax.yaxis.label.set_color(TEXT_C)
    ax.xaxis.label.set_color(TEXT_C)
    ax.grid(axis='y', color=GRID_C, linewidth=0.6, linestyle='--')

# ── 标题 ──────────────────────────────────────────────────────
fig.text(0.5, 0.975, '睡眠趋势分析报告', ha='center', va='top',
         color='white', fontsize=18, fontweight='bold')
fig.text(0.5, 0.962, f'{days[0].strftime("%Y.%m.%d")} — {days[-1].strftime("%Y.%m.%d")}  |  共 {len(days)} 天',
         ha='center', va='top', color='#888888', fontsize=11)

# ────────────────────────────────────────────────────────────
# 图1：每日睡眠堆叠柱 + 7日均线
# ────────────────────────────────────────────────────────────
style_ax(ax1, '每日睡眠时长（小时）')
bottom = np.zeros(len(days))
for k in STAGE_ORDER:
    vals = np.array(stage_vals[k])
    ax1.bar(xs, vals, bottom=bottom, color=STAGE_META[k]['color'],
            label=STAGE_META[k]['label'], width=0.8, alpha=0.85)
    bottom += vals

# 7日滚动均线
roll_xs = [x for x, v in zip(xs, total_roll) if v is not None]
roll_ys = [v for v in total_roll if v is not None]
ax1.plot(roll_xs, roll_ys, color='#FFD700', linewidth=2, label='7日均线', zorder=5)
ax1.axhline(7, color='#FF6B6B', linewidth=1.2, linestyle='--', alpha=0.8, label='推荐7小时')

ax1.set_ylabel('小时')
ax1.legend(loc='upper left', framealpha=0.3, labelcolor=TEXT_C,
           facecolor='#1E2130', edgecolor=GRID_C, ncol=6, fontsize=9)
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
ax1.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
ax1.set_xlim(xs[0] - timedelta(days=1), xs[-1] + timedelta(days=1))
ax1.set_ylim(0, 12)
ax1.tick_params(axis='x', rotation=30)

# 均值标注
avg_total = np.mean([v for v in total_sleep if v > 0])
ax1.text(0.99, 0.95, f'均值 {avg_total:.1f}h', transform=ax1.transAxes,
         ha='right', va='top', color='#FFD700', fontsize=10, fontweight='bold')

# ────────────────────────────────────────────────────────────
# 图2：血氧趋势
# ────────────────────────────────────────────────────────────
style_ax(ax2, '睡眠期血氧饱和度（SpO₂）')
spo2_xs = [x for x, v in zip(xs, spo2_mean) if v is not None]
spo2_ys = [v for v in spo2_mean if v is not None]
spo2_min_xs = [x for x, v in zip(xs, spo2_min) if v is not None]
spo2_min_ys = [v for v in spo2_min if v is not None]

if spo2_xs:
    ax2.fill_between(spo2_xs, spo2_ys, alpha=0.25, color='#4FC3F7')
    ax2.plot(spo2_xs, spo2_ys, color='#4FC3F7', linewidth=1.5, label='均值', zorder=4)
    ax2.scatter(spo2_min_xs, spo2_min_ys, color='#FF8A65', s=18, alpha=0.7, label='最低值', zorder=5)

    # 7日均线
    roll2_xs = [x for x, v in zip(spo2_xs, rolling_mean(spo2_ys)) if v is not None]
    roll2_ys = [v for v in rolling_mean(spo2_ys) if v is not None]
    ax2.plot(roll2_xs, roll2_ys, color='#FFD700', linewidth=2, label='7日均线', zorder=6)

    # 标注低于90的点
    for x, y in zip(spo2_min_xs, spo2_min_ys):
        if y < 90:
            ax2.annotate(f'{y:.0f}%', (x, y), textcoords='offset points',
                         xytext=(0, -14), color='#FF5252', fontsize=8)

ax2.axhline(95, color='#FF6B6B', linewidth=1, linestyle='--', alpha=0.7, label='95%警戒线')
ax2.set_ylabel('SpO₂ (%)')
ax2.set_ylim(88, 101)
ax2.legend(loc='lower left', framealpha=0.3, labelcolor=TEXT_C,
           facecolor='#1E2130', edgecolor=GRID_C, ncol=4, fontsize=9)
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
ax2.set_xlim(xs[0] - timedelta(days=1), xs[-1] + timedelta(days=1))
ax2.tick_params(axis='x', rotation=30)

if spo2_ys:
    ax2.text(0.99, 0.05, f'均值 {np.mean(spo2_ys):.1f}%', transform=ax2.transAxes,
             ha='right', va='bottom', color='#4FC3F7', fontsize=10, fontweight='bold')

# ────────────────────────────────────────────────────────────
# 图3：入睡 / 起床时间
# ────────────────────────────────────────────────────────────
style_ax(ax3, '入睡 & 起床时间')
bed_xs  = [x for x, v in zip(xs, bed_h)  if v is not None]
bed_ys  = [v for v in bed_h  if v is not None]
wake_xs = [x for x, v in zip(xs, wake_h) if v is not None]
wake_ys = [v for v in wake_h if v is not None]

if bed_xs:
    ax3.scatter(bed_xs, bed_ys, color='#AB47BC', s=22, alpha=0.6, label='入睡', zorder=4)
    roll_b = rolling_mean(bed_ys)
    roll_bx = [x for x, v in zip(bed_xs, roll_b) if v is not None]
    roll_by = [v for v in roll_b if v is not None]
    ax3.plot(roll_bx, roll_by, color='#CE93D8', linewidth=2, label='入睡7日均', zorder=5)

if wake_xs:
    ax3.scatter(wake_xs, wake_ys, color='#26A69A', s=22, alpha=0.6, label='起床', zorder=4)
    roll_w = rolling_mean(wake_ys)
    roll_wx = [x for x, v in zip(wake_xs, roll_w) if v is not None]
    roll_wy = [v for v in roll_w if v is not None]
    ax3.plot(roll_wx, roll_wy, color='#4DB6AC', linewidth=2, label='起床7日均', zorder=5)

# 01:00 警戒线 (to_axis(1) = (1-22)%24 = 3)
ax3.axhline(to_axis(1), color='#FF6B6B', linewidth=1, linestyle='--', alpha=0.7, label='01:00警戒')

ax3.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(axis_fmt))
ax3.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
ax3.set_ylabel('时间')
ax3.legend(loc='upper left', framealpha=0.3, labelcolor=TEXT_C,
           facecolor='#1E2130', edgecolor=GRID_C, ncol=5, fontsize=9)
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
ax3.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
ax3.set_xlim(xs[0] - timedelta(days=1), xs[-1] + timedelta(days=1))
ax3.tick_params(axis='x', rotation=30)

# ────────────────────────────────────────────────────────────
# 图4：月度平均睡眠堆叠柱
# ────────────────────────────────────────────────────────────
style_ax(ax4, '月度平均睡眠时长')
month_labels, month_deep, month_rem, month_core, month_total = [], [], [], [], []
for (yr, mo), info in months.items():
    label = f"{yr}/{mo:02d}"
    mdays = [d for d in info['days'] if sum(by_day[d].values()) >= 1]
    if not mdays:
        continue
    month_labels.append(label)
    month_deep.append(np.mean([by_day[d].get('asleepDeep', 0) for d in mdays]))
    month_rem.append(np.mean([by_day[d].get('asleepREM', 0) for d in mdays]))
    month_core.append(np.mean([by_day[d].get('asleepCore', 0) for d in mdays]))
    t = np.mean([sum(by_day[d].get(k,0) for k in ['asleepDeep','asleepREM','asleepCore']) for d in mdays])
    month_total.append(t)

mx = np.arange(len(month_labels))
b0 = np.zeros(len(month_labels))
for k, color_k in [('asleepDeep', '#2D6A9F'), ('asleepREM', '#6A5ACD'), ('asleepCore', '#5BA4CF')]:
    vals = [np.mean([by_day[d].get(k, 0) for d in months[tuple(int(p) for p in lbl.split('/'))]['days']
                     if sum(by_day[d].values()) >= 1])
            for lbl in month_labels]
    ax4.bar(mx, vals, bottom=b0, color=color_k, alpha=0.85)
    b0 += np.array(vals)

ax4.set_xticks(mx)
ax4.set_xticklabels(month_labels, rotation=30, color=TEXT_C, fontsize=9)
ax4.set_ylabel('小时')
ax4.axhline(7, color='#FF6B6B', linewidth=1.2, linestyle='--', alpha=0.8)
ax4.set_ylim(0, 10)

for i, (t, lbl) in enumerate(zip(month_total, month_labels)):
    reach = sum(1 for d in months[tuple(int(p) for p in lbl.split('/'))]['days']
                if sum(by_day[d].get(k,0) for k in ['asleepDeep','asleepREM','asleepCore']) >= 7) 
    total_n = len([d for d in months[tuple(int(p) for p in lbl.split('/'))]['days']
                   if sum(by_day[d].values()) >= 1])
    pct = reach/total_n*100 if total_n else 0
    ax4.text(i, t + 0.1, f'{pct:.0f}%', ha='center', va='bottom',
             color='#FFD700', fontsize=8)

# ────────────────────────────────────────────────────────────
# 图5：月度血氧箱线图
# ────────────────────────────────────────────────────────────
style_ax(ax5, '月度睡眠期血氧（SpO₂）')
box_data, box_labels = [], []
for (yr, mo), info in months.items():
    if info['spo2']:
        box_data.append(info['spo2'])
        box_labels.append(f"{yr}/{mo:02d}")

if box_data:
    bp = ax5.boxplot(box_data, patch_artist=True, labels=box_labels,
                     medianprops={'color': '#FFD700', 'linewidth': 2},
                     boxprops={'facecolor': '#1E4D7B', 'alpha': 0.8, 'edgecolor': '#4FC3F7'},
                     whiskerprops={'color': '#888888'},
                     capprops={'color': '#888888'},
                     flierprops={'marker': 'o', 'color': '#FF8A65', 'markersize': 4, 'alpha': 0.6})
    ax5.axhline(95, color='#FF6B6B', linewidth=1, linestyle='--', alpha=0.7)
    ax5.set_ylim(88, 101)
    ax5.set_ylabel('SpO₂ (%)')
    ax5.tick_params(axis='x', rotation=30)
    for label in ax5.get_xticklabels():
        label.set_color(TEXT_C)

# ── 底部统计摘要 ──────────────────────────────────────────────
avg_deep = np.mean([by_day[d].get('asleepDeep', 0) for d in days])
avg_rem  = np.mean([by_day[d].get('asleepREM', 0) for d in days])
avg_core = np.mean([by_day[d].get('asleepCore', 0) for d in days])
avg_awake = np.mean([by_day[d].get('awake', 0) for d in days])
reach7 = sum(1 for v in total_sleep if v >= 7)
spo2_vals = [v for vl in spo2_by_day.values() for v in vl]
spo2_low95 = sum(1 for v in spo2_vals if v < 95)

summary = (
    f"均值  总睡眠 {avg_total:.1f}h  |  深睡眠 {avg_deep:.1f}h ({avg_deep/avg_total*100:.0f}%)  "
    f"|  REM {avg_rem:.1f}h ({avg_rem/avg_total*100:.0f}%)  |  浅睡眠 {avg_core:.1f}h  "
    f"|  达标率(≥7h) {reach7}/{len(days)} ({reach7/len(days)*100:.0f}%)"
    + (f"  |  血氧均值 {np.mean(spo2_vals):.1f}%  低于95%次数 {spo2_low95}" if spo2_vals else "")
)
fig.text(0.5, 0.015, summary, ha='center', va='bottom',
         color='#AAAAAA', fontsize=9)

plt.savefig(OUT_PATH, dpi=150, bbox_inches='tight', facecolor=BG)
print(f"\n图表已保存: {OUT_PATH}")

# ── 终端摘要 ──────────────────────────────────────────────────
print("\n════════ 总体统计 ════════")
print(f"分析天数: {len(days)} 天 ({days[0]} ~ {days[-1]})")
print(f"平均睡眠: {avg_total:.2f}h / 夜")
print(f"  深睡眠: {avg_deep:.2f}h ({avg_deep/avg_total*100:.1f}%)")
print(f"  REM:    {avg_rem:.2f}h ({avg_rem/avg_total*100:.1f}%)")
print(f"  浅睡眠: {avg_core:.2f}h ({avg_core/avg_total*100:.1f}%)")
print(f"  清醒:   {avg_awake:.2f}h")
print(f"≥7h达标: {reach7}/{len(days)} 天 ({reach7/len(days)*100:.1f}%)")
if spo2_vals:
    print(f"血氧均值: {np.mean(spo2_vals):.1f}%  最低: {min(spo2_vals):.1f}%")
    print(f"低于95%: {spo2_low95} 次")

print("\n════════ 月度汇总 ════════")
print(f"{'月份':<10} {'天数':>6} {'均睡眠':>8} {'深睡%':>8} {'REM%':>7} {'≥7h%':>7} {'血氧均':>8}")
print("─" * 60)
for (yr, mo), info in months.items():
    mdays = [d for d in info['days'] if sum(by_day[d].values()) >= 1]
    if not mdays:
        continue
    mt = np.mean([sum(by_day[d].get(k,0) for k in ['asleepDeep','asleepREM','asleepCore']) for d in mdays])
    md = np.mean([by_day[d].get('asleepDeep', 0) for d in mdays])
    mr = np.mean([by_day[d].get('asleepREM', 0) for d in mdays])
    r7 = sum(1 for d in mdays if sum(by_day[d].get(k,0) for k in ['asleepDeep','asleepREM','asleepCore']) >= 7)
    sp = f"{np.mean(info['spo2']):.1f}%" if info['spo2'] else 'N/A'
    print(f"{yr}/{mo:02d}     {len(mdays):>5}    {mt:>6.2f}h  {md/mt*100:>6.1f}%  {mr/mt*100:>5.1f}%  {r7/len(mdays)*100:>5.1f}%    {sp:>6}")
