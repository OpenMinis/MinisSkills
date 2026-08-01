# Example — multi-day ("predict my whole week")

**User:** "Can you make a prediction for the whole week please?" (Earlier in the conversation: sleeps 21:30–05:30, good quality, varies ~30 min.)

**Consistency gate:** already answered — varies ~30 min → consistent. So one call:

```bash
python scripts/whenpeak_predict.py --wake 05:30 --sleep 21:30 --quality good --days 7
```

The response has `method: "flat_projection"` and a `forecast` array of 7 days, each with `dps`, peaks, and dip.

**Ideal answer:**

> Assuming you hold your usual 9:30pm–5:30am schedule, your week projects as very stable — no standout best or worst day, because this projection repeats your baseline forward.
>
> Every day follows the same rhythm: primary peak **7–10am** (highest-stakes meetings, deep work, decisions), a dip around **noon–1pm** (email, admin), and a second wind around **2–3pm** (follow-ups, reviews, analytical work).
>
> If you're placing several important things next week: first choice 8:30–9:30am, second 9:30–10:30am, backup 2–3pm, and keep 12:30–2pm light.
>
> Honestly: this is a low-confidence projection — it repeats one night forward rather than forecasting your actual future sleep, so treat it as your baseline pattern, not a prediction of each specific day.

**User:** "Can you create a visual chart of my week?"

**Ideal answer (no chart — this is deliberate):**

> Charts here work best for a single day's performance curve — happy to draw today's or tomorrow's. Which day matters most? I'll draw that one.

If they pick a day, run the single-day call for that day's expected schedule and chart it per `example_single_day.md`.

**What makes this right:** one API call (never a per-day loop), best/worst first, honest about what a flat projection is, and the weekly visual is redirected to the product rather than rendered as a bar chart of scores — timing is the product, not the number.
