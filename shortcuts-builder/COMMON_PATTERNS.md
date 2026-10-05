# Common Patterns

## Purpose

Provide a composable classification of high-frequency patterns for quickly breaking natural-language requests into action chains.

## Pattern Categories

| Category | Pattern | Purpose | Common actions |
|---|---|---|---|
| Input | `ask_text` | Manual text input | Ask for Input |
| Input | `ask_number` | Manual number input | Ask for Input |
| Input | `ask_date` | Date or date-time input | Ask for Input |
| Input | `share_input` | Receive shared input | Extension Input |
| Input | `clipboard_in` | Read clipboard | Get Clipboard |
| Input | `external_input` | Receive URL, image, or file | Share / Detect / File |
| Context | `current_location` | Read current location | Get Current Location |
| Context | `current_date` | Read current time | Current Date |
| Control | `menu_select` | Fixed branches | Choose from Menu |
| Control | `list_select` | Choose from a list | Choose from List |
| Control | `if_guard` | Conditional check | If |
| Control | `repeat_each` | Iterate over a list | Repeat with Each |
| Control | `dictionary_flow` | Build dictionary and get values | Dictionary / Get Dictionary Value |
| Data | `text_template` | Compose result text | Text |
| Data | `text_replace` | Text replacement | Replace Text |
| Data | `regex_extract` | Rule-based extraction | Match Text |
| Data | `json_request` | Network request | Get Contents of URL |
| Data | `json_parse` | Parse JSON | Get Dictionary from Input |
| Data | `url_encode` | Encode URL parameters | URL Encode |
| Output | `show_result` | Show result | Show Result |
| Output | `show_notification` | Notify on completion | Notification |
| Output | `share_output` | Share result | Share |
| Output | `open_target` | Open target page or app | Open URL / Open App |
| Destination | `write_system_note` | Write to system notes | Find Notes / Append to Note / Create Note |
| Destination | `write_reminder` | Create or edit reminders | Add New Reminder / Set Reminder |
| Destination | `write_file` | Write to file | Save File / Append File |
| Destination | `write_external_note_app` | Write to third-party note app | URI / third-party actions |
| Hybrid | `launcher_shortcut` | Shortcut serves only as entry point | Ask / Share + Handoff |
| Hybrid | `handoff_result` | Hand external processing result back to the shortcut | Open File / Open URL / Share |
| Minis | `minis_query` | Query data via Minis commands | apple-healthkit / apple-weather / apple-location etc. |
| Minis | `minis_process` | Process input via Minis commands | apple-vision / apple-nlp / apple-speech etc. |
| Minis | `minis_hybrid_write` | Write back to the system after Minis processing | Minis command + apple-reminders / apple-calendar / apple-photos |

## Selection Principles

### 1. Choose the input pattern first

Determine the entry point and input first, then decide the subsequent route. If the input is unclear, do not proceed to generation.

### 2. Then choose the destination pattern

Determine the final destination first, then add control and data processing. Do not write intermediate actions first and then guess the destination.

### 3. Control patterns exist only to solve branching and ordering

If, Menu, and Repeat are all control patterns; introduce them only when the task truly needs branching, conditions, or iteration.

### 4. Don't use external patterns when native actions suffice

Priority order:

1. System native actions
2. Documented AppIntents
3. Stable URI / URL Scheme
4. Third-party actions
5. Hybrid

## Composition Rules

A complete action chain is usually composed in this order:

1. Input pattern
2. Control pattern (optional)
3. Data-processing pattern (optional)
4. Destination pattern
5. Closing output pattern

## Usage Requirements

- Patterns speed up planning; they do not replace boundary clarification
- Keep pattern names abstract; do not tie them to a single case
- If the same pattern is reused across apps, keep the abstract name and bind the target app in the specific task
- For third-party apps, prefer generic pattern names and map the concrete implementation to the app's actual capabilities