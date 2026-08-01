from pathlib import Path
import re, subprocess
root=Path('/var/minis/workspace/MinisSkills_pr')
files=subprocess.check_output(['git','-C',str(root),'diff','upstream/main...HEAD','--name-only','--','*SKILL.md'],text=True).splitlines()
errors=[]
for rel in files:
 old=subprocess.run(['git','-C',str(root),'show','upstream/main:'+rel],capture_output=True,text=True).stdout
 new=(root/rel).read_text()
 # Only require technical-looking inline spans. Human-language spans were intentionally translated.
 spans=re.findall(r'`([^`\n]+)`',old)
 tech=[x for x in spans if not re.search(r'[\u3400-\u9fff]',x) and re.search(r'[/_.:$<>*]|--|[A-Z]{2,}|\d',x)]
 for x in tech:
  if x not in new: errors.append((rel,x))
print('technical_inline_spans',sum(1 for rel in files for x in re.findall(r'`([^`\n]+)`',subprocess.run(['git','-C',str(root),'show','upstream/main:'+rel],capture_output=True,text=True).stdout) if re.search(r'[/_.:$<>*]|--|[A-Z]{2,}|\d',x)))
print('missing',len(errors))
for rel,x in errors[:100]: print(rel,repr(x))
raise SystemExit(bool(errors))
