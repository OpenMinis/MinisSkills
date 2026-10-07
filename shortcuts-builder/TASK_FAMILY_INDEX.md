# TASK_FAMILY_INDEX

## Purpose

Organize high-frequency requests by task family to lower routing cost and avoid re-deciding "how this kind of thing is usually done" each time.

## Task Families

### 1. Recording

Typical targets:
- Notes
- Reminders
- Files
- Third-party note apps

Common structures:
- `ask_text`
- `share_input`
- `menu_select`
- `write_target`
- `show_notification`

Common recipes:
- `collect_text_then_write`
- `collect_text_then_choose_destination`
- `task_then_followup`

### 2. Query

Typical targets:
- Weather
- Calendar
- Exchange rates
- Simple APIs
- Local information extraction

Common structures:
- `ask_or_context`
- `request_or_native_query`
- `parse`
- `show_result`

Common recipes:
- `query_then_show`

### 3. Sharing

Typical targets:
- Share text
- Share images
- Share files
- Send after taking a screenshot

Common structures:
- `share_input`
- `transform`
- `share_output`

Common recipes:
- `share_input_then_process`

### 4. Navigation / Jump

Typical targets:
- Open an app
- Deep link to a page
- Open the target after writing
- Invoke third-party actions

Common structures:
- `prepare_value`
- `url_encode`
- `open_url` / `open_app_scheme`

Common recipes:
- `construct_and_open_uri`
- `task_then_followup`

### 5. Hybrid

Typical targets:
- Start complex downloads
- Start web processing
- Trigger Minis or external-service workflows
- Invoke complex scripts, signing, or conversion capabilities

Common structures:
- `collect_input`
- `handoff`
- `notify`

Common recipes:
- `hybrid_launcher`

### 6. Minis-Enhanced

Typical targets:
- Expose Minis CLI tool capabilities as shortcuts
- Trigger Minis AI, perception, health, home, and other capabilities via shortcuts
- Shortcut as entry point → Minis executes → result written back to the system

Conditions for use:
- The task's core capability lives in `apple-*` or `minis-*` commands, not in native Shortcuts actions
- Or the task needs to combine multiple Minis commands into a processing pipeline

Common entry points:
- `share_input` (triggered by sharing; passes file/URL/text to Minis)
- `ask_text` (manual input, used as a Minis command argument)
- `clipboard_in` (read clipboard content and hand it to Minis)

Common Minis backend capabilities (see `MINIS_CAPABILITIES.md`):
- AI perception: `apple-vision` (OCR/barcode/image classification), `apple-nlp` (entity recognition/sentiment analysis), `apple-speech` (speech to text)
- Health tracking: `apple-healthkit` (steps/heart rate/sleep/workout summaries)
- Smart home: `apple-homekit` (device control/scene execution)
- Information lookup: `apple-weather`, `apple-location`, `apple-maps`
- Web interaction: `minis-browser-use` (screenshots/content extraction/form filling)
- Media management: `apple-photos` (export/import/search), `apple-media` (music control)
- Self-interaction: `minis-sessions-cli` (conversation history search/automated conversations), `minis-model-use` (AI model invocation)

Common recipes:
- `hybrid_launcher`
- `minis_query_then_show`
- `minis_process_then_write`

## Order of Use

1. First identify which family the task belongs to
2. Then pick a common recipe under that family
3. If the user explicitly mentions Minis, check `MINIS_CAPABILITIES.md` to locate the specific tool
4. Then look up patterns and snippets
5. Finally proceed to XML generation
