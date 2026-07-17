#!/usr/bin/env python3
"""Generate favicon assets for the SheWrote starfield site."""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

BASE = 512
S = 4
CANVAS = BASE * S

BG = "#08090B"
BG_WARM = "#17110D"
GOLD = "#E4BD6B"
GOLD_SOFT = "#F7D99A"
GOLD_DIM = "#6E552F"
RED = "#A83E3B"
RED_DARK = "#6D2424"

FONT_WENKAI = WEB / "fonts" / "wenkai-subset.woff"
# 原 Songti SC 系统字体 → 自托管开源字体(OFL,合规),见 assets/fonts/LICENSES.md
FONT_SONG = ROOT / "assets" / "fonts" / "NotoSerifSC.ttf"


def rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def font(size: int) -> ImageFont.FreeTypeFont:
    path = FONT_WENKAI if FONT_WENKAI.exists() else FONT_SONG
    return ImageFont.truetype(str(path), size * S)


def scaled(points: tuple[float, ...]) -> tuple[int, ...]:
    return tuple(int(round(v * S)) for v in points)


def draw_centered_text(draw: ImageDraw.ImageDraw, text: str, x: float, y: float, fnt, fill):
    box = draw.textbbox((0, 0), text, font=fnt)
    tw, th = box[2] - box[0], box[3] - box[1]
    draw.text((x * S - tw / 2 - box[0], y * S - th / 2 - box[1]), text, font=fnt, fill=fill)


def gradient_background() -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    pix = img.load()
    bg = rgba(BG)
    warm = rgba(BG_WARM)
    for y in range(CANVAS):
        ny = y / CANVAS
        for x in range(CANVAS):
            nx = x / CANVAS
            center = max(0, 1 - math.hypot((nx - 0.38) / 0.78, (ny - 0.34) / 0.74))
            edge = math.hypot(nx - 0.5, ny - 0.5)
            t = min(1, center * 1.18)
            darken = max(0, edge - 0.35) * 1.35
            r = int(bg[0] * (1 - t) + warm[0] * t)
            g = int(bg[1] * (1 - t) + warm[1] * t)
            b = int(bg[2] * (1 - t) + warm[2] * t)
            pix[x, y] = (max(0, int(r * (1 - darken))), max(0, int(g * (1 - darken))), max(0, int(b * (1 - darken))), 255)
    return img


def rounded_mask() -> Image.Image:
    mask = Image.new("L", (CANVAS, CANVAS), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, CANVAS - 1, CANVAS - 1), radius=84 * S, fill=255)
    return mask


def draw_constellation(img: Image.Image):
    line_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    line = ImageDraw.Draw(line_layer)
    glow = ImageDraw.Draw(glow_layer)

    stars = [
        (92, 161, 2.4), (150, 101, 1.7), (228, 129, 2.2), (322, 82, 1.8),
        (398, 157, 2.8), (363, 267, 1.8), (438, 355, 2.3), (292, 419, 1.6),
        (177, 373, 2.1), (111, 282, 1.5),
    ]
    links = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 0), (2, 8)]

    for a, b in links:
        x1, y1, _ = stars[a]
        x2, y2, _ = stars[b]
        line.line(scaled((x1, y1, x2, y2)), fill=rgba(GOLD_DIM, 95), width=2 * S)

    for x, y, r in stars:
        glow.ellipse(scaled((x - r * 5, y - r * 5, x + r * 5, y + r * 5)), fill=rgba(GOLD, 34))
        line.ellipse(scaled((x - r, y - r, x + r, y + r)), fill=rgba(GOLD_SOFT, 230))

    red_mist = [(131, 391, 2.3), (151, 410, 1.4), (110, 423, 1.5), (394, 330, 1.8)]
    for x, y, r in red_mist:
        glow.ellipse(scaled((x - r * 6, y - r * 6, x + r * 6, y + r * 6)), fill=rgba(RED, 30))
        line.ellipse(scaled((x - r, y - r, x + r, y + r)), fill=rgba(RED, 175))

    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(5 * S))
    img.alpha_composite(glow_layer)
    img.alpha_composite(line_layer)


def draw_mark(img: Image.Image):
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    mark_font = font(346)

    draw_centered_text(gdraw, "她", 256, 268, mark_font, rgba(GOLD, 120))
    glow = glow.filter(ImageFilter.GaussianBlur(6 * S))
    img.alpha_composite(glow)

    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    draw_centered_text(sdraw, "她", 264, 276, mark_font, rgba(RED_DARK, 165))
    shadow = shadow.filter(ImageFilter.GaussianBlur(1.2 * S))
    img.alpha_composite(shadow)

    draw = ImageDraw.Draw(img)
    draw_centered_text(draw, "她", 256, 268, mark_font, rgba(GOLD_SOFT, 255))


def make_icon() -> Image.Image:
    img = gradient_background()
    mask = rounded_mask()
    img.putalpha(mask)

    border = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(border)
    bdraw.rounded_rectangle(scaled((16, 16, 496, 496)), radius=70 * S, outline=rgba(GOLD_DIM, 145), width=2 * S)
    bdraw.rounded_rectangle(scaled((27, 27, 485, 485)), radius=60 * S, outline=rgba(RED, 58), width=1 * S)
    img.alpha_composite(border)

    draw_constellation(img)
    draw_mark(img)
    return img


def save_pngs(img: Image.Image):
    for size, name in [(512, "favicon-512.png"), (32, "favicon-32.png")]:
        out = img.resize((size, size), Image.Resampling.LANCZOS)
        out.save(WEB / name, optimize=True)

    apple = img.resize((180, 180), Image.Resampling.LANCZOS)
    apple_bg = Image.new("RGBA", apple.size, rgba(BG))
    apple_bg.alpha_composite(apple)
    apple_bg.save(WEB / "apple-touch-icon.png", optimize=True)


def save_svg():
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="SheWrote favicon">
  <defs>
    <radialGradient id="bg" cx="38%" cy="34%" r="82%">
      <stop offset="0%" stop-color="{BG_WARM}"/>
      <stop offset="58%" stop-color="{BG}"/>
      <stop offset="100%" stop-color="#020304"/>
    </radialGradient>
    <filter id="softGlow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="7" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <rect width="512" height="512" rx="84" fill="url(#bg)"/>
  <rect x="16" y="16" width="480" height="480" rx="70" fill="none" stroke="{GOLD_DIM}" stroke-opacity=".56" stroke-width="2"/>
  <rect x="27" y="27" width="458" height="458" rx="60" fill="none" stroke="{RED}" stroke-opacity=".24" stroke-width="1"/>
  <g fill="none" stroke="{GOLD_DIM}" stroke-opacity=".45" stroke-width="2">
    <path d="M92 161 150 101 228 129 322 82 398 157 363 267 438 355 292 419 177 373 111 282 92 161"/>
    <path d="M228 129 177 373"/>
  </g>
  <g fill="{GOLD_SOFT}" filter="url(#softGlow)">
    <circle cx="92" cy="161" r="2.4"/><circle cx="150" cy="101" r="1.7"/><circle cx="228" cy="129" r="2.2"/>
    <circle cx="322" cy="82" r="1.8"/><circle cx="398" cy="157" r="2.8"/><circle cx="363" cy="267" r="1.8"/>
    <circle cx="438" cy="355" r="2.3"/><circle cx="292" cy="419" r="1.6"/><circle cx="177" cy="373" r="2.1"/><circle cx="111" cy="282" r="1.5"/>
  </g>
  <g fill="{RED}" opacity=".74" filter="url(#softGlow)">
    <circle cx="131" cy="391" r="2.3"/><circle cx="151" cy="410" r="1.4"/><circle cx="110" cy="423" r="1.5"/><circle cx="394" cy="330" r="1.8"/>
  </g>
  <text x="256" y="358" text-anchor="middle" font-family="LXGW WenKai, Noto Serif SC, serif" font-size="350" font-weight="600" fill="{RED_DARK}" opacity=".58">她</text>
  <text x="256" y="350" text-anchor="middle" font-family="LXGW WenKai, Noto Serif SC, serif" font-size="350" font-weight="600" fill="{GOLD_SOFT}">她</text>
</svg>
"""
    (WEB / "favicon.svg").write_text(svg, encoding="utf-8")


def main():
    WEB.mkdir(parents=True, exist_ok=True)
    save_pngs(make_icon())
    save_svg()


if __name__ == "__main__":
    main()
