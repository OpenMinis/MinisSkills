# Routing Framework

## Goal

First turn a natural-language task into a **task spec** and an **implementation route**, then decide whether to generate shortcut XML.

## Standard Task Spec

Before writing XML, normalize the request into this set of fields:

- `goal`: what the user actually wants to accomplish
- `trigger`: manual run, share sheet, Home Screen, widget, Siri, automation
- `input`: text, URL, image, file, location, time, clipboard, share input, no input
- `transform`: concatenate, extract, judge, loop, format, filter, network request, file handling
- `output`: display, notify, save, append, share, open, send, call another app
- `destination`: system app, file, URL Scheme, third-party action, external service
- `permissions`: location, photos, Reminders, Notes, network, file access, etc.
- `dependencies`: target app, plugin, URL Scheme, API, cookie, login state
- `interaction`: fully automatic, minimal interaction, multi-step interaction
- `runtime`: short foreground task, redirects acceptable, whether external network is allowed
- `delivery_mode`: draft only, deliver after validation, full signed delivery

If these fields are still unclear, do not write XML directly.

## Implementation Route Priority

By default, choose the implementation route in this order:

1. **Native WorkflowKit actions**
2. **Documented AppIntents**
3. **Stable URL Scheme / x-callback-url**
4. **Verified third-party Shortcuts actions**
5. **Minis command enhancement (see `MINIS_CAPABILITIES.md`)** ← new
6. **Hybrid execution: shortcut + Minis / external service**
7. **Not recommended as a shortcut; have Minis execute directly**

## When to Prefer a Shortcut

Tasks suited to Shortcut-native usually have these traits:

- Short foreground flow
- Clear user interaction
- Supported by existing system actions
- Output target is a common object such as Reminders, Notes, Photos, share, notification, URL, or files
- Simple network logic, usually just `Get Contents of URL` and basic JSON handling
- Low dependence on browser login state, cookies, or complex web rendering

## When to Prefer a Hybrid Flow

Tasks suited to **Hybrid** usually have these traits:

- The shortcut handles entry, interaction, and dispatch
- Minis handles complex downloads, web processing, signing, file conversion, and script execution
- A third-party signing service or remote service is needed
- The user still wants a shortcut as the final reusable entry point

**Minis command enhancement** is a subset of Hybrid, triggered only when the user explicitly mentions "use Minis", "go through Minis", or "can Minis do it". In that case, consult `MINIS_CAPABILITIES.md` to locate tools:
- AI perception (OCR, image classification, face detection, NLP, speech recognition)
- Health data (HealthKit query/write)
- Smart home (HomeKit control/scenes)
- Web interaction (browser screenshots, content extraction, form filling)
- Media handling (photo export/import, music control)
- System interaction (clipboard, device info, notifications)

## When Not to Force a Shortcut

In the following cases, default to having Minis execute directly rather than forcing a Shortcuts build:

- Needs complex web scraping, browser login state, cookies, or anti-bot bypass
- Needs long background tasks or heavy file processing
- Depends on unstable web structures or private interfaces
- The main work is shell, Python, downloaders, transcoders, or crawlers
- Generating a shortcut would only add maintenance cost without clearly improving reuse value

If the user still wants a shortcut for such a task, prefer a **launcher / hybrid shortcut**; do not pretend everything can be done in pure Shortcuts.

## Action Planning Order

First split the task into phases, then map to actions:

1. **Input acquisition**: Ask / Share Sheet / Clipboard / Choose / Date / URL
2. **Context preparation**: variables, dictionaries, defaults, branch conditions
3. **Core processing**: text handling, filtering, HTTP requests, lists, loops, conditionals
4. **Result destination**: Reminders, Notes, files, URL, notification, share, third-party app
5. **Wrap-up actions**: show result, confirmation message, open target, share artifact

Do not think about XML details first; get the action chain clear first.

## Failure Degradation Order

When a route has insufficient evidence or is too costly to implement, degrade in this order:

1. Native action → AppIntent
2. AppIntent → URL Scheme
3. URL Scheme → third-party action
4. Pure shortcut → hybrid execution
5. Complete artifact → draft / validated XML first
6. Fully automatic → minimal necessary clarification

## Minimal Clarification Rules

When the natural-language description is **vague, lacks boundaries, lacks a default destination, or lacks an interaction method**, enter clarification first instead of generating XML directly.

Ask the user only when this information is missing:

- The target app or destination is missing, so the action routes would be entirely different
- Necessary environment info is missing, such as the default target identifier, default Reminders list name, third-party app target parameters, or an API key
- Whether third-party services are acceptable would directly change the signing or implementation route
- Different interpretations would lead to clearly different behavior in the artifact
- The input method is unclear, e.g. manual input, share input, clipboard, URL, or file
- The write mode is unclear, e.g. create new, append, overwrite, pick an existing object, or write to a default object
- The run method is unclear, e.g. manual tap, Home Screen icon, share sheet, widget, or automation trigger

### Clarification Strategy

- First give a **minimal spec draft**, then ask the key questions.
- Questions may only cover ambiguities that would change the implementation route; do not turn every defaultable item into a question.
- If a stable default exists, you may state the default assumption and continue; if the default would noticeably change the user experience, you must ask first.
- If the target object has several reasonable interpretations, list the candidate boundaries for the user to choose from rather than deciding for them.
- Clarification questions use the fixed multiple-choice template by default, not free-form prose follow-ups.
- The number of questions is determined by the number of key ambiguities, not artificially capped at 1–3.
- The number of options per question is determined by the question itself, not forced to 3.
- After asking, you must attach a recommended flow and provide a line of text the user can copy directly to confirm.

### Fixed Question Template

```text
1. Question 1
• A: Answer 1
• B: Answer 2
• C: Answer 3

2. Question 2
• A: Answer 1
• B: Answer 2
• C: Answer 3
```

### Recommended-Flow Output After Questions

After the questions, add two parts:

1. **Recommended flow**: give the single most recommended implementation route.
2. **Copy-to-confirm text**: give a one-line text the user can reply with directly.

Format example:

```text
Recommended flow: A → B → C
Copy to confirm: Follow the recommended flow: 1A, 2B, 3C.
```

### Typical Cases That Must Be Asked First, Not Generated Directly

- "Save it to Notes" — does not say whether to create a new note, append to a fixed note, or choose a note each time
- "Add to Reminders" — does not say the default list, title format, or whether a time/date is needed
- "Send to a third-party app" — does not say the target object, write parameters, or whether the plugin or URI capability is installed
- "Download a video from some platform" — does not say whether Hybrid, third-party services, web login state, or external dependencies are acceptable

For other information, proceed with reasonable defaults.

## Execution Modes

- `draft-only`: output only the XML draft
- `build-and-validate`: output the draft and complete local validation
- `full-delivery`: generate, validate, sign, and deliver the artifact

Defaults:
- When first designing a complex task, start with `build-and-validate`
- When the user explicitly wants the final file, then use `full-delivery`

## Result Assessment

Before saying "this task can be built as a shortcut", confirm at least three things:

- Whether the route is clear
- Whether the key actions have supporting evidence
- Whether the final destination is deliverable

If only the first two are met, say "a draft can be produced / can be validated first"; do not claim the artifact is deliverable.
