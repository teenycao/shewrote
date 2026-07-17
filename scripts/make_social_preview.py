#!/usr/bin/env python3
"""Generate the 1280x640 social preview card for SheWrote."""

import csv
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "article" / "figs" / "social-preview-1280x640.png"
PROFILES = ROOT / "data" / "out" / "women_profiles.csv"

W, H = 1280, 640
S = 2

BG = "#08090B"
BG_WARM = "#17110D"
GOLD = "#E4BD6B"
GOLD_SOFT = "#B88E43"
GOLD_DIM = "#6E552F"
PAPER = "#F2D99B"
RED = "#A83E3B"
RED_DARK = "#6D2424"
WHITE = "#F7ECD1"

FONT_WENKAI = ROOT / "web" / "fonts" / "wenkai-subset.woff"
# 系统字体已替换为自托管开源字体(合规:OFL 可商用/嵌入/子集),见 assets/fonts/LICENSES.md
_FONTS = ROOT / "assets" / "fonts"
FONT_SONG = _FONTS / "NotoSerifSC.ttf"     # 宋体(原 Songti SC 系统字体)
FONT_SERIF = _FONTS / "NotoSerifSC.ttf"    # 拉丁/数字(原 New York 系统字体)
FONT_GEORGIA = _FONTS / "NotoSerifSC.ttf"  # 拉丁标签(原 Georgia 系统字体)


def color(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if path.exists():
        return ImageFont.truetype(str(path), size * S)
    return ImageFont.truetype(str(FONT_SONG), size * S)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def draw_centered(draw: ImageDraw.ImageDraw, xy, text, fnt, fill):
    x, y = xy
    tw, th = text_size(draw, text, fnt)
    draw.text((x * S - tw / 2, y * S - th / 2), text, font=fnt, fill=fill)


def draw_letterspaced(draw, xy, text, fnt, fill, spacing=0):
    x, y = xy
    cursor = x * S
    for ch in text:
        draw.text((cursor, y * S), ch, font=fnt, fill=fill)
        cw, _ = text_size(draw, ch, fnt)
        cursor += cw + spacing * S


def draw_vertical(draw, x, y, text, fnt, fill, line_gap=2):
    cursor = y * S
    for ch in text:
        cw, chh = text_size(draw, ch, fnt)
        draw.text((x * S - cw / 2, cursor), ch, font=fnt, fill=fill)
        cursor += chh + line_gap * S


def gradient_background() -> Image.Image:
    img = Image.new("RGBA", (W * S, H * S), color(BG))
    pix = img.load()
    for y in range(H * S):
        ny = y / (H * S)
        for x in range(W * S):
            nx = x / (W * S)
            center_glow = max(0, 1 - math.hypot((nx - 0.43) / 0.72, (ny - 0.53) / 0.64))
            edge_vignette = math.hypot(nx - 0.5, ny - 0.5)
            warm = int(18 * center_glow)
            dark = int(32 * max(0, edge_vignette - 0.36))
            r = max(0, 8 + warm - dark)
            g = max(0, 9 + int(warm * 0.72) - dark)
            b = max(0, 11 + int(warm * 0.44) - dark)
            pix[x, y] = (r, g, b, 255)
    return img


def load_names() -> list[str]:
    names = []
    with PROFILES.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["name"].replace("柳是", "柳如是")
            if 2 <= len(name) <= 4:
                names.append(name)
    return names


def draw_stars(base: Image.Image, names: list[str]):
    rng = random.Random(20260705)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    name_font = font(FONT_WENKAI, 18)
    name_font_large = font(FONT_WENKAI, 23)

    zones = []
    for _ in range(66):
        side = rng.choice(["top", "bottom", "left", "right", "field"])
        if side == "top":
            zones.append((rng.randint(30, 1190), rng.randint(18, 150)))
        elif side == "bottom":
            zones.append((rng.randint(60, 1185), rng.randint(480, 590)))
        elif side == "left":
            zones.append((rng.randint(34, 245), rng.randint(105, 525)))
        elif side == "right":
            zones.append((rng.randint(975, 1200), rng.randint(105, 525)))
        else:
            zones.append((rng.choice([rng.randint(250, 380), rng.randint(900, 990)]), rng.randint(160, 470)))

    for i, (x, y) in enumerate(zones):
        if 355 < x < 900 and 170 < y < 425:
            continue
        name = names[i % len(names)]
        alpha = rng.randint(34, 92)
        fnt = name_font_large if i % 13 == 0 else name_font
        fill = color(GOLD_SOFT if i % 13 == 0 else GOLD_DIM, alpha)
        draw.ellipse((x * S - 2, y * S - 2, x * S + 2, y * S + 2), fill=color(GOLD, min(alpha + 30, 120)))
        draw_vertical(draw, x, y + 7, name, fnt, fill, line_gap=1)

    for _ in range(340):
        x = rng.randint(0, W * S - 1)
        y = rng.randint(0, H * S - 1)
        a = rng.randint(18, 72)
        layer.putpixel((x, y), color(GOLD, a))

    for _ in range(26):
        x1, y1 = rng.randint(20, W - 20), rng.randint(40, H - 40)
        x2, y2 = x1 + rng.randint(-90, 110), y1 + rng.randint(-32, 38)
        if 340 < x1 < 930 and 160 < y1 < 450:
            continue
        draw.line((x1 * S, y1 * S, x2 * S, y2 * S), fill=color(GOLD_DIM, rng.randint(18, 42)), width=1 * S)

    base.alpha_composite(layer)


def draw_seal(draw):
    x, y, w, h = 1138, 72, 56, 194
    draw.rounded_rectangle((x * S, y * S, (x + w) * S, (y + h) * S), radius=8 * S, fill=color(RED))
    draw.rounded_rectangle(
        ((x + 3) * S, (y + 3) * S, (x + w - 3) * S, (y + h - 3) * S),
        radius=6 * S,
        outline=color("#D78178", 85),
        width=1 * S,
    )
    seal_font = font(FONT_WENKAI, 17)
    draw_vertical(draw, x + w / 2, y + 17, "中国古代才女", seal_font, color(WHITE), line_gap=3)
    tiny = font(FONT_GEORGIA, 10)
    draw_centered(draw, (x + w / 2, y + h - 20), "DATA", tiny, color("#F7D6CD", 170))


def draw_stat(draw, x, y, value, label, accent=False):
    value_font = font(FONT_SERIF, 50 if len(value) <= 4 else 44)
    label_font = font(FONT_GEORGIA, 17)
    fill = color(GOLD if accent else PAPER)
    draw.text((x * S, y * S), value, font=value_font, fill=fill)
    draw.text((x * S, (y + 58) * S), label, font=label_font, fill=color("#C8AA6B", 220))


def draw_group_separator(draw, x, y1, y2):
    draw.line((x * S, y1 * S, x * S, y2 * S), fill=color(GOLD_DIM, 135), width=1 * S)


def draw_inline_dash(draw, x1, x2, y):
    draw.line((x1 * S, y * S, x2 * S, y * S), fill=color(GOLD_DIM, 165), width=1 * S)


def main():
    img = gradient_background()
    draw_stars(img, load_names())
    draw = ImageDraw.Draw(img)

    zh_big = font(FONT_WENKAI, 82)
    subtitle = font(FONT_GEORGIA, 30)
    body = font(FONT_GEORGIA, 22)
    small = font(FONT_GEORGIA, 16)
    mono = font(FONT_GEORGIA, 14)

    # Central quiet panel, transparent enough to keep the starfield alive.
    panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    pdraw.rounded_rectangle((286 * S, 122 * S, 996 * S, 458 * S), radius=20 * S, fill=(6, 7, 9, 160))
    panel = panel.filter(ImageFilter.GaussianBlur(0.6 * S))
    img.alpha_composite(panel)

    draw.text((336 * S, 148 * S), "中国古代才女", font=zh_big, fill=color(GOLD))
    draw_letterspaced(draw, (344, 259), "SheWrote · Women Poets of Premodern China", subtitle, color(PAPER), spacing=0.6)
    draw.text(
        (344 * S, 309 * S),
        "The first gender-annotated open dataset of classical Chinese poetry",
        font=body,
        fill=color("#D4BE86", 235),
    )
    draw.text(
        (344 * S, 344 * S),
        "CBDB gender field x open poetry corpora",
        font=small,
        fill=color("#9E8151", 220),
    )

    # 数字会随数据修订变化;预览卡只保留长期稳定的项目描述。
    draw.line((344 * S, 395 * S, 892 * S, 395 * S), fill=color(GOLD_DIM, 125), width=1 * S)
    slogan = font(FONT_SONG, 34)
    draw.text((344 * S, 411 * S), "她写过,而记录可以证明。", font=slogan, fill=color(GOLD, 245))

    draw.text((86 * S, 552 * S), "shewrote.teenycao.com", font=mono, fill=color("#8F7140", 190))
    draw.text((86 * S, 582 * S), "github.com/teenycao/shewrote", font=mono, fill=color("#695232", 190))
    draw_seal(draw)

    out = img.resize((W, H), Image.Resampling.LANCZOS).convert("RGB")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT, quality=95)
    print(OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
