# Memos API Reference (Condensed)

Source: https://usememos.com/docs/api

## Conventions
- Base URL: `https://<your-memos-instance>/api/v1`
- Auth: `Authorization: Bearer <ACCESS_TOKEN>` (use env vars; don't print tokens)
- Pagination: `pageSize`, `pageToken`
- Filtering: `filter` (AIP-160 syntax, e.g., `memo.content:"foo"`)
- Partial update: `updateMask=field1,field2`
- Default content type: `application/json`

## Common Shell Vars
```sh
MEMOS_BASE=https://demo.usememos.com
AUTH_HEADER="Authorization: Bearer $MEMOS_TOKEN"
```

## Core Endpoints (cheatsheet)

### Memos
- List: `GET /memos?pageSize=20&pageToken=...&filter=...`
- Get: `GET /memos/{memo}`
- Create: `POST /memos` body `{content, visibility, resourceName, ...}`
- Update (partial): `PATCH /memos/{memo}?updateMask=content,visibility` body `{...}`
- Delete: `DELETE /memos/{memo}`

### Attachments
- List: `GET /attachments?pageSize=20`
- Get: `GET /attachments/{attachment}`
- Create: `POST /attachments` body `{filename,type,content?,externalLink?,memo?}`
- Update: `PATCH /attachments/{attachment}?updateMask=...`
- Delete: `DELETE /attachments/{attachment}`

### Activities
- List: `GET /activities?pageSize=50`
- Get: `GET /activities/{activity}`

### Auth / Users
- Me: `GET /auth/me`
- Sign in: `POST /auth/signin` (returns accessToken and sets refresh cookie)
- Refresh: `POST /auth/refresh`
- Sign out: `POST /auth/signout`

### Identity Providers
- List: `GET /identity-providers`
- Create: `POST /identity-providers`
- Get: `GET /identity-providers/{idp}`
- Update: `PATCH /identity-providers/{idp}?updateMask=...`
- Delete: `DELETE /identity-providers/{idp}`

### Resources (files linked to memos)
- List: `GET /resources?pageSize=...`
- Create: `POST /resources`
- Get: `GET /resources/{resource}`
- Update: `PATCH /resources/{resource}?updateMask=...`
- Delete: `DELETE /resources/{resource}`

### Tags
- List: `GET /tags`
- Create: `POST /tags`
- Update: `PATCH /tags/{tag}?updateMask=...`
- Delete: `DELETE /tags/{tag}`

## Curl Examples

List memos with filter and pagination:
```sh
curl -s -H "$AUTH_HEADER" \
  "$MEMOS_BASE/api/v1/memos?pageSize=20&filter=visibility=PUBLIC"
```

Create memo:
```sh
curl -s -X POST -H "Content-Type: application/json" -H "$AUTH_HEADER" \
  "$MEMOS_BASE/api/v1/memos" \
  -d '{"content":"hello world","visibility":"PUBLIC"}'
```

Update memo content (partial):
```sh
curl -s -X PATCH -H "Content-Type: application/json" -H "$AUTH_HEADER" \
  "$MEMOS_BASE/api/v1/memos/$MEMO_ID?updateMask=content" \
  -d '{"content":"updated text"}'
```

List attachments:
```sh
curl -s -H "$AUTH_HEADER" "$MEMOS_BASE/api/v1/attachments?pageSize=20"
```

Upload attachment metadata (server handles content/externalLink):
```sh
curl -s -X POST -H "Content-Type: application/json" -H "$AUTH_HEADER" \
  "$MEMOS_BASE/api/v1/attachments" \
  -d '{"filename":"a.png","type":"image/png","memo":"memos/123"}'
```

Sign in (username/password example):
```sh
curl -s -X POST -H "Content-Type: application/json" \
  "$MEMOS_BASE/api/v1/auth/signin" \
  -d '{"username":"user","password":"pass"}'
```

Refresh token:
```sh
curl -s -X POST "$MEMOS_BASE/api/v1/auth/refresh"
```

## Error Handling Tips
- 401/403: check token validity and scope; ensure `Authorization: Bearer ...` header present.
- 400: check request body fields and `updateMask` fields match payload.
- Pagination: always propagate `nextPageToken` until empty.
- Filters: follow AIP-160; quote strings, use `field op value`, e.g., `create_time>"2024-01-01T00:00:00Z"`.

## Safety
- Never echo tokens; use env vars (`$MEMOS_TOKEN`).
- Prefer `curl -s` to keep output clean; add `-i` only for debugging.
- For scripts, externalize base URL and token via environment.
