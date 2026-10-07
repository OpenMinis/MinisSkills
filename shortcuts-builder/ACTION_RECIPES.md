# Action Recipes

## Purpose

Provide skeletons of high-frequency action chains for quickly choosing an implementation route. Recipes describe structure, not specific cases.

## Recipe Catalog

| Recipe | Applicable scenario | Standard action chain |
|---|---|---|
| `collect_text_then_write` | Get a piece of text and write it to a single destination | `ask_text → write_target → notify` |
| `collect_text_then_choose_destination` | The same input can be written to multiple destinations | `ask_text → choose_menu → branch_write → notify` |
| `share_input_then_process` | Receive external content from the share sheet, then process it | `share_input → transform → output` |
| `query_then_show` | Take input parameters, then query and show the result | `ask_or_context → request_or_native_query → format → show` |
| `construct_and_open_uri` | Build a deep link and open it | `prepare_value → urlencode → url → open_url` |
| `task_then_followup` | Continue with follow-up actions after the core task | `core_task → followup_action` |
| `hybrid_launcher` | Shortcut acts as the entry point; complex processing is delegated to external capabilities | `collect_input → handoff → optional_notify` |

## Recipe Details

### `collect_text_then_write`

Applies to:

- Recording to system notes
- Creating reminders
- Writing to a fixed file
- Writing to a third-party note app

Key points:

- Input is usually `ask_text`
- The write mode must be decided first: create new, fixed object, or choose the object first
- Whether to notify or jump afterward must be confirmed separately

### `collect_text_then_choose_destination`

Applies to:

- The same input may land in multiple destinations
- The action chains differ between destinations, but the input is the same

Key points:

- First determine whether the set of destinations is fixed
- The number of branches should match the menu items one-to-one
- Each branch should independently complete its write and wrap-up

### `share_input_then_process`

Applies to:

- Share a webpage, image, file, or text, then process it

Key points:

- First confirm the type of shared input
- Then confirm whether processing means extract, convert, save, or forward

### `query_then_show`

Applies to:

- Weather, exchange rate, calendar, basic API queries

Key points:

- Prefer native query actions, then simple two-way HTTP
- When showing results, first produce the final readable text, then display or notify

### `construct_and_open_uri`

Applies to:

- The target app provides write, open, or jump capability via URI / URL Scheme

Key points:

- Dynamic parameters should go through `url_encode` first
- Do not hand-compute variable positions in `WFTextTokenString`
- When the target needs to be opened, use `open_url` as one of the last steps

### `task_then_followup`

Applies to:

- Automatically open the target after recording
- Continue to share after saving
- Jump to the next step after completion

Key points:

- First confirm "whether to continue with an action after completion"
- Follow-up is not default behavior; add it only when the user explicitly needs it

### `hybrid_launcher`

Applies to:

- The shortcut itself is not suited to carry all the logic
- Web processing, downloaders, external scripts, signing, or complex data processing is needed

Key points:

- The shortcut handles the entry point, parameter collection, and result display
- Complex execution is delegated to Minis or external services
- If the user only accepts a pure shortcut, do not apply this recipe by default

## Recipe Selection Order

1. First look at the input type
2. Then the destination
3. Then whether there are branches
4. Then whether follow-up actions are needed
5. Finally decide whether to switch to Hybrid

## Usage Limits

- Recipes cannot replace necessary clarification
- Recipes cannot override the target app's specific parameter validation
- The same recipe can bind to different destinations and should not be tied to the name of a single app