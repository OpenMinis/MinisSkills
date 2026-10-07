#!/usr/bin/env python3
"""render-clarification --json must always emit valid `user_ask` questions."""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPTS = ["把文章存到备忘录", "每天早上把天气存到备忘录", "做个快捷指令", "Save a web page to Drafts as Markdown"]
errors = []
for prompt in PROMPTS:
    r = subprocess.run([sys.executable, str(HERE / "render_clarification.py"), "--json", prompt], capture_output=True, text=True)
    if r.returncode:
        errors.append(f"{prompt!r}: exit {r.returncode}: {r.stderr[-200:]}")
        continue
    data = json.loads(r.stdout)
    for batch in data["batches"]:
        if not 1 <= len(batch) <= 4:
            errors.append(f"{prompt!r}: batch size {len(batch)} not in 1..4")
        for q in batch:
            opts = q["options"]
            if q.get("type") != "options": errors.append(f"{prompt!r}: type {q.get('type')}")
            if not 2 <= len(opts) <= 4: errors.append(f"{prompt!r}: {q['question']!r} has {len(opts)} options")
            if len(q["header"]) > 12: errors.append(f"{prompt!r}: header too long: {q['header']!r}")
            if any(len(o["label"]) > 12 for o in opts): errors.append(f"{prompt!r}: label too long in {q['question']!r}")
            if q.get("default") != "0": errors.append(f"{prompt!r}: default must point at the recommended first option")
            if len({o["label"] for o in opts}) != len(opts): errors.append(f"{prompt!r}: duplicate labels")
print("FAIL" if errors else "ok", *errors, sep="\n  " if errors else " ")
sys.exit(1 if errors else 0)
