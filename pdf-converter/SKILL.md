---
name: pdf-converter
description: >
  Convert Markdown, HTML, plain text, images, and pandoc-supported formats to PDF
  with CJK font rendering, half-width numbers, and emoji support. Use this skill
  whenever the user asks to convert a file to PDF, generate a PDF from markdown or
  HTML, export a PDF, or run "转PDF" / "生成PDF" / "导出PDF".
---

# pdf-converter

Convert various file formats to PDF with proper CJK rendering and emoji support.

## When to Use This Skill

Use this skill when the user needs to:

- Convert Markdown (`.md`) to PDF while preserving formatting, emoji, and Chinese text
- Convert HTML (`.htm`, `.html`) to PDF
- Convert plain text (`.txt`) to PDF
- Convert images (`.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`) to PDF — including multi-image merge
- Convert any pandoc-supported format (`.rst`, `.org`, `.latex`, etc.) to PDF

## Workflow

### Step 1: Prepare the input file

Make sure the input file exists and is readable. If the user provides content directly, save it to a temporary file first.

### Step 2: Run the conversion script

Execute the conversion script with the required arguments:

```bash
python3 scripts/to_pdf.py input.md -o output.pdf
```

The script handles all format detection automatically based on the file extension.

### Step 3: Verify the output

Check that the PDF was created and has a non-zero file size:

```bash
ls -la output.pdf
```

### Step 4: Handle long-running conversions

Conversion takes approximately **40-60 seconds** because CJK font subsetting (~20s) and weasyprint rendering (~15s) are CPU-intensive. Run long conversions in the background:

```bash
nohup python3 scripts/to_pdf.py input.md -o output.pdf > /tmp/pdf.log 2>&1 &
```

## Output Formatting

The PDF uses an amber theme with these conventions:

- **Tables**: amber header (#D97706 with white text) + zebra-striped rows (gray/white) + thin grid borders
- **Code blocks**: light gray background (#f2f3f5) + monospace font (DejaVu Sans Mono) + top gray bar
- **Blockquotes**: left amber border (#D97706) + light orange background (#fef7ed)
- **Headings**: h1 gets an amber underline; h1-h4 have clear visual hierarchy
- **Page footers**: centered page numbers

## How It Works

The conversion pipeline has three stages:

1. **pandoc** converts the input format to an HTML5 fragment
2. **fontTools** subsets CJK fonts (WenQuanYi Zen Hei) and Latin fonts (DejaVu Sans) for efficient embedding
3. **weasyprint** renders the HTML5 + @font-face CSS to PDF using a custom fontconfig that separates Asian and Latin font stacks

### Font Strategy

| Character type | Font | Processing |
|---|---|---|
| ASCII (digits/letters) | DejaVu Sans | Subsetted @font-face; half-width glyphs |
| CJK characters | WenQuanYi Zen Hei | Subsetted @font-face; excludes ASCII so digits fall back to DejaVu Sans |
| Emoji | Twemoji SVG | Downloaded from CDN in real-time; base64 inline in the HTML |

**Full-width digit fix**: A custom fontconfig configuration isolates system CJK fonts so weasyprint uses only the @font-face subset fonts + DejaVu Sans fallback, ensuring all numbers render as half-width.

## File Structure

```
pdf-converter/
├── SKILL.md
├── assets/
│   └── Twemoji-subset.ttf     # Font subset for emoji rendering
├── scripts/
│   ├── to_pdf.py              # Main conversion script
│   ├── _render.py             # weasyprint rendering subprocess
│   ├── gen_fonts.py           # Pre-generate font subsets
│   ├── emoji_img.py           # Emoji SVG download + base64 inline
│   └── subset_emoji.py        # Emoji subsetting (fallback)
└── emoji_cache/              # Cached Twemoji SVGs (created at runtime)
```

## Dependencies

All of the following must be installed on the system:

- **pandoc** (Markdown/format → HTML5)
- **fontTools** (font subsetting)
- **weasyprint** (HTML5 → PDF)
- **WenQuanYi Zen Hei** font and **DejaVu Sans** font
  (the script auto-detects fonts from common paths, see `to_pdf.py` for details)

## Error Handling

- Missing input file → print an error and exit with code 1
- weasyprint rendering error → print the error message and exit with code 2
- Missing output directory → attempt to create it automatically