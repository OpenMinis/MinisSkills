---
name: codex-on-ish
description: Install and run OpenAI Codex CLI inside the Minis/iSH Alpine sandbox on iOS, where rustls TLS and async sockets are broken. Covers the local MITM proxy with P-256 certs, version-spoofing to unlock newer models (gpt-5.6 family), forcing SSE instead of websockets, ChatGPT device-auth login driven by curl, and the refcounted proxy wrapper. Use when the user wants Codex or other Rust-based AI CLIs on the iPhone/iPad Minis shell, or hits "error sending request", "must support ECDSA_NISTP521_SHA512" panics, model "requires a newer version of Codex", or npm errno 65 inside iSH.
---

# Codex on iSH (Minis iOS sandbox)

Run the OpenAI Codex CLI natively in the Alpine/iSH environment. Works around the
platform's broken Rust networking stack with a local MITM proxy.

## Why this is needed (the two bugs)

1. **rustls misbehaves on iSH's translated CPU.** Official musl binaries ≥ v0.143
   panic at the first TLS handshake (`installed rustls crypto provider must
   support ECDSA_NISTP521_SHA512`) because aws-lc-rs CPU detection fails in the
   emulator. v0.130 (ring provider) handshakes, but ONLY with ECDSA P-256
   certificates — RSA and P-521 get refused.
2. **Async sockets to remote hosts fail** (`connect errno 65` / reqwest
   `error sending request`). Blocking-socket clients (curl, Python) work fine;
   loopback connections work fine. Routing Rust traffic through a local proxy
   converts the hostile leg into a reliable one.

Both bugs are iSH-specific. Termux forks do NOT fix them (verified: their
rustls code is identical to upstream).

## Install

```
sh scripts/setup.sh
```

This downloads codex v0.130.0 musl aarch64, generates the P-256 CA/server certs,
installs `pyproxy6.py` (proxy) and the `codex` wrapper into /usr/local/bin, and
writes `~/.codex/config.toml` defaults (model, yolo approval policy).

## Login (ChatGPT account)

Codex's own login flows die within minutes (iOS kills the app at 48 CPU-s/min
in background), so drive the OAuth device flow with curl instead:

```
sh scripts/token_poller3.sh &     # prints a live user_code, auto-renews
# user visits https://auth.openai.com/codex/device, enters the code
# poller exchanges the artifact and writes /tmp/token_result.json
sh scripts/write_auth_json.sh     # installs ~/.codex/auth.json
codex login status                # -> "Logged in using ChatGPT"
```

Key protocol facts (see references/auth-protocol.md):
- `POST /api/accounts/deviceauth/usercode` JSON `{client_id}` → device_auth_id + user_code
- poll `/deviceauth/token` with `{device_auth_id, client_id, user_code}` until it returns
  `authorization_code` + `code_verifier`
- exchange at `/oauth/token` **form-encoded** (JSON is rejected) with
  `redirect_uri=https://auth.openai.com/deviceauth/callback` → id/access/refresh tokens
- Python urllib is blocked by Cloudflare on these endpoints — always use curl.

## What the wrapper does

`codex` (wrapper) registers a refcount file, starts the proxy as a singleton
(pidfile + pgrep guard), waits for the port, execs `codex.bin` with
`SSL_CERT_FILE`/`HTTPS_PROXY` env, and cleans up on exit. The proxy tears itself
down ~8 s after the last client leaves. Output is silent; logs live in
/tmp/codex-proxy/.

## Model gating and the version spoof

The backend gates models by reported client version (e.g. gpt-5.6-* requires
≥ 0.144.0 — the exact versions that panic on iSH). The proxy rewrites
`0.130.0` → `0.151.0` in-flight (same byte length, so HTTP framing survives) in
the request line, `version:` header, and bodies.

It also down-translates the models catalog: drops `max`/`ultra` reasoning
efforts v0.130 can't parse, forces `prefer_websockets=false`, and rewrites
Content-Length. Websocket upgrades on `/backend-api/codex/responses` get a
local 501 so codex falls back to SSE (WS frames would stall the HTTP-framed
relay); other WS upgrades pass through raw.

## Troubleshooting

See references/troubleshooting.md for: cert re-generation, DNS EAI_AGAIN
retries, "models list failed to refresh", login poller death, upstream 502s,
and the iOS background CPU-budget kills.
