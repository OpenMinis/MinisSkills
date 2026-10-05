# Build Checklist

## Purpose

Before generating, confirm that you have enough information to start building.

## Required Checks

| Check | What to confirm | If unclear |
|---|---|---|
| Goal | What the user actually wants to accomplish | Clarify first |
| Entry point | Manual run, share sheet, widget, automation | Clarify first |
| Input | Text, URL, image, file, contextual data | Clarify first |
| Destination | System app, third-party app, file, URL, share sheet | Clarify first |
| Write mode | Create new, write to a fixed object, pick the object first | Clarify first |
| Order | Sequence of the core actions | Clarify first |
| Post-completion behavior | End, notify, open the target, continue to the next step | Clarify first |
| Hybrid scope | Pure Shortcuts, URI/third-party actions, Minis/external services | Clarify first |

## Pre-build Judgment

### Can proceed directly to build

All of the following hold:

- Goal is clear
- Input is clear
- Destination is clear
- Order is clear
- Post-completion behavior is clear

### Must stop and clarify first

Any of the following holds:

- Destination is unclear
- Write mode is unclear
- Order is unclear
- Post-completion behavior is unclear
- It is unclear whether external dependencies are acceptable

## Output Requirements

### When information is sufficient

First output a one-line flow summary (in the user's language):

```text
My understanding of the flow: A → B → C → D
```

### When information is insufficient

Switch to fixed-option clarification (in the user's language):

```text
1. Question 1
• A: Answer 1
• B: Answer 2
• C: Answer 3
• D: Answer 4

Recommended flow: A → B → C
Copy to confirm: fill in the options for the questions above per the recommended flow, then run.
```

## Usage Principles

- This checklist decides "can we start work", not how to implement
- If a missing item would change the route, ask first
- If a missing item only affects defaults, state the default and continue
