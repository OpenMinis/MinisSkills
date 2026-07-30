# `apple-reminders` command reference

Full contract for the built-in `apple-reminders` native command. Read this when you
need exact flags, response fields, error codes, or the date grammar. `SKILL.md`
covers the workflow and safety rules that sit on top of it.

Everything here is derived from the Minis source: the command dispatch lives in
`src/ios/NativeOffloads/RemindersOffload.m`, the five verb implementations in
`src/ios/NativeOffloads/CalendarOffload.m` (`calendar_cmd_reminders`,
`calendar_cmd_remind`, `calendar_cmd_update_reminder`,
`calendar_cmd_complete_reminder`, `calendar_cmd_delete_reminder`), and the shared
envelope, argument, and date helpers in
`src/ios/NativeOffloads/NativeOffloadUtils.m`.

The backend is EventKit (`EKReminder` / `EKCalendar` with
`EKEntityTypeReminder`). It reaches the same reminder store as the Reminders app,
so changes sync through the user's normal iCloud setup. Nothing here touches a
database directly, and there are no scripts or network calls.

**iOS only.** `reminders_offload_register()` installs the guest stub at
`/usr/local/bin/apple-reminders`, so the command is on `PATH` inside the sandbox on
iOS. The Android offload set has a calendar handler but no reminders handler, so
this command does not exist there — check for it before assuming, and say so
plainly rather than failing obscurely.

## Global behaviour

Every invocation prints exactly one JSON object to stdout.

Success envelope:

```json
{
  "ok": true,
  "tool": "apple-reminders",
  "action": "<action name>",
  "data": { },
  "timestamp": "2026-07-30T14:12:05+09:00"
}
```

Error envelope:

```json
{
  "ok": false,
  "tool": "apple-reminders",
  "action": "<action name>",
  "error": { "code": "invalid_args", "message": "Required: --id <reminder_id>" },
  "timestamp": "2026-07-30T14:12:05+09:00"
}
```

`timestamp` is ISO 8601 in the device's local timezone.

The `action` field does not always equal the subcommand you typed:

| Subcommand | `action` value |
|---|---|
| `list` | `reminders` |
| `create` | `remind` |
| `update` | `update` |
| `complete` | `complete` |
| `delete` | `delete` |

Global flags, accepted by every subcommand:

| Flag | Effect |
|---|---|
| `--help`, `-h` | Print help to **stderr**, exit 0 |
| `--compact` | Minify JSON. Without it, output is pretty-printed with sorted keys |
| `-q`, `--quiet` | Print only the `data` object on success, or only the `error` object on failure |

`-q` drops the `ok` field, so under `-q` you must use the exit code to tell success
from failure. Prefer `--compact` alone for large reads.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Success (also returned by `--help`) |
| 1 | Error — including "not found" |
| 2 | Invalid arguments |
| 3 | Reminders authorization denied |
| 4 | Not available |

Error codes in `error.code`: `authorization_denied`,
`authorization_not_determined`, `not_available`, `invalid_args`, `no_data`,
`internal_error`.

Every subcommand requests Reminders authorization first and fails with
`authorization_denied` (exit 3) if it is not granted. Retrying does not help; the
user has to grant access to Minis in iOS Settings.

## `list`

```
apple-reminders list [--incomplete | --completed] [--list <name>] [--limit <N>]
```

| Flag | Notes |
|---|---|
| `--incomplete` | Incomplete reminders, **including ones with no due date** |
| `--completed` | Completed reminders only |
| *(neither)* | All reminders, complete and incomplete |
| `--list <name>` | Case-insensitive **substring** match on list titles |
| `--limit <N>` | Default **100** |

`data`:

```json
{
  "reminders": [
    {
      "id": "A1B2C3D4-...",
      "title": "Pick up prescription",
      "completed": false,
      "list": "Errands",
      "priority": 0,
      "notes": null,
      "due": "2026-08-07T18:00:00+09:00"
    }
  ],
  "count": 1
}
```

- `notes` is `null` when empty.
- `due` is **absent** when the reminder has no due date, and `null` when it has
  date components that cannot be converted. Treat both as unscheduled.
- `id` is the EventKit `calendarItemIdentifier`. It is the only safe write target.

When more reminders matched than `--limit` allowed, `data` also carries:

```json
{
  "_warning": "Results truncated by --limit. Returned 100 of 412 total records. Use a larger --limit to retrieve more data.",
  "total_available": 412
}
```

**Result order is not guaranteed.** A truncated read is an arbitrary subset, not the
earliest or most urgent items, so a truncated read cannot support any statement
about the whole set. Narrow the scope or raise `--limit` above `total_available`.

There is no date-range filter, no search-text filter, and no sort flag. Group,
filter, and sort on your side after reading.

## `create`

```
apple-reminders create --title <t> [--due <dt>] [--list <name>] [--priority <0-9>] [--notes <text>]
```

`--title` is required; without it the command prints help to stderr and returns
`invalid_args` (exit 2).

`data` — note how little comes back:

```json
{ "id": "A1B2C3D4-...", "title": "Pick up prescription", "list": "Errands" }
```

`due`, `priority`, and `notes` are **not echoed**. To confirm any of them, follow up
with a `list` read.

Two silent failure modes:

- **Unmatched `--list` is not an error.** The list is resolved by case-insensitive
  substring across reminder lists; on no match the reminder is saved to the device's
  default reminder list and the response still reports `ok: true`. The returned
  `list` field is the only signal — always compare it against what you intended.
- **An unparseable `--due` is dropped.** No error, no warning, exit 0, reminder
  created with no due date.

`--parent-id` exists but always fails with `not_available` (exit 4): iOS through
26.5 exposes no public EventKit API for reminder subtasks, and the implementation
deliberately refuses to reach for private selectors. Create the reminder without it
and nest it by hand in the Reminders app if nesting matters.

## `update`

```
apple-reminders update --id <id> [--title <t>] [--due <dt>] [--list <name>] [--priority <0-9>] [--notes <text>]
```

`--id` is required (`invalid_args`, exit 2 if missing). An id that does not resolve
returns `no_data` (exit 1).

This is a patch: **omitted flags are left untouched.** Pass only what you intend to
change.

`data` returns full post-write state, which makes the response its own read-back:

```json
{
  "id": "A1B2C3D4-...",
  "title": "File taxes",
  "completed": false,
  "list": "Admin",
  "priority": 1,
  "notes": null,
  "due": "2026-08-10T09:00:00+09:00"
}
```

`--due` has the same silent-drop behaviour as `create`. Because `update` echoes
`due`, compare the returned value against what you intended — a mismatch means the
parse failed.

`--list` here moves the reminder to another list, using the same substring match,
but unlike `create` there is no fallback: on no match the reminder simply stays
where it is, reported as a successful update.

## `complete`

```
apple-reminders complete --id <id> [--undo]
```

Sets completion state: `--undo` marks the reminder incomplete again, so this verb is
fully reversible in both directions.

`data`:

```json
{ "id": "A1B2C3D4-...", "title": "File taxes", "completed": true, "list": "Admin" }
```

## `delete`

```
apple-reminders delete --id <id>
```

Removes the reminder from the store via EventKit `removeReminder:`.

`data`:

```json
{ "id": "A1B2C3D4-...", "title": "File taxes", "list": "Admin", "deleted": true }
```

Whether the deletion is recoverable from the Reminders app's Recently Deleted is
**not verified** for this path — do not promise the user that it is. Capture
`title`, `list`, `due`, `priority`, and `notes` from a read before deleting so the
reminder can be recreated by hand.

## Id resolution cost

`update`, `complete`, and `delete` resolve `--id` by fetching **every reminder in
the store** and linear-searching for a matching `calendarItemIdentifier`, under a
10-second timeout. If that fetch times out the lookup returns nothing, which
surfaces as `no_data` — "Reminder not found with id ...".

So `no_data` on a large store is ambiguous: it can mean the reminder is gone, or
that the scan did not finish. Re-read before telling the user their reminder no
longer exists.

## Date grammar

`--due` is parsed by `noff_parse_date`, in this order:

1. **Relative, past only** — `-<N>d`, `-<N>h`, `-<N>m` (`-7d`, `-2h`, `-30m`).
   `N` must be greater than 0, and only `d`, `h`, `m` are recognized. **There is no
   future form**: `+3d` does not parse.
2. **ISO 8601 internet date-time**, with or without fractional seconds —
   `2026-08-07T18:00:00+09:00`, `2026-08-07T18:00:00Z`.
3. **Local-timezone patterns**, tried in order, using the device timezone:
   `yyyy-MM-dd'T'HH:mm:ss`, `yyyy-MM-dd'T'HH:mm`, `yyyy-MM-dd`.

Anything else returns nothing, and the caller drops the flag without an error.
Natural language (`tomorrow`, `next Monday`, `내일`, `明天`) and bare offsets
(`3d`, `+1w`) all fail this way.

Because due dates are almost always in the future and relative parsing only goes
backwards, **absolute local datetimes are the only practical form for `--due`**:
compute `YYYY-MM-DDTHH:MM` yourself.

Stored due dates keep year, month, day, hour, and minute. A date-only value
therefore becomes 00:00 local — this command cannot create an all-day reminder. No
`EKAlarm` is attached by any verb, so treat "a notification will fire at that time"
as the Reminders app's behaviour, not something this command arranges.

**All-day reminders made elsewhere are indistinguishable in `list` output.** A
reminder created in the Reminders app with a date but no time is all-day in EventKit
— its `dueDateComponents` carry no hour or minute — and `list` converts those
components with `dateFromComponents:`, so it surfaces as `T00:00:00` local, exactly
like a reminder deliberately due at midnight. So a due time of exactly 00:00 is more
likely an all-day item than a midnight deadline: present it as a date rather than as
"due at 12:00 AM", and do not "correct" it by writing a time onto it.

## Priority scale

`--priority` takes 0–9 and is stored on `EKReminder.priority` without validation.
The EventKit scale is inverted relative to intuition:

| Value | Meaning |
|---|---|
| 0 | None |
| 1–4 | High (1 is highest) |
| 5 | Medium |
| 6–9 | Low (9 is lowest) |

Map user words onto it — high → 1, medium → 5, low → 9 — and never pass a number
the user offered as a 1-to-10 importance ranking.

## Not exposed

Not reachable through this command at all: sections, tags, flags, image or URL
attachments, subtasks, list creation or deletion, list emoji and color, all-day due
dates, recurrence rules, alarms, location triggers, messaging triggers, and
enumerating lists that contain no reminders. There is also no `lists` subcommand —
list titles are only observable through the `list` field of reminders that exist
inside them.
