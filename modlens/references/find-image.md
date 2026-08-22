# Finding the image path in the chat

Harnesses rarely hand you a clean path. Identify which harness you are in, then follow its branch. Never mix branches across harnesses.

## Codex

You see a text tag like `<image name=[Image #1] path="/tmp/xxxx.png">`:

- Extract the `path` value from the tag and run modlens on it. Pasted images live in a temp file Codex already created; a stripped image keeps its path tag next to the placeholder.
- Do NOT use `recover-paste` here: it detects Codex and refuses with this same guidance.

## Claude Code with a `[Image: source: <path>]` line

Newer Claude Code builds write every pasted image to `~/.claude/image-cache/<session-id>/` and, in the terminal (`cli`) entrypoint, inject that line as a user message. Undocumented internal behavior (observed on 2.1.201 through 2.1.231; the VSCode and desktop entrypoints do not inject it), so treat it as a shortcut, not a guarantee.

- If the file at that path exists, run modlens on it directly and skip `recover-paste`. The file is Claude Code's own cache: read it, never delete or move it.
- If the path is gone (the cache is cleaned after a while) or there is no such line, fall through to the next branch.

## Claude Code, Pi, or OpenCode (no usable path anywhere)

The image reads as `[Unsupported Image]`, a bare `[Image #1]`, or an attachment you simply cannot see. Whatever a gateway strips from the request, these harnesses persist user messages, image bytes included, in local session storage first: Claude Code and Pi in session JSONL files (`~/.claude/projects/`, `~/.pi/agent/sessions/`), OpenCode in a SQLite database (`~/.local/share/opencode/opencode.db`, read via node:sqlite, needs Node 22.13+; Bun cannot load node:sqlite, so a bunx-resolved launcher needs a real Node install for OpenCode recovery).

- Run `modlens recover-paste` from the project directory the conversation is happening in (`--count <n>` for several images). It detects which harness it is running inside and reads ONLY that harness's storage. In Claude Code it targets your exact session automatically via the injected `CLAUDE_CODE_SESSION_ID`; `--session <id>` is only needed to override.
- The output is JSON with real file paths, oldest to newest, so the LAST path is the most recent paste: analyze that one first. Entries carry `filename` when the harness stored one; match on it when the user's message mentions a name.
- Run every command yourself, never ask the user to run modlens or relay paths.
- When the analysis is done, delete the recovery output directory (each entry's `path` sits inside it): the files are private copies of the user's pastes, and nothing else cleans them up. Keep them only if the user asked.
- If the output's `detected` field is absent, detection failed and every store was scanned: check `harness` and `filename` match what you expect, force `--harness <claude-code|pi|opencode>` if not, and when in doubt ask the user for the file instead of describing the wrong image.
- Recovery is scoped to this project (the harness's own record of its working directory is checked), and recovered files are private to the user (0600).
- If recovery fails, ask the user to drag the image file into the terminal or type its path.

## Any other harness, or nothing matches

No path tag and `recover-paste` reports no transcripts: do not guess. Ask the user for the image file path, or suggest dragging the file into the terminal.
