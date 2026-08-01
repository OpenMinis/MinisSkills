# Example — single day ("I have a big meeting tomorrow")

**User:** "I have a big meeting tomorrow, when should I schedule it? I went to sleep at 9:30, woke up at 5:30 and still half-slept until 6am. Good sleep. I exercised yesterday morning. My schedule only varies by ~30 minutes and tonight will be the same."

**Extraction:** sleep_time=21:30, wake_time=05:30 (took the time they actually woke; the half-asleep hour is noise, not WASO), quality=good, exercise=morning. Schedule is consistent and tonight matches → a single-day call with last night's data stands in for tomorrow.

**Call:**
```bash
python scripts/whenpeak_predict.py --wake 05:30 --sleep 21:30 --quality good --exercise morning
```

**API returns** (abridged — full shape in `references/sample_response.json`):
```json
{
  "dps": 90.0,
  "peak_1": {"time": "07:00", "value": 90.0},
  "peak_2": {"time": "14:00", "value": 83.58},
  "dip":    {"time": "12:00", "value": 74.94},
  "chronotype": "Third Bird",
  "confidence": "low",
  "upgrade_prompt": "Connect Apple Health or send me a screenshot of your last 7 nights sleep for a 3x more accurate prediction."
}
```

**Ideal answer:**

> Your strongest window tomorrow is **7:00–10:00am** — if you control the invite, put the meeting at **8:30–9:30**. As an early riser you hold 84+ until about 10:30, so mid-morning is safe too.
>
> Avoid the stretch around **noon–1pm**: that's your projected dip, better kept for email and admin. If the morning is impossible, your second wind lands around **2–3pm** — that's the backup slot.
>
> Based on your sleep and the morning workout, tomorrow projects as a strong day. One honest note: this comes from a single self-reported night, so treat the exact times as a solid estimate rather than a guarantee.

**Then chart it:**
```bash
python scripts/whenpeak_predict.py --wake 05:30 --sleep 21:30 --quality good --exercise morning > /tmp/wp.json
python scripts/whenpeak_chart.py /tmp/wp.json -o performance_curve.png
```
Attach `performance_curve.png`.

**What makes this answer right:** it leads with the window and a concrete slot, uses the score only as "a strong day", maps each part of the day to a job (deep work / admin / backup), and notes the single-night confidence limit once, factually. Note the response does not repeat the API's `upgrade_prompt` marketing text, and the consent disclosure happened before this first call.
