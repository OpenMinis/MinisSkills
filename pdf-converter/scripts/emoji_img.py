#!/usr/bin/env python3
"""Emoji 处理：将文本中的 emoji 替换为内联 SVG（base64 data URI）

因为 Twemoji.ttf 和 NotoColorEmoji.ttf 都是 CBDT 彩色位图字体，
weasyprint 按位图像素大小渲染导致 emoji 巨大。
方案：下载 Twemoji SVG → base64 内联为 <img> → CSS 控制大小。
"""
import os, re, base64, hashlib, json, urllib.request

CACHE_DIR = '/var/minis/skills/pdf-converter/emoji_cache'
CDN_BASE = 'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg'

# 预下载缓存（避免每次转 PDF 都联网）
def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cp_to_hex(cp):
    """码点转 Twemoji SVG 文件名（如 1f4b0）"""
    return f'{cp:x}'


def _download_svg(emoji_char):
    """下载一个 emoji 的 SVG，返回 base64 data URI"""
    _ensure_cache_dir()
    # 处理复合 emoji（含 ZWJ 或 VS16）
    cps = []
    for c in emoji_char:
        cp = ord(c)
        if cp == 0xFE0F:  # Variation selector，保留
            cps.append(cp)
        elif cp == 0x200D:  # ZWJ
            cps.append(cp)
        else:
            cps.append(cp)
    hex_name = '-'.join(_cp_to_hex(cp) for cp in cps)
    # 去 FE0F 的版本（Twemoji 有时不用 FE0F）
    hex_name_no_vs = '-'.join(_cp_to_hex(cp) for cp in cps if cp != 0xFE0F)

    for name in [hex_name, hex_name_no_vs]:
        svg_path = os.path.join(CACHE_DIR, f'{name}.svg')
        if os.path.exists(svg_path):
            return svg_path
        # 尝试下载
        url = f'{CDN_BASE}/{name}.svg'
        try:
            urllib.request.urlretrieve(url, svg_path)
            return svg_path
        except:
            os.path.exists(svg_path) and os.unlink(svg_path)
            continue
    return None


def replace_emojis_with_svg(text, size_px=18):
    """将文本中的 emoji 替换为 <img> 标签（内联 base64 SVG）"""
    _ensure_cache_dir()
    result = []
    i = 0
    replaced = 0
    while i < len(text):
        c = text[i]
        cp = ord(c)
        # 检测 emoji：高码位 + variation selector + ZWJ 序列
        if cp >= 0x1F000 or (0x2600 <= cp <= 0x27BF) or (0x2700 <= cp <= 0x27BF) or cp == 0x26A0:
            # 收集完整 emoji 序列（含 VS16、ZWJ）
            emoji = c
            j = i + 1
            while j < len(text):
                nc = text[j]
                ncp = ord(nc)
                if ncp == 0xFE0F or ncp == 0x200D or (ncp >= 0x1F000 and ncp < 0x20000):
                    emoji += nc
                    j += 1
                else:
                    break
            # 获取 SVG
            svg_path = _download_svg(emoji)
            if svg_path and os.path.exists(svg_path):
                with open(svg_path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode()
                result.append(f'<img src="data:image/svg+xml;base64,{b64}" style="width:{size_px}px;height:{size_px}px;vertical-align:middle;display:inline-block" alt="{emoji}"/>')
                replaced += 1
            else:
                # 下载失败，保留原字符
                result.append(emoji)
            i = j
        else:
            result.append(c)
            i += 1
    if replaced > 0:
        print(f"  📦 {replaced} 个 emoji 替换为 SVG", file=__import__('sys').stderr)
    return ''.join(result)


if __name__ == '__main__':
    # 测试
    text = '庐山 🚗 门票 ¥160 🏔️ 三叠泉 ⚠️'
    result = replace_emojis_with_svg(text)
    print(f"Original: {text}")
    print(f"Result length: {len(result)} chars")
