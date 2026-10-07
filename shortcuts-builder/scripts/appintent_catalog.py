#!/usr/bin/env python3
"""Search the third-party App Intents catalog and emit Shortcuts action steps.

Catalog: data/thirdparty-appintents.json.gz (198 apps, ~1700 actions, read from each app's own
Metadata.appintents/extract.actionsdata). The catalog says which actions an app EXPOSES, not
whether the user has the app installed.

Subcommands
  search  <words...>            find apps/actions by app name, bundle id, action id, title, description
  show    <bundle> [<action>]   list an app's actions, or one action's parameters (+ enum cases)
  step    <bundle> <action> [--set name=value ...] [--format json|xml]
                                emit one WFWorkflowActions step you can paste into a draft

`step` writes three tiers of parameters:
  verified      text -> WFTextTokenString literal, bool -> true/false
  experimental  written on request, flagged "EXPERIMENTAL" on stderr, not yet confirmed on a device:
                  enum   -> {value: <case id>, title, subtitle}
                  int / number -> plain number
                  url / richtext -> WFTextTokenString literal
                  ANY kind with a variable: --set name=@<OutputUUID>:<OutputName>
                  (or @var:<VariableName>) -> WFTextTokenAttachment  (use this for image / file /
                  entity / array inputs)
  refused       a literal for date, location, entity, file, array ...: no serialization is known,
                so nothing is guessed. Pass a variable instead (see above).
TeamIdentifier 0000000000 is accepted by Shortcuts (verified).
"""
from __future__ import annotations

import argparse
import gzip
import json
import plistlib
import sys
import uuid
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "data" / "thirdparty-appintents.json.gz"
SAFE = ("text", "bool")


def load() -> dict:
    with gzip.open(CATALOG, "rt", encoding="utf-8") as fh:
        return json.load(fh)["apps"]


def find_app(apps: dict, key: str) -> tuple[str, dict]:
    if key in apps:
        return key, apps[key]
    low = key.lower()
    hits = [(b, a) for b, a in apps.items() if low == a["name"].lower()] or \
           [(b, a) for b, a in apps.items() if low in a["name"].lower() or low in b.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise SystemExit(f"no app matches {key!r}; try: search {key}")
    raise SystemExit("ambiguous app, use the bundle id:\n" + "\n".join(f"  {b}  ({a['name']})" for b, a in hits[:15]))


def kind_class(k: str) -> str:
    return k.split(":", 1)[0].split("<", 1)[0]


def usable(action: dict) -> str:
    """How much of an action can be authored with verified serializations."""
    ps = action["p"]
    if all(kind_class(p["k"]) in SAFE for p in ps):
        return "full"
    req = [p for p in ps if not p.get("o") and not p.get("in")]
    if all(kind_class(p["k"]) in SAFE + ("enum",) for p in req):
        return "partial"
    return "editor-only"


def cmd_search(a):
    apps = load()
    words = [w.lower() for w in a.words]
    n = 0
    for b, app in apps.items():
        for aid, act in app["actions"].items():
            hay = " ".join([b, app["name"], aid, act.get("d") or "", act.get("s") or ""]
                           + [p.get("t") or "" for p in act["p"]]
                           + [c["t"] or "" for p in act["p"] if p["k"].startswith("enum:")
                              for c in app.get("enums", {}).get(p["k"][5:], [])]).lower()
            if all(w in hay for w in words):
                n += 1
                if n <= a.limit:
                    print(f"{b}.{aid}  [{app['name']}]  {usable(act)}\n    {act.get('s') or act.get('d') or ''}")
    print(f"-- {n} match(es)" + (f", showing {a.limit}" if n > a.limit else ""))


def cmd_show(a):
    apps = load()
    bundle, app = find_app(apps, a.bundle)
    if not a.action:
        print(f"{app['name']}  ({bundle})  {len(app['actions'])} actions")
        for aid, act in app["actions"].items():
            print(f"  {aid}  [{usable(act)}]  {act.get('s') or act.get('d') or ''}")
        return
    act = app["actions"].get(a.action)
    if not act:
        raise SystemExit(f"action {a.action!r} not in {bundle}; have: {', '.join(app['actions'])}")
    print(f"{bundle}.{a.action}  [{usable(act)}]  component={act['c']}  openApp={bool(act['run'])}")
    print(f"  summary : {act.get('s')}\n  about   : {act.get('d')}\n  output  : {act.get('out')}")
    for p in act["p"]:
        flags = ("optional " if p.get("o") else "required ") + ("input " if p.get("in") else "")
        print(f"  - {p['n']}  ({p.get('t')})  kind={p['k']}  {flags}".rstrip())
        if p["k"].startswith("enum:"):
            for c in app.get("enums", {}).get(p["k"][5:], []):
                print(f"        case {c['id']}  \"{c['t']}\"")


def text_value(s: str) -> dict:
    return {"Value": {"string": s, "attachmentsByRange": {}}, "WFSerializationType": "WFTextTokenString"}


def build_step(app_name: str, bundle: str, aid: str, act: dict, enums: dict, values: dict):
    notes, params = [], {}
    by_name = {p["n"]: p for p in act["p"]}
    for name, val in values.items():
        p = by_name.get(name)
        if not p:
            raise SystemExit(f"unknown parameter {name!r}; valid: {', '.join(by_name)}")
        kc = kind_class(p["k"])
        if val.startswith("@"):
            ref = val[1:]
            if ref.startswith("var:"):
                inner = {"VariableName": ref[4:], "Type": "Variable"}
            else:
                uid, sep, oname = ref.partition(":")
                if not sep:
                    raise SystemExit(f"{name}: use @<OutputUUID>:<OutputName> or @var:<VariableName>")
                inner = {"OutputUUID": uid, "OutputName": oname, "Type": "ActionOutput"}
            params[name] = {"Value": inner, "WFSerializationType": "WFTextTokenAttachment"}
            if kc not in ("text", "bool"):
                notes.append(f"EXPERIMENTAL: variable reference written into {p['k']} parameter '{name}'")
            continue
        if kc in ("int", "number"):
            try:
                params[name] = int(val) if kc == "int" else float(val)
            except ValueError:
                raise SystemExit(f"{name} is {kc}: got {val!r}")
            notes.append(f"EXPERIMENTAL: {kc} parameter '{name}' written as a plain number")
        elif kc in ("url", "richtext"):
            params[name] = text_value(val)
            notes.append(f"EXPERIMENTAL: {kc} parameter '{name}' written as a text literal")
        elif kc == "text":
            params[name] = text_value(val)
        elif kc == "bool":
            if val.lower() not in ("true", "false"):
                raise SystemExit(f"{name} is boolean: use true/false")
            params[name] = val.lower() == "true"
        elif kc == "enum":
            cases = {c["id"]: c["t"] for c in enums.get(p["k"][5:], [])}
            if val not in cases:
                raise SystemExit(f"{name}: {val!r} is not a case id; have {', '.join(cases)}")
            params[name] = {"value": val, "title": {"key": cases[val]}, "subtitle": {"key": cases[val]}}
            notes.append(f"EXPERIMENTAL: enum '{name}' serialization for third-party apps")
        else:
            raise SystemExit(f"{name} has kind {p['k']}: no literal serialization is known. "
                             f"Pass a variable instead: --set {name}=@<OutputUUID>:<OutputName> or @var:<Name>")
    for p in act["p"]:
        if not p.get("o") and not p.get("in") and p["n"] not in params:
            notes.append(f"required parameter '{p['n']}' ({p['k']}) not set: user must fill it in the editor")
    step = {
        "WFWorkflowActionIdentifier": f"{bundle}.{aid}",
        "WFWorkflowActionParameters": {
            "UUID": str(uuid.uuid4()).upper(),
            "AppIntentDescriptor": {
                "TeamIdentifier": "0000000000",
                "BundleIdentifier": bundle,
                "Name": app_name,
                "AppIntentIdentifier": aid,
            },
            **params,
        },
    }
    return step, notes


def cmd_step(a):
    apps = load()
    bundle, app = find_app(apps, a.bundle)
    act = app["actions"].get(a.action)
    if not act:
        raise SystemExit(f"action {a.action!r} not in {bundle}")
    values = {}
    for item in a.set:
        k, sep, v = item.partition("=")
        if not sep:
            raise SystemExit(f"--set expects name=value, got {item!r}")
        values[k] = v
    step, notes = build_step(app["name"], bundle, a.action, act, app.get("enums", {}), values)
    for n in notes:
        print("note:", n, file=sys.stderr)
    if act["run"]:
        print("note: this intent opens the app when run", file=sys.stderr)
    if a.format == "json":
        print(json.dumps(step, ensure_ascii=False, indent=2))
    else:
        print(plistlib.dumps(step, fmt=plistlib.FMT_XML).decode())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("words", nargs="+"); s.add_argument("--limit", type=int, default=25)
    s.set_defaults(fn=cmd_search)
    s = sub.add_parser("show"); s.add_argument("bundle"); s.add_argument("action", nargs="?")
    s.set_defaults(fn=cmd_show)
    s = sub.add_parser("step"); s.add_argument("bundle"); s.add_argument("action")
    s.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    s.add_argument("--format", choices=("xml", "json"), default="xml")
    s.set_defaults(fn=cmd_step)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
