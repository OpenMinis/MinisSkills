# ChatGPT device-auth protocol (curl-driven)

All endpoints on `auth.openai.com` unless noted. Use curl — Cloudflare blocks
Python-urllib fingerprints on these paths (cf_route_error).

1. **Request a device code**
   ```
   POST /api/accounts/deviceauth/usercode
   content-type: application/json
   {"client_id":"app_EMoamEEZ73f0CkXaXp7hrann"}
   ```
   → `{device_auth_id, user_code, interval, expires_at}` (15 min TTL).
   The user enters the code at `https://auth.openai.com/codex/device`.

2. **Poll for the approval artifact** (every 5–10 s)
   ```
   POST /api/accounts/deviceauth/token
   {"device_auth_id":"...","client_id":"...","user_code":"..."}
   ```
   → `authorization_pending` until approved, then
   `{status:"success", authorization_code, code_challenge, code_verifier}`.
   NOTE: an authorization_code is burned by malformed redemption attempts —
   send the exchange correctly on the first try.

3. **Exchange for tokens** — FORM-ENCODED, not JSON:
   ```
   POST /oauth/token
   content-type: application/x-www-form-urlencoded
   grant_type=authorization_code
   code=<authorization_code>
   code_verifier=<code_verifier>
   client_id=app_EMoamEEZ73f0CkXaXp7hrann
   redirect_uri=https://auth.openai.com/deviceauth/callback
   ```
   → `{access_token, id_token, refresh_token, expires_in, ...}`
   (The redirect_uri is the device-flow value — NOT the browser flow's
   localhost:1455. JSON bodies fail with `token_exchange_user_error`.)

4. **Install** via scripts/write_auth_json.sh (auth.json format for v0.130:
   `{"OPENAI_API_KEY":null,"tokens":{"id_token","access_token","refresh_token"},
   "last_refresh":"<ISO8601 with nonzero fraction>"}`).

## Refresh

Codex refreshes tokens itself through the proxy (same client_id, grant_type
refresh_token). If refresh breaks, re-run the device flow.

## Models endpoint (account capabilities)

```
GET chatgpt.com/backend-api/codex/models?client_version=<v>
Authorization: Bearer <access_token>
originator: codex_cli_rs
```
The list is filtered server-side by client_version — the reason the proxy
spoofs 0.151.0.
