#!/usr/bin/env python3
"""Port of TodooCard image_to_payload.swift → pure Python (Pillow).

Restored verified implementation (used successfully before the fast rewrite).
Keeps device-compatible SE0368 + QuickLZ stored framing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

T3_W, T3_H = 528, 792

PALETTE = [
    ("black", (0, 0, 0), 0),
    ("white", (255, 255, 255), 1),
    ("yellow", (255, 255, 0), 2),
    ("red", (255, 0, 0), 3),
    ("blue", (0, 0, 255), 5),
    ("green", (0, 255, 0), 6),
]


def cover_resize(im: Image.Image, tw: int, th: int) -> Image.Image:
    im = ImageOps.exif_transpose(im).convert("RGBA")
    sw, sh = im.size
    scale = max(tw / sw, th / sh)
    nw, nh = max(1, int(round(sw * scale))), max(1, int(round(sh * scale)))
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (tw, th), (255, 255, 255, 255))
    canvas.paste(im, ((tw - nw) // 2, (th - nh) // 2), im)
    return canvas.convert("RGB")


def nearest_color(r: float, g: float, b: float):
    best = PALETTE[0]
    best_d = 1e30
    for item in PALETTE:
        cr, cg, cb = item[1]
        d = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if d < best_d:
            best_d = d
            best = item
    return best


def floyd_steinberg_six_color(im: Image.Image) -> list[int]:
    w, h = im.size
    px = im.load()
    work = [[[float(v) for v in px[x, y]] for x in range(w)] for y in range(h)]
    codes = [1] * (w * h)

    def add_err(x, y, er, eg, eb, weight):
        if 0 <= x < w and 0 <= y < h:
            work[y][x][0] += er * weight
            work[y][x][1] += eg * weight
            work[y][x][2] += eb * weight

    for y in range(h):
        for x in range(w):
            r, g, b = work[y][x]
            r = min(255.0, max(0.0, r))
            g = min(255.0, max(0.0, g))
            b = min(255.0, max(0.0, b))
            _name, (cr, cg, cb), code = nearest_color(r, g, b)
            codes[y * w + x] = code
            er, eg, eb = r - cr, g - cg, b - cb
            add_err(x + 1, y, er, eg, eb, 7 / 16)
            add_err(x - 1, y + 1, er, eg, eb, 3 / 16)
            add_err(x, y + 1, er, eg, eb, 5 / 16)
            add_err(x + 1, y + 1, er, eg, eb, 1 / 16)
    return codes


def pack_nibbles(codes: list[int]) -> bytes:
    out = bytearray()
    n = len(codes)
    for i in range(0, n, 2):
        hi = codes[i] & 0x0F
        lo = codes[i + 1] & 0x0F if i + 1 < n else 0
        out.append((hi << 4) | lo)
    return bytes(out)


def rotate180(codes: list[int]) -> list[int]:
    return list(reversed(codes))


def flip_h(codes: list[int], w: int, h: int) -> list[int]:
    out = [0] * (w * h)
    for y in range(h):
        base = y * w
        for x in range(w):
            out[base + (w - 1 - x)] = codes[base + x]
    return out


def se0368_transform(codes: list[int], w: int, h: int) -> list[int]:
    """Exact port of rotatedClockwiseMirroredForSE0368 from official Swift."""
    dest_w = h
    out = [0] * (w * h)
    for di in range(w * h):
        dx = di % dest_w
        dy = di // dest_w
        sx = w - 1 - dy
        sy = h - 1 - dx
        out[di] = codes[sy * w + sx]
    return out


def quicklz_stored(raw: bytes) -> bytes:
    if len(raw) % 64:
        raise ValueError(f"raw len {len(raw)} not ÷64")
    out = bytearray(4)
    for off in range(0, len(raw), 64):
        out += b"\x74\x43\x40"
        out += raw[off : off + 64]
    return bytes(out)


def codes_preview(codes: list[int], w: int, h: int) -> Image.Image:
    m = {c: rgb for _, rgb, c in PALETTE}
    im = Image.new("RGB", (w, h))
    p = im.load()
    for i, c in enumerate(codes):
        p[i % w, i // w] = m.get(c, (128, 128, 128))
    return im


def convert(
    input_path: str | Path,
    output_prefix: str | Path,
    orientation: str = "normal",
    make_preview: bool = True,
) -> dict:
    input_path = Path(input_path)
    output_prefix = Path(output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    im = Image.open(input_path)
    covered = cover_resize(im, T3_W, T3_H)
    codes = floyd_steinberg_six_color(covered)

    if orientation == "rotate-180-then-flip-horizontal":
        codes = flip_h(rotate180(codes), T3_W, T3_H)
    elif orientation != "normal":
        raise ValueError(f"unsupported orientation: {orientation}")

    bitmap = pack_nibbles(codes)
    bin_path = Path(str(output_prefix) + ".bin")
    bin_path.write_bytes(bitmap)

    controller = pack_nibbles(se0368_transform(codes, T3_W, T3_H))
    qlz = quicklz_stored(controller)
    qlz_path = Path(str(output_prefix) + ".protocol.qlz")
    qlz_path.write_bytes(qlz)

    preview_path = None
    if make_preview:
        preview_path = Path(str(output_prefix) + ".preview.png")
        codes_preview(codes, T3_W, T3_H).save(preview_path)

    return {
        "bin": str(bin_path),
        "bin_bytes": len(bitmap),
        "qlz": str(qlz_path),
        "qlz_bytes": len(qlz),
        "preview": str(preview_path) if preview_path else None,
        "size": f"{T3_W}x{T3_H}",
        "orientation": orientation,
    }


def validate_qlz(path: str | Path) -> None:
    data = Path(path).read_bytes()
    if len(data) < 4:
        raise SystemExit(f"payload too small: {len(data)}")
    body = data[4:]
    if len(body) % 67 != 0:
        raise SystemExit(f"body length {len(body)} not multiple of 67")
    blocks = len(body) // 67
    for i in range(blocks):
        if body[i * 67 : i * 67 + 3] != b"\x74\x43\x40":
            raise SystemExit(f"bad block marker at {i}")
    raw_len = blocks * 64
    expected = (T3_W * T3_H + 1) // 2
    if raw_len != expected:
        raise SystemExit(f"raw length {raw_len} != expected {expected}")
    print(f"OK payload {path}: {len(data)} bytes, {blocks} blocks, raw={raw_len}")


def main():
    ap = argparse.ArgumentParser(description="Convert image to TodooCard T3 payload")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output-prefix", required=True)
    ap.add_argument(
        "--orientation",
        default="normal",
        choices=["normal", "rotate-180-then-flip-horizontal"],
    )
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--validate-only", metavar="QLZ")
    args = ap.parse_args()
    if args.validate_only:
        validate_qlz(args.validate_only)
        return
    info = convert(args.input, args.output_prefix, args.orientation, not args.no_preview)
    print("Color mode: six-color Floyd-Steinberg dithering")
    print(f"Image orientation: {info['orientation']}")
    print(f"Wrote {info['bin']} ({info['bin_bytes']} bytes)")
    print(f"Wrote {info['qlz']} ({info['qlz_bytes']} bytes)")
    if info["preview"]:
        print(f"Wrote {info['preview']}")
    validate_qlz(info["qlz"])


if __name__ == "__main__":
    main()
