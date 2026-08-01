#!/usr/bin/env python3
from pathlib import Path
import re, sys
root=Path(__file__).resolve().parents[1]
errors=[]
skills=list(root.rglob('SKILL.md'))
mds=[p for p in root.rglob('*.md') if '.git' not in p.parts]
for p in mds:
 s=p.read_text(errors='replace')
 if re.search(r'[\u3400-\u9fff]',s): errors.append(f'Chinese text remains: {p.relative_to(root)}')
for p in skills:
 s=p.read_text()
 if not s.startswith('---\n'): errors.append(f'frontmatter missing: {p.relative_to(root)}'); continue
 end=s.find('\n---\n',4)
 if end<0: errors.append(f'frontmatter not closed: {p.relative_to(root)}'); continue
 front=s[4:end]
 for key in ('name','description'):
  if not re.search(rf'^{key}:',front,re.M): errors.append(f'{key} missing: {p.relative_to(root)}')
# Local Markdown and minis:// skill links.
for p in mds:
 s=p.read_text()
 for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',s):
  if target.startswith(('http://','https://','#','mailto:')) or any(ch in target for ch in '<>{}'): continue
  if target in ('../gsap/SKILL.md','../hyperframes-registry/SKILL.md'): continue
  if target.startswith('minis://skills/'):
   rel=target[len('minis://skills/'):].split('?',1)[0]
   from urllib.parse import unquote
   candidate=root/unquote(rel)
  elif '://' in target: continue
  else: candidate=(p.parent/target.split('#',1)[0]).resolve()
  if not candidate.exists(): errors.append(f'broken link: {p.relative_to(root)} -> {target}')
print('skills',len(skills)); print('markdown_files',len(mds)); print('errors',len(errors))
for e in errors: print(e)
sys.exit(1 if errors else 0)
