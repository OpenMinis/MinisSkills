---
name: pdf-converter
description: >
  Convert documents to PDF via a typst-based pipeline. Supports Markdown, HTML, plain text, images, and any
  pandoc-supported format. Use this skill whenever the user asks to
  "convert to PDF", "generate a PDF", "export as PDF", "turn X into a PDF",
  or says "转PDF" / "生成PDF" / "导出PDF". Also covers merging multiple images into one PDF.
compatibility: Python 3, pandoc, typst, py3-pillow; Alpine (iSH) / Termux (Android) / Debian
---

# pdf-converter

Convert documents to PDF with proper CJK rendering, half-width digits, and
emoji support. Uses a typst-based pipeline that compiles markup directly to
PDF in **~5 s per conversion** for a typical 10-page document.

## When to Use This Skill

Use this skill when the user needs to:

- Convert **Markdown** (`.md`) to PDF preserving tables, code blocks, emoji, and Chinese text
- Convert **HTML** (`.htm`, `.html`) to PDF
- Convert **plain text** (`.txt`) to PDF
- Convert **images** (`.png` / `.jpg` / `.jpeg` / `.gif` / `.bmp` / `.webp`) to PDF, including multi-image merge into one PDF
- Convert any **pandoc-supported** format (`.rst`, `.org`, `.latex`, etc.) to PDF

## Workflow

### Step 1 — Prerequisites (self-checked on every run)

The script verifies `pandoc` + `typst` are on `PATH` (and `PIL` for the
image-merge path). If anything is missing, it prints platform-specific install
commands and exits non-zero — no silent pandoc/typst failure later.

| Platform | Install |
|----------|---------|
| Alpine (iSH / Docker) | `apk add pandoc typst py3-pillow font-wqy-zenhei font-dejavu font-noto-emoji` |
| Termux (Android) | `pkg install pandoc typst python-pillow font-wqy-zenhei font-dejavu noto-color-emoji` |
| Debian / Ubuntu | `apt install pandoc typst python3-pillow fonts-wqy-zenhei fonts-dejavu fonts-noto-color-emoji` |

The font directory is auto-detected from candidate paths (`/usr/share/fonts`,
`$PREFIX/share/fonts`, `/usr/local/share/fonts`).

### Step 2 — Run the conversion

Format is detected by the file extension:

```bash
# Markdown → PDF (formatting, emoji, Chinese, half-width digits, amber theme)
python3 scripts/to_pdf.py doc.md -o out.pdf

# HTML → PDF
python3 scripts/to_pdf.py page.html -o out.pdf

# Plain text → PDF (file stem used as title unless --title given)
python3 scripts/to_pdf.py notes.txt -o out.pdf --title "My Notes"

# Merge images into one PDF (one page per image)
python3 scripts/to_pdf.py img1.jpg img2.png -o merged.pdf

# Any pandoc-supported format (.rst/.org/.latex…) → PDF
python3 scripts/to_pdf.py doc.rst -o out.pdf
```

### Step 3 — Verify the output

```bash
ls -la out.pdf
```

On success the script prints `✅ PDF generated: <path>` and exits 0. On failure
it prints a `❌`-prefixed diagnostic to stderr and exits non-zero.

## Performance

```
pandoc (input → typst markup)      ~1-2 s
emoji SVG prefetch (parallel)       ~0 s warm cache, ~30 s first-run for ~90 emoji
typst compile (typst → PDF)         ~1-3 s for a 10-page document
─────────────────────────────────────────
total                               ~5 s warm cache
```

On iOS (iSH, emulated x86) expect a 5–10× slowdown; for very large documents
or first-run emoji downloads, run in the background to avoid iOS killing the
app:

```bash
nohup python3 scripts/to_pdf.py big.md -o big.pdf > /tmp/pdf.log 2>&1 &
```

## Output Formatting (amber theme)

- **Headings**: h1 with amber underline (`#D97706`), h1–h4 hierarchy
- **Tables**: amber header (white bold text) + zebra stripes + thin grid borders, spans full content width
- **Code blocks**: light gray background (`#f2f3f5`) + DejaVu Sans Mono + top gray bar
- **Blockquotes**: amber left bar + light orange background (`#fef7ed`)
- **Emoji**: Twemoji SVG vector images, baseline-aligned with CJK text
- **Footer**: centered page number

## How It Works

```
pandoc (MD/HTML/… → typst)  →  [emoji → SVG, table-width fix]  →  typst compile (→ PDF)
```

| Component | Role |
|-----------|------|
| **pandoc** | Converts MD / HTML / reST / org / latex → typst markup |
| **typst** | Rust binary; compiles typst markup → PDF with native font fallback |
| **Twemoji SVG** | Emoji → vector images; CDN download + local cache |
| **PIL** | Image merging (lazy-imported; image-only mode skips pandoc/typst entirely) |

### Font Strategy

| Character type | Font | Handling |
|----------------|------|----------|
| ASCII (digits / letters) | DejaVu Sans | typst native fallback — half-width glyphs |
| Chinese | WenQuanYi Zen Hei | typst native fallback |
| Emoji | Twemoji SVG | CDN download → typst `image()` embed |

## Configuration (environment variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `EMOJI_CDN_BASE` | unset | Override the Twemoji CDN with a single mirror URL (corporate proxy, ghproxy, air-gapped cache). When unset, a GitHub raw → jsDelivr → unpkg fallback chain is used. |
| `PDF_CONVERTER_WORKERS` | 8 on Termux, 4 elsewhere | Concurrency for SVG prefetch. iSH defaults lower because emulated x86 has tight fd / memory limits. |
| `EMOJI_SVG_TIMEOUT` | 15 | Per-request timeout in seconds for SVG downloads. Raise on very slow networks; lower on fast reliable ones. |

## File Structure

```
pdf-converter/
├── SKILL.md
├── .gitignore
├── assets/
│   ├── template.typ         # typst amber-theme template (committed)
│   └── emoji_cache/         # Twemoji SVG cache (gitignored, created at runtime)
├── scripts/
│   └── to_pdf.py            # main script (pandoc + typst + SVG emoji)
└── evals/
    ├── evals.json           # test cases
    ├── pdf-format-test.md   # comprehensive format test document
    └── pdf-format-test.pdf  # expected output reference (10 pages, ~275 KB)
```

## Error Handling

| Condition | Behavior |
|-----------|----------|
| Missing input file | Python `IOError` / pandoc error, exit non-zero |
| Missing `pandoc` / `typst` (text mode) | Self-check prints install hints, exit 1 |
| Missing `PIL` (image mode) | Self-check prints install hint, exit 1 |
| pandoc parse error | stderr `❌ pandoc: <msg>`, exit 1 |
| typst compile error | stderr `❌ typst: <msg>`, exit 1 |
| typst compile timeout | default 120 s; stderr error, exit 1 |
| Emoji SVG download fails on all mirrors | Falls back to Noto Color Emoji bitmap font; stderr warning, conversion continues |

## Testing

Verify the install (and any dependency change) using the bundled format-test
document, then sanity-check against the bundled reference PDF:

```bash
python3 scripts/to_pdf.py evals/pdf-format-test.md -o /tmp/test.pdf
pdfinfo /tmp/test.pdf | grep Pages      # expect: Pages: 10
ls -la /tmp/test.pdf                    # expect: ~200-350 KB
```

Check visually: amber table headers at full width, SVG emoji rendered (not
tofu boxes), half-width digits inside CJK paragraphs, all sections present.
Compare against `evals/pdf-format-test.pdf` (generated from the same source).

## Key Implementation Notes

- **Table header height**: a show rule replacing cells with plain `text()` drops the cell's `inset`; use `block(inset: ...)` instead to preserve padding.
- **Table width**: pandoc emits `columns: N` for narrow tables → rewritten to `1fr` columns so tables span full content width.
- **Emoji alignment**: `box(image(...), baseline: 5%)` aligns the image bottom with the CJK text baseline.
- **Emoji detection**: `U+2600-27BF` uses a precise frozenset of 116 Twemoji-provided codepoints (not the full range — symbols like ☐☒★♔♪ aren't Twemoji and would 404); `U+1F300-1FAFF` uses the full range.
- **Parallel SVG prefetch**: unique emoji sequences are collected, then missing SVGs are batch-downloaded concurrently before the replacement pass — first-run (empty cache) ~30 s instead of >180 s serial.
- **CDN fallback**: each SVG tries GitHub raw → jsDelivr → unpkg (or the single URL in `EMOJI_CDN_BASE`); a 404 or timeout on one mirror transparently retries the next, with a per-request timeout (`EMOJI_SVG_TIMEOUT`, default 15 s) to prevent hung connections from stalling the prefetch batch.
- **Mode-aware dependency check**: image-merge mode requires only PIL; text/markup mode requires pandoc + typst. Image-only users aren't forced to install the heavy pandoc/typst toolchain.
