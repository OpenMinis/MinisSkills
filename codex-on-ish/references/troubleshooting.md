# Troubleshooting Codex on iSH

## Quick diagnostics

| Symptom | Cause | Fix |
|---|---|---|
| `error sending request for url` from codex | direct reqwest sockets to remote hosts | confirm wrapper env is set (`HTTPS_PROXY=http://127.0.0.1:8894`) |
| panic `must support ECDSA_NISTP521_SHA512` | codex ≥ 0.143 (aws-lc provider) on iSH | use codex.bin v0.130; do not `codex update` |
| `failed to connect to websocket: 501` in stderr | proxy blocked the responses-endpoint WS upgrade | informational — SSE fallback working as designed |
| `failed to refresh available models` | catalog contains efforts the old client can't parse | check pyproxy6 logged "models transform"; restart proxy |
| npm-style `connect errno 65` | same iSH async-socket disease | route through any blocking-socket proxy |
| `gaierror(-3, 'Try again')` in proxy log | iSH DNS flake | pyproxy6 retries + caches; just retry the command |
| upstream 502 Bad Gateway from proxy | upstream connect failed | usually transient; DNS retry inside proxy handles it |

## Proxy maintenance

- State dir: `/tmp/codex-proxy/` (proxy.pid, clients/, proxy.log, proxy.out)
- Kill stale singleton: `pkill -f pyproxy6 && rm -f /tmp/codex-proxy/proxy.pid`
- Regenerate certs if expiry: rerun the cert block in scripts/setup.sh
- Full log: `tail -f /tmp/codex-proxy/proxy.log`

## iOS process-death rules (device-verified, iOS 26)

- Foreground: 90 CPU-s / 180 s — advisory only
- Background: 48 CPU-s / 60 s — **the whole app is killed**
- Consequences: long codex runs need the app foregrounded; backgrounded runs
  are throttled (governor) and may look frozen for a while, then resume.
- Never leave `codex login`'s own server waiting while switching apps — use
  the curl-driven device-auth flow instead (scripts/token_poller3.sh).

## HTTP relay internals (if you must modify the proxy)

- Requests are framed; bodies rewritten length-neutrally (`0.130.0` → `0.151.0`)
- `accept-encoding` is forced to `identity` so responses are rewriteable text
- Only `/backend-api/codex/models` responses are buffered+transformed
  (effort filter, `prefer_websockets=false`); everything else raw-pumps
- NEVER defer trailing bytes speculatively when scanning a stream for a token:
  an HTTP request's final bytes will never arrive if the server is waiting on
  them — only defer suffixes that are a true prefix of the search token
- WebSocket upgrades on `/backend-api/codex/responses` must be 501'd (codex
  falls back to SSE); all other WS upgrades switch to raw pump

## Version notes

- v0.130.0 = last musl release whose rustls (ring) works on iSH
- v0.131–0.140 also boot but models are gated client-side at the server
- v0.141+ panic on first TLS attempt — verified 0.144 and 0.151
- Spoofed client version 0.151.0 unlocks gpt-5.6-sol/terra/luna for accounts
  whose plan has them (slug `gpt-5.6` alone is API-only)
