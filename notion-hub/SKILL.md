---
name: notion-hub
version: 1.0.0
description: |
  Read and write Notion data using Python + notion-client SDK. Authenticated via NOTION_API_KEY env var.
  Supports search, page CRUD (Markdown↔Blocks bidirectional conversion), database schema/query/create/add-row,
  block-level operations (append/update/delete), and comments.
  Trigger this skill whenever the user mentions "Notion", "notion", "notion-hub", "Notion page",
  "Notion database", "read Notion", "write Notion", "Notion API", or any scenario requiring
  programmatic read/write access to Notion data.
---

# Notion Hub

Read/write Notion via `notion-client` Python SDK. All operations through a single CLI script.

## Prerequisites

- **Environment variable**: `NOTION_API_KEY` — Notion Internal Integration Token
  - If not set, prompt user to create: [Set NOTION_API_KEY](minis://settings/environments?create_key=NOTION_API_KEY&create_value=)
  - Get token at: https://www.notion.so/my-integrations
- **uv**: The script uses uv inline script metadata (`notion-client>=3.0.0`, `httpx>=0.27`). Dependencies are auto-installed on first `uv run`, no manual pip install needed.
- **Integration access**: The integration must be connected to target pages/databases in Notion UI (Share → Connections → add integration)

## CLI Script

Path: `/var/minis/skills/notion-hub/scripts/notion_hub.py`

Run: `uv run --script --cache-dir /root/.cache/uv /var/minis/skills/notion-hub/scripts/notion_hub.py <command> [options]`

Alias for brevity:
```sh
NH="uv run --script --cache-dir /root/.cache/uv /var/minis/skills/notion-hub/scripts/notion_hub.py"
```

## Commands Reference

### Search & Discovery

```sh
# Search everything
$NH search "meeting notes"
$NH search "project" --filter page
$NH search --filter database
$NH search "Q1" --sort descending --limit 5

# List users / get bot info
$NH users
$NH users --me
```

### Pages — Read

```sh
# Get page properties (compact)
$NH page-get <page_id_or_url>
$NH page-get <page_id> --raw  # full API response

# Read page content as Markdown (best for AI consumption)
$NH page-read <page_id>
$NH page-read <page_id> --depth 5  # deeper recursion
$NH page-read <page_id> -o /var/minis/workspace/page.md  # save to file

# Accepts Notion URLs directly:
$NH page-read "https://notion.so/My-Page-abc123def456..."
```

### Pages — Write

```sh
# Create page under another page
$NH page-create --page-id <parent_id> --title "New Page" --icon "📝"

# Create page in a database (= add row with content)
$NH page-create --database-id <db_id> --properties '{"Name":{"title":[{"text":{"content":"Task 1"}}]}}'

# Write Markdown content to a page
$NH page-write <page_id> --text "# Hello\n\nThis is a paragraph.\n\n- Item 1\n- Item 2"

# Write from file
$NH page-write <page_id> --file /var/minis/workspace/content.md

# Replace all existing content
$NH page-write <page_id> --text "Fresh content" --replace

# Update page properties
$NH page-update <page_id> --properties '{"Status":{"status":{"name":"Done"}}}'
$NH page-update <page_id> --icon "✅"
$NH page-update <page_id> --archived true  # archive page
```

### Databases

```sh
# Get database schema (shows all properties, types, select options)
$NH db-get <database_id>
$NH db-get <database_id> --raw

# Query database rows
$NH db-query <database_id>
$NH db-query <database_id> --limit 20

# Query with filter
$NH db-query <database_id> --filter '{"property":"Status","status":{"equals":"In Progress"}}'

# Query with sort
$NH db-query <database_id> --sorts '[{"property":"Created","direction":"descending"}]'

# Compound filter
$NH db-query <db_id> --filter '{"and":[{"property":"Status","status":{"equals":"Done"}},{"property":"Priority","select":{"equals":"High"}}]}'

# Quick add a row (auto-detects property types from schema)
$NH db-add-row -d <database_id> --props '{"Name":"My Task","Status":"In Progress","Priority":"High","Due Date":"2024-03-15"}'
$NH db-add-row -d <database_id> --title "Simple row with just a title"

# Create a new database
$NH db-create --page-id <parent_page_id> --title "Task Tracker" --properties '{
  "Name": {"title": {}},
  "Status": {"status": {}},
  "Priority": {"select": {"options": [{"name":"High"},{"name":"Medium"},{"name":"Low"}]}},
  "Due Date": {"date": {}},
  "Tags": {"multi_select": {"options": [{"name":"Bug"},{"name":"Feature"}]}},
  "Assignee": {"people": {}},
  "Done": {"checkbox": {}}
}'

# Update database schema
$NH db-update <db_id> --title "New Title"
$NH db-update <db_id> --properties '{"New Column": {"rich_text": {}}}'
```

### Blocks (Page Content)

```sh
# Get top-level blocks of a page
$NH blocks-get <page_id>
$NH blocks-get <page_id> --raw

# Get ALL blocks recursively (full page tree)
$NH blocks-get-all <page_id>
$NH blocks-get-all <page_id> --depth 5

# Append content
$NH block-append <page_id> --text "A new paragraph"
$NH block-append <page_id> --text "Item A\\nItem B\\nItem C" --type bulleted_list_item
$NH block-append <page_id> --blocks '[{"type":"heading_2","heading_2":{"rich_text":[{"text":{"content":"Section"}}]}},{"type":"paragraph","paragraph":{"rich_text":[{"text":{"content":"Content here"}}]}}]'

# Update a specific block
$NH block-update <block_id> --content '{"paragraph":{"rich_text":[{"text":{"content":"Updated text"}}]}}'

# Delete a block
$NH block-delete <block_id>
```

### Comments

```sh
# List comments on a page
$NH comments-list <page_id>

# Add a comment to a page
$NH comment-create "This looks good!" --page-id <page_id>

# Reply in a discussion thread
$NH comment-create "Agreed" --discussion-id <discussion_id>
```

## Notion Filter Syntax Quick Reference

```json
// Text property
{"property": "Name", "rich_text": {"contains": "keyword"}}

// Select
{"property": "Status", "select": {"equals": "Done"}}

// Multi-select
{"property": "Tags", "multi_select": {"contains": "Bug"}}

// Status
{"property": "Status", "status": {"equals": "In Progress"}}

// Checkbox
{"property": "Done", "checkbox": {"equals": true}}

// Date
{"property": "Due", "date": {"before": "2024-04-01"}}
{"property": "Due", "date": {"on_or_after": "2024-01-01"}}

// Number
{"property": "Score", "number": {"greater_than": 80}}

// Compound (AND)
{"and": [{"property": "Status", "status": {"equals": "Done"}}, {"property": "Priority", "select": {"equals": "High"}}]}

// Compound (OR)
{"or": [{"property": "Status", "status": {"equals": "Done"}}, {"property": "Status", "status": {"equals": "Archived"}}]}
```

## Notion Sort Syntax

```json
[{"property": "Created", "direction": "descending"}]
[{"property": "Name", "direction": "ascending"}]
[{"timestamp": "last_edited_time", "direction": "descending"}]
```

## Property Value Syntax for db-add-row --props

The `--props` JSON maps property names to simple values. The script auto-detects types from the database schema:

| Type | Value format | Example |
|------|-------------|---------|
| title | string | `"My Title"` |
| rich_text | string | `"Some text"` |
| number | number | `42` |
| select | string (option name) | `"High"` |
| multi_select | comma-separated string or array | `"Bug,Feature"` or `["Bug","Feature"]` |
| status | string (status name) | `"In Progress"` |
| date | ISO date string or {start, end} | `"2024-03-15"` |
| checkbox | boolean | `true` |
| url | string | `"https://..."` |
| email | string | `"a@b.com"` |
| relation | comma-separated IDs or array | `"id1,id2"` |
| people | comma-separated user IDs | `"user_id"` |
| files | URL string or array of URLs | `"https://file.png"` |

## Workflow Tips

1. **First time**: Run `$NH search` or `$NH search --filter database` to discover accessible pages/databases and get their IDs.
2. **Before writing to a database**: Run `$NH db-get <id>` to see the schema (property names, types, select options).
3. **Reading a page**: Use `page-read` for Markdown output — much more readable than raw blocks.
4. **Writing a page**: Use `page-write --text` with Markdown — the script auto-converts to Notion blocks.
5. **IDs**: Both raw UUIDs and full Notion URLs are accepted for all ID parameters.
6. **Pagination**: All list/query commands auto-paginate. Use `--limit` to cap results.

## Error Handling

All errors return `{"error": "..."}` JSON. Common issues:
- 401: Invalid or expired token
- 403: Integration not connected to the target page/database
- 404: Page/database not found or not accessible
- 429: Rate limited (auto-retry is not implemented; wait and retry)

## Security Notes

- **NOTION_API_KEY**: Never echo, print, or expose the token value in conversation. Always reference via `$NOTION_API_KEY`.
- **User emails**: The `users` command auto-masks email addresses (e.g. `w***3@gmail.com`). Do not attempt to retrieve or display full emails.
- **File URLs**: Notion internal file URLs contain signed AWS tokens. The script auto-strips these from Markdown/block output. If you need to download a file, use `blocks-get --raw` and handle the URL in a script without printing it.
- **Recursion depth**: `blocks-get-all` and `page-read` cap at depth 10 to prevent API call storms.
