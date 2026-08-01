import sys
import json

inp, outp = sys.argv[1], sys.argv[2]
with open(inp, 'r', encoding='utf-8') as f:
    data = json.load(f)

t = data.get('tweet', {}) or {}
author = t.get('author', {}) or {}
lines = []
lines.append(f"Author: {author.get('name','unknown')} (@{author.get('screen_name','')})")
text = t.get('text') or '(no text)'
lines.append(f"Text: {text}")
lines.append(f"Created: {t.get('creation_date','')}")
lines.append(f"Sensitive: {t.get('possibly_sensitive', False)}")
lines.append('Media:')

media_all = ((t.get('media') or {}).get('all') or [])
for m in media_all:
    mtype = m.get('type')
    if mtype == 'photo':
        url = m.get('url')
        if url:
            lines.append(f"  photo {url}")
    elif mtype in ('video', 'gif'):
        url = m.get('url')
        variants = m.get('variants') or []
        if variants:
            try:
                url = max(variants, key=lambda v: v.get('bitrate') or 0).get('url') or url
            except Exception:
                pass
        if url:
            lines.append(f"  {mtype} {url}")
        thumb = m.get('thumbnail_url')
        if thumb:
            lines.append(f"  thumb {thumb}")

with open(outp, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
