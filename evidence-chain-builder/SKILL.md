---
name: evidence-chain-builder
description: >
  Score a claim against the evidence behind it. Use this skill whenever the user
  wants to know whether something is actually supported — "is that true", "what's
  the source", "that sounds made up", "can you back that up" — or before repeating
  any number, statistic, market size, study result or benchmark that arrived without
  a citation, especially from a model or a summary. It separates the claim from its
  evidence, grades each item by source type, and reports an evidence score plus an
  explicit list of what is *not* backed by independently verifiable sources. Also
  trigger when the user is preparing something that will be published, filed or
  relied on — a report, a filing, compliance material, a post quoting figures — and
  the claims need sources pinned to them first. Trigger on 证据链, 论断验证, 防幻觉,
  信源可信, 有出处吗, 这句话有依据吗, 논거 검증, 근거, 裏付け, 出典.
compatibility: >
  Python 3.8+ on PATH. Standard library only — nothing to install, no network, works
  offline. Writes nothing to disk unless the caller redirects the output.
---

# Evidence Chain Builder

## Overview

`scripts/evidence_chain.py` splits a claim from its evidence and scores how well the
evidence carries it. Every evidence item is tagged with a source type, and the type
decides whether that item counts:

| type | counts as independently verifiable |
|---|---|
| `official` — a primary document, filing, standard, or the issuing body itself | yes |
| `paper` — peer-reviewed literature, or a dataset with a stated method | yes |
| `data` — raw measurements, logs, exports the user can re-run | yes |
| `internal` — the user's own notes, records, or an undocumented internal number | no |
| `assertion` — the claim restated, someone's opinion, or no source stated | no |

The score is the share of items that count, as a percentage. `internal` and
`assertion` are not "worth less" by taste — they are items nobody outside the
conversation can check, and that is the property the score is measuring.

Full taxonomy, edge cases and tagging rules: `references/evidence-types.md`.

## The one boundary that matters

**This tool does not decide whether a claim is true. It grades the evidence, and
nothing else.**

That boundary is the whole point. A grader that also pronounced on truth would
reproduce exactly the failure it exists to catch — a confident verdict unsupported
by anything. So the tool reports what can be checked and what cannot, and stops.

Two consequences to carry into your answer:

- A score of 100 does not mean the claim is correct. It means every item offered is
  the kind of thing that could be checked. Nobody has checked it yet.
- A low score does not mean the claim is false. It means the claim is **not
  established**, which is a different and more useful statement.

Never upgrade "not established" into "false", and never upgrade a high score into
"true". Both are the same mistake in opposite directions.

## Workflow

1. **Separate the claim from the evidence before running anything.** Write the claim
   as one sentence. If the user gave you three conclusions, that is three runs — a
   single chain will average unrelated things and hide the weak one.
2. **Tag every item, and tag honestly.** An item is `official` only if it names a
   document or issuing body that exists independently of the conversation. "Our
   records show" is `internal`. "Studies suggest" with no study is `assertion`. If
   you cannot tell what an item is, it is `assertion` until the user says otherwise —
   guessing a stronger type defeats the tool.
3. **Run the tool** (command below).
4. **Read the verdict band, not just the number.** The bands are defined below.
5. **Name the gap concretely.** Do not report "the evidence is weak". Report which
   items are unverifiable and what specifically would replace each one — "the
   failure-rate figure needs the QA report it came from, not a description of it".
6. **Report the score and the gap together.** A score without the unverifiable list
   invites the reader to treat the number as a quality grade, which it is not.

## Command

```bash
python3 scripts/evidence_chain.py \
  --claim "Device X failure rate is below 0.5%" \
  --evidences "2025 QA audit report@official:QA dept" \
              "no complaints on record@internal:support" \
              "peer-reviewed cohort study@paper:JAMA"
```

Evidence strings take an optional `@type:source` suffix; one argument per item, or
several joined with `||`. No suffix means `assertion`.

| flag | meaning |
|---|---|
| `--claim TEXT` | the claim to test |
| `--evidences E1 E2 ...` | evidence items, optionally `@type:source` |
| `--from FILE.json` | `{claim, evidences:[{text, source, type}]}` for longer chains |
| `--threshold N` | score needed to count as supported (default `50`) |
| `--subject TEXT` | what the claim is about, printed in the header |
| `--json` | machine-readable output, for gating or downstream use |
| `--fail-below-threshold` | exit `1` when not supported; default is exit `0` either way |

Exit codes: `0` the chain was scored, whatever the verdict; `2` usage or input
error. Non-zero-to-signal-unsupported is opt-in, because a caller that treats any
non-zero exit as "the command broke" would report a finding as an error.

Run `python3 scripts/evidence_chain.py --help` for the authoritative flag list.

## Reading the result

| condition | what you may say |
|---|---|
| no evidence supplied | nothing is established. There is no chain to stand on. |
| score below threshold | **Do not treat this claim as a conclusion.** Say which items are unverifiable. |
| score at or above threshold | Supported *to the stated threshold*. The sources still need a human check. |

The verdict text is deliberately phrased to survive being quoted out of context.
Keep that phrasing when you relay it; do not round it up to "verified".

Threshold defaults to 50 because a chain where the majority of the weight is
checkable is at least auditable. Raise it with `--threshold` when the claim will be
published, filed, or acted on — 80 for anything going to a regulator or a customer.
Say which threshold you used, since the verdict depends on it.

## What this cannot do

| asked for | status |
|---|---|
| Confirm a cited source exists | Not checked. The tool never fetches anything. |
| Detect a fabricated citation | Not possible here — a plausible-looking but invented reference scores as `paper` |
| Judge whether the claim is true | Out of scope by design; see the boundary above |
| Weigh study quality — sample size, bias, design | Not modelled. `paper` means "a paper was named", not "a good paper" |
| Rank sources against each other | Types are unordered beyond verifiable / not verifiable |
| Resolve conflicting evidence | Two sources that disagree both score; the conflict is yours to surface |
| Handle a claim with several parts | Run it per part; averaging hides the weak link |

State these limits plainly when they bite rather than padding the answer. If the user
needs source existence checked, that is a search task — do it as one, and treat the
result as a new evidence item, not as the same chain.

## Examples

**A figure that arrived with no source.** The user says "an analyst told me this
market grows 30% a year". Run the chain with the figure as the claim and
`"analyst estimate@assertion"` as its only evidence. The score is 0 and the verdict
is that it is not established. Say that, and say what would fix it: the analyst's
published note, or the underlying data. Do not soften it into "could be higher or
lower".

**Mixed chain, honestly reported.**

```bash
python3 scripts/evidence_chain.py --claim "Device X failure rate is below 0.5%" \
  --evidences "2025 QA audit report@official:QA dept" \
              "no complaints on record@internal:support" \
              "peer-reviewed cohort study@paper:JAMA"
# -> 67/100, 2 of 3 verifiable, threshold 50
```

Relay it as: two of the three items can be checked, the support log cannot, and the
claim clears a 50 threshold but not an 80 one.

**Gating a publish step.**

```bash
python3 scripts/evidence_chain.py --from claims.json --threshold 80 --fail-below-threshold
```

Exit `1` means at least one claim is not carried by verifiable evidence. Report which
ones by name; do not just forward the exit code.

**A non-English request.** "这段有依据吗" needs no translation step — run the tool
on the claim as written and answer in the user's language. The tool's own output is
English; your reply is not.

## Working on Minis

The sandbox makes this skill stronger than a plain script port, so use it:

- **Run it in the on-device shell.** `python3 scripts/evidence_chain.py ...` works
  as-is in the Alpine sandbox; there is nothing to install.
- **Pin the artifacts you can reach.** When an evidence item is a file the device can
  see — a contract, an export, a photo of a label, a record — add its `sha256sum` to
  the evidence text. A named document can be swapped later; a named document plus its
  digest cannot. That is the difference between "there is a report" and "there is
  this report".
- **Keep it on the device.** The tool never uploads and never fetches, which is
  exactly what you want when the evidence is confidential. Do not compensate by
  pasting the evidence into a web search — that would undo the property that made
  this safe to run here.
- **Save the report into the workspace**, not to a temp path, so the chain is still
  there in a later session when someone asks where the number came from.
