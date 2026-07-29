---
name: apple-reminders
description: >
  Read, brief on, capture, and safely change tasks in the native Apple Reminders
  app through the on-device `apple-reminders` command. Use this skill whenever the
  user asks about their reminders, to-dos, or tasks — daily or weekly briefings,
  what is overdue or due today, unscheduled inbox items, adding or capturing a new
  task, rescheduling a due date, changing priority, moving a task to another list,
  marking things done, cleaning up a list, or finding a specific reminder. Trigger
  it even when the user never says "reminder": "what's on my plate today", "add
  milk to my shopping list", "push that to Friday", "what did I miss this week",
  "clear out the done stuff", "브리핑", "할 일", "미리알림", "오늘 뭐 해야 해",
  "장바구니에 추가", "마감 지난 것", "提醒事项", "待办", "今天要做什么",
  "リマインダー", "タスク". Also trigger when the user asks for something Reminders
  cannot do through this command (tags, sections, attachments, flags, subtasks,
  recurring reminders) so the limitation is reported accurately instead of guessed.
compatibility: >
  iOS only. Requires the built-in `apple-reminders` native command and granted
  Reminders permission; the command is not registered on Android. No external
  dependencies, no scripts, no network.
---

# Apple Reminders

## Overview

`apple-reminders` is a built-in native command backed by EventKit. It exposes five
verbs — `list`, `create`, `update`, `complete`, `delete` — over reminder titles,
due dates, lists, priorities, notes, and completion state. Every call prints one
JSON envelope to stdout.

The command is small, but three of its behaviours fail *silently and successfully*:
a mistyped list name, an unparseable due date, and a truncated read all return
`ok: true`. Most of this skill exists to keep those three from turning into wrong
answers or misplaced tasks. Read `references/cli.md` for the full contract — flags,
JSON shapes, error codes, and the exact date grammar.

```
apple-reminders list     [--incomplete|--completed] [--list <name>] [--limit <N>]
apple-reminders create   --title <t> [--due <dt>] [--list <name>] [--priority <0-9>] [--notes <text>]
apple-reminders update   --id <id> [--title <t>] [--due <dt>] [--list <name>] [--priority <0-9>] [--notes <text>]
apple-reminders complete --id <id> [--undo]
apple-reminders delete   --id <id>
```

Add `--compact` to minimize JSON, `-q` to print only the `data` field. Prefer
`--compact` for large reads to save context.

The command is iOS-only. If it is not on `PATH`, say that reminder access is not
available on this device rather than reaching for a workaround.

## Three checks before any write

These are not style preferences. Each one prevents a wrong result that the command
itself reports as success.

**1. Resolve the exact list title from a read. Never pass a guessed name.**

`--list` matches by *case-insensitive substring*, so `--list Work` also matches
`Workout`, and when several titles match, EventKit's calendar order decides which
one wins — not you. Worse, on `create` an unmatched `--list` is not an error: the
reminder is silently saved to the default list and the response still says
`ok: true`. So read first, pick the exact title, then write, then confirm the
`list` field in the response is the list you intended.

Empty lists never appear in `list` output, because list titles are only observable
through the reminders inside them. If the user names a list you cannot find, say it
is either empty or nonexistent — do not create the task somewhere else and hope.

**2. Compute due dates as absolute local datetimes yourself.**

Accepted forms are `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM`, `YYYY-MM-DDTHH:MM:SS`
(interpreted in the device's local timezone), and full ISO 8601 with an offset or
`Z`. Relative offsets are accepted *only into the past* (`-7d`, `-2h`, `-30m`);
there is no `+3d` form.

Anything else — `tomorrow`, `next Monday`, `+1d`, `3d`, `내일` — fails to parse, and
a failed parse is **dropped without an error**: the reminder is created or updated
with no due-date change and the command still exits 0. So resolve the user's
wording into a concrete date and time before you build the command, and state the
date you chose in your answer so a misreading is visible.

Two consequences worth knowing: `YYYY-MM-DD` alone becomes 00:00 local, since this
command has no all-day form; and `create` does not echo `due` back, so after any
`create --due` you must read the reminder back to confirm the date actually landed.
`update` does echo `due`, so its own response is the confirmation.

**3. Treat a truncated read as "I have not seen the data yet".**

`--limit` defaults to 100, and result order is not guaranteed — so a truncated read
is an *arbitrary* subset, not the first 100 by date. When `data` contains
`_warning` and `total_available`, you cannot say anything about the whole set:
"nothing is overdue" may simply mean the overdue items were outside the window.

Re-run with a narrower scope (`--incomplete`, `--list <exact title>`) or with
`--limit` above `total_available`, then answer. Say so if you deliberately answer
from a bounded scope.

## Workflow

1. **Read the real state first.** Ground every answer in actual titles, list names,
   due dates, and completion state. For briefings use one `--incomplete` read;
   `--incomplete` includes reminders with no due date, which is what you want for
   an inbox view.
2. **Normalize time language** into explicit dates, times, and weekdays before
   reasoning or writing. Use the device's local timezone.
3. **Keep reads bounded** by list, completion state, and limit — the three filters
   that exist. There is no date-range or text-search filter, so date grouping and
   keyword matching happen on your side, after the read.
4. **Target writes by `id` only.** Get `id` from a `list` read. Never write against
   a title you have not resolved to a single id. If several reminders share a
   title, disambiguate by list, due date, or notes, and name which one you chose.
5. **Verify after writing.** `update` and `complete` return post-write state — read
   it, don't assume. `create` returns only `id`, `title`, and `list`, so verify due
   date, priority, and notes with a follow-up read when they matter.
6. **Report the exact affected set** — titles, lists, and dates — not a count.
7. **Do not retry a failed write blindly.** Check `error.code` first:
   `authorization_denied` needs the user to grant Reminders access in Settings, and
   retrying will not help; `invalid_args` means fix the command; `no_data` means the
   id no longer resolves — re-read before concluding the reminder is gone.

## Write safety

This skill supports standing delegation — a user who has told you to act on their
reminders without checking in each time has granted it, and asking again on every
write makes the skill useless for the exact people who want it. So when standing
delegation applies, execute high-impact writes without stopping for a separate
confirmation.

Delegation removes the *prompt*, not the *evidence*. Every delegated write must
still be bounded to a target set you enumerated from a read, verified by read-back,
and reported afterward with the exact items affected — that report is what makes the
change reviewable after the fact, which is the whole basis for skipping the prompt.
When standing delegation does not apply, restate the qualifying set and scope before
writing.

Preserve everything the user did not ask to change. `update` is a patch: flags you
omit are left untouched, so pass only the fields you intend to change. Never send a
field "to be safe".

Match the care to how recoverable each verb is:

- **`complete`** is fully reversible with `complete --id <id> --undo`. Lowest risk.
  Prefer completing over deleting when the user's intent is "this is done", and
  when they say "clear" or "clean up", ask which they mean if it is not obvious
  from context — the two are not equivalent and only one is undoable.
- **`update`** overwrites the previous value with no undo. Capture the current
  value from your read before patching, and report `old → new` so the user can
  reverse it manually.
- **`delete`** is the only irreversible verb here. This skill cannot guarantee
  whether a deletion made through this command is recoverable from the Reminders
  app's Recently Deleted, so do not tell the user it is. Before deleting, capture
  `title`, `list`, `due`, `priority`, and `notes`, and include them in your report
  so the reminder can be recreated by hand if the deletion was wrong.
- **Bulk changes** need an enumerated target set before the first write, never a
  filter applied blindly. Keep batches small enough to report individually. If any
  single write returns `ok: false`, stop and report what has already been applied —
  do not continue through the rest of the batch, because a partially applied bulk
  change that is reported as complete is far harder to recover from than a stopped
  one.

Priority is inverted and unvalidated: `1` is the highest, `5` is medium, `9` is the
lowest, `0` is none. Map the user's words to that scale (high → 1, medium → 5,
low → 9) and never pass a number the user gave you as if it were a 1–10 ranking.

Ids from `update`, `complete`, and `delete` are resolved by scanning the whole
reminder store with a 10-second cap. On a large store, a `no_data` "Reminder not
found" can be that timeout rather than a missing reminder — re-read before telling
the user their reminder is gone.

## Output conventions

Name the list for every reminder when location matters, and use exact dates with
weekdays (`Fri 2026-08-07`) rather than "in 3 days". A `null` due date means
unscheduled, not undated-and-fine.

For briefings, build the groups yourself from one `--incomplete` read and order
them by operational meaning, skipping groups that are empty:

- **Overdue** — due before now, oldest first
- **Due today**
- **Upcoming** — next 7 days unless the user asked for a different horizon
- **Unscheduled** — `due: null`
- **Cleanup candidates** — long-overdue or clearly stale items, only when asked

Keep it short and actionable. Never print raw JSON to the user unless they are
debugging. If your read was truncated or scoped, say so in one line rather than
implying the briefing is complete.

## What this command cannot do

Report these plainly when asked. Do not simulate them, do not write them into
`--notes` as a silent substitute, and do not report success for something you did
not do — the honest limitation is more useful than a fake feature.

| Requested | Status |
|---|---|
| Sections within a list | Not exposed |
| Tags / hashtags | Not exposed |
| Flag a reminder | Not exposed |
| Image or URL attachments | Not exposed |
| Subtasks | Rejected with `not_available` — iOS has no public API for it |
| Creating or deleting a list | Not exposed; ask the user to create it in the Reminders app first |
| List emoji or color | Not exposed |
| All-day due dates | Not exposed; a date-only value becomes 00:00 local |
| Recurring reminders | Not exposed |
| Alarms, location or messaging triggers | Not exposed; this command sets a due date, and whether a notification fires is up to the Reminders app |
| Listing empty lists | Not observable — list titles only appear via reminders inside them |
| Filtering by date range or search text | Not exposed; read bounded, then filter your side |

When a request needs one of these, offer the closest honest alternative — a note in
`--notes`, a priority instead of a flag, a separate list the user creates — and let
the user decide.

## Examples

**Daily briefing.** "What's on my plate today?"

```bash
apple-reminders list --incomplete --limit 200 --compact
```

Check `_warning`; if present, raise `--limit` above `total_available` and re-read.
Then group into Overdue / Due today / Upcoming / Unscheduled, naming each list.

**Capture into a named list.** "Add pick up prescription to my errands list, Friday 6pm"

Read first to resolve the exact list title, compute the absolute datetime, create,
then confirm the `list` field came back as the list you intended and read the due
date back:

```bash
apple-reminders list --incomplete --limit 200 --compact
apple-reminders create --title "Pick up prescription" --list "Errands" --due 2026-08-07T18:00
apple-reminders list --list "Errands" --incomplete --compact
```

**Reschedule.** "Push the tax filing task to next Monday."

Resolve the id from a read, patch only `--due`, and use the returned `due` as
confirmation. Report `Wed 2026-08-05 → Mon 2026-08-10`.

**Ambiguous list name.** The user says "work list" and the read shows both `Work`
and `Workout`. Do not pass `--list work`; it would match by substring and the
winner is unpredictable. Pass the exact title you determined, or name both and ask
which one when the reminder's content does not settle it.

**Unsupported request.** "Attach this screenshot to the visa reminder."

Say the on-device command has no attachment support, so you cannot do it from here;
offer to reference the file path in the reminder's notes instead, and mention that
attaching it by hand in the Reminders app is the only way to get a real attachment.
