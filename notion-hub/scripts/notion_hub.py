#!/usr/bin/env -S uv run --script --cache-dir /root/.cache/uv
# /// script
# requires-python = ">=3.10"
# dependencies = ["notion-client>=3.0.0", "httpx>=0.27"]
# ///
"""
notion_hub.py — Comprehensive Notion API CLI for AI-driven management.

Usage:
    uv run --script notion_hub.py <command> [options]

Environment:
    NOTION_API_KEY — Required. Notion Internal Integration Token.

All output is JSON for easy parsing by AI agents.
"""

import os
import sys
import json
import argparse
import httpx
from notion_client import Client, APIResponseError

# ─── Globals ───────────────────────────────────────────────────────────────────

TOKEN = os.environ.get("NOTION_API_KEY", "")
# Use 2022-06-28 API version for full database properties support.
# The 2025-09-03+ versions split properties into data_sources, breaking
# databases.retrieve/update for property schema access.
API_VERSION = "2022-06-28"
notion: Client = None  # initialized in main()

def init_client():
    global notion
    if not TOKEN:
        print(json.dumps({"error": "NOTION_API_KEY environment variable is not set"}))
        sys.exit(1)
    notion = Client(auth=TOKEN, notion_version=API_VERSION)

def out(data):
    """Print JSON output."""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))

def err(msg):
    print(json.dumps({"error": str(msg)}, ensure_ascii=False))
    sys.exit(1)

def api_call(func, *args, **kwargs):
    """Wrap API call with error handling."""
    try:
        return func(*args, **kwargs)
    except APIResponseError as e:
        err(f"Notion API error ({e.status}): {e.body}")
    except Exception as e:
        err(str(e))

# ─── Pagination helper ─────────────────────────────────────────────────────────

def paginate(func, *args, limit=None, **kwargs):
    """Auto-paginate a Notion list/query endpoint. Returns all results."""
    results = []
    has_more = True
    next_cursor = None
    while has_more:
        page_size = min(100, limit - len(results)) if limit else 100
        resp = api_call(func, *args, start_cursor=next_cursor, page_size=page_size, **kwargs)
        results.extend(resp.get("results", []))
        has_more = resp.get("has_more", False)
        next_cursor = resp.get("next_cursor")
        if limit and len(results) >= limit:
            results = results[:limit]
            break
    return results

# ─── Rich text helpers ─────────────────────────────────────────────────────────

def plain_text(rich_text_array):
    """Extract plain text from a rich_text array."""
    if not rich_text_array:
        return ""
    return "".join(rt.get("plain_text", "") for rt in rich_text_array)

def make_rich_text(text):
    """Create a simple rich_text array from a string."""
    return [{"type": "text", "text": {"content": text}}]

def extract_property_value(prop):
    """Extract a human-readable value from a Notion property object."""
    t = prop.get("type", "")
    if t == "title":
        return plain_text(prop.get("title", []))
    elif t == "rich_text":
        return plain_text(prop.get("rich_text", []))
    elif t == "number":
        return prop.get("number")
    elif t == "select":
        sel = prop.get("select")
        return sel.get("name") if sel else None
    elif t == "multi_select":
        return [s.get("name") for s in prop.get("multi_select", [])]
    elif t == "status":
        st = prop.get("status")
        return st.get("name") if st else None
    elif t == "date":
        d = prop.get("date")
        if d:
            return {"start": d.get("start"), "end": d.get("end")}
        return None
    elif t == "checkbox":
        return prop.get("checkbox")
    elif t == "url":
        return prop.get("url")
    elif t == "email":
        return prop.get("email")
    elif t == "phone_number":
        return prop.get("phone_number")
    elif t == "formula":
        f = prop.get("formula", {})
        ft = f.get("type", "")
        return f.get(ft)
    elif t == "relation":
        return [r.get("id") for r in prop.get("relation", [])]
    elif t == "rollup":
        r = prop.get("rollup", {})
        rt = r.get("type", "")
        return r.get(rt)
    elif t == "people":
        return [p.get("name", p.get("id")) for p in prop.get("people", [])]
    elif t == "files":
        files = prop.get("files", [])
        result = []
        for f in files:
            ft = f.get("type", "")
            if ft == "file":
                result.append({"name": f.get("name"), "url": f["file"].get("url")})
            elif ft == "external":
                result.append({"name": f.get("name"), "url": f["external"].get("url")})
        return result
    elif t == "created_time":
        return prop.get("created_time")
    elif t == "created_by":
        return prop.get("created_by", {}).get("name")
    elif t == "last_edited_time":
        return prop.get("last_edited_time")
    elif t == "last_edited_by":
        return prop.get("last_edited_by", {}).get("name")
    elif t == "unique_id":
        uid = prop.get("unique_id", {})
        prefix = uid.get("prefix", "")
        number = uid.get("number", "")
        return f"{prefix}-{number}" if prefix else str(number)
    else:
        return prop.get(t)

def format_page_row(page):
    """Extract a compact summary of a page/database row."""
    props = page.get("properties", {})
    row = {"id": page.get("id"), "url": page.get("url")}
    for name, prop in props.items():
        row[name] = extract_property_value(prop)
    return row

# ─── Block helpers ─────────────────────────────────────────────────────────────

def block_to_text(block):
    """Convert a block to a simplified dict with text content."""
    btype = block.get("type", "")
    data = block.get(btype, {})
    result = {
        "id": block.get("id"),
        "type": btype,
        "has_children": block.get("has_children", False),
    }
    # Extract text from rich_text if present
    if "rich_text" in data:
        result["text"] = plain_text(data["rich_text"])
    if "caption" in data:
        result["caption"] = plain_text(data["caption"])
    # Special types
    if btype == "child_page":
        result["title"] = data.get("title", "")
    elif btype == "child_database":
        result["title"] = data.get("title", "")
    elif btype in ("image", "file", "video", "pdf"):
        ft = data.get("type", "")
        if ft == "file":
            # Strip signed query params from Notion internal URLs
            raw_url = data.get("file", {}).get("url", "")
            result["url"] = raw_url.split("?")[0] if raw_url else ""
        elif ft == "external":
            result["url"] = data.get("external", {}).get("url")
    elif btype == "bookmark":
        result["url"] = data.get("url")
    elif btype == "embed":
        result["url"] = data.get("url")
    elif btype == "link_to_page":
        result["target"] = data.get("page_id") or data.get("database_id")
    elif btype == "table":
        result["table_width"] = data.get("table_width")
        result["has_column_header"] = data.get("has_column_header")
        result["has_row_header"] = data.get("has_row_header")
    elif btype == "table_row":
        cells = data.get("cells", [])
        result["cells"] = [plain_text(cell) for cell in cells]
    elif btype == "code":
        result["language"] = data.get("language")
        result["text"] = plain_text(data.get("rich_text", []))
    elif btype == "equation":
        result["expression"] = data.get("expression")
    elif btype == "to_do":
        result["checked"] = data.get("checked", False)
        result["text"] = plain_text(data.get("rich_text", []))
    elif btype == "toggle":
        result["text"] = plain_text(data.get("rich_text", []))
    elif btype == "callout":
        result["text"] = plain_text(data.get("rich_text", []))
        icon = data.get("icon")
        if icon and icon.get("type") == "emoji":
            result["icon"] = icon.get("emoji")
    return result

# ─── Build property value for page create/update ──────────────────────────────

def build_property_value(ptype, value):
    """Build a Notion property value object from type + value."""
    if ptype == "title":
        return {"title": make_rich_text(str(value))}
    elif ptype == "rich_text":
        return {"rich_text": make_rich_text(str(value))}
    elif ptype == "number":
        return {"number": float(value) if value is not None else None}
    elif ptype == "select":
        return {"select": {"name": str(value)} if value else None}
    elif ptype == "multi_select":
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",")]
        return {"multi_select": [{"name": v} for v in value]}
    elif ptype == "status":
        return {"status": {"name": str(value)} if value else None}
    elif ptype == "date":
        if isinstance(value, str):
            return {"date": {"start": value}}
        elif isinstance(value, dict):
            return {"date": value}
    elif ptype == "checkbox":
        return {"checkbox": bool(value)}
    elif ptype == "url":
        return {"url": str(value) if value else None}
    elif ptype == "email":
        return {"email": str(value) if value else None}
    elif ptype == "phone_number":
        return {"phone_number": str(value) if value else None}
    elif ptype == "relation":
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",")]
        return {"relation": [{"id": v} for v in value]}
    elif ptype == "people":
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",")]
        return {"people": [{"id": v} for v in value]}
    elif ptype == "files":
        if isinstance(value, str):
            value = [value]
        return {"files": [{"type": "external", "name": v.split("/")[-1], "external": {"url": v}} for v in value]}
    else:
        return {ptype: value}

# ─── Block builder ─────────────────────────────────────────────────────────────

def make_block(btype, text="", **kwargs):
    """Create a block object for appending."""
    block = {"type": btype, "object": "block"}
    if btype in ("paragraph", "heading_1", "heading_2", "heading_3",
                 "bulleted_list_item", "numbered_list_item", "quote", "toggle"):
        block[btype] = {"rich_text": make_rich_text(text)}
    elif btype == "to_do":
        block[btype] = {
            "rich_text": make_rich_text(text),
            "checked": kwargs.get("checked", False),
        }
    elif btype == "callout":
        block[btype] = {
            "rich_text": make_rich_text(text),
            "icon": {"type": "emoji", "emoji": kwargs.get("icon", "💡")},
        }
    elif btype == "code":
        block[btype] = {
            "rich_text": make_rich_text(text),
            "language": kwargs.get("language", "plain text"),
        }
    elif btype == "divider":
        block[btype] = {}
    elif btype == "bookmark":
        block[btype] = {"url": text}
    elif btype == "embed":
        block[btype] = {"url": text}
    elif btype == "image":
        block[btype] = {"type": "external", "external": {"url": text}}
    elif btype == "equation":
        block[btype] = {"expression": text}
    elif btype == "table_of_contents":
        block[btype] = {}
    else:
        block[btype] = {"rich_text": make_rich_text(text)}
    return block

# ═══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Search ────────────────────────────────────────────────────────────────────

def cmd_search(args):
    """Search pages and databases."""
    kwargs = {}
    if args.query:
        kwargs["query"] = args.query
    if args.filter:
        kwargs["filter"] = {"value": args.filter, "property": "object"}
    if args.limit:
        kwargs["page_size"] = min(args.limit, 100)
    if args.sort:
        kwargs["sort"] = {
            "direction": args.sort,
            "timestamp": "last_edited_time",
        }
    resp = api_call(notion.search, **kwargs)
    results = resp.get("results", [])
    items = []
    for r in results:
        obj_type = r.get("object")
        item = {
            "id": r.get("id"),
            "object": obj_type,
            "url": r.get("url"),
            "created_time": r.get("created_time"),
            "last_edited_time": r.get("last_edited_time"),
        }
        if obj_type == "page":
            props = r.get("properties", {})
            for name, prop in props.items():
                if prop.get("type") == "title":
                    item["title"] = plain_text(prop.get("title", []))
                    break
        elif obj_type == "database":
            item["title"] = plain_text(r.get("title", []))
            item["description"] = plain_text(r.get("description", []))
        items.append(item)
    out({"count": len(items), "results": items})

# ─── Users ─────────────────────────────────────────────────────────────────────

def cmd_users(args):
    """List users or get current bot user."""
    if args.me:
        resp = api_call(notion.users.me)
        out(resp)
    elif args.id:
        resp = api_call(notion.users.retrieve, user_id=args.id)
        _redact_user_pii(resp)
        out(resp)
    else:
        results = paginate(notion.users.list)
        for u in results:
            _redact_user_pii(u)
        out({"count": len(results), "users": results})

def _redact_user_pii(user):
    """Redact PII (email) from user objects to prevent leakage into AI context."""
    if "person" in user and "email" in user.get("person", {}):
        email = user["person"]["email"]
        # Keep domain but mask local part: w***3@gmail.com
        if "@" in email:
            local, domain = email.rsplit("@", 1)
            if len(local) > 2:
                masked = local[0] + "***" + local[-1]
            else:
                masked = local[0] + "***"
            user["person"]["email"] = f"{masked}@{domain}"

# ─── Pages ─────────────────────────────────────────────────────────────────────

def cmd_page_get(args):
    """Retrieve a page."""
    resp = api_call(notion.pages.retrieve, page_id=args.id)
    if args.raw:
        out(resp)
    else:
        out(format_page_row(resp))

def cmd_page_create(args):
    """Create a new page."""
    kwargs = {}
    # Parent
    if args.database_id:
        kwargs["parent"] = {"database_id": args.database_id}
    elif args.page_id:
        kwargs["parent"] = {"page_id": args.page_id}
    else:
        err("Must specify --database-id or --page-id as parent")

    # Properties from JSON
    if args.properties:
        kwargs["properties"] = json.loads(args.properties)
    elif args.title:
        # Simple title-only creation
        kwargs["properties"] = {"title": {"title": make_rich_text(args.title)}}

    # Icon
    if args.icon:
        kwargs["icon"] = {"type": "emoji", "emoji": args.icon}

    # Cover
    if args.cover:
        kwargs["cover"] = {"type": "external", "external": {"url": args.cover}}

    # Content blocks from JSON
    if args.content:
        kwargs["children"] = json.loads(args.content)

    resp = api_call(notion.pages.create, **kwargs)
    out({"id": resp.get("id"), "url": resp.get("url"), "created": True})

def cmd_page_update(args):
    """Update page properties."""
    kwargs = {"page_id": args.id}

    if args.properties:
        kwargs["properties"] = json.loads(args.properties)

    if args.archived is not None:
        kwargs["archived"] = args.archived

    if args.icon:
        kwargs["icon"] = {"type": "emoji", "emoji": args.icon}

    if args.cover:
        kwargs["cover"] = {"type": "external", "external": {"url": args.cover}}

    resp = api_call(notion.pages.update, **kwargs)
    out({"id": resp.get("id"), "url": resp.get("url"), "updated": True})

# ─── Databases ─────────────────────────────────────────────────────────────────

def cmd_db_get(args):
    """Retrieve a database schema."""
    resp = api_call(notion.databases.retrieve, database_id=args.id)
    if args.raw:
        out(resp)
    else:
        schema = {}
        for name, prop in resp.get("properties", {}).items():
            prop_info = {"type": prop.get("type"), "id": prop.get("id")}
            # Include select/multi_select/status options
            ptype = prop.get("type", "")
            if ptype == "select" and prop.get("select"):
                prop_info["options"] = [o.get("name") for o in prop["select"].get("options", [])]
            elif ptype == "multi_select" and prop.get("multi_select"):
                prop_info["options"] = [o.get("name") for o in prop["multi_select"].get("options", [])]
            elif ptype == "status" and prop.get("status"):
                prop_info["options"] = [o.get("name") for o in prop["status"].get("options", [])]
                prop_info["groups"] = [{"name": g.get("name"), "options": [o.get("name") for o in g.get("option_ids", [])]} for g in prop["status"].get("groups", [])]
            elif ptype == "relation" and prop.get("relation"):
                prop_info["database_id"] = prop["relation"].get("database_id")
                prop_info["synced_property_name"] = prop["relation"].get("synced_property_name")
            elif ptype == "formula" and prop.get("formula"):
                prop_info["expression"] = prop["formula"].get("expression")
            elif ptype == "rollup" and prop.get("rollup"):
                prop_info["rollup"] = {
                    "relation_property_name": prop["rollup"].get("relation_property_name"),
                    "rollup_property_name": prop["rollup"].get("rollup_property_name"),
                    "function": prop["rollup"].get("function"),
                }
            schema[name] = prop_info
        out({
            "id": resp.get("id"),
            "title": plain_text(resp.get("title", [])),
            "description": plain_text(resp.get("description", [])),
            "url": resp.get("url"),
            "is_inline": resp.get("is_inline"),
            "properties": schema,
        })

def cmd_db_query(args):
    """Query a database with optional filter and sort."""
    kwargs = {}
    if args.filter:
        kwargs["filter"] = json.loads(args.filter)
    if args.sorts:
        kwargs["sorts"] = json.loads(args.sorts)

    # SDK 3.0 removed databases.query (now data_sources.query).
    # Use raw HTTP POST to /v1/databases/{id}/query for compatibility.
    results = _db_query_raw(args.id, limit=args.limit, **kwargs)
    rows = [format_page_row(r) for r in results]
    out({"count": len(rows), "rows": rows})

def _db_query_raw(database_id, limit=None, **kwargs):
    """Query database via raw HTTP (databases.query removed in SDK 3.0)."""
    """Query database via raw HTTP (databases.query removed in SDK 3.0)."""
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {os.environ.get('NOTION_API_KEY', '')}",
        "Notion-Version": API_VERSION,
        "Content-Type": "application/json",
    }
    results = []
    has_more = True
    next_cursor = None
    while has_more:
        body = dict(kwargs)
        page_size = min(100, limit - len(results)) if limit else 100
        body["page_size"] = page_size
        if next_cursor:
            body["start_cursor"] = next_cursor
        resp = httpx.post(url, headers=headers, json=body, timeout=30)
        if resp.status_code != 200:
            err(f"Notion API error ({resp.status_code}): {resp.text}")
        data = resp.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")
        if limit and len(results) >= limit:
            results = results[:limit]
            break
    return results

def cmd_db_create(args):
    """Create a new database."""
    kwargs = {}
    if args.page_id:
        kwargs["parent"] = {"type": "page_id", "page_id": args.page_id}
    else:
        err("Must specify --page-id as parent")

    kwargs["title"] = make_rich_text(args.title or "Untitled Database")

    if args.properties:
        kwargs["properties"] = json.loads(args.properties)
    else:
        # Minimal: just a title property
        kwargs["properties"] = {
            "Name": {"title": {}},
        }

    if args.inline:
        kwargs["is_inline"] = True

    if args.icon:
        kwargs["icon"] = {"type": "emoji", "emoji": args.icon}

    resp = api_call(notion.databases.create, **kwargs)
    out({"id": resp.get("id"), "url": resp.get("url"), "created": True})

def cmd_db_update(args):
    """Update a database (title, description, properties)."""
    kwargs = {"database_id": args.id}

    if args.title:
        kwargs["title"] = make_rich_text(args.title)

    if args.description:
        kwargs["description"] = make_rich_text(args.description)

    if args.properties:
        kwargs["properties"] = json.loads(args.properties)

    if args.archived is not None:
        kwargs["archived"] = args.archived

    resp = api_call(notion.databases.update, **kwargs)
    out({"id": resp.get("id"), "url": resp.get("url"), "updated": True})

# ─── Blocks (Page Content) ────────────────────────────────────────────────────

def cmd_blocks_get(args):
    """Get block children (page content)."""
    results = paginate(notion.blocks.children.list, block_id=args.id, limit=args.limit)
    if args.raw:
        out({"count": len(results), "blocks": results})
    else:
        blocks = [block_to_text(b) for b in results]
        out({"count": len(blocks), "blocks": blocks})

def cmd_blocks_get_recursive(args):
    """Recursively get all blocks (full page content)."""
    max_depth = min(args.depth or 3, 10)  # cap at 10 to prevent API call storms

    def fetch_children(block_id, depth=0):
        if depth > max_depth:
            return []
        results = paginate(notion.blocks.children.list, block_id=block_id)
        blocks = []
        for b in results:
            simplified = block_to_text(b)
            if b.get("has_children") and depth < max_depth:
                simplified["children"] = fetch_children(b["id"], depth + 1)
            blocks.append(simplified)
        return blocks

    blocks = fetch_children(args.id)
    out({"blocks": blocks})

def cmd_block_append(args):
    """Append blocks to a page or block."""
    if args.blocks:
        children = json.loads(args.blocks)
    elif args.text:
        # Simple: append paragraph(s) from text
        children = []
        for line in args.text.split("\\n"):
            children.append(make_block(args.type or "paragraph", line))
    else:
        err("Must specify --blocks (JSON) or --text")

    resp = api_call(notion.blocks.children.append, block_id=args.id, children=children)
    results = resp.get("results", [])
    out({"appended": len(results), "block_ids": [b.get("id") for b in results]})

def cmd_block_update(args):
    """Update a single block."""
    kwargs = {"block_id": args.id}
    if args.content:
        kwargs.update(json.loads(args.content))
    if args.archived is not None:
        kwargs["archived"] = args.archived
    resp = api_call(notion.blocks.update, **kwargs)
    out({"id": resp.get("id"), "type": resp.get("type"), "updated": True})

def cmd_block_delete(args):
    """Delete (archive) a block."""
    resp = api_call(notion.blocks.delete, block_id=args.id)
    out({"id": resp.get("id"), "deleted": True})

# ─── Comments ──────────────────────────────────────────────────────────────────

def cmd_comments_list(args):
    """List comments on a page or block."""
    results = paginate(notion.comments.list, block_id=args.id)
    comments = []
    for c in results:
        comments.append({
            "id": c.get("id"),
            "text": plain_text(c.get("rich_text", [])),
            "created_time": c.get("created_time"),
            "created_by": c.get("created_by", {}).get("id"),
        })
    out({"count": len(comments), "comments": comments})

def cmd_comment_create(args):
    """Add a comment to a page or discussion."""
    kwargs = {"rich_text": make_rich_text(args.text)}
    if args.page_id:
        kwargs["parent"] = {"page_id": args.page_id}
    elif args.discussion_id:
        kwargs["discussion_id"] = args.discussion_id
    else:
        err("Must specify --page-id or --discussion-id")
    resp = api_call(notion.comments.create, **kwargs)
    out({"id": resp.get("id"), "created": True})

# ─── Page content as Markdown ──────────────────────────────────────────────────

def cmd_page_read(args):
    """Read full page content as Markdown-like text."""
    # Get page title
    page = api_call(notion.pages.retrieve, page_id=args.id)
    title = ""
    for name, prop in page.get("properties", {}).items():
        if prop.get("type") == "title":
            title = plain_text(prop.get("title", []))
            break

    max_depth = min(args.depth or 3, 10)  # cap at 10

    def blocks_to_md(block_id, depth=0, indent=0):
        if depth > max_depth:
            return ""
        results = paginate(notion.blocks.children.list, block_id=block_id)
        lines = []
        list_counter = 0
        for b in results:
            btype = b.get("type", "")
            data = b.get(btype, {})
            prefix = "  " * indent
            text = plain_text(data.get("rich_text", []))

            if btype == "paragraph":
                lines.append(f"{prefix}{text}")
                lines.append("")
            elif btype == "heading_1":
                lines.append(f"{prefix}# {text}")
                lines.append("")
            elif btype == "heading_2":
                lines.append(f"{prefix}## {text}")
                lines.append("")
            elif btype == "heading_3":
                lines.append(f"{prefix}### {text}")
                lines.append("")
            elif btype == "bulleted_list_item":
                lines.append(f"{prefix}- {text}")
                list_counter = 0
            elif btype == "numbered_list_item":
                list_counter += 1
                lines.append(f"{prefix}{list_counter}. {text}")
            elif btype == "to_do":
                checked = "x" if data.get("checked") else " "
                lines.append(f"{prefix}- [{checked}] {text}")
            elif btype == "toggle":
                lines.append(f"{prefix}<details><summary>{text}</summary>")
            elif btype == "quote":
                lines.append(f"{prefix}> {text}")
                lines.append("")
            elif btype == "callout":
                icon = ""
                if data.get("icon") and data["icon"].get("type") == "emoji":
                    icon = data["icon"]["emoji"] + " "
                lines.append(f"{prefix}> {icon}{text}")
                lines.append("")
            elif btype == "code":
                lang = data.get("language", "")
                lines.append(f"{prefix}```{lang}")
                lines.append(f"{prefix}{text}")
                lines.append(f"{prefix}```")
                lines.append("")
            elif btype == "divider":
                lines.append(f"{prefix}---")
                lines.append("")
            elif btype == "image":
                ft = data.get("type", "")
                url = ""
                if ft == "file":
                    # Notion internal file URLs contain signed tokens; use placeholder
                    raw_url = data.get("file", {}).get("url", "")
                    url = raw_url.split("?")[0] + "?signed=redacted"
                elif ft == "external":
                    url = data.get("external", {}).get("url", "")
                caption = plain_text(data.get("caption", []))
                lines.append(f"{prefix}![{caption}]({url})")
                lines.append("")
            elif btype == "bookmark":
                url = data.get("url", "")
                caption = plain_text(data.get("caption", []))
                lines.append(f"{prefix}[{caption or url}]({url})")
                lines.append("")
            elif btype == "embed":
                url = data.get("url", "")
                lines.append(f"{prefix}[Embed: {url}]({url})")
                lines.append("")
            elif btype == "child_page":
                lines.append(f"{prefix}📄 **{data.get('title', '')}** (child page)")
                lines.append("")
            elif btype == "child_database":
                lines.append(f"{prefix}🗃️ **{data.get('title', '')}** (child database)")
                lines.append("")
            elif btype == "table_of_contents":
                lines.append(f"{prefix}[Table of Contents]")
                lines.append("")
            elif btype == "equation":
                lines.append(f"{prefix}$${data.get('expression', '')}$$")
                lines.append("")
            elif btype == "table_row":
                cells = data.get("cells", [])
                row_text = " | ".join(plain_text(cell) for cell in cells)
                lines.append(f"{prefix}| {row_text} |")
            elif btype == "table":
                pass  # table rows are children
            elif btype == "synced_block":
                pass  # content is in children
            elif btype == "column_list":
                pass  # columns are children
            elif btype == "column":
                pass  # content is in children
            else:
                if text:
                    lines.append(f"{prefix}{text}")
                    lines.append("")

            # Recurse into children
            if b.get("has_children") and depth < max_depth:
                child_md = blocks_to_md(b["id"], depth + 1, indent + 1)
                if child_md:
                    lines.append(child_md)
                    if btype == "toggle":
                        lines.append(f"{prefix}</details>")
                        lines.append("")

            # Reset list counter for non-list items
            if btype not in ("numbered_list_item",):
                list_counter = 0

        return "\n".join(lines)

    md = ""
    if title:
        md = f"# {title}\n\n"
    md += blocks_to_md(args.id)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
        out({"saved": args.output, "length": len(md)})
    else:
        out({"title": title, "markdown": md})

# ─── Page write (Markdown → Blocks) ───────────────────────────────────────────

def cmd_page_write(args):
    """Write content to a page. Accepts simple Markdown-like text or JSON blocks."""
    if args.blocks:
        children = json.loads(args.blocks)
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
        children = md_to_blocks(text)
    elif args.text:
        children = md_to_blocks(args.text)
    else:
        err("Must specify --blocks, --text, or --file")

    if args.replace:
        # Delete existing children first
        existing = paginate(notion.blocks.children.list, block_id=args.id)
        failed = 0
        for b in existing:
            try:
                notion.blocks.delete(block_id=b["id"])
            except Exception:
                failed += 1
        if failed:
            import sys as _sys
            print(json.dumps({"warning": f"Failed to delete {failed}/{len(existing)} existing blocks"}),
                  file=_sys.stderr)

    # Append in batches of 100 (API limit)
    all_ids = []
    for i in range(0, len(children), 100):
        batch = children[i:i+100]
        resp = api_call(notion.blocks.children.append, block_id=args.id, children=batch)
        all_ids.extend([b.get("id") for b in resp.get("results", [])])

    out({"appended": len(all_ids), "block_ids": all_ids})

def md_to_blocks(text):
    """Convert simple Markdown text to Notion blocks."""
    lines = text.split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("### "):
            blocks.append(make_block("heading_3", stripped[4:]))
        elif stripped.startswith("## "):
            blocks.append(make_block("heading_2", stripped[3:]))
        elif stripped.startswith("# "):
            blocks.append(make_block("heading_1", stripped[2:]))
        elif stripped.startswith("- [x] ") or stripped.startswith("- [X] "):
            blocks.append(make_block("to_do", stripped[6:], checked=True))
        elif stripped.startswith("- [ ] "):
            blocks.append(make_block("to_do", stripped[6:], checked=False))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append(make_block("bulleted_list_item", stripped[2:]))
        elif len(stripped) > 2 and stripped[0].isdigit() and ". " in stripped[:5]:
            idx = stripped.index(". ")
            blocks.append(make_block("numbered_list_item", stripped[idx+2:]))
        elif stripped.startswith("> "):
            blocks.append(make_block("quote", stripped[2:]))
        elif stripped.startswith("```"):
            lang = stripped[3:].strip() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append(make_block("code", "\n".join(code_lines), language=lang))
        elif stripped == "---" or stripped == "***":
            blocks.append(make_block("divider"))
        elif stripped.startswith("!["):
            # Image: ![alt](url)
            try:
                alt = stripped[2:stripped.index("]")]
                url = stripped[stripped.index("(")+1:stripped.rindex(")")]
                blocks.append(make_block("image", url))
            except (ValueError, IndexError):
                blocks.append(make_block("paragraph", stripped))
        else:
            blocks.append(make_block("paragraph", stripped))

        i += 1

    return blocks

# ─── Quick add row to database ─────────────────────────────────────────────────

def cmd_db_add_row(args):
    """Quick-add a row to a database. Properties as key=value pairs."""
    if not args.database_id:
        err("Must specify --database-id")

    # First get schema to determine property types
    db = api_call(notion.databases.retrieve, database_id=args.database_id)
    schema = db.get("properties", {})

    properties = {}
    if args.props:
        raw_props = json.loads(args.props)
        for name, value in raw_props.items():
            if name in schema:
                ptype = schema[name].get("type", "rich_text")
                properties[name] = build_property_value(ptype, value)
            else:
                # Guess: try as rich_text
                properties[name] = build_property_value("rich_text", value)
    elif args.title:
        # Find the title property
        for name, prop in schema.items():
            if prop.get("type") == "title":
                properties[name] = build_property_value("title", args.title)
                break

    resp = api_call(notion.pages.create,
                    parent={"database_id": args.database_id},
                    properties=properties)
    out({"id": resp.get("id"), "url": resp.get("url"), "created": True})

# ═══════════════════════════════════════════════════════════════════════════════
# CLI Parser
# ═══════════════════════════════════════════════════════════════════════════════

def build_parser():
    parser = argparse.ArgumentParser(description="Notion Hub — AI-friendly Notion CLI")
    sub = parser.add_subparsers(dest="command", help="Command")

    # search
    p = sub.add_parser("search", help="Search pages and databases")
    p.add_argument("query", nargs="?", help="Search query")
    p.add_argument("--filter", choices=["page", "database"], help="Filter by object type")
    p.add_argument("--sort", choices=["ascending", "descending"], help="Sort by last_edited_time")
    p.add_argument("--limit", type=int, help="Max results")

    # users
    p = sub.add_parser("users", help="List users or get bot info")
    p.add_argument("--me", action="store_true", help="Get current bot user")
    p.add_argument("--id", help="Get specific user by ID")

    # page get
    p = sub.add_parser("page-get", help="Get page properties")
    p.add_argument("id", help="Page ID")
    p.add_argument("--raw", action="store_true", help="Raw API response")

    # page create
    p = sub.add_parser("page-create", help="Create a page")
    p.add_argument("--database-id", help="Parent database ID")
    p.add_argument("--page-id", help="Parent page ID")
    p.add_argument("--title", help="Page title (simple mode)")
    p.add_argument("--properties", help="Properties as JSON")
    p.add_argument("--content", help="Content blocks as JSON array")
    p.add_argument("--icon", help="Emoji icon")
    p.add_argument("--cover", help="Cover image URL")

    # page update
    p = sub.add_parser("page-update", help="Update page properties")
    p.add_argument("id", help="Page ID")
    p.add_argument("--properties", help="Properties as JSON")
    p.add_argument("--archived", type=lambda x: x.lower() == "true", default=None, help="Archive/unarchive")
    p.add_argument("--icon", help="Emoji icon")
    p.add_argument("--cover", help="Cover image URL")

    # page read (as markdown)
    p = sub.add_parser("page-read", help="Read page content as Markdown")
    p.add_argument("id", help="Page ID or URL")
    p.add_argument("--depth", type=int, default=3, help="Max recursion depth")
    p.add_argument("--output", "-o", help="Save to file")

    # page write
    p = sub.add_parser("page-write", help="Write content to a page")
    p.add_argument("id", help="Page ID")
    p.add_argument("--text", help="Markdown-like text to write")
    p.add_argument("--file", help="Read content from file")
    p.add_argument("--blocks", help="Blocks as JSON array")
    p.add_argument("--replace", action="store_true", help="Replace existing content")

    # db get (schema)
    p = sub.add_parser("db-get", help="Get database schema")
    p.add_argument("id", help="Database ID")
    p.add_argument("--raw", action="store_true", help="Raw API response")

    # db query
    p = sub.add_parser("db-query", help="Query database rows")
    p.add_argument("id", help="Database ID")
    p.add_argument("--filter", help="Filter as JSON")
    p.add_argument("--sorts", help="Sorts as JSON array")
    p.add_argument("--limit", type=int, help="Max results")

    # db create
    p = sub.add_parser("db-create", help="Create a database")
    p.add_argument("--page-id", required=True, help="Parent page ID")
    p.add_argument("--title", help="Database title")
    p.add_argument("--properties", help="Properties schema as JSON")
    p.add_argument("--inline", action="store_true", help="Create as inline database")
    p.add_argument("--icon", help="Emoji icon")

    # db update
    p = sub.add_parser("db-update", help="Update database")
    p.add_argument("id", help="Database ID")
    p.add_argument("--title", help="New title")
    p.add_argument("--description", help="New description")
    p.add_argument("--properties", help="Properties schema changes as JSON")
    p.add_argument("--archived", type=lambda x: x.lower() == "true", default=None, help="Archive/unarchive")

    # db add-row (quick)
    p = sub.add_parser("db-add-row", help="Quick-add a row to a database")
    p.add_argument("--database-id", "-d", required=True, help="Database ID")
    p.add_argument("--title", help="Title (for simple rows)")
    p.add_argument("--props", help="Properties as JSON object {name: value, ...}")

    # blocks get
    p = sub.add_parser("blocks-get", help="Get block children")
    p.add_argument("id", help="Block/Page ID")
    p.add_argument("--raw", action="store_true", help="Raw API response")
    p.add_argument("--limit", type=int, help="Max blocks")

    # blocks get recursive
    p = sub.add_parser("blocks-get-all", help="Get all blocks recursively")
    p.add_argument("id", help="Block/Page ID")
    p.add_argument("--depth", type=int, default=3, help="Max depth")

    # block append
    p = sub.add_parser("block-append", help="Append blocks to a page/block")
    p.add_argument("id", help="Parent block/page ID")
    p.add_argument("--blocks", help="Blocks as JSON array")
    p.add_argument("--text", help="Simple text (creates paragraphs)")
    p.add_argument("--type", default="paragraph", help="Block type for --text mode")

    # block update
    p = sub.add_parser("block-update", help="Update a block")
    p.add_argument("id", help="Block ID")
    p.add_argument("--content", help="Block content as JSON")
    p.add_argument("--archived", type=lambda x: x.lower() == "true", default=None, help="Archive block")

    # block delete
    p = sub.add_parser("block-delete", help="Delete a block")
    p.add_argument("id", help="Block ID")

    # comments list
    p = sub.add_parser("comments-list", help="List comments on a page/block")
    p.add_argument("id", help="Block/Page ID")

    # comment create
    p = sub.add_parser("comment-create", help="Create a comment")
    p.add_argument("text", help="Comment text")
    p.add_argument("--page-id", help="Parent page ID")
    p.add_argument("--discussion-id", help="Discussion thread ID")

    return parser

# ─── ID normalization ──────────────────────────────────────────────────────────

def normalize_id(raw):
    """Extract and normalize a Notion ID from a URL or raw string."""
    if not raw:
        return raw
    # Handle Notion URLs
    if "notion.so" in raw or "notion.site" in raw:
        # Extract the ID part (last 32 hex chars, possibly with dashes)
        import re
        match = re.search(r"([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", raw)
        if match:
            return match.group(1)
    # Remove dashes if present (API accepts both)
    return raw.strip()

def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    init_client()

    # Normalize IDs
    if hasattr(args, "id") and args.id:
        args.id = normalize_id(args.id)
    if hasattr(args, "page_id") and args.page_id:
        args.page_id = normalize_id(args.page_id)
    if hasattr(args, "database_id") and args.database_id:
        args.database_id = normalize_id(args.database_id)

    # Dispatch
    commands = {
        "search": cmd_search,
        "users": cmd_users,
        "page-get": cmd_page_get,
        "page-create": cmd_page_create,
        "page-update": cmd_page_update,
        "page-read": cmd_page_read,
        "page-write": cmd_page_write,
        "db-get": cmd_db_get,
        "db-query": cmd_db_query,
        "db-create": cmd_db_create,
        "db-update": cmd_db_update,
        "db-add-row": cmd_db_add_row,
        "blocks-get": cmd_blocks_get,
        "blocks-get-all": cmd_blocks_get_recursive,
        "block-append": cmd_block_append,
        "block-update": cmd_block_update,
        "block-delete": cmd_block_delete,
        "comments-list": cmd_comments_list,
        "comment-create": cmd_comment_create,
    }

    func = commands.get(args.command)
    if func:
        func(args)
    else:
        err(f"Unknown command: {args.command}")

if __name__ == "__main__":
    main()
