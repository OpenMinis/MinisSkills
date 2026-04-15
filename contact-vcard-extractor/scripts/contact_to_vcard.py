#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image
except Exception:
    Image = None

VCARD_ESC = str.maketrans({"\\": "\\\\", ";": "\\;", ",": "\\,", "\n": "\\n", "\r": ""})

PHONE_RE = re.compile(r"(?:(?:\+|00)\d{1,3}[\s\-.]?)?(?:\(?\d{2,4}\)?[\s\-.]?)?\d{3,4}[\s\-.]?\d{4}(?:\s*(?:ext\.?|x|转|分机)\s*\d+)?")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s，。；;,]+", re.I)
LABELS = {
    "name": ["姓名", "名字", "联系人", "name"],
    "org": ["公司", "单位", "机构", "组织", "company", "org", "organization"],
    "title": ["职位", "职务", "岗位", "title", "position"],
    "phone": ["电话", "手机", "手机号", "联系电话", "tel", "phone", "mobile", "cell"],
    "email": ["邮箱", "邮件", "email", "e-mail", "mail"],
    "address": ["地址", "住址", "通讯地址", "addr", "address"],
    "url": ["网站", "网址", "主页", "官网", "website", "url", "web"],
    "note": ["备注", "说明", "note", "memo"],
}


def esc(s):
    return (s or "").strip().translate(VCARD_ESC)


def clean_phone(s):
    s = s.strip().replace("（", "(").replace("）", ")")
    s = re.sub(r"^(电话|手机|手机号|前台|座机|固话|tel|phone|mobile|cell)[:：\s]+", "", s, flags=re.I)
    # vCard TEL must contain the number only; labels like “前台” belong in NOTE or UI, not TEL.
    s = re.sub(r"[（(]\s*(?:前台|手机|座机|固话|办公室|公司|微信|WeChat|wechat)\s*[）)]", "", s, flags=re.I)
    s = re.sub(r"\s*(?:前台|手机|座机|固话|办公室|公司|微信|WeChat|wechat)\s*$", "", s, flags=re.I)
    return s.strip()


def extract_phones(s):
    return [clean_phone(p) for p in PHONE_RE.findall(s or "") if clean_phone(p)]


def split_name(name):
    name = (name or "").strip()
    if not name:
        return "", ""
    if re.search(r"[\u4e00-\u9fff]", name):
        return name[:1], name[1:]
    parts = name.split()
    if len(parts) == 1:
        return "", parts[0]
    return parts[-1], " ".join(parts[:-1])


def label_value(line):
    line = line.strip().strip("|•· ")
    if not line:
        return None, None
    for key, labels in LABELS.items():
        for lab in labels:
            m = re.match(rf"^\s*{re.escape(lab)}\s*[:：=\-]\s*(.+)$", line, re.I)
            if m:
                return key, m.group(1).strip()
    return None, None


def parse_text(text):
    c = {"name":"", "org":"", "title":"", "phones":[], "emails":[], "urls":[], "address":"", "note":""}
    lines = [x.strip() for x in re.split(r"[\n\r]+", text or "") if x.strip()]
    leftovers = []
    for line in lines:
        key, val = label_value(line)
        if key:
            if key == "phone":
                nums = extract_phones(val)
                c["phones"].extend(nums or [clean_phone(val)])
            elif key == "email": c["emails"].append(val)
            elif key == "url": c["urls"].append(val)
            elif key in c: c[key] = val
            continue
        emails = EMAIL_RE.findall(line)
        phones = PHONE_RE.findall(line)
        urls = URL_RE.findall(line)
        for e in emails:
            if e not in c["emails"]: c["emails"].append(e)
        for p in phones:
            p = clean_phone(p)
            if p and p not in c["phones"]: c["phones"].append(p)
        for u in urls:
            if u not in c["urls"]: c["urls"].append(u)
        stripped = EMAIL_RE.sub("", PHONE_RE.sub("", URL_RE.sub("", line))).strip(" ，,;；|-/")
        if stripped:
            leftovers.append(stripped)
    if not c["name"] and leftovers:
        # Prefer short human-looking line, not address/company suffix.
        candidates = [x for x in leftovers if len(x) <= 30 and not re.search(r"公司|集团|有限|地址|路|街|区|市|省", x)]
        c["name"] = candidates[0] if candidates else leftovers[0]
    if not c["org"]:
        for x in leftovers:
            if re.search(r"公司|集团|有限|LLC|Inc\.?|Ltd\.?|Co\.?", x, re.I):
                c["org"] = x; break
    if not c["title"]:
        for x in leftovers:
            if re.search(r"经理|总监|主管|工程师|顾问|负责人|CEO|CTO|Founder|Manager|Director", x, re.I):
                c["title"] = x; break
    if not c["address"]:
        for x in leftovers:
            if re.search(r"地址|路|街|号|楼|室|区|市|省|Address", x, re.I) and x != c["org"]:
                c["address"] = re.sub(r"^地址[:：\s]*", "", x); break
    if not c["note"]:
        used = {c["name"], c["org"], c["title"], c["address"]}
        extra = [x for x in leftovers if x not in used]
        if extra:
            c["note"] = "；".join(extra[:4])
    # de-dupe
    for k in ["phones", "emails", "urls"]:
        seen=[]
        for x in c[k]:
            if x and x not in seen: seen.append(x)
        c[k]=seen
    return c


def vcard(c):
    name = c.get("name") or "未命名联系人"
    family, given = split_name(name)
    out = ["BEGIN:VCARD", "VERSION:3.0"]
    out.append(f"N:{esc(family)};{esc(given)};;;")
    out.append(f"FN:{esc(name)}")
    if c.get("org"): out.append(f"ORG:{esc(c['org'])}")
    if c.get("title"): out.append(f"TITLE:{esc(c['title'])}")
    for p in c.get("phones", []):
        out.append(f"TEL;TYPE=CELL:{esc(p)}")
    for e in c.get("emails", []): out.append(f"EMAIL;TYPE=INTERNET:{esc(e)}")
    for u in c.get("urls", []): out.append(f"URL:{esc(u if u.lower().startswith(('http://','https://')) else 'https://' + u)}")
    if c.get("address"): out.append(f"ADR;TYPE=WORK:;;{esc(c['address'])};;;;")
    if c.get("note"): out.append(f"NOTE:{esc(c['note'])}")
    out.append(f"REV:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    out.append("END:VCARD")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Extract contact fields from text and export vCard")
    ap.add_argument("--text", help="raw text")
    ap.add_argument("--text-file")
    ap.add_argument("--json", action="store_true", help="print parsed contact JSON")
    ap.add_argument("--out", default="/var/minis/workspace/contact.vcf")
    args = ap.parse_args()
    text = args.text or ""
    if args.text_file:
        text += "\n" + Path(args.text_file).read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        text = sys.stdin.read()
    c = parse_text(text)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(vcard(c), encoding="utf-8")
    if args.json:
        print(json.dumps({"contact": c, "vcf": args.out}, ensure_ascii=False, indent=2))
    else:
        print(args.out)

if __name__ == "__main__":
    main()
