---
name: codex-image
description: Generate images using OpenAI's Codex backend API with gpt-image-2 tool. Use when the user asks to generate images via Codex, ChatGPT image generation, or gpt-image-2. Triggers on "codex image", "codex generate", "gpt-image", "chatgpt generate image". Token is auto-fetched from chatgpt.com session — no manual token setup needed.
---

# Codex Image Generation

Generate images via `chatgpt.com/backend-api/codex/responses` using the `image_generation` tool (gpt-image-2).

## Requirements

- A ChatGPT account (token is fetched automatically via browser session)
- No manual token setup needed — the skill handles auth automatically

## Auth Token Resolution (in order)

1. `--token` argument (CLI only)
2. `CODEX_IMAGE_TOKEN` environment variable
3. `--token-file` argument (CLI only)
4. `~/.chatgpt_auth.json` cache (valid for 8 hours)
5. **Auto login flow** — fetches from `https://chatgpt.com/api/auth/session` via `minis-browser-use`:
   - If already logged in → token extracted immediately
   - If not logged in → opens `chatgpt.com/auth/login` in the browser, then polls every 30s in a new tab for up to 5 minutes
   - On success → saves token to `~/.chatgpt_auth.json` (chmod 600)

## Usage

```bash
python3 scripts/codex_image.py "a cute rabbit on a light background" \
  --output rabbit.png \
  --model gpt-5.4 \
  --effort low
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `prompt` | (required) | Image description |
| `--output` | `codex_image.png` | Output file path |
| `--model` | `gpt-5.4` | Codex model |
| `--effort` | `low` | Reasoning effort: low/medium/high |
| `--token` | - | Access token directly (skips auto auth) |
| `--token-file` | - | File containing token (skips auto auth) |

### Output

JSON with `success`, `path`, `size`, `revised_prompt` on success.

## Auth Script (standalone)

```bash
python3 scripts/get_auth.py
```

Returns JSON `{"success": true, "accessToken": "...", "source": "cache|session|login"}`.
Can be used independently to refresh or pre-fetch the token.

## Workflow

1. **Token**: auto-resolved via `get_auth.py`:
   - Already cached → use directly
   - Already logged in (browser session) → extract immediately
   - Not logged in → `minis-open` pops the ChatGPT login page to the user in foreground, then polls every 10s (up to 5 min) until login is detected
2. Construct the prompt from the user's request.
3. Run `scripts/codex_image.py` with appropriate arguments.
4. Send the generated image to the user.

## Notes

- Token is cached in `~/.chatgpt_auth.json` for 8 hours (chmod 600).
- The endpoint requires `stream: true`; the script handles SSE parsing internally.
- Token is a ChatGPT session token, not an OpenAI API key. It expires and is refreshed automatically on next use.
- Image generation uses `gpt-image-2` under the hood with auto quality/size.
- Token usage is split: main `usage` tracks text tokens, `tool_usage.image_gen` tracks image tokens separately.
- This uses an internal/unofficial API endpoint. Availability may change.
