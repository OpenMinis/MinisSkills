#!/usr/bin/env python3
"""今天吃点啥 — TodooCard 528×792 meal recommendation card."""
from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 528, 792

# E-paper friendly palette (will dither cleanly)
INK = (16, 18, 22)
PAPER = (250, 247, 240)
CREAM = (236, 230, 216)
WARM = (228, 210, 170)
MUTED = (98, 96, 92)
RED = (168, 44, 38)
YELLOW = (214, 176, 42)
BLUE = (46, 74, 148)
GREEN = (48, 118, 72)
CHARCOAL = (32, 34, 38)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    cands = [
        "/usr/share/fonts/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto/NotoSansCJK-Bold.ttc",
    ]
    for p in cands:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_background(seed: int = 7) -> Image.Image:
    """Layered premium background: warm paper, soft vignette, geometric mesh, grain."""
    rng = random.Random(seed)
    base = Image.new("RGB", (W, H), PAPER)
    px = base.load()

    # vertical warm gradient (top cooler paper → bottom cream)
    for y in range(H):
        t = y / (H - 1)
        # slight ease
        t2 = t * t * (3 - 2 * t)
        col = lerp(PAPER, CREAM, t2 * 0.85)
        for x in range(W):
            # soft radial vignette darkening edges
            nx = (x - W / 2) / (W * 0.62)
            ny = (y - H / 2) / (H * 0.62)
            r = math.sqrt(nx * nx + ny * ny)
            v = min(1.0, max(0.0, (r - 0.55) / 0.7))
            c2 = lerp(col, (210, 204, 192), v * 0.55)
            px[x, y] = c2

    d = ImageDraw.Draw(base, "RGBA")

    # large faint circle motif (top-right)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse([W - 340, -120, W + 80, 300], outline=(16, 18, 22, 28), width=18)
    od.ellipse([W - 300, -80, W + 40, 260], outline=(16, 18, 22, 18), width=10)
    od.ellipse([-120, H - 320, 220, H + 40], outline=(168, 44, 38, 22), width=14)
    od.ellipse([-90, H - 290, 190, H + 10], outline=(168, 44, 38, 14), width=8)

    # diagonal hairline grid (very light)
    step = 42
    for i in range(-H, W + H, step):
        od.line([(i, 0), (i + H, H)], fill=(16, 18, 22, 12), width=1)
    for i in range(0, H, step * 2):
        od.line([(0, i), (W, i)], fill=(16, 18, 22, 10), width=1)

    # geometric corner frame ticks
    tick = 28
    for x0, y0, dx, dy in [
        (28, 28, 1, 1),
        (W - 28, 28, -1, 1),
        (28, H - 28, 1, -1),
        (W - 28, H - 28, -1, -1),
    ]:
        od.line([(x0, y0), (x0 + dx * tick, y0)], fill=(16, 18, 22, 70), width=2)
        od.line([(x0, y0), (x0, y0 + dy * tick)], fill=(16, 18, 22, 70), width=2)

    # sparse gold dots constellation
    for _ in range(40):
        x = rng.randint(20, W - 20)
        y = rng.randint(20, H - 20)
        r = rng.choice([1, 1, 1, 2])
        od.ellipse([x - r, y - r, x + r, y + r], fill=(214, 176, 42, rng.randint(35, 70)))

    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")

    # fine grain
    grain = Image.new("RGB", (W, H), PAPER)
    gpx = grain.load()
    for y in range(H):
        for x in range(W):
            n = rng.randint(-10, 10)
            gpx[x, y] = (128 + n, 128 + n, 128 + n)
    grain = grain.filter(ImageFilter.GaussianBlur(0.6))
    base = Image.blend(base, grain, 0.06)
    return base


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font_obj, max_w: float) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        t = cur + ch
        if draw.textlength(t, font=font_obj) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def meal_period(hour: int | None = None) -> tuple[str, str, str]:
    """Always show unified meal title."""
    return "今日", "TODAY'S EATS", "今天吃点啥"



def category_style(cat: str) -> tuple[tuple[int, int, int], str]:
    m = {
        "米粉": (RED, "酸辣鲜香 · 一碗过瘾"),
        "火锅": (RED, "热气腾腾 · 放开吃"),
        "烧烤": (YELLOW, "炭火香气 · 配饮正好"),
        "面条": (BLUE, "暖胃一碗 · 简单满足"),
        "盖饭": (GREEN, "快捷扎实 · 干饭人选"),
        "日料": (BLUE, "清爽节奏 · 换个口味"),
        "韩式料理": (RED, "酱香拉满 · 配饭很香"),
        "炸鸡": (YELLOW, "酥脆解馋 · 松弛时刻"),
        "汉堡": (YELLOW, "手抓自由 · 零仪式感"),
        "披萨": (RED, "分享氛围 · 轻松一餐"),
        "饺子": (GREEN, "皮薄馅大 · 稳妥之选"),
        "寿司": (BLUE, "精致小口 · 慢一点吃"),
        "麻辣烫": (RED, "一个人的幸福锅"),
        "冒菜": (RED, "麻辣鲜香 · 冒着热气"),
        "黄焖鸡": (YELLOW, "酱香下饭 · 米饭加倍"),
        "小吃": (MUTED, "随便吃吃 · 也很满足"),
        "快餐": (MUTED, "出餐很快 · 懒人友好"),
        "中餐厅": (CHARCOAL, "家常硬菜 · 吃得踏实"),
    }
    return m.get(cat, (CHARCOAL, "附近风向 · 就它了"))


def render(pick: dict, out_path: str | Path, meal_override: str | None = None) -> Path:
    meal_cn, meal_kicker, meal_title = meal_period()
    cat = pick.get("_query") or pick.get("category_label") or "美食"
    if cat.startswith("MKPOI"):
        cat = pick.get("_query") or "美食"
    accent, vibe = category_style(cat)
    name = pick.get("name") or "未命名餐厅"
    dist = int(pick.get("distance_m") or 0)
    addr = (pick.get("address") or "").replace("中国", "").replace(", 北京市", " · 北京").strip(" ,，")
    phone = pick.get("phone") or ""
    now = datetime.now()

    if dist < 500:
        near = "步行可达 · 骑手很快"
    elif dist < 1200:
        near = "距离不远 · 配送通常稳"
    elif dist < 2000:
        near = "稍远一点 · 值得等待"
    else:
        near = "稍远 · 预留配送时间"

    img = make_background(seed=hash(name) % 10000)
    d = ImageDraw.Draw(img)

    f_brand = font(13, True)
    f_kicker = font(14, True)
    f_title = font(34, True)
    f_name = font(32, True)
    f_name_sm = font(26, True)
    f_dist = font(78, True)
    f_unit = font(24, True)
    f_body = font(20)
    f_lab = font(14, True)
    f_small = font(17)
    f_tiny = font(13)

    # 顶部不要使用实心黑条：电子纸上会显得压迫、像故障线
    # 保留细黑色左侧装饰线即可
    # d.rectangle([0, 0, W, 8], fill=INK)
    d.text((40, 28), meal_kicker, font=f_brand, fill=MUTED)
    d.text((W - 40, 28), now.strftime("%m.%d  %H:%M"), font=f_brand, fill=MUTED, anchor="ra")

    # thin gold rule
    d.line([(40, 52), (W - 40, 52)], fill=YELLOW, width=2)

    d.text((40, 68), meal_title, font=f_title, fill=INK)

    # category chip + decorative diamond
    chip = cat
    chip_w = d.textlength(chip, font=f_kicker) + 34
    d.rounded_rectangle([40, 118, 40 + chip_w, 150], radius=16, fill=accent)
    d.text((40 + chip_w / 2, 134), chip, font=f_kicker, fill=PAPER if accent != YELLOW else INK, anchor="mm")
    # small diamond after chip
    cx = 40 + chip_w + 18
    d.polygon([(cx, 128), (cx + 6, 134), (cx, 140), (cx - 6, 134)], fill=YELLOW)

    # main glass card for restaurant
    card = [32, 175, W - 32, 360]
    # shadow-ish double border
    d.rounded_rectangle([card[0] + 4, card[1] + 5, card[2] + 4, card[3] + 5], radius=22, fill=(200, 194, 182))
    d.rounded_rectangle(card, radius=22, fill=PAPER, outline=INK, width=2)
    # inner thin frame
    d.rounded_rectangle([card[0] + 10, card[1] + 10, card[2] - 10, card[3] - 10], radius=16, outline=lerp(INK, PAPER, 0.75), width=1)

    # top label inside card
    d.text(((card[0] + card[2]) / 2, card[1] + 32), "RECOMMENDED", font=f_brand, fill=MUTED, anchor="mm")
    d.line([((card[0] + card[2]) / 2 - 50, card[1] + 48), ((card[0] + card[2]) / 2 + 50, card[1] + 48)], fill=YELLOW, width=1)

    # restaurant name centered, auto size
    max_name_w = card[2] - card[0] - 48
    use_font = f_name
    lines = wrap_text(d, name, use_font, max_name_w)
    if len(lines) > 2 or any(d.textlength(x, font=use_font) > max_name_w for x in lines):
        use_font = f_name_sm
        lines = wrap_text(d, name, use_font, max_name_w)
    lines = lines[:3]
    total_h = len(lines) * (38 if use_font == f_name else 32)
    y0 = (card[1] + card[3]) / 2 - total_h / 2 + 10
    for i, ln in enumerate(lines):
        d.text(((card[0] + card[2]) / 2, y0 + i * (38 if use_font == f_name else 32)), ln, font=use_font, fill=INK, anchor="mm")

    # distance block with big number
    d.text((48, 390), "DISTANCE", font=f_brand, fill=MUTED)
    d.text((48, 455), f"{dist}", font=f_dist, fill=INK, anchor="lm")
    dw = d.textlength(f"{dist}", font=f_dist)
    d.text((48 + dw + 6, 440), "m", font=f_unit, fill=MUTED, anchor="lm")
    d.text((48, 510), near, font=f_body, fill=MUTED)

    # right side vertical accent bar with meters scale decoration
    d.rectangle([W - 54, 390, W - 48, 520], fill=accent)
    for i, yy in enumerate(range(390, 521, 26)):
        d.line([(W - 48, yy), (W - 40, yy)], fill=INK if i % 2 == 0 else MUTED, width=1)

    # vibe / reason panel
    d.rounded_rectangle([32, 545, W - 32, 640], radius=18, fill=INK)
    # gold left rail
    d.rounded_rectangle([44, 562, 50, 622], radius=3, fill=YELLOW)
    d.text((64, 568), "WHY THIS", font=f_brand, fill=YELLOW)
    vlines = wrap_text(d, vibe, f_body, W - 130)
    yy = 598
    for ln in vlines[:2]:
        d.text((64, yy), ln, font=f_body, fill=PAPER, anchor="lm")
        yy += 26

    # address section
    d.line([(40, 662), (W - 40, 662)], fill=lerp(INK, PAPER, 0.7), width=1)
    d.text((40, 678), "ADDRESS", font=f_brand, fill=MUTED)
    alines = wrap_text(d, addr or "附近", f_small, W - 80)
    yy = 702
    for ln in alines[:2]:
        d.text((40, yy), ln, font=f_small, fill=INK)
        yy += 24

    # footer
    d.rectangle([0, H - 42, W, H], fill=INK)
    d.text((40, H - 21), phone or "今天吃点啥 · TodooCard", font=f_tiny, fill=PAPER, anchor="lm")
    d.text((W - 40, H - 21), "ENJOY", font=f_tiny, fill=YELLOW, anchor="ra")

    # 整体上移，减少顶部留白与内容下沉感；底部用纸色补齐
    lifted = Image.new("RGB", (W, H), PAPER)
    lifted.paste(img, (0, -10))
    # 向下延伸底部黑色 footer，覆盖上移后产生的底部白区
    lifted_draw = ImageDraw.Draw(lifted)
    lifted_draw.rectangle([0, H - 10, W, H], fill=INK)
    img = lifted

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-json", default="/tmp/food_pick.json")
    ap.add_argument("--out", default="/var/minis/attachments/eat_card.png")
    ap.add_argument("--send", action="store_true")
    args = ap.parse_args()

    pick_path = Path(args.pick_json)
    if not pick_path.exists():
        raise SystemExit(f"pick json not found: {pick_path}")
    pick = json.loads(pick_path.read_text())
    if "_query" not in pick and "category" in pick and not str(pick["category"]).startswith("MKPOI"):
        pick["_query"] = pick["category"]

    out = render(pick, args.out)
    print(f"rendered {out}")

    tdir = Path("/var/minis/shared/todoocard/templates")
    tdir.mkdir(parents=True, exist_ok=True)
    Image.open(out).save(tdir / "eat.png")
    (tdir / "eat.json").write_text(
        json.dumps(
            {
                "name": "eat",
                "title": "今天吃点啥",
                "size": "528x792",
                "script": str(Path(__file__).resolve()),
                "last_render": datetime.now().isoformat(timespec="seconds"),
                "pick": pick,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if args.send:
        # Prefer CLI entry for sending; keep a thin optional path here.
        import subprocess

        here = Path(__file__).resolve().parent
        subprocess.check_call(
            [
                "python3",
                str(here / "todoocard_cli.py"),
                "eat",
                "--prepare-only",
            ]
        )


if __name__ == "__main__":
    main()
