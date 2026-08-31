# Compose a reminder card

Use this reference when source material contains more information than one useful
Reminders card: documents, meeting notes, screenshots, several dates, missing
times, or multiple links.

## One visible home

Extract the source first, then project each useful fact into one card part:

| Card part | Purpose |
|---|---|
| title | The action or scheduled item the user will recognize at a glance |
| trigger | The action's actual due time, recurrence, or arrive/leave condition |
| notes | Brief context needed at the moment of action |
| canonical link | The one page that performs the action or provides the essential reference |
| evidence | Source text or image location used for reasoning, not copied by default |

Use the title as the scan line, not as a miniature record. A date, place, owner,
or event name can stay when it helps identify the action. Metadata already carried
by the trigger, list, priority, or notes adds no value when repeated in the title.
Read title, notes, and trigger together and remove a duplicate when the card remains
equally actionable without it.

## Dates without invented times

Dates in the same source can serve different jobs. A registration deadline can
trigger “Register for DevDay,” while the later event date is supporting context.
Assign a date to `due` only when it controls this action; keep context dates in
notes.

The current command cannot store a typed all-day due. Bare `YYYY-MM-DD` becomes a
timed midnight. For a date-only trigger:

1. apply the user's established storage preference when one exists;
2. otherwise ask once whether to use a real local time or leave due unset and keep
   the date in notes;
3. use midnight only when the user explicitly chooses midnight or accepts that
   approximation.

Collect the choice once for a batch when the same preference can apply to every
date-only candidate.

## One useful link

Choose one canonical link by the action it enables: Register, Join, Pay, Review,
or another concrete next step. The current command cannot write the native
reminder URL field, so a needed link can only be stored as concise labelled note
text. Treat it as note text, not as a native URL or attachment.

Keep a second link only when it supports a genuinely different next step or
reference the user will need. Source archiving is a different job from composing a
reminder; a card does not need to preserve every supplied URL.

## Example

Source:

```text
OpenAI DevDay Exchange 2026; registration closes Sep 4 (no time supplied);
Seoul event Oct 22 at 14:00; registration URL; event-information URL.
```

Card proposal on the current command:

```text
title: Register for OpenAI DevDay Exchange 2026
due: unresolved date-only trigger
notes:
  Event: Oct 22 at 14:00 · Seoul
  Register: <registration URL>
```

The registration page is the canonical action link. The general information page
stays out unless it adds needed information or the user asks to retain it. After
the storage choice is resolved, use this same card as the write intent and the
read-back comparison. Report only its verified phone-sized projection.
