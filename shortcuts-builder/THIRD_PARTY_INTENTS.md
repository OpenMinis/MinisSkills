# Orchestrating System and Third-Party App Intents

How to compose a shortcut from **first-party actions** (`is.workflow.actions.*`, `com.apple.*`) and **third-party App Intents** (`<bundle id>.<IntentName>`). Read this before putting any third-party app step into a draft.

## 0. First-party or third-party: how to tell

Decide by the **action identifier**, then by who owns the app:

| Identifier looks like | Kind | Where it is documented | Needs the app installed |
|---|---|---|---|
| `is.workflow.actions.*` | **First-party, classic action** (built into Shortcuts) | `ACTION_PARAM_INDEX.md`, `ACTIONS.md` | No |
| `com.apple.*` (for example `com.apple.reminders.*`) | **First-party App Intent** (Apple apps) | `APPINTENTS.md`, `scripts/lookup_action_grounding.py` | Apple's own app, normally present |
| `<any other bundle id>.<IntentName>` (for example `com.openminis.app.QuickTaskIntent`) | **Third-party App Intent** | `scripts/appintent_catalog.py` | **Yes**, the user must have that app |

Three rules follow from this table:

1. **The two kinds look different in the file.** A first-party classic action has no `AppIntentDescriptor`. An App Intent (first-party `com.apple.*` or third-party) must carry one, and its identifier must equal `BundleIdentifier` + `.` + `AppIntentIdentifier`.
2. **Different sources of truth.** Never look up a third-party intent in `APPINTENTS.md` (Apple only) and never look up an `is.workflow.actions.*` action in the catalog. If a lookup returns nothing, you are in the wrong source, not looking at a missing action.
3. **Different rules about what you may write.** For first-party actions, follow the reference docs. For third-party intents, author only the verified kinds in section 3; everything else is left to the editor.

Other things called "third-party" in this skill are **not** App Intents: `HubSign` (a signing service, see SKILL.md "Signing"), and external web services reached by URL. Do not apply this file to them.

## 1. Source of truth

| Question | Where to look |
|---|---|
| What does an Apple action take? | `ACTION_PARAM_INDEX.md`, `ACTIONS.md`, `APPINTENTS.md`, `scripts/lookup_action_grounding.py` |
| What does a third-party app expose? | `scripts/appintent_catalog.py` over `data/thirdparty-appintents.json.gz` |
| Is the app on the user's phone? | Not in the catalog. If several candidate apps could do the job, ask with `user_ask` (candidates as options; a `timeout` means use the first, which should be the app already referenced in the request or the most widely used one). Otherwise tell the user the step needs the app installed. |

The catalog is read from each app's own `Metadata.appintents/extract.actionsdata`: 198 apps, about 1,700 actions. It lists what an app **exposes**, not what the user has installed. It contains only apps from the harvest account, so a missing app does not mean the app has no intents.

```bash
S=scripts/appintent_catalog.py
python3 $S search weather            # app name, bundle id, intent id, summary, parameter titles, enum case names
python3 $S show <bundle|app name>             # all intents of one app, with authoring level
python3 $S show <bundle> <IntentName>         # parameters, kinds, enum cases, output type
python3 $S step <bundle> <IntentName> --set name=value ...   # one WFWorkflowActions step (xml or --format json)
```

## 2. Step structure (verified on device)

```text
WFWorkflowActionIdentifier   = <BundleIdentifier>.<AppIntentIdentifier>
WFWorkflowActionParameters
  UUID                       = fresh uppercase UUID
  AppIntentDescriptor
    BundleIdentifier         = app bundle id
    AppIntentIdentifier      = intent identifier from the catalog
    Name                     = app display name
    TeamIdentifier           = "0000000000"     # accepted by Shortcuts, no real Team ID needed
  <parameter name>           = value (see section 3)
```

Parameter keys are the catalog's `name` field, not the visible title.

## 3. Parameter kinds: what may be authored

Three tiers. **Verified** means it was run on a device and the effect was observed. **Experimental** means `appintent_catalog.py step` will write it on request, but it has not been confirmed; every use is flagged `EXPERIMENTAL` and must be named in the report. **Refused** means no serialization is known, so nothing is guessed.

| Catalog kind | Tier | How |
|---|---|---|
| `text` | **verified** | `WFTextTokenString` with `attachmentsByRange` (see `VARIABLES.md` to embed a variable) |
| `bool` | **verified** | plain `true` / `false` |
| `enum:<Name>` | **experimental** (a case id as `value` imported and ran once), see 3.1 | `{value, title:{key}, subtitle:{key}}` |
| `int`, `number` | **experimental** | plain number, `--set name=5` |
| `url`, `richtext` | **experimental** | text literal |
| `date`, `location` | **refused** as a literal | pass a variable (next row) |
| any kind, **from a variable** (image, file, entity, array, date ...) | **experimental** | `--set name=@<OutputUUID>:<OutputName>` or `@var:<Name>` -> `WFTextTokenAttachment` |
| `entity:<Type>`, `array<...>`, `file`, `intents`, `measurement`, `searchCriteria` as a literal | **refused** | no literal form is known; use a variable |

**Rule: never label an experimental write as verified.** Use experimental writes when the user asks for them, tell the user plainly which parameters are experimental and that they should check them in the editor after import, and never invent a literal form for a refused kind.

`appintent_catalog.py step` enforces the tiers: it prints an `EXPERIMENTAL` note for each experimental write, refuses the rest, and notes each required parameter left unset.

When the user confirms an experimental kind works on a device, move it to **verified** here with the date, in the same change that records the evidence.

### 3.1 Enumerations

- Writing the case **id** as `value` with the display title in `title`/`subtitle` was run on a device and the shortcut imported and ran.
- Which field the system resolves when `value` and `title` disagree is **not settled**. The conflict test was inconclusive. Always make `value` and `title` describe the **same** case. Never write a conflicting pair.
- Case ids come only from the catalog. The validator rejects an id that is not a known case.

## 4. Authoring levels shown by `show` / `search`

| Level | Meaning | What to do |
|---|---|---|
| `full` | every parameter is text or bool, **or the intent has no parameters at all** | author the whole step |
| `partial` | every required parameter is text, bool or enum, and at least one other parameter is a kind we cannot write | author the text, bool and enum ones, leave the rest at defaults. If a required parameter is an enum, report it as only partly verified (section 3.1). |
| `editor-only` | a required parameter is a kind with no verified literal form (entity, file, date ...) | write it from a variable (experimental), or place the step and tell the user which parameter to pick in the editor, or choose another route |

Of the roughly 1,700 catalogued intents, about 970 are `full`, but about 770 of those take no parameters at all (toggles, open-app, start/stop). Only about 200 are `full` and also take text or bool inputs, so do not assume an arbitrary app has a writable action: check with `show`. Say plainly in the delivery note when a step is `partial` or `editor-only`.

## 5. Choosing between first-party, third-party and Minis

Order of preference:

1. A **first-party action** that does the job (no extra app to install, and its parameters are documented).
2. A **third-party Intent** when the user named the app, or no first-party action covers it.
3. A **URL scheme** (`URL_SCHEMES.md`) if the app has no Intent but has a scheme.
4. Hand the work to Minis (`MINIS_CAPABILITIES.md`) when logic is too heavy for a shortcut.

Before adding a third-party step, check:

- `openAppWhenRun` (`openApp=True` in `show`): the app is brought to the foreground and the flow may pause there. Unsuitable for background or automation-triggered flows.
- Required parameters of an unverified kind (`editor-only`).
- The intent exists in the catalog under the exact bundle id you are using (`show <bundle>` lists them). An app can ship several bundle ids, for example an iPad edition; do not mix them.

## 6. Chaining steps

- Each step gets its own `UUID`. To use an earlier result, the consuming parameter references that UUID with `OutputUUID` + `OutputName` (format in `VARIABLES.md`). `CustomOutputName` on the producing step sets the name shown.
- The catalog's `out` field shows what an intent returns: `entity:<Type>`, `primitive`, `array`, `intents` (file/media), or `None`. `None` only means the metadata declares no output type; it does not prove the step returns nothing. Do not feed an unknown entity into a text parameter and assume it flattens to useful text. Insert an explicit conversion (Get Text / Get Details) or tell the user it is unverified.
- Passing a **text** output into a third-party **text** parameter is the safest pairing and is what `VARIABLES.md` documents.
- Mixing is fine: for example, a first-party `Get Current Weather` step feeding a Text step whose result goes to a third-party text parameter.

## 7. Workflow when a request names an app or a capability

1. Identify each capability (read, create, toggle, send, search ...) and the app that should do it.
2. `search` for the capability, `show <app>` for the candidate.
3. Pick intents whose level is `full` or `partial`. If every candidate is `editor-only`, say so and propose an alternative.
4. Draft the action chain (SKILL.md step 8), generate each third-party step with `step`, paste into the draft.
5. Run `scripts/validate-shortcut`. It checks, for catalogued apps:
   - identifier equals `BundleIdentifier.AppIntentIdentifier`
   - every parameter key exists for that intent
   - bool parameters are booleans
   - enum values are known case ids
   Apps not in the catalog only get the generic identifier check.
6. In the report, list each third-party step with its app, its level, and anything left to the editor.

## 8. Not verified yet

State these as unverified in reports; do not claim they work:

- Serialization of `int`, `number`, `date`, `url`, `richtext`, `location`, entity, array, file and variable-reference parameters for third-party intents.
- Whether the system resolves an enum by `value` or by `title`.
- Behavior of intents inside app extensions (`component` other than `main`) when the extension is not the main target.
- Whether a step still runs when the app is not installed (expected to fail or show a missing-app state).

When a new pattern is verified on a device, record it here with the date, then allow it in `appintent_catalog.py` and `validate_shortcut.py`.

## 9. Adding an app or refreshing the catalog

If the user asks for an app that is not in the catalog, say so and offer to add it. The full procedure, the safety rules (no passwords through the agent, never purchase) and the known pitfalls are in `EXTRACTING_APP_INTENTS.md`. Do not start an extraction without the user's agreement.
