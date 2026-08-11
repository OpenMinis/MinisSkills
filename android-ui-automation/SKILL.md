---
name: android-ui-automation
description: >
  Automate Android apps that have no public API or web version by driving the
  UI layer through the Accessibility Service. Handles: deep-link launch (open
  an app into a specific screen), intelligent node location (find a button or
  text by fuzzy match, not exact text), tap-and-verify (confirm an action had
  its effect), and human-like swipes. Use this whenever the user wants to
  control a phone-only app on Android — e.g. "open Spotify and play X",
  "tap the like button", "swipe through my feed", "play 连名带姓", anything
  involving `spotify://`, `weixin://`, or apps with no web/API surface. Also
  use when the user asks why an automation didn't work (permissions, missing
  app, hidden view trees). Android-only; requires the Minis Accessibility
  Service enabled.
compatibility: Android, requires the Minis Accessibility Service; uses the bundled android-a11y-cli
---

# Android UI Automation

Drive Android apps through their **UI layer** when they have no public API or
web version. This is the fallback that makes "phone-only" apps automatable.

## When to use

- The target app has **no API / no web page** (WeChat Moments, many CN apps).
- Offload fine-grained clicking to reliable scripts instead of brittle commands.
- The user asks to **play/search/open/tap/swipe** inside an installed Android app.

Do **not** use this for apps that already have a proper skill (e.g.
`bilibili-hub`, `spotify-hub`) — prefer the API path when one exists.

## Core workflow

Follow this order. Each step has a reason; don't skip verification.

1. **Resolve the target**
   Confirm the app is installed. If unsure, ask the user or try the deep link
   and check the foreground package (see step 2).

2. **Launch via deep link** — `scripts/open_deep_link.py`
   ```
   python3 scripts/open_deep_link.py "spotify://search/circles%20post%20malone" --pkg com.spotify.music
   ```
   - It constructs/opens the link **and verifies the app reached the foreground**.
   - Percent-encode query values (CJK and `&`/`?` break raw links).
   - If it returns `ok:false`, don't proceed — the app is missing, the scheme
     is unhandled, or something redirected. Surface the error.
   - ⚠️ Some apps (Spotify) land on a **suggestion page**, not results — tap a
     suggestion row first (see `references/app-deep-links.md`), then locate the
     result.

3. **Locate the node** — `scripts/find_node.py`
   ```
   python3 scripts/find_node.py "Circles" --clickable-only --top 5
   ```
   - Uses fuzzy scoring (exact > substring > node-fragment), prefers clickable.
   - Read the `nodeId` and `center` from the top result.

4. **Tap and verify** — `scripts/tap_and_verify.py`
   ```
   python3 scripts/tap_and_verify.py --query "Circles – Post Malone" --marker "暂停"
   ```
   - The `marker` is the proof it worked (e.g. after tapping play, a **pause**
     button must appear). Never report success without a marker.
   - Retries a few times with relocation in case the tree changed.

5. **Human-like swipes** (when the tree is unavailable) — use gestures:
   ```
   android-a11y-cli gesture swipe X1 Y1 X2 Y2
   ```
   Vary distance/pause randomly to look natural. This is the ONLY fallback when
   an app (like WeChat Moments) hides its view tree.

## Why the verify step matters

A raw tap is fire-and-forget: the UI may be mid-animation or the node may have
drifted. Verifying a **success marker** (pause button, title, toast) converts
"I clicked something" into "I know it worked". If the marker never appears,
say so honestly instead of claiming success.

## Known limitations

- Apps can **hide their view tree** from the Accessibility Service (WeChat
  Moments is a known case). When `ui dump` returns no app nodes, **do NOT
  blind-tap guessed coordinates** — either use swipes (scroll-only) or ask the
  user to tap precisely.
- The Accessibility Service can be **revoked** (e.g. after a force-stop). Check
  `android-a11y-cli service status`; if not running, ask the user to re-enable
  it in Settings → Accessibility.
- Deep-link support varies by app/build. Read `references/app-deep-links.md`
  for the tested set and always confirm foreground.

## Examples

**Play a song on Spotify (no API key, no Premium):**
```
python3 scripts/open_deep_link.py "spotify://search/circles%20post%20malone"
python3 scripts/find_node.py "添加建议"          # suggestion page → tap to get results
python3 scripts/tap_and_verify.py --query "添加建议“circles post malone”" --marker "Circles"
python3 scripts/find_node.py "Circles – Post Malone" --clickable-only
python3 scripts/tap_and_verify.py --query "Circles – Post Malone" --marker "暂停"
```

**Human-like feed scroll (WeChat Moments):**
```
android-a11y-cli ui info            # confirm weixin:// foreground
android-a11y-cli gesture swipe 540 1600 540 800   # repeat with varied distance/pause
```

**Decline gracefully when the app can't be reached:**
Report `ok:false` from `open_deep_link.py` rather than proceeding blind.

## Output format

Always report the confirmed state, e.g.:

# [Result]
- Opened: spotify://search/... via deep link, foreground=com.spotify.music
- Tapped: node <id> ("Circles – Post Malone")
- Verified: playback bar shows pause button → playing
