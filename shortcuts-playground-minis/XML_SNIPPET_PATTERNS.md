# XML Snippet Patterns

## Purpose

Provide a minimal-structure index for high-frequency actions, reducing the cost of looking up parameters in long documents.

## Order of Use

1. Determine the action chain first
2. Then pick the matching snippet skeleton
3. Then fill in variables and parameters
4. Finally run local validation

## High-Frequency Snippet Index

| Snippet | Action identifier | Required keys | Input wiring notes | Common mistakes |
|---|---|---|---|---|
| Ask / Text | `is.workflow.actions.ask` | `UUID`, `WFAskActionPrompt` | Add `WFInputType = Text` for text input | Missing Prompt |
| Menu / Start | `is.workflow.actions.choosefrommenu` | `GroupingIdentifier`, `WFControlFlowMode=0`, `WFMenuItems` | The start node must have menu items | Empty menu items |
| Menu / Case | `is.workflow.actions.choosefrommenu` | `GroupingIdentifier`, `WFControlFlowMode=1`, `WFMenuItemTitle` | Title must match a menu item | Case title does not match |
| Menu / End | `is.workflow.actions.choosefrommenu` | `GroupingIdentifier`, `WFControlFlowMode=2` | A menu group must be closed | Missing end node |
| Find Notes | `is.workflow.actions.filter.notes` | `UUID`, `WFContentItemFilter` | `WFContentPredicateTableTemplate`; Name uses `Operator=99` | Writing Name as `Operator=4` |
| Append to Note | `is.workflow.actions.appendnote` | `IntentAppIdentifier`, `WFInput`, `WFNote` | Text comes from the previous step's output; Note comes from Find Notes output | `WFNote` not wired |
| Add New Reminder | `is.workflow.actions.addnewreminder` | `UUID`, `WFCalendarItemTitle` | Minimal stable parameter is the title; the list is usually added via `WFCalendarItemCalendar` | Filling in too many optional parameters from the start |
| URL Encode | `is.workflow.actions.urlencode` | `UUID` | Encode dynamic text before embedding it in a URI | Concatenating raw text directly into the URI |
| URL | `is.workflow.actions.url` | `UUID`, `WFURLActionURL` | Prefer `WFTextTokenString` for dynamic content | Wrong placeholder position |
| Open URL | `is.workflow.actions.openurl` | `WFInput` | Input usually comes from the URL action's output | Missing `WFInput` |
| Notification | `is.workflow.actions.notification` | No mandatory fixed minimal keys | Commonly `WFNotificationActionTitle`, `WFNotificationActionBody` | Empty title or body |

## Key Rules

### 1. Find Notes

- `WFContentItemFilter` must be `WFContentPredicateTableTemplate`
- When searching by title, `Name` may only use `Operator = 99`
- `Values.String` uses `WFTextTokenString`

### 2. Append to Note

- `WFInput` is the content to append
- `WFNote` is a Note object, not a title string
- The typical preceding action is `Find Notes`

### 3. Add New Reminder

- For minimal runnable usage, fill in only the title and list
- Complex reminder time, location, and notes are later extensions and should not be added by default

### 4. URI-Type Actions

- Encode all dynamic URI text first
- Do not hand-compute positions in a `WFTextTokenString` containing `￼`
- Always compute positions with:

```bash
/var/minis/skills/shortcuts-playground-minis/scripts/placeholder-range 'text with ￼ placeholder'
```

## Snippet Selection Rules

- Prefer the minimal runnable structure
- Make validation pass first, then add optional parameters
- If an action already has a stable preceding-action combination, use the common combination rather than assembling it in isolation