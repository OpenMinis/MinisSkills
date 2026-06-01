#!/usr/bin/env python3
import json, math, argparse
from datetime import datetime, timedelta, date
from collections import defaultdict
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('--sleep', default='/var/minis/workspace/sleep_raw.json')
parser.add_argument('--spo2',  default='/var/minis/workspace/spo2_raw.json')
parser.add_argument('--out',   default='/var/minis/workspace/sleep_report_7d.json')
args = parser.parse_args()

sleep_data=json.load(open(args.sleep))
spo2_data=json.load(open(args.spo2))
samples=sleep_data.get('samples', sleep_data)
spo2_samples=spo2_data.get('samples', spo2_data)
STAGE_MAP={'asleepDeep':'Deep','asleepREM':'REM','asleepCore':'Core','awake':'Awake','inBed':None}

def parse_dt(s): return datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S')
def sleep_date(dt): return (dt-timedelta(days=1)).date() if dt.hour<14 else dt.date()
def hm_float(dt): return dt.hour+dt.minute/60

def fmt_h(v):
    if v is None or math.isnan(v): return '—'
    h=int(v); m=int(round((v-h)*60))
    if m==60: h+=1; m=0
    return f'{h%24:02d}:{m:02d}'

nights=defaultdict(lambda: defaultdict(float)); bed={}; wake={}; segments=defaultdict(list)
for s in samples:
    raw=s.get('stage') or s.get('value') or s.get('sleepStage','')
    stage=STAGE_MAP.get(raw)
    st=s.get('startDate') or s.get('start'); en=s.get('endDate') or s.get('end')
    if not st or not en: continue
    a=parse_dt(st); b=parse_dt(en); n=sleep_date(a); dur=(b-a).total_seconds()/3600
    if stage: nights[n][stage]+=dur; segments[n].append({'stage':stage,'start':a.isoformat(),'end':b.isoformat(),'hours':dur})
    af=hm_float(a); af=af+24 if af<14 else af
    bf=hm_float(b); bf=bf+24 if bf<14 else bf
    bed[n]=min(bed.get(n,af),af); wake[n]=max(wake.get(n,bf),bf)

spo2=defaultdict(list)
for s in spo2_samples:
    dt=parse_dt(s['date']); val=s.get('percentage') or s.get('value')
    if isinstance(val,(int,float)) and val>50: spo2[sleep_date(dt)].append(float(val))

valid=sorted([d for d in nights if sum(nights[d].values())>1])[-7:]
rows=[]
for d in valid:
    st=nights[d]; total=sum(st.values()); sp=spo2.get(d,[])
    rows.append({
        'date':str(d),'label':d.strftime('%m/%d'),'weekday':'一二三四五六日'[d.weekday()],
        'total':round(total,2),'deep':round(st.get('Deep',0),2),'rem':round(st.get('REM',0),2),'core':round(st.get('Core',0),2),'awake':round(st.get('Awake',0),2),
        'deep_pct':round(st.get('Deep',0)/total*100,1) if total else 0,
        'rem_pct':round(st.get('REM',0)/total*100,1) if total else 0,
        'spo2_mean':round(float(np.mean(sp)),1) if sp else None,
        'spo2_min':round(float(min(sp)),1) if sp else None,
        'bed':fmt_h(bed.get(d,0)%24) if d in bed else '—',
        'wake':fmt_h(wake.get(d,0)%24) if d in wake else '—'
    })
summary={
    'days':len(rows),
    'avg_total':round(float(np.mean([r['total'] for r in rows])),1) if rows else 0,
    'avg_deep':round(float(np.mean([r['deep'] for r in rows])),1) if rows else 0,
    'avg_rem':round(float(np.mean([r['rem'] for r in rows])),1) if rows else 0,
    'avg_spo2':round(float(np.mean([r['spo2_mean'] for r in rows if r['spo2_mean']])),1) if any(r['spo2_mean'] for r in rows) else None,
    'min_spo2':round(float(min([r['spo2_min'] for r in rows if r['spo2_min']])),1) if any(r['spo2_min'] for r in rows) else None,
    'good_days':sum(1 for r in rows if r['total']>=7),
    'range': (rows[0]['label']+'–'+rows[-1]['label']) if rows else ''
}
json.dump({'summary':summary,'rows':rows}, open(args.out,'w'), ensure_ascii=False, indent=2)
print(args.out)
