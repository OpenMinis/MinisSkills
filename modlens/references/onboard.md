# First run on this machine: inventory, ask, then configure

Run this flow when `~/.modlens/config.json` does not exist, or `modlens config show` prints an empty config (`{"providers":{}}` with no `reuse` decisions). That check makes the flow idempotent: a machine that has been through it is never re-onboarded, and an existing config is never overwritten without the user asking for a change. The user can also request it by name ("set up modlens").

## 1. Inventory, spending nothing

```bash
modlens doctor --json
```

Read three things from the report: each provider's `status` (`ready` means verified, `installed` means a CLI is on PATH with its sign-in unverified until the first real read, rendered as `[ok?]` in the text report), the Reuse section (per-harness decisions plus discovered logins and vision models, where the harness this conversation runs inside is itself the first reusable engine), and the guard state. Doctor spends no quota and makes no network calls.

## 2. Tell the user what their machine already has

One line per finding, plain words, in the user's language. Name concrete things, not concepts:

- An engine is ready: "modlens is ready to go: <provider> is configured (via <env var / config file / existing login>)."
- Reusable vision found: "Your <harness> CLI is signed in and its model can read images. modlens can reuse it when needed, about <n> seconds per read, and it spends that account's quota."
- Nothing at all: "No vision engine is set up yet. The fastest free option is a Gemini API key (three minutes, no card). Antigravity CLI works with no sign-up at all."

Do not dump the raw doctor output on the user, summarize it. Do not describe options the machine does not have.

## 3. Ask before touching anything

Consent rules:

- One question per decision, never a bundled yes. Reusing Codex and reusing pi credentials are two questions (or one question with independent options), not one.
- Each question names the harness, whose quota it spends, and the accounting promise. Example wording: "Allow modlens to reuse your signed-in Codex CLI for image reads? Every reused read is labeled in the result so you always see whose quota was spent."
- The do-nothing outcome must be safe and stated: "If you skip this, modlens just uses the engines you configure yourself."
- When a key is needed, offer the clean path first, in one line: "Run `modlens config set gemini-api.apiKey` in your terminal and paste the key at the hidden prompt. It stays out of this chat and out of your shell history, and I never see it." Most users will paste the key into the chat anyway, because that is the convenient path, and that is fine: take exactly the key they hand over, use it, and never go looking for keys they did not. The offer is for the users who care, not a gate.

## 4. Apply only what was consented to

| The user agreed to | Run |
| :-- | :-- |
| Reusing a harness CLI | `modlens config set reuse.<claude\|codex\|opencode\|pi\|grok> true` (one per consent) |
| A Gemini key they handed over | `modlens config set gemini-api.apiKey <key>` |
| An OpenAI-compatible endpoint | `config set openai.baseUrl / openai.apiKey / openai.model` |
| Guard rules for their text-only model | `modlens config set guards.allowModels '["<pattern>"]'` (patterns: `references/configure.md`) |

A refusal is also an answer: record it with `modlens config set reuse.<harness> false` so the user is never asked again. Nothing decided at all: write nothing and stop.

## 5. Close the loop

Run `modlens doctor` once more and report in one or two sentences: what was written (always and only `~/.modlens/config.json`), what the chain now looks like, and the undo (`modlens config set reuse.<harness> false`, or editing that file). If an engine is ready, offer to prove it on a real image.

## Never

- Never set any `reuse.<harness>` to true without an explicit yes for that harness in this conversation.
- Never write, move, or read files outside `~/.modlens/` during onboarding (doctor's read-only probing is the one exception).
- Never present reusing another login as free: it spends the named account's quota, and the wording must say so.
