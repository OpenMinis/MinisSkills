---
name: shortcuts-builder
description: Build and remix Apple Shortcuts from natural-language automation requests in Minis — routing, clarification, action-chain planning, XML generation, local validation, and signing via a user-chosen backend; suited to system automation, notes, reminders, weather, share, URL, files, and hybrid shortcuts.
---

# Shortcuts Builder

## Language

Reply to the user in the user's language (e.g. Chinese question -> Chinese answer). The skill files themselves are English.

## Goal

Reliably turn natural-language automation requests into one or more of the following results:

- A judgment on whether the task should be built as a shortcut first
- A route choice: pure Shortcuts / Hybrid / not-shortcut-first
- Action-chain planning
- An unsigned XML draft
- Locally validated XML
- A signed `.shortcut` product

This skill is an adaptation of the upstream [`viticci/shortcuts-playground-plugin`](https://github.com/viticci/shortcuts-playground-plugin) (MIT) for Minis on iPhone/iPad. It keeps the upstream knowledge base and methods, and adds Minis-oriented routing, clarification, an environment profile, build checks, and delivery logic. See `UPSTREAM_ATTRIBUTION.md`.

## Quick Path (read this first)

For a typical request, do these in order. Every item is detailed later; this is the map.

1. **Decide the route** (`BUILD_CHECKLIST.md`, `CAPABILITY_DECISION.md`). If the request is not shortcut-first, stop.
2. **Ask what is missing** with `user_ask` (section 4). Use the recommended default on timeout, except for signing and uploads.
3. **Pick each action from the right source.** Look at the identifier prefix:
   - `is.workflow.actions.*` -> first-party classic action -> `ACTION_PARAM_INDEX.md`
   - `com.apple.*` -> first-party App Intent -> `APPINTENTS.md`
   - anything else (`<bundle id>.<Intent>`) -> **third-party App Intent** -> `THIRD_PARTY_INTENTS.md` and `scripts/appintent_catalog.py`
4. **Draft** unsigned XML in `/var/minis/attachments/shortcut/drafts/`, then **validate** (`scripts/validate-shortcut`) until it passes.
5. **Sign only if the user wants a finished file**, after they have chosen a backend. Then verify the file header is `AEA1`.
6. **Report** the route, the action chain, the paths, and anything left for the user (apps to install, parameters to pick in the editor).

## Hard Constraints

- Always use `BUILD_CHECKLIST.md` first to decide whether the conditions to start work are met.
- Always determine the task label first: `shortcut-native`, `shortcut-hybrid`, `not-shortcut-first`.
- Always normalize the request into a task spec before choosing actions or writing XML.
- Always clarify before generating when the request has a key ambiguity.
- Always ask the user's choices with the `user_ask` tool when it is available (see section 4: batches of at most 4, recommended option first and set as `default`). Use the fixed option-style text template only when `user_ask` is unavailable, and end it with a recommended flow and copyable confirmation text. Ask in the user's language.
- Always proceed with the recommended (default) option when a `user_ask` card times out, and say which default was applied. Never apply a default for a `confirm`-type question; a timeout there means do not perform the action.
- Never use a default to choose a signing backend, to approve an upload to a third party (HubSign), or to authorize anything irreversible. Those need an explicit answer.
- Always prefer the most stable, shortest, and easiest-to-validate implementation route.
- Always prefer reusing framework-layer docs, the environment profile, patterns, recipes, and the XML snippet index; do not assemble from scratch every time.
- Always generate unsigned XML first, then run local validation, then decide whether to sign and deliver.
- Always treat the final product directory as `/var/minis/attachments/shortcut/`.
- Always save pre-signing drafts in `/var/minis/attachments/shortcut/drafts/` or the archive directory.
- Always use `scripts/resolve-icon` to set `WFWorkflowIconGlyphNumber` and `WFWorkflowIconStartColor`, unless the user explicitly specifies integer values.
- Always prefer `scripts/placeholder-range` to compute positions when a `WFTextTokenString` contains placeholders.
- Always run the Craig Loop (validate, read the errors, apply targeted fixes, re-validate) with `scripts/validate-shortcut`; at most 5 rounds, and stop if the same error is unchanged for 2 consecutive rounds.
- Always confirm before signing that the user has chosen a signing backend (`sign-shortcut --show-config`). If it is unconfigured (exit code 10), ask the user to pick one of the two backends first (use an interactive question tool if available); never choose HubSign on the user's behalf.
- Always sign with `scripts/sign-shortcut`; the backend is `mac` (the user's own Mac, over SSH) or `hubsign` (third-party; drafts are uploaded).
- Always tell the user when delivering a signed product: the first import shows a system "untrusted shortcut" style prompt, and the user must tap "Allow" / "Import Anyway" once to finish installing.
- Always verify before reporting completion: the file exists, its size is greater than 0, and its header is `AEA1`.
- Never generate XML directly when boundaries, order, or post-completion behavior are unclear.
- Never treat "XML generated" as done; without a product or an explicit delivery status it is not complete.
- Never hard-code one example as the default target; all examples are pattern references only.
- Never invent action identifiers, UUIDs, icon color values, or parameter structures; when unsure, go back to the reference docs.
- Never label a third-party App Intent parameter as verified unless `THIRD_PARTY_INTENTS.md` lists it as verified (text and bool). Other kinds may be written only through `appintent_catalog.py step` (experimental tier, variables for image/file/entity/array/date); name every experimental parameter in the report and ask the user to check it after import. Never invent a literal form for a refused kind.
- Never write an enum whose `value` and `title` name different cases.
- Never push tasks such as complex web scraping, browser login state, downloaders, or transcoders into a pure shortcut by default; switch to Hybrid when necessary.
- Never present signing as a private, local-only step. With `hubsign`, drafts are uploaded to a third-party service: say so plainly and get the user's confirmation (`--i-understand-upload`).
- Never write an SSH password into a file or onto the command line; reference an environment variable by name with `--password-env VARIABLE_NAME`, or use `--key`.

## Scope

Applies to:

- Generating a new shortcut
- Modifying or remixing an unsigned XML shortcut
- Turning a natural-language automation request into a reusable flow
- Completing planning, generation, validation, and on-demand signed delivery in Minis

Does not apply to:

- Only analyzing the repository's value, without generating a shortcut
- Only explaining shortcut concepts, without an artifact
- Decompiling or internally editing an already signed `.shortcut`
- Pure web search tasks
- Tasks clearly better executed directly by Minis than carried by a shortcut

## Directory and Document Layers

### Framework Layer

- `METHODOLOGY.md` ← **Primary entry point: 10-step methodology cheat sheet; read this file first for every build task**
- `BUILD_CHECKLIST.md`
- `CAPABILITY_DECISION.md`
- `ROUTING_FRAMEWORK.md`
- `CLARIFICATION_TEMPLATES.md`
- `COMMON_PATTERNS.md`
- `ACTION_RECIPES.md`
- `TEMPLATE_MAPPING.md`
- `TASK_FAMILY_INDEX.md`
- `XML_SNIPPET_PATTERNS.md`
- `ACTION_PARAM_INDEX.md`
- `KNOWN_PITFALLS.md`
- `ENV_PROFILE.md`
- `STABILITY_NOTES.md`

### Technical Reference Layer

- `BEST_PRACTICES.md`
- `ACTIONS.md`
- `APPINTENTS.md`
- `AUTOMATION_TRIGGERS.md` (OS 27 automation triggers; can only be written with an exported sample)
- `PARAMETER_TYPES.md`
- `PLIST_FORMAT.md`
- `VARIABLES.md`
- `CONTROL_FLOW.md`
- `FILTERS.md`
- `EXAMPLES.md`
- `URL_SCHEMES.md`
- `ICONS_AND_COLORS.md`
- `HEALTHKIT.md`
- `THIRD_PARTY_ACTIONS.md`
- `THIRD_PARTY_INTENTS.md` (**read before using any third-party app step**: step structure, which parameter kinds may be authored, chaining, what is unverified)
- `EXTRACTING_APP_INTENTS.md` (maintainers only: how to extract a new app's intents from its package and refresh the catalog; **not needed to build a shortcut**, read it only when the user asks to add or update an app's intents)
- `TOOLKIT_SNAPSHOT.md`
- `golden-shortcuts/index.jsonl`

### Script Layer

- `scripts/check-local-assets`
- `scripts/profile-summary`
- `scripts/load-env-profile`
- `scripts/preflight-request`
- `scripts/render-clarification`
- `scripts/resolve-icon`
- `scripts/placeholder-range`
- `scripts/validate-shortcut` (the default target is **iOS/iPadOS, OS 27**; no flag is needed for a normal iPhone shortcut. Add `--target-platform macos` only for a Mac-only shortcut, and `--target-os 26` only to check against the older OS)
- `scripts/lookup_action_grounding.py` (look up action parameters/enum values/platform compatibility: `python3 scripts/lookup_action_grounding.py --identifier openapp`; same iOS default)
- `scripts/appintent_catalog.py` (search/show/step over the third-party App Intents catalog: `python3 scripts/appintent_catalog.py search weather`; details in `THIRD_PARTY_INTENTS.md`)
- `scripts/fix-positions`
- `scripts/index-golden`
- `scripts/match-golden`
- `scripts/sign-shortcut` (signing entry point, choose one of two backends; implementation in `sign_shortcut.py`, HubSign channel in `sign_shortcut_via_hubsign.py`)
- `scripts/selftest_minis.py`

## Workflow

### 1. Pre-build Check

First read `BUILD_CHECKLIST.md` and confirm:

- Goal
- Entry point
- Input
- Destination
- Write mode
- Execution order
- Post-completion behavior
- Hybrid acceptance scope

If one is missing and would change the route, stop and clarify first.

### 2. Route Decision

Read `CAPABILITY_DECISION.md` and label the task:

- `shortcut-native`
- `shortcut-hybrid`
- `not-shortcut-first`

**Consult `MINIS_CAPABILITIES.md` to locate tools only when the user explicitly asks to involve Minis (for example "use Minis", "can Minis do this", or "go through Minis"). Otherwise decide the route as usual.**

If it is `not-shortcut-first`, do not proceed to XML generation.

### 3. Task Spec Normalization

Read `ROUTING_FRAMEWORK.md` and break the request into:

- `goal`
- `trigger`
- `input`
- `transform`
- `output`
- `destination`
- `permissions`
- `dependencies`
- `interaction`
- `runtime`
- `delivery_mode`

If the spec is incomplete, do not proceed to generation.

### 4. Necessary Clarification

If the spec lacks key boundaries, use `CLARIFICATION_TEMPLATES.md`, or run directly:

```bash
/var/minis/skills/shortcuts-builder/scripts/preflight-request 'raw user request'
/var/minis/skills/shortcuts-builder/scripts/render-clarification 'raw user request'
```

Requirements:

- Ask only questions that would change the route
- The number of questions follows the number of key ambiguities
- The number of options follows the question itself; it is not fixed at 3
- Ask in the user's language

**Preferred: the `user_ask` tool.** Get the questions ready to send:

```bash
/var/minis/skills/shortcuts-builder/scripts/render-clarification --json 'raw user request'
```

The output has `batches`; each batch is a valid `questions` array for one `user_ask` call (at most 4 questions per call). The recommended option is first and `default` is `"0"`, so the card marks it as recommended. Translate the question and option text into the user's language before sending. Put every needed question in one call; start a second call only when a later question depends on an earlier answer.

Answer handling:

| Result | What to do |
|---|---|
| `answered` / `other` | Use it. `other` text is the user's own words: follow it. |
| `delegated` ("You decide") | Use the recommended option and state that assumption. |
| `timeout` | Proceed with the `default` option, say plainly which default was applied so the user can correct it, and keep the build easy to change. |
| `dismissed` | Do not ask the same question again; if the user's next message answers it, take that as the answer. |
| `unavailable` | Fall back to the text template below. |

Defaults are the most reliable and least surprising route, never an irreversible one. Choose the default yourself when the tool output does not, using the same rule.

**Fallback: text template.** Only when `user_ask` is not available, run `render-clarification` without `--json` and send the fixed option-style template, ending with a recommended flow and copyable confirmation text.

### 5. Read the Environment Profile

Run first:

```bash
/var/minis/skills/shortcuts-builder/scripts/profile-summary
/var/minis/skills/shortcuts-builder/scripts/load-env-profile
```

Read the summary first, then decide whether the full profile is needed. If defaults exist, use them directly; if missing but the route is unaffected, state a default and continue.

### 6. Pattern and Recipe Selection

Read first:

- `TASK_FAMILY_INDEX.md`
- `COMMON_PATTERNS.md`
- `ACTION_RECIPES.md`
- `TEMPLATE_MAPPING.md`

Once the action chain is determined, run `scripts/match-golden` to match the most relevant golden shortcut as a wiring reference:

```bash
/var/minis/skills/shortcuts-builder/scripts/match-golden --actions "action1,action2" --patterns "pattern1,pattern2" --top 2
```

**If the task has been clearly decided to go through Minis (the user asked for it), also confirm in this step:**

- The exact subcommand and parameters of the required Minis command
- The input source (how the shortcut passes user input/files to Minis)
- The output write-back method (how Minis results return to the shortcut: clipboard/file/URL)

Determine:

- Which family the task belongs to
- Input pattern
- Control pattern
- Data-processing pattern
- Destination pattern
- Closing pattern
- Whether a frequent recipe skeleton can be reused directly
- Whether a stable mapping can directly shorten route selection
- If Minis-enhanced, the boundary between the Minis command chain and the shortcut

### 7. Technical Reference Reading

**Check the cheat sheets first**:

1. `ACTION_PARAM_INDEX.md` — confirm the required parameters and serialization of the current action
2. `KNOWN_PITFALLS.md` — confirm whether the current action hits a known pitfall
3. `STABILITY_NOTES.md` — confirm whether a known instability point is hit

**Then read detailed references as needed**:

- `BEST_PRACTICES.md`
- `ACTIONS.md`
- `APPINTENTS.md`
- `THIRD_PARTY_INTENTS.md` (when the flow uses a third-party app's Intent)
- `VARIABLES.md`
- `CONTROL_FLOW.md`
- `FILTERS.md`
- `PARAMETER_TYPES.md`
- `EXAMPLES.md`

Read only the parts the current task needs; do not load all docs at once.

### 8. Action Chain Design

First write a short plan that states:

- Which actions are needed
- Which actions produce variables
- Which actions consume the previous step's output
- Whether Menu / If / Repeat / Dictionary / URL request is needed
- Which parts are done inside Shortcuts, and which are delegated to a URL scheme, a third-party app's App Intent, Minis, or an external web service
- For each third-party app step: look it up with `scripts/appintent_catalog.py` (`search`, then `show`), note its authoring level (`full` / `partial` / `editor-only`), and generate the step with `appintent_catalog.py step`. Prefer a first-party action when one does the job. See `THIRD_PARTY_INTENTS.md`.

### 9. Snippet Skeleton Selection

When a frequent action is hit, read `XML_SNIPPET_PATTERNS.md` first and use the minimal snippet skeleton directly.

### 10. Icon and UUID

- Use `scripts/resolve-icon` to generate the icon and color
- When generating new UUIDs, prefer a stable command or Python
- Do not use placeholder UUIDs

### 11. Draft Generation

Output to:

```text
/var/minis/attachments/shortcut/drafts/<shortcut name>.xml
```

Requirements:

- Complete plist XML
- Not a fragment
- Meets the comment and structure requirements of `BEST_PRACTICES.md`

### 12. Local Validation

Run:

```bash
/var/minis/skills/shortcuts-builder/scripts/validate-shortcut /path/to/draft.xml
```

Before validating, automatically fix placeholder positions:

```bash
/var/minis/skills/shortcuts-builder/scripts/fix-positions /path/to/draft.xml
```

Rules:

- At most 5 rounds
- Stop if the same error is unchanged for 2 consecutive rounds
- Prefer targeted fixes; do not rewrite the whole file

### 13. Delivery Mode Decision

Supported:

- `draft-only`
- `build-and-validate`
- `full-delivery`

For complex new tasks default to `build-and-validate`; use `full-delivery` when the user explicitly wants a finished product.

### 14. Signing

Run only in `full-delivery` mode. First check the backend:

```bash
/var/minis/skills/shortcuts-builder/scripts/sign-shortcut --show-config
```

If `configured` is false (or signing exits with code 10), ask the user to pick one of the two with `user_ask` (an `options` question; put the Mac option first). **A timeout here is not consent: do not sign and do not fall back to HubSign.** Tell the user the build is ready unsigned and ask again later. The HubSign upload also needs its own explicit answer (`--i-understand-upload` only after the user chose it):

| Option | Privacy | Prerequisites |
|---|---|---|
| The user's own Mac (SSH) | Drafts are sent only to the user's own Mac; recommended | A Mac (macOS 12+) with the `shortcuts` command and SSH access; the user must provide an SSH key or put the password in an environment variable |
| HubSign (third-party, free) | Drafts are uploaded to a third-party service and their content is visible to the operator | None, zero configuration |

After the choice, configure once:

```bash
# Mac: pick one of the two (the password is passed only as an env var name; the value is never saved to disk)
scripts/sign-shortcut --setup-mac user@host --password-env MAC_SSH_PASSWORD
scripts/sign-shortcut --setup-mac user@host --key ~/.ssh/id_ed25519
# HubSign: you must first tell the user that drafts will be uploaded; add this flag only after the user agrees
scripts/sign-shortcut --setup-hubsign --i-understand-upload
```

Then sign as usual:

```bash
scripts/sign-shortcut /path/to/draft.xml --name "Shortcut Name"
# Optional: --mode anyone|people-who-know-me (mac backend only), --backend mac|hubsign (temporary override for this run)
```

This step will:

- Archive the draft
- Sign with the chosen backend (the Mac backend uses a temporary directory on the remote side and deletes it after signing)
- Output the `.shortcut` product and verify the header is `AEA1`

When delivering, remind the user: the signing certificate is issued by Apple per signature and is not the user's own developer certificate, so on first import iOS shows a system prompt and the user must tap "Allow" / "Import Anyway" once. This is a normal step, not a fault.

### 15. Final Verification and Report

Minimum verification:

- The product file exists
- The file size is greater than 0
- The file header is `AEA1`

Report contents:

- Route type
- Action chain summary
- Draft path
- Validation status
- If signed, also the product path
- Prerequisites before running
- Which parts depend on the user's environment (for example which third-party apps must be installed)

## Default Output Structure

### Judgment tasks

- Task label
- Main reasons
- Recommended delivery mode

### Generation tasks

- Flow summary
- Main dependencies
- Draft path
- Validation status
- Product path (if any)

### Remix tasks

- What is kept
- What is changed
- New draft path
- Product path (if any)

## Success Criteria

The skill is working as intended if it can:

- Decide first whether the task should be built as a shortcut
- Choose reliably between native / hybrid / not-shortcut-first
- Clarify first, rather than start work, when boundaries are unclear
- Use patterns, recipes, and snippets to shorten planning and generation
- Generate and validate XML grounded in the knowledge base
- Sign and deliver to `/var/minis/attachments/shortcut/` when needed
