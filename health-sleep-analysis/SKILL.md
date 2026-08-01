---
name: health-sleep-analysis
description: Analyze sleep health data from Apple HealthKit, including sleep stages (Deep/REM/Core/Awake), blood oxygen saturation (SpO2) during sleep, sleep duration trends, bedtime patterns, resting heart rate, and HRV. Use this skill whenever the user asks about sleep quality, sleep analysis, blood oxygen during sleep, sleep stages breakdown, sleep trends over time, heart rate, HRV, or any health data analysis involving sleep or cardiac health. Triggers on: "sleep analysis", "blood oxygen", "sleep quality", "deep sleep", "REM sleep", "resting heart rate", "HRV", "heart health", "sleep analysis", "sleep quality", "blood oxygen", "deep sleep", "resting heart rate", "heart rate variability" and similar in any language.
---

# Sleep Health Analysis Skill

Fetch sleep, SpO2, heart rate, and HRV data from Apple HealthKit, analyze it, and produce visual reports.

## Language Rules (IMPORTANT)

> **Detect the language of the user's message and apply it consistently throughout the entire response:**
>
> - **Written analysis, conclusions, health advice** -> user's language
> - **Chart/image text labels, titles, axes, legend, insight cards, footer** -> user's language
> - **Code, script internals, variable names** -> English (always)
> - **When rendering SVG charts**: pass a `--lang` argument to the rendering scripts; the scripts will localize all on-chart text automatically
>
> Supported `--lang` values: `zh` (Chinese, default), `en` (English), `ja` (Japanese)
> If the user writes in another language, fall back to `en` for chart text and reply in their language.

---

## Pre-built Scripts (call directly, no rewriting needed)

| Script | Purpose |
|---|---|
| `sleep_report_data.py` | Extract 7-day report JSON from raw HealthKit data |
| `sleep_report_librsvg.py` | Render 7-day weekly report card -> SVG + PNG via `rsvg-convert` |
| `sleep_month_trend_librsvg.py` | Render 30-day monthly trend -> SVG + PNG via `rsvg-convert` |
| `sleep_halfyear.py` | Long-term trend (30+ days), matplotlib charts |
| `cardiac_analysis.py` | Cardiac health: RHR, HRV, SpO2, max HR |

---

## Quick Start

### Step 1 - Install dependencies

```bash
apk add rsvg-convert font-noto-cjk -q
python3 -c "import matplotlib, numpy" 2>/dev/null || apk add py3-matplotlib py3-numpy -q
```

### Step 2 - Fetch data (write to /tmp to avoid workspace sync delay)

```bash
# 7-day weekly report
apple-healthkit sleep --days 8 --compact -q > /tmp/sleep_raw.json
apple-healthkit blood-oxygen --days 8 --limit 2000 --compact -q > /tmp/spo2_raw.json

# 30-day monthly trend
apple-healthkit sleep --days 31 --compact -q > /tmp/sleep_raw.json
apple-healthkit blood-oxygen --days 31 --limit 5000 --compact -q > /tmp/spo2_raw.json
```

**Important:** Always write raw data to `/tmp/` first, not `/var/minis/workspace/`. The workspace directory has an iSH to iOS sync delay that causes stale reads. Copy to the workspace only after scripts finish.

### Step 3 - Run the appropriate script

```bash
# ── 7-day weekly report card ──────────────────────────────────
python3 /var/minis/skills/health-sleep-analysis/sleep_report_data.py \
    --sleep /tmp/sleep_raw.json --spo2 /tmp/spo2_raw.json \
    --out /tmp/sleep_report_7d.json

python3 /var/minis/skills/health-sleep-analysis/sleep_report_librsvg.py \
    --data /tmp/sleep_report_7d.json \
    --out-prefix /tmp/sleep_report_7d \
    --lang zh                          # zh | en | ja

# ── 30-day monthly trend ──────────────────────────────────────
python3 /var/minis/skills/health-sleep-analysis/sleep_month_trend_librsvg.py \
    --days 30 \
    --sleep /tmp/sleep_raw.json --spo2 /tmp/spo2_raw.json \
    --out-prefix /tmp/sleep_month_trend \
    --lang zh                          # zh | en | ja

# ── Half-year trend (26 weeks, weekly aggregation) ────────────
apple-healthkit sleep --days 186 --compact -q > /tmp/sleep_raw.json
apple-healthkit blood-oxygen --days 186 --limit 10000 --compact -q > /tmp/spo2_raw.json
python3 /var/minis/skills/health-sleep-analysis/sleep_longterm_librsvg.py \
    --period halfyear \
    --sleep /tmp/sleep_raw.json --spo2 /tmp/spo2_raw.json \
    --out-prefix /tmp/sleep_halfyear \
    --lang zh                          # zh | en | ja

# ── Full-year trend (12 months, monthly aggregation) ──────────
apple-healthkit sleep --days 366 --compact -q > /tmp/sleep_raw.json
apple-healthkit blood-oxygen --days 366 --limit 10000 --compact -q > /tmp/spo2_raw.json
python3 /var/minis/skills/health-sleep-analysis/sleep_longterm_librsvg.py \
    --period year \
    --sleep /tmp/sleep_raw.json --spo2 /tmp/spo2_raw.json \
    --out-prefix /tmp/sleep_year \
    --lang zh

# ── Long-term trend (matplotlib, 30+ days) ───────────────────
DAYS=185
cd /var/minis/workspace
apple-healthkit sleep --days $((DAYS+1)) --compact -q > sleep_raw.json
apple-healthkit blood-oxygen --days $((DAYS+1)) --limit 10000 --compact -q > spo2_raw.json
python3 /var/minis/skills/health-sleep-analysis/sleep_halfyear.py
# Output: sleep_halfyear.png (current directory)

# ── Cardiac health ────────────────────────────────────────────
apple-healthkit heart-rate --days 30 --limit 5000 --compact -q > /tmp/hr_raw.json
apple-healthkit hrv --days 30 --limit 500 --compact -q > /tmp/hrv_raw.json
python3 /var/minis/skills/health-sleep-analysis/cardiac_analysis.py
```

### Step 4 - Copy output and display

```bash
cp /tmp/sleep_report_7d.png /var/minis/workspace/sleep_report_7d.png
cp /tmp/sleep_month_trend.png /var/minis/workspace/sleep_month_trend.png
```

Display in chat with Markdown inline images. Follow up with a written analysis in the user's language.

---

## Localization Reference

When rendering SVG charts, scripts accept `--lang <code>`. The following strings must be translated for each language:

| Key | zh | en | ja |
|---|---|---|---|
| report_title_7d | Weekly Sleep Report | Weekly Sleep Report | Weekly Sleep Report |
| report_title_30d | Monthly Sleep Trend | Monthly Sleep Trend | Monthly Sleep Trend |
| subtitle_suffix | nights recorded | nights recorded | nights recorded |
| avg_sleep | Avg Sleep | Avg Sleep | Avg Sleep |
| good_days | Goal Days | Goal Days | Goal Days |
| deep_avg | Avg Deep | Avg Deep | Avg Deep |
| min_spo2 | Min SpO2 | Min SpO2 | Min SpO2 |
| stage_trend | Sleep Stage Trend | Sleep Stage Trend | Sleep Stage Trend |
| key_insights | Key Insights | Key Insights | Key Insights |
| daily_detail | Daily Detail | Daily Detail | Daily Detail |
| deep | Deep | Deep | Deep |
| core | Core | Core | Core |
| awake | Awake | Awake | Awake |
| bedtime | Bedtime | Bedtime | Bedtime |
| min_o2 | Min O2 | Min O2 | Min O2 |
| spo2_trend_title | Nightly Min SpO2 | Nightly Min SpO2 | Nightly Min SpO2 |
| weekly_summary | Weekly Summary | Weekly Summary | Weekly Summary |
| monthly_conclusion | Monthly Summary | Monthly Summary | Monthly Summary |
| insight_duration | Issue: Sleep Too Short | Issue: Sleep Too Short | Issue: Sleep Too Short |
| insight_bedtime | Late Bedtime | Late Bedtime | Late Bedtime |
| insight_spo2 | SpO2 avg OK, low dips noted | SpO2 avg OK, low dips noted | SpO2 avg OK, low dips noted |
| recommend_7h | Goal 7h | Goal 7h | Goal 7h |
| data_source | Source: Apple HealthKit · For reference only | Source: Apple HealthKit · For reference only | Source: Apple HealthKit · For reference only |
| generated | Generated | Generated | Generated |
| sleep_intelligence | Sleep Intelligence | Sleep Intelligence | Sleep Intelligence |

---

## Script Argument Reference

### sleep_report_data.py

```
--sleep   path to sleep_raw.json   (default: /var/minis/workspace/sleep_raw.json)
--spo2    path to spo2_raw.json    (default: /var/minis/workspace/spo2_raw.json)
--out     output JSON path         (default: /var/minis/workspace/sleep_report_7d.json)
```

### sleep_report_librsvg.py

```
--data        input JSON from sleep_report_data.py
--out-prefix  SVG/PNG output prefix   (default: /var/minis/workspace/sleep_report_7d_librsvg)
--lang        zh | en | ja            (default: zh)
--width       canvas width px         (default: 1280)
--height      canvas height px        (default: 1760)
```

### sleep_month_trend_librsvg.py

```
--days        number of nights to include  (default: 30)
--sleep       path to sleep_raw.json
--spo2        path to spo2_raw.json
--out-prefix  SVG/PNG output prefix        (default: /var/minis/workspace/sleep_month_trend)
--lang        zh | en | ja                 (default: zh)
```

---

## Data Processing

### Night attribution rule

Records between 00:00 and 13:59 belong to the **previous calendar day** (same sleep session):

```python
def sleep_date(dt):
    return (dt - timedelta(days=1)).date() if dt.hour < 14 else dt.date()
```

### Sleep stage mapping

| HealthKit value | Stage |
|---|---|
| `asleepDeep` | Deep |
| `asleepREM` | REM |
| `asleepCore` | Core (light) |
| `awake` | Awake |
| `inBed` | In-bed (excluded) |

### HealthKit JSON field names

Raw samples use `start` / `end`, not `startDate` / `endDate`. Always check both:

```python
ss = s.get('startDate') or s.get('start')
ee = s.get('endDate')   or s.get('end')
```

### Workspace sync delay

Writing large files directly to `/var/minis/workspace/` can result in iSH reading a stale cached version. Always:

1. Write data and outputs to `/tmp/`
2. Run scripts with `/tmp/` paths
3. `cp` final PNGs to `/var/minis/workspace/` for display

---

## Health Standards

### Sleep duration

| Range | Rating |
|---|---|
| ≥ 7h | ✅ Sufficient |
| 6-7h | ⚠️ Slightly short |
| < 6h | ❌ Insufficient (adults need 7-9h) |

### Sleep stages

| Stage | Healthy % | Function |
|---|---|---|
| Deep | ≥ 13% | Physical recovery, immunity, memory |
| REM | 20-25% | Emotion regulation, cognition |
| Core | 45-55% | Transitional |

### SpO2

| Range | Rating |
|---|---|
| ≥ 95% | ✅ Normal |
| 90-94% | ⚠️ Low, monitor |
| < 90% | ❌ Dangerous, seek medical advice |

> Frequent drops below 95% (>20% of readings) or any reading below 90% warrants evaluation for **obstructive sleep apnea (OSA)**, especially with snoring, daytime sleepiness, or morning headaches.

### Resting Heart Rate (RHR)

| Range | Rating |
|---|---|
| < 40 bpm | ❌ Too low, consult doctor |
| 40-60 bpm | ✅ Excellent (athlete level) |
| 60-80 bpm | ✅ Normal |
| 80-100 bpm | ⚠️ Elevated |
| > 100 bpm | ❌ Tachycardia, consult doctor |

Estimate RHR from raw heart rate data (lowest 25% of daily readings):

```python
vals = sorted(by_day[date])
rhr = mean(vals[:max(1, len(vals)//4)])
```

### HRV (SDNN)

| Range | Rating |
|---|---|
| ≥ 50 ms | ✅ Good |
| 30-50 ms | ⚠️ Fair |
| < 30 ms | ❌ Low autonomic function |

---

## Common Issues

**Q: Only a few SpO2 readings?**
A: Add `--limit`, use 2000 for short-term, 10000 for long-term.

**Q: Chinese/Japanese characters show as boxes?**
A: Run `apk add font-noto-cjk` first.

**Q: Missing data for some nights?**
A: Apple Watch likely not worn; nights with < 1h total are auto-filtered.

**Q: Chart still shows stale data after re-running?**
A: Write outputs to `/tmp/` and use `--sleep /tmp/... --spo2 /tmp/...` arguments. Copy PNG to the workspace only for display.

**Q: 30-day chart shows only 6-7 bars?**
A: The workspace JSON is stale. Fetch fresh data to `/tmp/` and pass `/tmp/` paths explicitly to the script.
