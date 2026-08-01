import json
import random
import sys
from collections import Counter
from pathlib import Path
from datetime import datetime

HISTORY_PATH = Path('/var/minis/shared/fucai3d/history.json')


def load_history():
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(history):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8')


def normalize_digits(s):
    parts = str(s).strip().replace(',', ' ').split()
    if len(parts) == 1 and len(parts[0]) == 3 and parts[0].isdigit():
        return ' '.join(list(parts[0]))
    if len(parts) == 3 and all(p.isdigit() and len(p) == 1 for p in parts):
        return ' '.join(parts)
    raise ValueError('开奖号码格式应为 3 位数字，例如: 8 0 2')


def parse_nums(digits):
    d = str(digits).split()
    if len(d) == 3 and all(x.isdigit() for x in d):
        return list(map(int, d))
    return None


def upsert_result(issue, draw_date, digits, fetched_at=None):
    history = load_history()
    fetched_at = fetched_at or datetime.now().isoformat(timespec='seconds')
    entry = {
        'issue': str(issue),
        'draw_date': str(draw_date),
        'digits': normalize_digits(digits),
        'fetched_at': fetched_at,
    }
    for i, old in enumerate(history):
        if old.get('issue') == entry['issue']:
            history[i] = entry
            history.sort(key=lambda x: x.get('issue', ''))
            save_history(history)
            return history, entry, False
    history.append(entry)
    history.sort(key=lambda x: x.get('issue', ''))
    save_history(history)
    return history, entry, True


def recent_features(history, recent_window=30):
    recent = history[-recent_window:]
    exact = {h.get('digits') for h in recent if h.get('digits')}
    sums = set()
    pairs = set()
    for h in recent:
        nums = parse_nums(h.get('digits', ''))
        if nums:
            sums.add(sum(nums))
            pairs.add((nums[0], nums[1]))
            pairs.add((nums[1], nums[2]))
    return recent, exact, sums, pairs


def digit_frequency(history, window=30):
    sample = history[-window:]
    counter = Counter()
    for h in sample:
        nums = parse_nums(h.get('digits', ''))
        if nums:
            counter.update(nums)
    for i in range(10):
        counter[i] += 0
    hot = [n for n, _ in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]
    cold = [n for n, _ in sorted(counter.items(), key=lambda kv: (kv[1], kv[0]))]
    return {
        'window': len(sample),
        'frequency': {str(k): counter[k] for k in range(10)},
        'hot_digits': hot,
        'cold_digits': cold,
    }


def weighted_choice(pool, bias_digits):
    weights = []
    for n in pool:
        if n in bias_digits:
            weights.append(4)
        else:
            weights.append(1)
    return random.choices(pool, weights=weights, k=1)[0]


def generate_candidate(mode, hot_digits, cold_digits):
    pool = list(range(10))
    if mode == 'cold':
        bias = set(cold_digits[:5])
    elif mode == 'hot':
        bias = set(hot_digits[:5])
    elif mode == 'balanced':
        bias = set(cold_digits[:3] + hot_digits[:3])
    else:
        bias = set()
    nums = [weighted_choice(pool, bias) for _ in range(3)]
    return ' '.join(map(str, nums))


def recommend(history, count=5, recent_window=30, mode='balanced'):
    _, recent_exact, recent_sum, recent_pairs = recent_features(history, recent_window=recent_window)
    freq = digit_frequency(history, window=recent_window)
    hot_digits = freq['hot_digits']
    cold_digits = freq['cold_digits']

    picks = []
    seen = set(recent_exact)
    tries = 0
    while len(picks) < count and tries < 5000:
        tries += 1
        cand = generate_candidate(mode, hot_digits, cold_digits)
        if cand in seen:
            continue
        nums = parse_nums(cand)
        s = sum(nums)
        if s in recent_sum:
            continue
        if (nums[0], nums[1]) in recent_pairs or (nums[1], nums[2]) in recent_pairs:
            continue
        seen.add(cand)
        picks.append(cand)

    while len(picks) < count and tries < 10000:
        tries += 1
        cand = ' '.join(str(random.randint(0, 9)) for _ in range(3))
        if cand in seen:
            continue
        seen.add(cand)
        picks.append(cand)
    return picks


def strategy_pack(history, count=5, recent_window=30):
    return {
        'balanced': recommend(history, count=count, recent_window=recent_window, mode='balanced'),
        'cold_favor': recommend(history, count=3, recent_window=recent_window, mode='cold'),
        'hot_mix': recommend(history, count=3, recent_window=recent_window, mode='hot'),
    }


def stats(history, window=30):
    total = len(history)
    latest = history[-1] if history else None
    freq = digit_frequency(history, window=window)
    return {
        'total_records': total,
        'latest': latest,
        'analysis_window': freq['window'],
        'digit_frequency': freq['frequency'],
        'hot_digits_top5': freq['hot_digits'][:5],
        'cold_digits_top5': freq['cold_digits'][:5],
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: update ISSUE DATE DIGITS | recommend [COUNT] [MODE] | stats [WINDOW] | bundle [COUNT]')
        raise SystemExit(1)

    cmd = sys.argv[1]
    if cmd == 'update':
        if len(sys.argv) < 5:
            print('usage: update ISSUE DATE DIGITS')
            raise SystemExit(1)
        history, entry, created = upsert_result(sys.argv[2], sys.argv[3], ' '.join(sys.argv[4:]))
        print(json.dumps({'created': created, 'entry': entry, 'total_records': len(history)}, ensure_ascii=False))
    elif cmd == 'recommend':
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        mode = sys.argv[3] if len(sys.argv) > 3 else 'balanced'
        history = load_history()
        print(json.dumps({'mode': mode, 'recommendations': recommend(history, count=count, mode=mode), 'total_records': len(history)}, ensure_ascii=False))
    elif cmd == 'stats':
        window = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        print(json.dumps(stats(load_history(), window=window), ensure_ascii=False))
    elif cmd == 'bundle':
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        history = load_history()
        print(json.dumps({'stats': stats(history), 'strategies': strategy_pack(history, count=count)}, ensure_ascii=False))
    else:
        print('unknown command')
        raise SystemExit(1)
