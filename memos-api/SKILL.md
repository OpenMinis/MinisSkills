---
name: memos-api
description: |
  Handles Memos API usage: crafting curl/python requests with Authorization Bearer tokens, paginating with pageSize/pageToken, using filter (AIP-160 syntax), updateMask updates, and mapping common endpoints (memo CRUD, attachments, activities, auth, identity providers). Trigger when user asks to call/inspect/troubleshoot Memos API, generate sample requests, or batch download memos. Warn to avoid printing tokens.
compatibility: Requires curl and/or python3. Use env vars for tokens.
---

# Memos API Skill

## When to use
- User wants to call Memos API, build curl/python examples, or debug responses
- Needs memo CRUD, attachments, activities, auth/identity providers, or list/filter/pagination
- Needs batch download scripts or reference docs for endpoints

## How to use
1) Require base URL and bearer token (env var recommended). Do **not** print secret values.
2) For list endpoints: support `pageSize`, `pageToken`, and `filter` (AIP-160) if available.
3) For updates: use `updateMask=field1,field2` when partial updates are supported.
4) Return ready-to-run curl examples; optionally include python `requests` snippet.
5) If user needs full endpoint details, load reference file `references/memos-api-reference.md`.

## Quick curl templates
- List memos (example):
  ```sh
  curl -s -H "Authorization: Bearer $MEMOS_TOKEN" \
       "$MEMOS_BASE/api/v1/memos?pageSize=20"
  ```
- Create memo:
  ```sh
  curl -s -X POST -H "Content-Type: application/json" \
       -H "Authorization: Bearer $MEMOS_TOKEN" \
       "$MEMOS_BASE/api/v1/memos" \
       -d '{"content":"hello"}'
  ```
- Update memo (partial):
  ```sh
  curl -s -X PATCH -H "Content-Type: application/json" \
       -H "Authorization: Bearer $MEMOS_TOKEN" \
       "$MEMOS_BASE/api/v1/memos/$MEMO_ID?updateMask=content" \
       -d '{"content":"updated"}'
  ```
- List attachments:
  ```sh
  curl -s -H "Authorization: Bearer $MEMOS_TOKEN" \
       "$MEMOS_BASE/api/v1/attachments?pageSize=20"
  ```

## Bundled references
- `references/memos-api-reference.md` — full scraped API reference (all services/endpoints).

## Notes
- Keep responses concise; link to reference when detailed schemas are needed.
- Use placeholders/env vars (`$MEMOS_BASE`, `$MEMOS_TOKEN`, `$MEMO_ID`) and avoid leaking secrets.
- Prefer `curl -s` and JSON bodies; add headers only as required.
