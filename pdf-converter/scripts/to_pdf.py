#!/usr/bin/env python3
"""转PDF：Markdown/HTML/文本/图片 → PDF（中文 + Emoji，数字半角）

引擎：pandoc（MD→HTML）+ fontTools（CJK子集化）+ weasyprint（HTML→PDF）

字体策略（解决全角数字问题的核心）：
  - ASCII（数字/字母/符号）→ DejaVu Sans（系统自带，半角字形）
  - 中文/CJK标点 → WenQuanYi Zen Hei 子集（不含ASCII，回退到DejaVu渲染数字）
  - Emoji → Twemoji 预子集化

性能：wqy subset ~20s + weasyprint ~15s ≈ 35-60s
"""
import argparse, os, sys, shutil, tempfile, subprocess as sp
from pathlib import Path

# Emoji 替换模块（把 emoji 替换为内联 SVG 图片，避免 CBDT 位图字体尺寸巨大）
sys.path.insert(0, os.path.dirname(__file__))
from emoji_img import replace_emojis_with_svg as _replace_emoji

# ── 字体源 ──
CJK_TTC = '/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc'   # fontNumber 0 = Regular
DEJAVU_REG = '/usr/share/fonts/dejavu/DejaVuSans.ttf'     # Latin Regular
DEJAVU_BLD = '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf'  # Latin Bold
# Emoji 不用字体（CBDT位图字体在weasyprint中尺寸巨大），
# 改用 emoji_img.py 把 emoji 替换为内联 SVG 图片（CSS可控大小）

# Emoji 的 unicode-range（确保不拦截 ASCII/中文）
EMOJI_RANGE = ("U+1F000-1FFFF,U+2600-27BF,U+2700-27BF,U+2190-21FF,U+2B00-2BFF,"
               "U+FE0F,U+200D,U+20E3,U+231A-231B,U+23E9-23FA,U+24C2,"
               "U+25A0-25FF,U+2934-2935,U+3030,U+303D,U+3297,U+3299,U+2139")


def is_cjk_char(c):
    """判断字符是否为 CJK 字符（需要用中文字体渲染的）"""
    cp = ord(c)
    # CJK 统一表意文字 + 扩展A
    if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
        return True
    # CJK 符号和标点（、。，！？等）
    if 0x3000 <= cp <= 0x303F:
        return True
    # 全角ASCII/标点（不包含！让数字用DejaVu）
    # 注意：不全角化数字，所以 0xFF00-0xFFEF 范围排除 FF10-FF19（全角数字）
    if 0xFF00 <= cp <= 0xFFEF and not (0xFF10 <= cp <= 0xFF19):
        return True
    # 特殊标点
    if cp in (0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026):  # —''""…
        return True
    # 日文假名（部分文档可能含）
    if 0x3040 <= cp <= 0x30FF:
        return True
    # 高码位 emoji/符号由 emoji 字体处理，不纳入 CJK
    return False


def subset_cjk(text, work_dir):
    """子集化中文字体(wqy) + Latin字体(DejaVu)，返回 @font-face CSS
    
    关键：所有字体都用 @font-face 显式引用子集文件，
    避免 weasyprint 通过 fontconfig 回退到系统大字体（如 Noto CJK，含全角数字）。
    """
    from fontTools.ttLib import TTFont
    from fontTools.subset import Subsetter, Options

    opts = Options()
    opts.drop_tables += ['DSIG']

    # 1. CJK 子集（只含中文字符，不含 ASCII）
    cjk_chars = set()
    for c in text:
        if is_cjk_char(c):
            cjk_chars.add(c)
    cjk_str = ''.join(sorted(cjk_chars))

    cjk_out = os.path.join(work_dir, 'CJK.ttf')
    if cjk_str:
        font = TTFont(CJK_TTC, fontNumber=0)
        ss = Subsetter(options=opts)
        ss.populate(text=cjk_str)
        ss.subset(font)
        font.save(cjk_out)
        font.close()

    # 2. Latin 子集（ASCII 数字/字母/符号，用 DejaVu Sans 确保半角）
    latin_chars = set(chr(i) for i in range(32, 127))
    for c in text:
        if 0x0080 <= ord(c) <= 0x024F:  # Latin-1 Supplement + Extended
            latin_chars.add(c)
    latin_str = ''.join(sorted(latin_chars))

    latin_out = os.path.join(work_dir, 'Latin.ttf')
    font = TTFont(DEJAVU_REG)
    ss = Subsetter(options=opts)
    ss.populate(text=latin_str)
    ss.subset(font)
    font.save(latin_out)
    font.close()

    latin_bld_out = os.path.join(work_dir, 'Latin-Bold.ttf')
    font = TTFont(DEJAVU_BLD)
    ss = Subsetter(options=opts)
    ss.populate(text=latin_str)
    ss.subset(font)
    font.save(latin_bld_out)
    font.close()

    # 3. 构建 @font-face CSS
    # 用 unicode-range 精确划定各字体管辖范围，杜绝系统大字体回退
    css = ''
    # Latin（数字/字母）— 管辖 ASCII + Latin 补充
    css += f'@font-face {{ font-family:"Latin"; src:url("file://{latin_out}") format("truetype"); font-weight:normal; unicode-range:U+0020-007E,U+00A0-024F,U+2000-206F,U+20A0-20CF; }}\n'
    css += f'@font-face {{ font-family:"Latin"; src:url("file://{latin_bld_out}") format("truetype"); font-weight:bold; unicode-range:U+0020-007E,U+00A0-024F,U+2000-206F,U+20A0-20CF; }}\n'
    # CJK（中文）— 管辖 CJK 范围，绝不覆盖 ASCII
    if cjk_str:
        css += f'@font-face {{ font-family:"CJK"; src:url("file://{cjk_out}") format("truetype"); font-weight:normal; unicode-range:U+3000-303F,U+4E00-9FFF,U+3400-4DBF,U+FF00-FFEF,U+2014-201D,U+2026,U+3040-30FF; }}\n'
        css += f'@font-face {{ font-family:"CJK"; src:url("file://{cjk_out}") format("truetype"); font-weight:bold; unicode-range:U+3000-303F,U+4E00-9FFF,U+3400-4DBF,U+FF00-FFEF,U+2014-201D,U+2026,U+3040-30FF; }}\n'
    # Emoji 不用字体（CBDT 位图字体在 weasyprint 中尺寸巨大）
    # 改用 emoji_img.py 把 emoji 替换为内联 SVG 图片

    return css


# ── 样式（琥珀色主题：表头+斑马纹 / 灰底代码块 / 琥珀色竖条引用块）──
def build_css(font_face_css):
    return font_face_css + '''
* { box-sizing:border-box; }
body {
  font-family:"Latin","CJK",sans-serif;
  line-height:1.8; font-size:11pt; color:#1a1a1a;
  max-width:900px; margin:0 auto; padding:1.5em;
}
h1,h2,h3,h4 { font-family:"Latin","CJK",sans-serif; font-weight:bold; color:#1a1a1a; }
h1 { font-size:18pt; border-bottom:2px solid #D97706; padding-bottom:0.3em; }
h2 { font-size:15pt; border-bottom:1px solid #e0e0e0; padding-bottom:0.2em; margin-top:1.2em; }
h3 { font-size:13pt; margin-top:1em; }
p { margin:0.5em 0; }

/* 代码块：灰底等宽 */
code,pre { font-family:"Latin","DejaVu Sans Mono","Courier New",monospace; font-size:9.5pt; }
pre {
  background:#f2f3f5; padding:0.8em 1em; overflow-x:auto;
  border-radius:4px; white-space:pre-wrap; border-top:2px solid #d2d4d7;
}
code { background:#ececed; padding:0.15em 0.4em; border-radius:3px; }
pre code { background:none; padding:0; }

/* 引用块：琥珀色竖条 */
blockquote {
  border-left:4px solid #D97706;
  background:#fef7ed;
  margin:1em 0; padding:0.6em 1em;
  color:#505050; font-size:10pt;
}
blockquote p { margin:0.3em 0; }

/* 表格：琥珀色表头 + 斑马纹 */
table { border-collapse:collapse; width:100%; margin:1em 0; }
th,td { border:1px solid #d2d4d7; padding:0.5em 0.6em; text-align:left; font-size:10pt; }
th { background:#D97706; color:#fff; font-weight:bold; border-color:#D97706; }
tbody tr:nth-child(even) td { background:#f7f8fa; }
tbody tr:nth-child(odd)  td { background:#fff; }

img { max-width:100%; height:auto; }
a { color:#D97706; text-decoration:none; }
ul,ol { padding-left:2em; }
li { margin:0.2em 0; }
hr { border:none; border-top:1px solid #ddd; margin:1.5em 0; }
@page { margin:2cm 2.5cm;
  @bottom-center { content:"— " counter(page) " —"; font-size:8pt; color:#999; }
}
'''


def read_text(path):
    raw = open(path, 'rb').read()
    for enc in ('utf-8', 'utf-16', 'gbk', 'gb2312', 'latin-1'):
        try:
            return raw.decode(enc)
        except:
            pass
    return raw.decode('utf-8', errors='replace')


def replace_emojis(html_body):
    """将 HTML body 中的 emoji 替换为内联 SVG 图片（CSS 可控大小）"""
    try:
        return _replace_emoji(html_body, size_px=18)
    except Exception as e:
        print(f"  ⚠️ emoji 替换失败: {e}", file=sys.stderr)
        return html_body


def render_pdf(html_body, out_pdf, title, font_css):
    """构造完整 HTML 并用 weasyprint 渲染 PDF
    
    关键：通过自定义 fontconfig 配置 + 环境变量，确保 weasyprint 不会
    通过 fontconfig 回退到系统 CJK 字体（含全角数字），只用 @font-face 子集字体。
    """
    from weasyprint import HTML

    # 创建临时字体目录：只含 DejaVu（Latin 半角数字/字母）
    # 不放任何 emoji 字体（CBDT 位图字体在 weasyprint 中尺寸巨大）
    # emoji 已在 HTML 中替换为内联 SVG 图片（尺寸由 CSS 控制）
    tmp_font_dir = tempfile.mkdtemp(prefix='fc_fonts_')
    import shutil as sh
    for f in ['DejaVuSans.ttf', 'DejaVuSans-Bold.ttf']:
        src = f'/usr/share/fonts/dejavu/{f}'
        if os.path.exists(src):
            sh.copy(src, tmp_font_dir)

    # 创建自定义 fontconfig 配置：只扫描临时字体目录
    fc_conf = os.path.join(tmp_font_dir, 'fonts.conf')
    with open(fc_conf, 'w') as f:
        f.write(f'''<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>{tmp_font_dir}</dir>
  <cachedir>{tmp_font_dir}/cache</cachedir>
  <config></config>
</fontconfig>''')

    css = build_css(font_css)
    html = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head><body>
{html_body}
</body></html>'''
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
        f.write(html)
        hp = f.name
    try:
        # 用自定义 fontconfig 配置，子进程渲染
        env = os.environ.copy()
        env['FONTCONFIG_FILE'] = fc_conf
        sp.run(['fc-cache', '-f', tmp_font_dir], capture_output=True, timeout=30,
               env=env)
        # 用子进程运行 weasyprint，确保 FONTCONFIG_FILE 生效
        sp.run([sys.executable,
                '/var/minis/skills/pdf-converter/scripts/_render.py',
                hp, out_pdf, fc_conf],
               env=env, capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(hp)
        sh.rmtree(tmp_font_dir, ignore_errors=True)


def md_to_pdf(inp, out):
    """Markdown → PDF"""
    text = read_text(inp)
    work = tempfile.mkdtemp()
    try:
        font_css = subset_cjk(text, work)
        r = sp.run(['pandoc', inp, '--to', 'html5'],
                   capture_output=True, text=True)
        if r.returncode != 0:
            print(f"❌ pandoc: {r.stderr}", file=sys.stderr)
            return False
        render_pdf(replace_emojis(r.stdout), out, Path(inp).stem, font_css)
        print(f"✅ PDF 已生成: {out}")
        return True
    finally:
        shutil.rmtree(work, ignore_errors=True)


def txt_to_pdf(inp, out, title=None):
    """纯文本 → PDF"""
    import html as H
    text = read_text(inp)
    work = tempfile.mkdtemp()
    try:
        font_css = subset_cjk(text, work)
        body = []
        for line in text.splitlines():
            e = H.escape(line)
            body.append(f'<p>{e}</p>' if e.strip() else '<br>')
        render_pdf(replace_emojis('\n'.join(body)), out, title or Path(inp).stem, font_css)
        print(f"✅ PDF 已生成: {out}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def html_to_pdf(inp, out):
    """HTML → PDF"""
    text = read_text(inp)
    work = tempfile.mkdtemp()
    try:
        font_css = subset_cjk(text, work)
        if '</head>' in text:
            styled = text.replace('</head>', f'<style>{build_css(font_css)}</style>\n</head>', 1)
            hp = os.path.join(work, 'doc.html')
            with open(hp, 'w', encoding='utf-8') as f:
                f.write(styled)
            from weasyprint import HTML
            HTML(filename=hp).write_pdf(out)
        else:
            render_pdf(replace_emojis(text), out, Path(inp).stem, font_css)
        print(f"✅ PDF 已生成: {out}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def img_to_pdf(paths, out):
    """图片 → PDF（多图合并，每页一张）"""
    from PIL import Image
    imgs = [Image.open(p).convert('RGB') for p in paths]
    imgs[0].save(out, save_all=True, append_images=imgs[1:], quality=95)
    print(f"✅ PDF 已生成: {out} ({len(imgs)} 页)")


def main():
    p = argparse.ArgumentParser(description='转PDF：MD/HTML/文本/图片 → PDF')
    p.add_argument('input', nargs='+', help='输入文件')
    p.add_argument('-o', '--output', help='输出PDF路径')
    p.add_argument('--title', help='文档标题（仅文本模式）')
    a = p.parse_args()

    inputs = [Path(x) for x in a.input]
    out = a.output or (inputs[0].with_suffix('.pdf').name if len(inputs) == 1 else 'merged.pdf')
    IMG = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}

    if all(x.suffix.lower() in IMG for x in inputs):
        img_to_pdf([str(x) for x in inputs], out)
        return
    if len(inputs) != 1:
        print("❌ 多文件仅支持图片合并", file=sys.stderr)
        sys.exit(1)

    x = inputs[0]
    e = x.suffix.lower()
    if e in IMG:
        img_to_pdf([str(x)], out)
    elif e == '.md':
        md_to_pdf(str(x), out)
    elif e in ('.html', '.htm'):
        html_to_pdf(str(x), out)
    elif e == '.txt':
        txt_to_pdf(str(x), out, a.title or x.stem)
    else:
        # pandoc 兜底（.rst/.org/.latex 等）
        text = read_text(str(x))
        work = tempfile.mkdtemp()
        try:
            font_css = subset_cjk(text, work)
            r = sp.run(['pandoc', str(x), '--to', 'html5'],
                       capture_output=True, text=True)
            if r.returncode != 0:
                print(f"❌ pandoc: {r.stderr}", file=sys.stderr)
                sys.exit(1)
            render_pdf(replace_emojis(r.stdout), out, x.stem, font_css)
            print(f"✅ PDF 已生成: {out}")
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
