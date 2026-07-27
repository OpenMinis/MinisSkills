---
name: pdf-converter
version: 2.2.0
description: 将各种格式文件转换为 PDF。支持 Markdown(.md)、HTML(.htm/.html)、纯文本(.txt)、图片(.png/.jpg/.jpeg/.gif/.bmp/.webp)以及 pandoc 支持的格式(.rst/.org/.latex等)。当用户提到「转PDF」「生成PDF」「导出PDF」「convert to PDF」时触发。
---

# pdf-converter

## 使用方法

```bash
# Markdown → PDF（保留格式、emoji、中文，数字半角，琥珀色主题排版）
python3 /var/minis/skills/pdf-converter/scripts/to_pdf.py 文档.md -o 输出.pdf

# 文本 → PDF
python3 /var/minis/skills/pdf-converter/scripts/to_pdf.py 文档.txt -o 输出.pdf

# HTML → PDF
python3 /var/minis/skills/pdf-converter/scripts/to_pdf.py 网页.html -o 输出.pdf

# 多图片合并为PDF
python3 /var/minis/skills/pdf-converter/scripts/to_pdf.py 图1.jpg 图2.png -o 合并.pdf
```

⚠️ **性能提示**：转换约需 **40-60 秒**（CJK 字体子集化 ~20s + weasyprint ~15s），建议后台运行：
```bash
nohup python3 /var/minis/skills/pdf-converter/scripts/to_pdf.py input.md -o output.pdf > /tmp/pdf.log 2>&1 &
```

## 排版样式（琥珀色主题）

- **表格**：琥珀色表头(#D97706 白字) + 斑马纹行(灰/白交替) + 细网格边框
- **代码块**：浅灰底(#f2f3f5) + 等宽字体(DejaVu Sans Mono) + 顶部灰条
- **引用块**：左侧琥珀色竖条(border-left #D97706) + 淡橙底(#fef7ed)
- **标题**：h1 底部琥珀色下划线，h1-h4 层级分明
- **页脚**：居中页码

## 技术架构

- **pandoc**：Markdown/其他格式 → HTML5 片段
- **fontTools**：子集化字体（WenQuanYi 中文 + DejaVu Latin）
- **Twemoji CDN**：emoji → SVG 实时下载缓存，CSS 可控大小
- **weasyprint**（子进程 + 自定义 fontconfig）：HTML5 → PDF

## 字体策略（核心）

| 字符类型 | 字体 | 处理 |
|---------|------|------|
| ASCII（数字/字母） | DejaVu Sans | 子集化 @font-face，半角字形 |
| 中文 | WenQuanYi Zen Hei | 子集化 @font-face，不含 ASCII |
| Emoji | Twemoji SVG | CDN 实时下载 → base64 内联图片 |

**全角数字问题解决**：通过自定义 fontconfig 配置隔离系统 CJK 字体，
确保 weasyprint 只用 @font-face 子集字体 + DejaVu Sans 回退（半角数字）。

## 文件结构

```
pdf-converter/
├── SKILL.md          # 本文件
├── scripts/
│   ├── to_pdf.py     # 主转换脚本
│   ├── _render.py    # weasyprint 渲染子进程
│   ├── gen_fonts.py  # 预生成字体子集
│   ├── emoji_img.py  # emoji SVG 下载 + base64 内联
│   └── subset_emoji.py  # emoji 子集化（备用）
└── emoji_cache/  # 已缓存的 Twemoji SVG
```
