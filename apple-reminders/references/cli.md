# `apple-reminders` command reference

This is the detailed contract for Minis' built-in iOS command. Installed builds
can be newer than the public source and older builds may lack newer flags. Check
`apple-reminders --help` before using a build-varying branch and treat it as
authoritative.

Verified on 2026-08-30 against the public OpenMinis 1.12 source at commit
[`09fc199`](https://github.com/OpenMinis/OpenMinis/tree/09fc199928de0f26685e766c34e6d541c7a69e5a).
The implementation delegates reminder work from
[`RemindersOffload.m`](https://github.com/OpenMinis/OpenMinis/blob/09fc199928de0f26685e766c34e6d541c7a69e5a/src/ios/NativeOffloads/RemindersOffload.m)
to EventKit-backed functions in
[`CalendarOffload.m`](https://github.com/OpenMinis/OpenMinis/blob/09fc199928de0f26685e766c34e6d541c7a69e5a/src/ios/NativeOffloads/CalendarOffload.m).
It uses the same reminder store as Apple's Reminders app and does not read its
database directly.

## Contents

- [Platform and global behavior](#platform-and-global-behavior)
- [List](#list)
- [Create](#create)
- [Update](#update)
- [Complete and undo](#complete-and-undo)
- [Delete](#delete)
- [Date grammar](#date-grammar)
- [Priority](#priority)
- [Recurrence](#recurrence)
- [Location geofences](#location-geofences)
- [Verification](#verification)
- [Errors and timeout ambiguity](#errors-and-timeout-ambiguity)
- [Not exposed](#not-exposed)

## Platform and global behavior

The command is registered only on iOS. Check its existence before use; inspect full
help when requested flags can vary by build:

```bash
command -v apple-reminders
apple-reminders --help
```

The five verbs are:

```text
apple-reminders list
apple-reminders create
apple-reminders update
apple-reminders complete
apple-reminders delete
```

Global flags:

| Flag | Effect |
|---|---|
| `--help`, `-h` | Prints help to stderr and exits 0 |
| `--compact` | Minifies the JSON envelope |
| `-q`, `--quiet` | Prints only `data` on success or `error` on failure |

Prefer `--compact` without quiet mode. Quiet output removes `ok`, so the process
exit code becomes essential.

Typical envelope:

```json
{
  "ok": true,
  "tool": "apple-calendar",
  "action": "reminders",
  "data": {},
  "timestamp": "2026-08-30T12:00:00+09:00"
}
```

Because the current implementation delegates to `CalendarOffload`, recognized
reminder actions can say `tool: "apple-calendar"`; other builds may say
`"apple-reminders"`. Do not validate success from `tool`. Validate exit status,
`ok`, the expected `action`, response shape, and stored state.

Action values:

| Verb | `action` |
|---|---|
| `list` | `reminders` |
| `create` | `remind` |
| `update` | `update` |
| `complete` | `complete` |
| `delete` | `delete` |

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Command accepted; also used by help |
| 1 | Error, including unresolved ID |
| 2 | Invalid arguments |
| 3 | Permission denied |
| 4 | Capability unavailable |

Exit 0 is not proof that a list or date was applied. See the silent behaviors below.

## List

```text
apple-reminders list [--incomplete | --completed] [--list <name>] [--limit <N>]
```

| Flag | Meaning |
|---|---|
| `--incomplete` | Incomplete reminders, including ones with no due date |
| `--completed` | Completed reminders only |
| neither | All completed and incomplete reminders |
| `--list <name>` | Case-insensitive substring across list titles |
| `--limit <N>` | Maximum results; default 100 |

Example `data`:

```json
{
  "reminders": [
    {
      "id": "A1B2C3D4-...",
      "title": "Send project update",
      "completed": false,
      "list": "Work",
      "priority": 1,
      "notes": null,
      "due": "2026-09-01T09:00:00+09:00",
      "recurrence": {
        "frequency": "weekly",
        "interval": 1,
        "days_of_week": ["mon"],
        "never_ends": true
      },
      "location": {
        "name": "Office",
        "latitude": 37.5665,
        "longitude": 126.978,
        "radius_m": 200,
        "proximity": "enter"
      }
    }
  ],
  "count": 1
}
```

`due`, `recurrence`, and `location` are absent when not set. `notes` is null
when empty. A due value can be null when date components cannot be converted.

When more records match than the limit:

```json
{
  "_warning": "Results truncated by --limit...",
  "total_available": 412
}
```

Order is unspecified. A truncated response is an arbitrary subset. Raise the limit
above `total_available` or narrow the query before concluding that an item or date
group is absent.

There is a second silent read failure: the implementation waits 10 seconds for
EventKit but does not check whether that wait timed out. A timeout becomes
`ok:true`, `count:0`, with no warning. Treat an unexpected empty result as
empty-or-timed-out and retry once with a narrower available filter, or repeat the
same bounded read when no safe narrower scope exists. Even after retry, an empty
result is not strong absence proof. A positive ID match is strong evidence;
deletion absence needs independent fetch-completion evidence, such as expected
known survivors in the same bounded result.

`--list` can match and merge multiple lists. Empty lists never appear because the
output learns list titles only from returned reminders. The command has no list ID,
account, search, date-range, sort, or cursor option.

## Create

```text
apple-reminders create --title <text>
  [--due <datetime>] [--list <name>] [--priority <0-9>] [--notes <text>]
  [recurrence flags] [location flags]
```

`--title` is required. Example response:

```json
{
  "id": "A1B2C3D4-...",
  "title": "Send project update",
  "list": "Work",
  "recurrence": {
    "frequency": "weekly",
    "interval": 1,
    "days_of_week": ["mon"],
    "never_ends": true
  },
  "location": {
    "name": "Office",
    "latitude": 37.5665,
    "longitude": 126.978,
    "radius_m": 200,
    "proximity": "enter"
  }
}
```

The response omits due, priority, and notes. Positively match the returned ID in a
follow-up read before claiming those fields were stored. A match remains useful
when the wider result is truncated; truncation prevents absence claims.

Silent behaviors:

- An unmatched `--list` falls back to the device's default reminder list and
  returns success. Compare the returned full `list` title.
- An unparseable `--due` is ignored and returns success. With a recurrence request,
  the missing valid due causes recurrence validation to fail instead.
- Priority is converted to an integer without strict validation in the current
  public source. Pass only a validated 0–9 value.

An observed single list match does not prove uniqueness because an empty colliding
list remains invisible. Treat named-list creation as best effort, stop on known
collisions, and disclose that only post-write destination verification is possible.
An unobserved requested list may be empty or absent. If absent, create could fall
back to the default list. Attempt it only for one create after the user accepts that
risk, then verify the returned full list; never use it for a batch or list move.
For exactly one observed match, one ordinary create may proceed as best effort; a
batch or list move requires the user to accept that limit.

`--parent-id` may appear in help but always returns `not_available`; public iOS
EventKit exposes no reminder subtask relationship.

## Update

```text
apple-reminders update --id <id>
  [--title <text>] [--due <datetime>] [--list <name>]
  [--priority <0-9>] [--notes <text>]
  [recurrence flags | --clear-recur]
  [location flags | --clear-location]
```

`--id` is required and must come from a read. Update is a patch: omitted fields
remain unchanged. Pass only fields the user asked to change.

The response includes ID, title, completion, list, priority, notes, and due when
present. It also includes recurrence or location when present. The response is the
in-memory post-save object, not an independent re-fetch, so high-impact work still
benefits from bounded read-back.

The current implementation sets and serializes `dueDateComponents` but neither
updates nor exposes `startDateComponents`. A successful due-only update therefore
proves only that the due field changed. It does not prove that a timed recurring
series was fully re-anchored. In one observed build, the requested due and existing
recurrence rule read back successfully while an independent EventKit read still
showed the old start. Actual next-occurrence behavior was not established by that
observation. Treat a request to retime an existing recurring reminder as
unsupported unless the user explicitly accepts a due-field-only patch with that
hidden-start limitation.

Silent behaviors:

- An invalid `--due` is ignored, leaving the previous due unchanged.
- An unmatched `--list` leaves the previous list unchanged.
- Recurrence option flags without `--recur` do not create a rule. Always include
  the base frequency when adding or replacing recurrence.

`--clear-recur` removes the current recurrence. Although the current
implementation processes clear before a supplied new rule, do not combine clear
and set flags. Use one unambiguous intent per update.

`--clear-location` removes the structured location alarm. Full new location
arguments already replace the old geofence. Do not combine clear and set flags in
one update. Time-based alarms, when present in a build, are not removed by
`--clear-location`.

There is no `--clear-due` or `--clear-notes`.

## Complete and undo

```text
apple-reminders complete --id <id> [--undo]
```

Without `--undo`, the command requests completion. With it, the command requests
incompletion. A typical non-recurring completion response is:

```json
{
  "id": "A1B2C3D4-...",
  "title": "Send project update",
  "completed": true,
  "list": "Work"
}
```

This is the most recoverable mutation and should represent “done.” The response is
not a separate final re-fetch; verify broad or consequential changes with a bounded
completed or incomplete read.

For a recurring item, an observed build returned `ok:true`, `action:"complete"`,
and `data.completed:false` even though one occurrence committed and the series
advanced. The handler serializes `isCompleted` from the same mutable `EKReminder`
object after save rather than fetching the completed occurrence. Apple does not
document the exact post-save boolean projection, so neither value of this field is
a recurring-completion receipt. Confirm the target due in a fresh completed read
and the successor or terminal absence in a fresh incomplete read. In particular,
`completed:false` is not evidence of a no-op and never authorizes a retry.
Treat the mismatch as response-fidelity failure, not proof that the write failed.

For a recurring reminder, Apple EventKit exposes only the first incomplete
occurrence. Completing it makes the next occurrence available. Treat completion as
“finish this occurrence and advance the series,” then verify the next incomplete
occurrence. Do not promise that `--undo` is a simple rollback after advancement.

Recurring completion is **retry-unsafe**. The active series can keep the same ID
after a completion, so repeating the same command can complete the newly exposed
successor rather than harmlessly re-completing the prior occurrence. The command
has no idempotency key, expected-due guard, or revision precondition.

Before dispatch, record the active ID, due, recurrence, and a bounded matching
completed baseline. If the baseline is truncated, unexpectedly empty, ambiguous,
or cannot uniquely isolate the series, skip the automated behavioral completion;
use a manual one-tap step or report the test inconclusive.

For one user-authorized step, dispatch exactly one write-bearing shell/tool call
total with exactly one completion invocation. Every later call in the same turn is
read-only, including after success, timeout, lost response, or ambiguity. Those
uncertain outcomes are possibly committed and must not be retried. Re-read active
and bounded completed state instead. A verified nonterminal step adds one completed
occurrence, exposes the immediate next due predicted by the full recurrence rule,
and does not otherwise mutate the series. A terminal step adds one completed
occurrence and leaves no active successor under a trustworthy read. On builds whose
read-back uses `count` for remaining occurrences, a one-count reduction is
corroborating rather than primary evidence. Stop on any larger jump or unexplained
delta.

A larger jump or two distinct completion timestamps proves that the end-to-end
single-step invariant failed; state alone does not identify the actor, shell/tool
call count, or native invocation count. Inspect expanded tool-call logs before
attribution, and never label the observation a native double-save without them.

Chat retry/edit/revert controls remove or replace visible conversation and tool
history only. They do not compensate an already committed Reminder write. If a
write-bearing turn is rewound and run again, first read current external state and
treat the rerun as a new mutation; never infer rollback because the earlier tool
card disappeared.

At the final count, no active successor should remain. Because an EventKit fetch
timeout can masquerade as an empty successful list, absence is conclusive only
when the same bounded read also returns expected known survivors or comparable
fetch-completion evidence. Otherwise report final enforcement as inconclusive.

## Delete

```text
apple-reminders delete --id <id>
```

```json
{
  "id": "A1B2C3D4-...",
  "title": "Send project update",
  "list": "Work",
  "deleted": true
}
```

The command calls EventKit removal and does not independently re-fetch active or
Recently Deleted state. Capture a deletion record first. `deleted:true` does not
prove the item entered Apple's Recently Deleted list or will be recoverable.

Reminder delete has no occurrence or span flag. When `recurrence` is present,
require explicit whole-series deletion intent rather than implying that one future
occurrence can be removed.

## Date grammar

`--due` and `--recur-until` use the shared date parser:

1. Past-only offsets: `-7d`, `-2h`, `-30m`.
2. ISO 8601 with an offset or `Z`.
3. Device-local patterns: `yyyy-MM-dd'T'HH:mm:ss`,
   `yyyy-MM-dd'T'HH:mm`, and `yyyy-MM-dd`.

There is no future relative form: `+3d` does not parse. Natural-language dates do
not parse. Convert them before invoking the command.

A date-only value becomes 00:00 local with hour and minute components. It is not a
typed all-day value. Conversely, an all-day reminder created in Apple's app can
also serialize as 00:00 here, making intentional midnight and all-day
indistinguishable.

The due field alone does not expose whether the installed build attached a
time-based `EKAlarm`. Do not promise a notification banner. A one-time physical
device smoke test provides evidence only for the current device, account,
notification settings, and Focus state; it does not prove build-wide behavior. Do
not schedule a second notification automatically because it could duplicate alerts.

## Priority

EventKit priority is inverted:

| Value | Meaning |
|---|---|
| 0 | None |
| 1–4 | High; 1 is highest |
| 5 | Medium |
| 6–9 | Low; 9 is lowest |

Use high → 1, medium → 5, low → 9 unless the user gives an exact valid EventKit
value. Do not treat a user's “10 out of 10” importance as `--priority 10`.

## Recurrence

Use this branch only when runtime help shows the flags.

```text
--recur daily|weekly|monthly|yearly
--recur-interval <positive integer>
--recur-days <comma-separated weekdays>
--recur-until <ISO datetime>
--recur-count <positive integer>
--clear-recur
```

Rules:

- Recurrence requires a valid due date, either stored already for update or passed
  in the same command.
- Interval defaults to 1.
- Weekday tokens accept names/codes such as `mon`, `monday`, or `mo`.
- `--recur-days` is invalid with daily frequency. For weekly recurrence, omitting
  days uses the due date's weekday.
- `--recur-until` and `--recur-count` are mutually exclusive. With neither, the
  rule repeats forever.
- Until must be later than the effective due date.
- One recurrence rule is stored; a new full rule replaces the previous one.

### Reminders UI interoperability

EventKit supports both date-based and occurrence-count ends for reminders. Apple's
Mac Reminders guide, however, exposes only **End Repeat > On Date** in the UI.
Consequently, a rule can read back as `count:N` through EventKit while the
Reminders inspector displays **Never**. Do not use that display alone as evidence
that the count was lost, and do not edit/save the repeat field merely to correct
the label because the UI may overwrite a value it cannot represent.

Verify count-based storage with command read-back. When actual enforcement matters,
use a disposable recurring test and apply the retry-unsafe completion guard above.
Each accepted nonterminal step must add one completed occurrence, expose the
immediate next due predicted by the full rule, and leave the rest of the series
unchanged. The terminal step must add one completed occurrence and leave no
successor under a trustworthy read. A one-count reduction, when this build
serializes remaining occurrences that way, is corroborating evidence. Only after
every step passes may absence of an N+1 occurrence establish enforcement. A manual
one-tap completion in Reminders can isolate EventKit behavior from agent or shell
replay. For an automated test, use a separate human-reviewed turn for each step;
never batch multiple completions. Keep this behavioral check separate from whether
a notification alarm exists.

Apple documents that only the first incomplete reminder in a recurring set is
obtainable; completing it exposes the next. The command has no occurrence/span
selector for reminder update or delete. Before update, move, or delete, state the
repeating scope and require explicit whole-series intent. After completion, verify
the next occurrence rather than assuming the same item can simply be undone.

Do not use a due-only patch followed by recurrence replacement as a verified
re-anchor procedure. A replacement can validate a new rule against the current
due, but the command still cannot update or inspect the hidden start components.
Recurrence-only replacement and clear remain separate capabilities with their own
verification. Clear recurrence in its own update and never mix `--clear-recur`
with `--recur*`.

Examples:

```bash
apple-reminders create --title "Send weekly report" \
  --due 2026-08-31T09:00 --recur weekly --recur-days mon --compact

apple-reminders create --title "Water plants" \
  --due 2026-08-31T08:00 --recur daily --recur-interval 2 \
  --recur-count 10 --compact

apple-reminders update --id "<id>" --clear-recur --compact
```

Serialized recurrence contains `frequency`, `interval`, optional
`days_of_week`, and exactly one ending form: `until`, `count`, or
`never_ends:true`.

Apple's documented Mac UI boundary:
https://support.apple.com/guide/reminders/remndc729e28/mac

## Location geofences

Use this branch only when runtime help shows the flags.

```text
--lat <WGS-84 latitude>
--lng <WGS-84 longitude>
--location-name <label>
--radius <non-negative meters>
--proximity enter|leave
--clear-location
```

Both latitude and longitude are required. Latitude must be -90 through 90 and
longitude -180 through 180. Omitted name defaults to a coordinate label. Omitted
radius uses the system default. Proximity defaults to `enter`; use `leave` for
departure.

When an address is given, `apple-location forward --address "<address>"` can
resolve it. Use returned WGS-84 `latitude` and `longitude`, never a `gcj02_*`
variant. If several places are plausible, resolve the place with the user before
creating the reminder. Address geocoding may require connectivity.

Location arguments add or replace one structured geofence. Bad or partial
coordinates fail the command. If Location Services permission is denied, the
command fails before saving rather than silently creating a reminder without the
requested geofence.

Examples:

```bash
apple-reminders create --title "Pick up parcel" \
  --location-name "Station" --lat 37.5547 --lng 126.9707 \
  --radius 200 --proximity enter --compact

apple-reminders update --id "<id>" --clear-location --compact
```

Serialized location contains name, latitude, longitude, `radius_m`, and
`proximity`. A due date and location geofence may coexist. Treat precise
coordinates as sensitive; ordinary user-facing reports should show the place name,
arrive/leave intent, and radius rather than raw latitude/longitude.

## Verification

Use the weakest sufficient verification without overstating it:

1. Require expected exit status, `ok`, `action`, and response fields.
2. Compare returned ID, title, and full list title.
3. Compare fields echoed by update or by recurrence/location create.
4. For due, priority, notes, or any material omitted field, use a bounded read and
   positively match the returned ID. Truncation does not invalidate a returned
   match; it invalidates absence claims.
5. Check truncation and the silent-empty timeout before using absence as evidence.
6. If final read-back cannot be completed, report the write as accepted but
   unverified. Do not retry a create blindly.

There is no exact read-by-ID command. Verification therefore depends on a positive
ID match in a nonempty result. An empty result alone cannot verify absence because
the fetch may have timed out.

## Errors and timeout ambiguity

Error codes include `authorization_denied`, `authorization_not_determined`,
`not_available`, `invalid_args`, `no_data`, and `internal_error`.

`update`, `complete`, and `delete` resolve an ID by fetching all reminders and
linear-searching under a 10-second wait. On a large or slow store, `no_data` can
mean the fetch timed out, not that the ID never existed. Separately, `list` can
turn the same timeout into an empty successful result. Re-read before declaring an
item absent.

Never continue a batch after permission denial, invalid arguments, unexpected
response shape, wrong destination, failed verification, or uncertain dispatch.

## Not exposed

No current verb or flag provides:

- sections, native tags, flags, or subtasks;
- image/file attachments;
- the reminder URL field or URL attachments;
- list enumeration, account/source IDs, exact list selection, or list management;
- typed all-day due values, clearing due, or clearing notes;
- `startDateComponents` read/write or a verifiable recurring-time anchor update;
- message/contact triggers;
- search, sort, due/completion range, pagination, or exact read-by-ID;
- completion timestamp or revision guard;
- idempotency keys;
- Recently Deleted inspection or recovery.

Do not invent a command to cover these gaps. Use the manual iPhone recovery and
honest recreation workflow in [capture-recovery.md](capture-recovery.md).
