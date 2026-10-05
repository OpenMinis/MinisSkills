# Template Mapping

## Purpose

Map high-frequency requests to:

- Task label
- Applicable recipe
- Preferred action patterns
- Common XML snippets
- Default delivery mode

This shortens planning time from natural language to XML.

## Mapping Table

| Request type | Task label | Preferred recipe | Key patterns | Common snippets | Default delivery |
|---|---|---|---|---|---|
| Quickly record text to a single destination | `shortcut-native` | `collect_text_then_write` | `ask_text`, `write_target`, `show_notification` | Ask, Append/Create Note, Add Reminder, Notification | `build-and-validate` |
| Write the same input to multiple destinations | `shortcut-native` / `shortcut-hybrid` | `collect_text_then_choose_destination` | `ask_text`, `menu_select`, `branch_write` | Ask, Menu, destination snippets | `build-and-validate` |
| Process shared input | `shortcut-native` / `shortcut-hybrid` | `share_input_then_process` | `share_input`, `transform`, `output` | Share input related snippets | `build-and-validate` |
| Query and show result | `shortcut-native` | `query_then_show` | `ask_or_context`, `request_or_native_query`, `show_result` | Ask, URL/HTTP, Text, Show Result | `build-and-validate` |
| Build a URI and open the target | `shortcut-native` / `shortcut-hybrid` | `construct_and_open_uri` | `url_encode`, `url`, `open_url` | URL Encode, URL, Open URL | `build-and-validate` |
| Open a target after completing a task | `shortcut-native` / `shortcut-hybrid` | `task_then_followup` | `core_task`, `followup_action` | destination + Open URL/App | `build-and-validate` |
| Shortcut as entry point only | `shortcut-hybrid` | `hybrid_launcher` | `collect_input`, `handoff`, `notify` | Ask/Share + handoff | `draft-only` / `build-and-validate` |

## Usage Rules

1. Do route decision first
2. Then find the closest request type in this table
3. After choosing a recipe, move on to `COMMON_PATTERNS.md` and `XML_SNIPPET_PATTERNS.md`
4. If a request matches multiple types, choose the primary recipe in the order "entry → destination → follow-up behavior"

## Don't Use It This Way

- Do not skip the route decision and apply a recipe directly
- Do not treat the mapping table as a case library
- Do not generate XML straight from the table before boundaries are clarified
