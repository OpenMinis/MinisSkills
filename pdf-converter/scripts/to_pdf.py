#!/usr/bin/env python3
"""Convert Markdown/HTML/Text/Images to PDF (Chinese + Emoji, half-width digits)

Engine: pandoc (→typst) + typst (compile PDF)

- Emoji: embedded as Twemoji SVG images (crisp vector rendering, no bitmap distortion)
- Fonts: native typst fallback (DejaVu Sans → WenQuanYi Zen Hei), half-width digits
"""
import argparse, os, sys, shutil, tempfile, subprocess as sp, urllib.request, concurrent.futures
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_TEMPLATE = os.path.join(_SKILL_DIR, 'assets', 'template.typ')
_CACHE_DIR = os.path.join(_SKILL_DIR, 'assets', 'emoji_cache')
# CDN mirrors tried in order — first success wins. GitHub raw is primary
# (canonical source); jsDelivr and unpkg are CDNs mirroring the npm package,
# used as fallback when raw.githubusercontent.com is rate-limited or blocked.
# Override the whole list with the EMOJI_CDN_BASE env var (single URL).
_CDN_BASES = [b for b in (
    os.environ.get('EMOJI_CDN_BASE'),
    'https://raw.githubusercontent.com/twitter/twemoji/v14.0.2/assets/svg',
    'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg',
    'https://unpkg.com/twemoji@14.0.2/assets/svg',
) if b]

# Per-request timeout for SVG downloads. urlretrieve has no timeout parameter,
# so we use urlopen + shutil.copyfileobj below. Mobile networks (especially
# iSH on iOS) need this to avoid hanging the whole prefetch batch when a
# single CDN node is unresponsive.
_SVG_TIMEOUT = int(os.environ.get('EMOJI_SVG_TIMEOUT', '15'))


def _detect_prefetch_workers():
    """Concurrency for the SVG prefetch batch.

    Termux (PREFIX set) runs native ARM → 8 workers.
    iSH on iOS is interpreted x86 with tight fd/memory limits → 4 workers.
    Override either via the PDF_CONVERTER_WORKERS env var.
    """
    env = os.environ.get('PDF_CONVERTER_WORKERS')
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return 8 if os.environ.get('PREFIX') else 4


_PREFETCH_WORKERS = _detect_prefetch_workers()


def _find_font_dir():
    """Locate the system fonts directory (Alpine, Termux, Debian, macOS).

    Returns the first existing candidate path.
    """
    prefix = os.environ.get('PREFIX', '')  # Termux sets PREFIX
    candidates = [
        '/usr/share/fonts',                                  # Alpine/Debian
        os.path.join(prefix, 'share/fonts'),                 # Termux
        '/usr/local/share/fonts',                            # macOS Homebrew
        '/System/Library/Fonts',                             # macOS
    ]
    for d in candidates:
        if d and os.path.isdir(d):
            return d
    return '/usr/share/fonts'  # fallback default


# External tools the script shells out to. Each entry lists install commands
# per platform; shown to the user when the binary is missing.
_INSTALL_HINTS = {
    'pandoc': (
        ('Alpine (iSH/Docker)', 'apk add pandoc'),
        ('Termux (Android)',    'pkg install pandoc'),
        ('Debian/Ubuntu',       'apt install pandoc'),
    ),
    'typst': (
        ('Alpine (iSH/Docker)', 'apk add typst'),
        ('Termux (Android)',    'pkg install typst'),
        ('Debian/Ubuntu',       'apt install typst'),
    ),
}


def _check_dependencies(*, need_pil=False, core=True):
    """Verify required external tools exist; exit with install hints if missing.

    core (pandoc + typst) is required for text/markup conversion.
    PIL is only required for the image-merge path (lazy-imported there).
    Pass core=False for image-only mode so users aren't forced to install
    the heavy pandoc/typst toolchain just to merge images.
    """
    missing = []
    if core:
        for tool in ('pandoc', 'typst'):
            if shutil.which(tool) is None:
                missing.append(tool)
    if need_pil:
        try:
            import PIL  # noqa: F401
        except ImportError:
            missing.append('python-pillow')
    if not missing:
        return
    print('❌ Missing required dependencies: ' + ', '.join(missing),
          file=sys.stderr)
    print('\nInstall hints:', file=sys.stderr)
    for tool in missing:
        if tool in _INSTALL_HINTS:
            print(f'\n  {tool}:', file=sys.stderr)
            for platform, cmd in _INSTALL_HINTS[tool]:
                print(f'    {platform:<20} {cmd}', file=sys.stderr)
        elif tool == 'python-pillow':
            print('    pip3 install pillow', file=sys.stderr)
            print('    Alpine:  apk add py3-pillow', file=sys.stderr)
            print('    Termux:  pkg install python-pillow', file=sys.stderr)
    sys.exit(1)


# Twemoji provides only 116 of 448 codepoints in U+2600-27BF.
# Store the exact set to avoid 404s on non-emoji symbols (★♔♩➜ ☐☒ etc.).
_TWEMOJI_SYMBOLS = frozenset({
    0x2600, 0x2601, 0x2602, 0x2603, 0x2604, 0x260E, 0x2611, 0x2614, 0x2615, 0x2618,
    0x261D, 0x2620, 0x2622, 0x2623, 0x2626, 0x262A, 0x262E, 0x262F, 0x2638, 0x2639,
    0x263A, 0x2640, 0x2642, 0x2648, 0x2649, 0x264A, 0x264B, 0x264C, 0x264D, 0x264E,
    0x264F, 0x2650, 0x2651, 0x2652, 0x2653, 0x265F, 0x2660, 0x2663, 0x2665, 0x2666,
    0x2668, 0x267B, 0x267E, 0x267F, 0x2692, 0x2693, 0x2694, 0x2695, 0x2696, 0x2697,
    0x2699, 0x269B, 0x269C, 0x26A0, 0x26A1, 0x26A7, 0x26AA, 0x26AB, 0x26B0, 0x26B1,
    0x26BD, 0x26BE, 0x26C4, 0x26C5, 0x26C8, 0x26CE, 0x26CF, 0x26D1, 0x26D3, 0x26D4,
    0x26E9, 0x26EA, 0x26F0, 0x26F1, 0x26F2, 0x26F3, 0x26F4, 0x26F5, 0x26F7, 0x26F8,
    0x26F9, 0x26FA, 0x26FD, 0x2702, 0x2705, 0x2708, 0x2709, 0x270A, 0x270B, 0x270C,
    0x270D, 0x270F, 0x2712, 0x2714, 0x2716, 0x271D, 0x2721, 0x2728, 0x2733, 0x2734,
    0x2744, 0x2747, 0x274C, 0x274E, 0x2753, 0x2754, 0x2755, 0x2757, 0x2763, 0x2764,
    0x2795, 0x2796, 0x2797, 0x27A1, 0x27B0, 0x27BF,
})


def _is_emoji_char(c):
    """True if *c* is a Twemoji-covered emoji codepoint.

    U+2600-27BF: only the 116 codepoints Twemoji actually provides
                 (avoids 404s on symbols like ☐☒★♔♩➜).
    U+1F300-1FAFF: full range (Twemoji covers virtually all).
    """
    cp = ord(c)
    if cp in _TWEMOJI_SYMBOLS:
        return True
    if 0x1F300 <= cp <= 0x1FAFF:
        return True
    return False


def _ensure_cache():
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _download_with_timeout(url, path):
    """Download URL to path with a per-request socket timeout.

    Returns True on success, False on any error (caller must clean up `path`).
    urllib.request.urlretrieve has no timeout parameter, so we use urlopen +
    shutil.copyfileobj — necessary for flaky mobile networks where a hung
    connection would otherwise stall the whole prefetch batch.
    """
    try:
        with urllib.request.urlopen(url, timeout=_SVG_TIMEOUT) as resp:
            with open(path, 'wb') as f:
                shutil.copyfileobj(resp, f)
        return True
    except Exception:
        return False


def _download_emoji_svg(emoji_char):
    """Download Twemoji SVG for an emoji, return local path. None on failure."""
    _ensure_cache()
    cps = [ord(c) for c in emoji_char]
    cps_no_vs = [cp for cp in cps if cp != 0xFE0F]

    def _valid(svg_path):
        """A valid Twemoji SVG must be non-empty and start with <svg."""
        try:
            with open(svg_path, 'rb') as f:
                head = f.read(16)
            return len(head) > 0 and head.lstrip().startswith(b'<svg')
        except Exception:
            return False

    # 1. Check cache first (zero network cost)
    for cps_list in [cps, cps_no_vs]:
        hex_name = '-'.join(f'{cp:x}' for cp in cps_list)
        svg_path = os.path.join(_CACHE_DIR, f'{hex_name}.svg')
        if os.path.exists(svg_path):
            if _valid(svg_path):
                return svg_path
            os.unlink(svg_path)  # corrupted cache entry, drop it

    # 2. Cache miss — try every CDN mirror, then both codepoint spellings
    for cps_list in [cps, cps_no_vs]:
        hex_name = '-'.join(f'{cp:x}' for cp in cps_list)
        svg_path = os.path.join(_CACHE_DIR, f'{hex_name}.svg')
        for base in _CDN_BASES:
            url = f'{base}/{hex_name}.svg'
            if _download_with_timeout(url, svg_path) and _valid(svg_path):
                return svg_path
            if os.path.exists(svg_path):
                os.unlink(svg_path)
    return None


def _collect_emoji_sequences(text):
    """Scan text, return list of unique emoji sequences (preserving first-seen order)."""
    seqs = []
    seen = set()
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if _is_emoji_char(c):
            j = i + 1
            while j < n:
                nc = text[j]
                ncp = ord(nc)
                if ncp == 0xFE0F or ncp == 0x200D or _is_emoji_char(nc):
                    j += 1
                else:
                    break
            seq = text[i:j]
            if seq not in seen:
                seen.add(seq)
                seqs.append(seq)
            i = j
        else:
            i += 1
    return seqs


def _prefetch_svgs(sequences):
    """Batch-download missing SVGs concurrently (8 workers).

    Called once before the replacement pass so all SVGs are in cache
    when _download_emoji_svg runs in the main loop (pure cache hits).
    """
    _ensure_cache()

    def _is_valid(svg_path):
        try:
            with open(svg_path, 'rb') as f:
                head = f.read(16)
            return head.lstrip().startswith(b'<svg')
        except Exception:
            return False

    # Determine which sequences need downloading
    to_fetch = []  # list of hex_names
    seen_hex = set()
    for seq in sequences:
        cps_no_vs = [cp for cp in (ord(c) for c in seq) if cp != 0xFE0F]
        hex_name = '-'.join(f'{cp:x}' for cp in cps_no_vs)
        if hex_name in seen_hex:
            continue
        # Check if already cached and valid
        svg_path = os.path.join(_CACHE_DIR, f'{hex_name}.svg')
        if os.path.exists(svg_path) and _is_valid(svg_path):
            continue
        seen_hex.add(hex_name)
        to_fetch.append(hex_name)

    if not to_fetch:
        return

    def _fetch(hex_name):
        svg_path = os.path.join(_CACHE_DIR, f'{hex_name}.svg')
        for base in _CDN_BASES:
            url = f'{base}/{hex_name}.svg'
            if _download_with_timeout(url, svg_path) and _is_valid(svg_path):
                return
            if os.path.exists(svg_path):
                os.unlink(svg_path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=_PREFETCH_WORKERS) as ex:
        list(ex.map(_fetch, to_fetch))


def _scale_emoji(typst_content):
    """Replace emoji in typst content with SVG image references."""
    # Phase 1: collect unique emoji sequences
    seqs = _collect_emoji_sequences(typst_content)

    # Phase 2: batch-download missing SVGs in parallel (one shot, fast)
    if seqs:
        _prefetch_svgs(seqs)

    # Phase 3: replace — all SVGs now cached (or confirmed unavailable)
    result = []
    i = 0
    n = len(typst_content)
    replaced = 0
    failed = 0
    while i < n:
        c = typst_content[i]
        if _is_emoji_char(c):
            # Collect the full emoji sequence (incl. ZWJ, VS16)
            j = i + 1
            while j < n:
                nc = typst_content[j]
                ncp = ord(nc)
                if ncp == 0xFE0F or ncp == 0x200D or _is_emoji_char(nc):
                    j += 1
                else:
                    break
            seq = typst_content[i:j]
            svg_path = _download_emoji_svg(seq)  # cache hit (prefetched)
            if svg_path and os.path.exists(svg_path):
                # baseline: 5% aligns image bottom just below text baseline
                result.append(f'#box(image("{svg_path}", width: 1.2em), baseline: 5%)')
                replaced += 1
            else:
                # SVG unavailable, fall back to bitmap font
                safe = seq.replace('\\', '\\\\').replace('"', '\\"')
                result.append(f'#box(text(size: 1.2em, font: "Noto Color Emoji")[{safe}], baseline: 5%)')
                failed += 1
            i = j
        else:
            result.append(c)
            i += 1
    if replaced > 0:
        print(f"  {replaced} emoji → SVG", file=sys.stderr)
    if failed > 0:
        print(f"  ⚠️ {failed} emoji SVG download failed, fell back to bitmap", file=sys.stderr)
    return ''.join(result)


def read_text(path):
    raw = open(path, 'rb').read()
    for enc in ('utf-8', 'utf-16', 'gbk', 'gb2312', 'latin-1'):
        try:
            return raw.decode(enc)
        except:
            pass
    return raw.decode('utf-8', errors='replace')


def _get_template():
    with open(_TEMPLATE, 'r', encoding='utf-8') as f:
        return f.read()


def _pandoc_to_typst(inp):
    r = sp.run(['pandoc', inp, '-t', 'typst'], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"❌ pandoc: {r.stderr}", file=sys.stderr)
        return None
    return r.stdout


def _typst_compile(typ_content, out_pdf):
    work = tempfile.mkdtemp(prefix='typst_')
    typ_file = os.path.join(work, 'doc.typ')
    with open(typ_file, 'w', encoding='utf-8') as f:
        f.write(typ_content)
    try:
        cmd = ['typst', 'compile', '--font-path', _find_font_dir(),
               '--root', '/', typ_file, out_pdf]
        r = sp.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(f"❌ typst: {r.stderr[:500]}", file=sys.stderr)
            return False
        return True
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _fix_table_widths(typst_content):
    """Replace pandoc's `columns: N` (integer count) with 1fr equal columns,
    so tables span the full page content width.

    Pandoc emits `columns: 4` for narrow tables; typst then sizes the table
    to content width only. Converting to `columns: (1fr, 1fr, 1fr, 1fr)`
    stretches the table to the full content width.
    """
    import re

    def repl(m):
        n = int(m.group(1))
        cols = ', '.join(['1fr'] * n)
        return f'columns: ({cols}),'

    return re.sub(r'columns:\s*(\d+)\s*,', repl, typst_content)


def _build_content(body):
    template = _get_template()
    scaled = _scale_emoji(body)
    fixed = _fix_table_widths(scaled)
    return template + '\n' + fixed


def md_to_pdf(inp, out):
    body = _pandoc_to_typst(inp)
    if body is None:
        return False
    content = _build_content(body)
    if _typst_compile(content, out):
        print(f"✅ PDF generated: {out}")
        return True
    return False


def txt_to_pdf(inp, out, title=None):
    text = read_text(inp)
    lines = []
    for line in text.splitlines():
        esc = line.replace('\\', '\\\\').replace('#', '\\#').replace('$', '\\$').replace('<', '\\<').replace('>', '\\>')
        lines.append(esc if esc.strip() else '')
    body = '\n\n'.join(lines)
    t = title or Path(inp).stem
    content = _build_content(f'\n\n= {t}\n\n' + body)
    if _typst_compile(content, out):
        print(f"✅ PDF generated: {out}")
        return True
    return False


def html_to_pdf(inp, out):
    body = _pandoc_to_typst(inp)
    if body is None:
        return False
    content = _build_content(body)
    if _typst_compile(content, out):
        print(f"✅ PDF generated: {out}")
        return True
    return False


def img_to_pdf(paths, out):
    from PIL import Image
    imgs = [Image.open(p).convert('RGB') for p in paths]
    imgs[0].save(out, save_all=True, append_images=imgs[1:], quality=95)
    print(f"✅ PDF generated: {out} ({len(imgs)} pages)")


def main():
    p = argparse.ArgumentParser(description='Convert to PDF: MD/HTML/Text/Images')
    p.add_argument('input', nargs='+', help='input file(s)')
    p.add_argument('-o', '--output', help='output PDF path')
    p.add_argument('--title', help='document title (text mode only)')
    a = p.parse_args()

    inputs = [Path(x) for x in a.input]
    out = a.output or (inputs[0].with_suffix('.pdf').name if len(inputs) == 1 else 'merged.pdf')
    IMG = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}

    is_img_only = all(x.suffix.lower() in IMG for x in inputs)
    # Image-merge needs only PIL; text/markup paths also need pandoc+typst.
    _check_dependencies(need_pil=is_img_only, core=not is_img_only)

    if is_img_only:
        img_to_pdf([str(x) for x in inputs], out)
        return
    if len(inputs) != 1:
        print("❌ Multiple files are only supported for image merging", file=sys.stderr)
        sys.exit(1)

    x = inputs[0]
    e = x.suffix.lower()
    if e in IMG:
        img_to_pdf([str(x)], out)
    elif e == '.md':
        if not md_to_pdf(str(x), out):
            sys.exit(1)
    elif e in ('.html', '.htm'):
        if not html_to_pdf(str(x), out):
            sys.exit(1)
    elif e == '.txt':
        if not txt_to_pdf(str(x), out, a.title or x.stem):
            sys.exit(1)
    else:
        # pandoc fallback (.rst/.org/.latex etc.)
        body = _pandoc_to_typst(str(x))
        if body is None:
            sys.exit(1)
        content = _build_content(body)
        if not _typst_compile(content, out):
            sys.exit(1)
        print(f"✅ PDF generated: {out}")


if __name__ == '__main__':
    main()
