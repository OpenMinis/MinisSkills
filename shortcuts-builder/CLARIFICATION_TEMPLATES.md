# Clarification Templates

> Present these questions to the user in the user's own language; the English below is the canonical template.

## Purpose

When a request has key ambiguities, use as few questions as possible to pin down the implementation boundary, avoiding a wrong start and later rework.

## Applicable Conditions

Enter clarification when any one of these holds:

- The input method is unclear
- The output target is unclear
- The write mode is unclear
- The execution order is unclear
- The behavior after completion is unclear
- Whether external dependencies are acceptable is unclear

## How to Ask

Prefer the `user_ask` tool; `scripts/render-clarification --json '<request>'` emits the questions in its shape (recommended option first, `default` set to it, at most 4 per call). The fixed text format below is the fallback when `user_ask` is unavailable.

- On `timeout`, proceed with the `default` (recommended) option and say which one was applied.
- On `delegated`, use the recommended option and state the assumption.
- On `dismissed`, do not ask again.
- Never let a timeout stand in for consent to sign, upload to a third party, or do anything irreversible: those questions have no default.

## Execution Rules

- Each time, ask only questions that would change the implementation route
- The number of questions is determined by the number of key ambiguities, not artificially capped at 1–3
- Every question uses the fixed multiple-choice format
- A recommended flow must be given after the questions
- Text the user can copy directly to confirm must be given after the questions
- Do not enter XML generation before clarification is done

## Fixed Output Format

```text
My understanding of the flow: ……

1. Question 1
• A: Answer 1
• B: Answer 2
• C: Answer 3

2. Question 2
• A: Answer 1
• B: Answer 2
• C: Answer 3

Recommended flow: ……
Copy to confirm: Follow the recommended flow: 1A, 2B.
```

## Question Dimensions

### 1. Entry Point

```text
1. Where does this shortcut start from?
• A: Manual run
• B: Runs after receiving content from the share sheet
• C: Widget, automation, or another entry point
```

### 2. Input Method

```text
2. What is the main input method?
• A: A prompt dialog for manual input
• B: Read the clipboard or the current selection
• C: Receive external input such as a URL, image, or file
```

### 3. Target Object

```text
3. Where should the result be written or output?
• A: A native system app
• B: A third-party app
• C: A file, URL, or the share sheet
```

### 4. Write Mode

```text
4. How should the content be handled at the target?
• A: Create a new item or object
• B: Write to a fixed object
• C: Choose an object each time before writing
```

### 5. Execution Order

```text
5. What is the order of the key steps?
• A: End right after the core task is done
• B: Show the result after the core task is done
• C: After the core task, continue by opening the target, jumping to a page, or running the next step
```

### 6. Accepted Scope of External Dependencies

```text
6. If a pure shortcut is unstable, is an alternative path acceptable?
• A: Only a pure shortcut
• B: Shortcut + URL Scheme / third-party actions
• C: Hybrid of shortcut + Minis / external services
```

## How to Write the Recommended Flow

Keep only the key stages in the recommended flow; do not write expanded explanations.

Recommended:

```text
Recommended flow: Manual run → Get input → Write to target → Notify completion
```

Not recommended:

```text
Recommended flow: First we pop up an input box, and then depending on your choice we may……
```

## How to Write the Copy-to-Confirm Text

Recommended:

```text
Copy to confirm: Follow the recommended flow: 1A, 2A, 3B, 4B, 5B.
```

If there are defaults:

```text
Copy to confirm: Follow the recommended flow: 1A, 2A, 3B, 4B, 5B; the default target follows the current configuration.
```

## Typical Trigger Cases

- "Make me a shortcut" with no mention of input and output
- One request could map to several action chains
- The target app is clear, but the write mode is not
- The target is clear, but the execution order is not
- It is unclear whether to open an app or jump to a page after completion

## Conditions for Skipping Clarification

You can build directly when all of the following hold:

- The target is clear
- The input is clear
- The output is clear
- The order is clear
- Whether external dependencies are acceptable is clear

If the missing information only affects defaults and not the route, state the default assumption and continue.
