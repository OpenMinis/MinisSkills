---
name: hyperframes-cli
version: 1.0.0
description: >
  HyperFrames CLI and Minis rendering. Use for: (1) CLI commands — init, lint, preview,
  render, transcribe, tts, doctor; (2) Minis iOS rendering via hf-render.py
  (set_viewport + minis-browser-use + ffmpeg, no Chrome required); (3) Website-to-video
  workflow — capture a URL and produce a professional MP4 in 7 steps; (4) Preview/snapshot
  compositions at correct resolution. Trigger when user says render, init project, lint,
  transcribe audio, generate TTS, capture a website for video, or run any hyperframes CLI command.
source: |
  Adapted from the official HyperFrames CLI and website-to-hyperframes skills by HeyGen.
  Originals:
    https://github.com/heygen-com/hyperframes/tree/main/skills/hyperframes-cli
    https://github.com/heygen-com/hyperframes/tree/main/skills/website-to-hyperframes
  Original license: Apache-2.0 (https://github.com/heygen-com/hyperframes/blob/main/LICENSE)
  Minis adaptation: Merged hyperframes-cli + website-to-hyperframes into a single skill,
  added hf-render.py (iOS-native renderer using minis-browser-use set_viewport + ffmpeg),
  added check-env.py and install-skill.py for dependency management.
  Adapter copyright: OpenMinis contributors, MIT License.
---

# HyperFrames CLI

## Environment Check (Run First)

Before any task, verify the environment is ready:

```bash
python3 /var/minis/skills/hyperframes-cli/scripts/check-env.py
```

This checks:
- `minis-browser-use` — built-in Minis tool for browser control (required for rendering and preview)
- `ffmpeg` — video encoding
- `hyperframes` skill — composition authoring
- `hyperframes-cli` skill — this skill itself (hf-render.py)

**If anything is missing**, run with `--fix` to auto-install:
```bash
python3 /var/minis/skills/hyperframes-cli/scripts/check-env.py --fix
```

Or install a specific skill manually:
```bash
# From heygen-com/hyperframes (HyperFrames skills)
python3 /var/minis/skills/hyperframes-cli/scripts/install-skill.py \
  hyperframes --repo heygen-com/hyperframes --subdir skills

# From OpenMinis/MinisSkills (community skills)
python3 /var/minis/skills/hyperframes-cli/scripts/install-skill.py notion-hub
```

**If `minis-browser-use` is missing**: it is a Minis built-in tool. Update Minis App to the latest version — it ships with the app and cannot be installed separately.

After installing missing skills, **restart the conversation** for them to take effect.

Everything runs through `npx hyperframes`. Requires Node.js >= 22 and FFmpeg.

## Workflow

1. **Scaffold** — `npx hyperframes init my-video`
2. **Write** — author HTML composition (see the `hyperframes` skill)
3. **Lint** — `npx hyperframes lint`
4. **Preview** — `npx hyperframes preview`
5. **Render** — `npx hyperframes render`

Lint before preview — catches missing `data-composition-id`, overlapping tracks, unregistered timelines.

## Scaffolding

```bash
npx hyperframes init my-video                        # interactive wizard
npx hyperframes init my-video --example warm-grain   # pick an example
npx hyperframes init my-video --video clip.mp4        # with video file
npx hyperframes init my-video --audio track.mp3       # with audio file
npx hyperframes init my-video --non-interactive       # skip prompts (CI/agents)
```

Templates: `blank`, `warm-grain`, `play-mode`, `swiss-grid`, `vignelli`, `decision-tree`, `kinetic-type`, `product-promo`, `nyt-graph`.

`init` creates the right file structure, copies media, transcribes audio with Whisper, and installs AI coding skills. Use it instead of creating files by hand.

## Linting

```bash
npx hyperframes lint                  # current directory
npx hyperframes lint ./my-project     # specific project
npx hyperframes lint --verbose        # info-level findings
npx hyperframes lint --json           # machine-readable
```

Lints `index.html` and all files in `compositions/`. Reports errors (must fix), warnings (should fix), and info (with `--verbose`).

## Previewing

```bash
npx hyperframes preview                   # serve current directory
npx hyperframes preview --port 4567       # custom port (default 3002)
```

Hot-reloads on file changes. Opens the studio in your browser automatically.

### 🍎 Minis (iOS) Alternative — Preview & Snapshot

Set viewport to composition size first, then navigate. This gives accurate preview at the correct resolution.

```bash
# Preview at correct resolution
minis-browser-use set_viewport --width 960 --height 540
minis-browser-use navigate --url minis://workspace/<project>/index.html

# Snapshot at specific timestamps
minis-browser-use execute_js --script 'window.__hf.seek(2.5)'
minis-browser-use screenshot   # saves to /var/minis/browser/
```

Always `set_viewport` before navigating — otherwise the browser uses the phone's default viewport and the composition renders at the wrong scale.

## Rendering

```bash
npx hyperframes render                                # standard MP4
npx hyperframes render --output final.mp4             # named output
npx hyperframes render --quality draft                # fast iteration
npx hyperframes render --fps 60 --quality high        # final delivery
npx hyperframes render --format webm                  # transparent WebM
npx hyperframes render --docker                       # byte-identical
```

| Flag           | Options               | Default                    | Notes                       |
| -------------- | --------------------- | -------------------------- | --------------------------- |
| `--output`     | path                  | renders/name_timestamp.mp4 | Output path                 |
| `--fps`        | 24, 30, 60            | 30                         | 60fps doubles render time   |
| `--quality`    | draft, standard, high | standard                   | draft for iterating         |
| `--format`     | mp4, webm             | mp4                        | WebM supports transparency  |
| `--workers`    | 1-8 or auto           | auto                       | Each spawns Chrome          |
| `--docker`     | flag                  | off                        | Reproducible output         |
| `--gpu`        | flag                  | off                        | GPU-accelerated encoding    |
| `--strict`     | flag                  | off                        | Fail on lint errors         |
| `--strict-all` | flag                  | off                        | Fail on errors AND warnings |

**Quality guidance:** `draft` while iterating, `standard` for review, `high` for final delivery.

### 🍎 Minis (iOS) — hf-render.py

`npx hyperframes render` requires Puppeteer + Chrome (unavailable on iOS). Use the Minis-native renderer instead — it uses `minis-browser-use set_viewport` to lock the browser to the exact composition size, captures frames at Retina resolution, and encodes with FFmpeg.

**One-line render:**
```bash
python3 /var/minis/skills/hyperframes-cli/hf-render.py <project_dir>
```

**Full options:**
```bash
python3 /var/minis/skills/hyperframes-cli/hf-render.py <project_dir> \
  --fps 24 \
  --quality high \
  --output /var/minis/workspace/<project>/renders/output.mp4
```

| Flag | Options | Default | Notes |
|---|---|---|---|
| `--fps` | 24, 30 | 24 | 30fps increases render time ~25% |
| `--quality` | draft, standard, high | standard | draft=2Mbps, standard=4Mbps, high=8Mbps |
| `--output` | path | `<project>/renders/output.mp4` | Output path |
| `--width` / `--height` | px | auto from `data-width/height` | Override composition size |

**How it works:**
1. `set_viewport W H` — locks browser CSS viewport to composition size
2. Navigate to `minis://workspace/<rel-path>/index.html` (supports subdirectories)
3. Wait for `window.__hf` (`{ duration, seek }`) — works with GSAP and pure CSS animations
4. For each frame: `execute_js __hf.seek(t)` → `screenshot --with-base64` → save JPEG
5. Frames captured at Retina resolution (e.g. 2880×1620 for 960×540 @ DPR=3)
6. `ffmpeg` lanczos-downscale → MP4 (h264_videotoolbox, fallback libx264)
7. `set_viewport --reset` always runs — even on error or Ctrl-C

**Performance:** ~10fps capture (~12s for a 5s@24fps video on iPhone).

**Requirements for `index.html`:**

The composition MUST expose `window.__hf` at the end of its `<script>` block:

```js
// Required: __hf render protocol
const DURATION = 5.0; // seconds — must match your actual animation length
window.__hf = {
  get duration() { return DURATION; },
  seek(t) { tl.pause(); tl.seek(Math.max(0, Math.min(t, DURATION)), false); }
};
window.__playerReady = true;
window.__renderReady = true;
```

**DURATION must equal the GSAP timeline's actual duration.** If ambient animations use `repeat`, calculate carefully:

```js
// WRONG — glow-gold ends at 0.4 + 2.0*(2+1) = 6.4s, timeline extends past 5s → black frames
tl.to("#glow", { duration: 2.0, repeat: 2, yoyo: true }, 0.4);

// CORRECT — calculate max repeats that fit within DURATION
const DURATION = 5.0;
tl.to("#glow", {
  duration: 2.0,
  repeat: Math.floor((DURATION - 0.4) / 2.0) - 1,  // = 1 repeat, ends at 4.4s
  yoyo: true
}, 0.4);
```

**HTML template rules (required for correct rendering):**
- Fixed `width/height` on `html`, `body`, and `#stage` — match `data-width`/`data-height`
- No `<meta name="viewport">` — the renderer sets viewport externally via `set_viewport`
- No scale wrappers, no `transform: scale()` on the stage — these break pixel accuracy
- Project must be under `/var/minis/workspace/` — the renderer converts the path to a `minis://` URL
- **Multi-scene layout: use `position:absolute; inset:0` per scene** — see note below

> **⚠️ Minis layout difference from standard HyperFrames:**
> The standard skill says `.scene-content` should use `width:100%; height:100%`. In Minis/iOS
> WebKit, `set_viewport` sets the CSS viewport *width* but iOS Safari's height is influenced by
> system UI, so `height:100%` on a flex container can exceed the stage height. Content then
> centers relative to that oversized container and lands outside the screenshot crop.
>
> **Fix:** for compositions with multiple sequential scenes, give each scene its own
> `position:absolute; inset:0` container (see the `hyperframes` skill → "Multi-scene compositions"
> section). For single-scene compositions, `width:100%; height:100%` is fine.

```html
<!-- Correct HTML structure -->
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<!-- NO viewport meta -->
<style>
  html, body { margin: 0; padding: 0; width: 960px; height: 540px; overflow: hidden; }
  #stage { width: 960px; height: 540px; position: relative; overflow: hidden; }
</style>
</head>
<body>
<div id="stage" data-composition-id="my-comp" data-width="960" data-height="540">
  <!-- content -->
</div>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<script>
  window.__timelines = window.__timelines || {};
  const DURATION = 5.0;
  const tl = gsap.timeline({ paused: true });
  // ... tweens ...
  window.__timelines["my-comp"] = tl;

  window.__hf = {
    get duration() { return DURATION; },
    seek(t) { tl.pause(); tl.seek(Math.max(0, Math.min(t, DURATION)), false); }
  };
  window.__playerReady = true;
  window.__renderReady = true;
</script>
</body>
</html>
```

## Transcription

```bash
npx hyperframes transcribe audio.mp3
npx hyperframes transcribe video.mp4 --model medium.en --language en
npx hyperframes transcribe subtitles.srt   # import existing
npx hyperframes transcribe subtitles.vtt
npx hyperframes transcribe openai-response.json
```

## Text-to-Speech

```bash
npx hyperframes tts "Text here" --voice af_nova --output narration.wav
npx hyperframes tts script.txt --voice bf_emma
npx hyperframes tts --list  # show all voices
```

## Troubleshooting

```bash
npx hyperframes doctor       # check environment (Chrome, FFmpeg, Node, memory)
npx hyperframes browser      # manage bundled Chrome
npx hyperframes info         # version and environment details
npx hyperframes upgrade      # check for updates
```

Run `doctor` first if rendering fails. Common issues: missing FFmpeg, missing Chrome, low memory.

## Other

```bash
npx hyperframes compositions   # list compositions in project
npx hyperframes docs           # open documentation
npx hyperframes benchmark .    # benchmark render performance
```

---

## Website → Video Workflow

Turn any URL into a video in 7 steps. Read each step's reference file before executing it.

| Step | What | Reference |
|------|------|-----------|
| 1 | Capture website (screenshots, tokens, assets) | [references/website-to-video/step-1-capture.md](references/website-to-video/step-1-capture.md) |
| 2 | Write DESIGN.md (brand colors, fonts, style) | [references/website-to-video/step-2-design.md](references/website-to-video/step-2-design.md) |
| 3 | Write SCRIPT.md (narration, scene durations) | [references/website-to-video/step-3-script.md](references/website-to-video/step-3-script.md) |
| 4 | Write STORYBOARD.md (per-beat creative direction) | [references/website-to-video/step-4-storyboard.md](references/website-to-video/step-4-storyboard.md) |
| 5 | Generate VO + map word timestamps to beats | [references/website-to-video/step-5-vo.md](references/website-to-video/step-5-vo.md) |
| 6 | Build compositions (use the `hyperframes` skill) | [references/website-to-video/step-6-build.md](references/website-to-video/step-6-build.md) |
| 7 | Lint, snapshot, render, handoff | [references/website-to-video/step-7-validate.md](references/website-to-video/step-7-validate.md) |

**Visual techniques** (SVG drawing, Canvas 2D, 3D, typing, MotionPath, Lottie): [references/website-to-video/techniques.md](references/website-to-video/techniques.md)

### Quick formats

| Type | Duration | Beats | Narration |
|---|---|---|---|
| Social ad (IG/TikTok) | 10-15s | 3-4 | Optional |
| Product demo | 30-60s | 5-8 | Full |
| Feature announcement | 15-30s | 3-5 | Full |
| Brand reel | 20-45s | 4-6 | Optional |

Landscape: 1920×1080 · Portrait: 1080×1920 · Square: 1080×1080
