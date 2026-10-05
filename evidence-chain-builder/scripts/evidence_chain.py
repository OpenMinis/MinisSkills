#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evidence-chain-builder - grade how well a claim is carried by evidence.

Turns "claim -> evidence" into a scored, auditable chain. Every piece of evidence is
tagged with a source type, whether it can be independently verified, and where it
came from. Output is an evidence score plus an explicit list of what is NOT carried
by verifiable evidence.

The boundary that matters: this tool does NOT decide whether a claim is true. It
grades the evidence and nothing else. A claim resting only on internal notes or
bare assertions is reported as not established, because that is the honest reading.
See references/evidence-types.md for the type taxonomy and its rationale.

Stdlib only, no network, writes nothing to disk unless you redirect the output.

Usage:
  evidence_chain.py --claim "CLAIM" --evidences "E1||E2||E3"
  evidence_chain.py --from claim.json [--json]
  evidence_chain.py --claim "..." --evidences "..." --threshold 60

Evidence strings may carry a source marker, "@type:source", e.g.
  "2025 audit report@official:QA dept"

Exit codes: 0 = chain scored (whatever the verdict); 2 = usage or input error.
Add --fail-below-threshold when you want a non-zero exit to act as a gate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

TYPES = ("official", "paper", "data", "internal", "assertion")
VERIFIABLE = {
    "official": True,
    "paper": True,
    "data": True,
    "internal": False,
    "assertion": False,
}
LABEL = {
    "official": "official",
    "paper": "paper",
    "data": "data",
    "internal": "internal (not independently verifiable)",
    "assertion": "assertion (not independently verifiable)",
}
MARKER = re.compile(r"@(\w+)(?::(.*))?$", re.S)


def parse_evidence(raw: str) -> dict:
    """Split 'text@type:source' into its parts. An absent marker means 'assertion'."""
    text, src_type, source = raw.strip(), "assertion", ""
    m = MARKER.search(text)
    if m and m.group(1).lower() in TYPES:
        src_type = m.group(1).lower()
        source = (m.group(2) or "").strip()
        text = text[: m.start()].strip()
    return {"text": text, "type": src_type, "source": source}


def collect(evidences) -> list:
    out = []
    for item in evidences:
        for piece in str(item).split("||"):
            if piece.strip():
                out.append(parse_evidence(piece))
    return out


def score_chain(evidence: list) -> tuple:
    """Return (score, verifiable_count, unverifiable_types)."""
    if not evidence:
        return 0, 0, []
    strong = [e for e in evidence if VERIFIABLE.get(e["type"])]
    pct = round(100 * len(strong) / len(evidence))
    weak = sorted({e["type"] for e in evidence if not VERIFIABLE.get(e["type"])})
    return pct, len(strong), weak


def render(claim, evidence, pct, strong_n, weak, threshold, source_note) -> str:
    total = len(evidence)
    lines = ["# Evidence chain", ""]
    if source_note:
        lines += [f"> Subject: {source_note}", ""]
    lines += ["## Claim", "", claim, "", "## Evidence score", ""]
    if not total:
        lines += [
            "**No evidence was supplied.** Nothing here is established. Supply at "
            "least one official, paper or data source before drawing a conclusion.",
            "",
        ]
    else:
        lines += [
            f"**{pct}/100** - {strong_n} of {total} items can be independently verified"
            f" (threshold {threshold}).",
            "",
        ]

    if evidence:
        lines += ["## Evidence", ""]
        for i, e in enumerate(evidence, 1):
            origin = e["source"] or "no source stated"
            lines.append(f"{i}. [{LABEL.get(e['type'], e['type'])}] {e['text']}")
            lines.append(f"   - source: {origin}")
        lines.append("")

    lines += ["## Verdict", ""]
    if not total:
        lines.append(
            "**Do not treat this claim as a conclusion.** There is no evidence chain "
            "to stand on."
        )
    elif pct >= threshold:
        lines.append(
            f"**{pct}/100 of the evidence can be independently verified**, which meets "
            f"the threshold of {threshold}. The claim is **supported to that threshold**, "
            f"and the original sources still need a human check before anyone relies on it."
        )
    else:
        lines.append(
            f"**Do not treat this claim as a conclusion.** Only {pct}/100 of the "
            f"evidence can be independently verified"
            + (f", and it leans on: {', '.join(weak)}." if weak else ".")
        )
        lines.append(
            "Replace the unverifiable items with official, paper or data sources, then "
            "re-run."
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Grade a claim's evidence chain. Does not judge truth."
    )
    ap.add_argument("--claim", help="the claim to test")
    ap.add_argument(
        "--evidences",
        nargs="+",
        help="evidence items; one per argument or separated by '||'; "
        "optionally suffixed '@type:source'",
    )
    ap.add_argument(
        "--from",
        dest="from_file",
        help="JSON file: {claim, evidences:[{text, source, type}]}",
    )
    ap.add_argument(
        "--threshold",
        type=int,
        default=50,
        help="score needed to count as supported (default 50)",
    )
    ap.add_argument("--subject", default="", help="what the claim is about, for the header")
    ap.add_argument(
        "--fail-below-threshold",
        action="store_true",
        help="exit 1 instead of 0 when the claim is not supported (opt-in gate)",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()

    if a.from_file:
        try:
            with open(a.from_file, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError) as exc:
            print(f"[!] cannot read {a.from_file}: {exc}", file=sys.stderr)
            return 2
        claim = str(d.get("claim", ""))
        raw = []
        for e in d.get("evidences", []) or []:
            if isinstance(e, str):
                raw.append(e)
                continue
            t = str(e.get("type", "assertion")).lower()
            t = t if t in TYPES else "assertion"
            src = str(e.get("source", "") or "")
            raw.append(f"{e.get('text', '')}@{t}:{src}" if src else f"{e.get('text', '')}@{t}")
        evidences = raw
    elif a.claim is not None:
        claim = a.claim
        evidences = a.evidences or []
    else:
        ap.print_usage(sys.stderr)
        print("[!] supply --claim or --from", file=sys.stderr)
        return 2

    if not claim.strip():
        print("[!] claim is empty", file=sys.stderr)
        return 2

    evidence = collect(evidences)
    pct, strong_n, weak = score_chain(evidence)

    if a.json:
        print(
            json.dumps(
                {
                    "claim": claim,
                    "score": pct,
                    "threshold": a.threshold,
                    "supported": bool(evidence) and pct >= a.threshold,
                    "evidence_count": len(evidence),
                    "verifiable_count": strong_n,
                    "unverifiable_types": weak,
                    "evidence": evidence,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(render(claim, evidence, pct, strong_n, weak, a.threshold, a.subject))

    if a.fail_below_threshold and not (evidence and pct >= a.threshold):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
