"""
Profile card image generator.
Inspired by hoyo-buddy's Drawer patterns — gradient bg, circular avatar, PIL composition.
"""
from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── Font resolution ──────────────────────────────────────────────
FONT_PATHS = [
    "C:/Windows/Fonts/segoeui.ttf",        # Windows
    "C:/Windows/Fonts/arial.ttf",           # Windows fallback
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
]
BOLD_FONT_PATHS = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
]

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _find_font(paths: list[str]) -> Optional[str]:
    for p in paths:
        if Path(p).exists():
            return p
    return None


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = ("bold" if bold else "regular", size)
    if key in _font_cache:
        return _font_cache[key]
    paths = BOLD_FONT_PATHS if bold else FONT_PATHS
    path = _find_font(paths)
    if path:
        font = ImageFont.truetype(path, size)
    else:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


# ─── Color utilities ──────────────────────────────────────────────
def hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def lerp_color(c1: Tuple[int, ...], c2: Tuple[int, ...], t: float) -> Tuple[int, ...]:
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


# ─── Drawing primitives ──────────────────────────────────────────
def gradient_background(
    width: int, height: int,
    color1: Tuple[int, int, int], color2: Tuple[int, int, int],
    direction: str = "diagonal",
) -> Image.Image:
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        for x in range(width):
            if direction == "horizontal":
                t = x / max(width - 1, 1)
            elif direction == "vertical":
                t = y / max(height - 1, 1)
            else:  # diagonal
                t = (x + y) / max(width + height - 2, 1)
            r, g, b = lerp_color(color1, color2, t)
            draw.point((x, y), fill=(r, g, b, 255))
    return img


def fast_gradient(
    width: int, height: int,
    color1: Tuple[int, int, int], color2: Tuple[int, int, int],
) -> Image.Image:
    """Fast gradient using PIL line drawing instead of pixel-by-pixel."""
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(height - 1, 1)
        r, g, b = lerp_color(color1, color2, t)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
    return img


def circular_crop(image: Image.Image, size: int) -> Image.Image:
    image = image.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(image, (0, 0), mask)
    return output


def rounded_rect(
    width: int, height: int, radius: int,
    fill: Tuple[int, int, int, int] = (0, 0, 0, 128),
) -> Image.Image:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=fill)
    return img


def draw_progress_bar(
    width: int, height: int, progress: float,
    bg_color: Tuple[int, int, int, int] = (255, 255, 255, 40),
    fill_color: Tuple[int, int, int, int] = (255, 200, 50, 255),
    radius: int = 0,
) -> Image.Image:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = radius or height // 2
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=r, fill=bg_color)
    filled_w = max(r * 2, int(width * min(1.0, max(0.0, progress))))
    if filled_w > 0:
        draw.rounded_rectangle((0, 0, filled_w - 1, height - 1), radius=r, fill=fill_color)
    return img


# ─── Profile card themes ─────────────────────────────────────────
THEMES = {
    "midnight": {"bg1": (15, 15, 35), "bg2": (40, 20, 60), "accent": (160, 120, 255), "bar": (160, 120, 255, 255), "text": (255, 255, 255), "sub": (180, 180, 200)},
    "sunset": {"bg1": (45, 15, 25), "bg2": (60, 30, 20), "accent": (255, 140, 80), "bar": (255, 140, 80, 255), "text": (255, 255, 255), "sub": (200, 180, 170)},
    "ocean": {"bg1": (10, 25, 45), "bg2": (15, 45, 65), "accent": (80, 200, 255), "bar": (80, 200, 255, 255), "text": (255, 255, 255), "sub": (170, 200, 220)},
    "forest": {"bg1": (15, 30, 20), "bg2": (25, 50, 30), "accent": (120, 230, 140), "bar": (120, 230, 140, 255), "text": (255, 255, 255), "sub": (180, 210, 185)},
    "sakura": {"bg1": (40, 15, 30), "bg2": (55, 20, 45), "accent": (255, 140, 180), "bar": (255, 140, 180, 255), "text": (255, 255, 255), "sub": (220, 190, 200)},
}
DEFAULT_THEME = "midnight"


# ─── Main card generator ─────────────────────────────────────────
def draw_profile_card(
    username: str,
    avatar_bytes: Optional[bytes],
    level: int,
    xp_progress: int,
    xp_required: int,
    coins: int,
    messages: int,
    voice_minutes: int,
    badges: list[str],
    title: Optional[str] = None,
    theme: str = DEFAULT_THEME,
) -> io.BytesIO:
    t = THEMES.get(theme, THEMES[DEFAULT_THEME])

    W, H = 800, 340
    PADDING = 30
    AVATAR_SIZE = 100
    BAR_HEIGHT = 16

    # ── Background ──
    card = fast_gradient(W, H, t["bg1"], t["bg2"])

    # ── Dark overlay panel ──
    panel = rounded_rect(W - PADDING * 2, H - PADDING * 2, 20, (0, 0, 0, 80))
    card.alpha_composite(panel, (PADDING, PADDING))

    draw = ImageDraw.Draw(card)

    # ── Avatar ──
    ax, ay = PADDING + 25, PADDING + 25
    # avatar glow ring
    glow = Image.new("RGBA", (AVATAR_SIZE + 8, AVATAR_SIZE + 8), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((0, 0, AVATAR_SIZE + 7, AVATAR_SIZE + 7), fill=(*t["accent"], 120))
    card.alpha_composite(glow, (ax - 4, ay - 4))

    if avatar_bytes:
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar_circle = circular_crop(avatar_img, AVATAR_SIZE)
            card.alpha_composite(avatar_circle, (ax, ay))
        except Exception:
            # fallback: draw colored circle
            draw.ellipse((ax, ay, ax + AVATAR_SIZE, ay + AVATAR_SIZE), fill=(*t["accent"], 180))
    else:
        draw.ellipse((ax, ay, ax + AVATAR_SIZE, ay + AVATAR_SIZE), fill=(*t["accent"], 180))

    # ── Username + title ──
    tx = ax + AVATAR_SIZE + 20
    ty = ay + 8
    font_name = get_font(28, bold=True)
    font_title = get_font(16)
    font_stat = get_font(18)
    font_small = get_font(14)
    font_badge = get_font(20)
    font_level = get_font(22, bold=True)

    draw.text((tx, ty), username.lower(), fill=t["text"], font=font_name)
    if title:
        draw.text((tx, ty + 34), title.lower(), fill=t["sub"], font=font_title)

    # ── Level badge (right side) ──
    level_text = f"lv.{level}"
    lx = W - PADDING - 30
    font_lv_big = get_font(36, bold=True)
    bbox = draw.textbbox((0, 0), level_text, font=font_lv_big)
    lw = bbox[2] - bbox[0]
    draw.text((lx - lw, ay + 10), level_text, fill=t["accent"], font=font_lv_big)

    # ── XP progress bar ──
    bar_y = ay + AVATAR_SIZE + 25
    bar_x = PADDING + 25
    bar_w = W - PADDING * 2 - 50
    progress = xp_progress / max(xp_required, 1)
    bar_img = draw_progress_bar(bar_w, BAR_HEIGHT, progress, (255, 255, 255, 30), t["bar"])
    card.alpha_composite(bar_img, (bar_x, bar_y))

    # XP text
    xp_text = f"{xp_progress:,} / {xp_required:,} xp"
    pct_text = f"{progress * 100:.0f}%"
    draw.text((bar_x, bar_y + BAR_HEIGHT + 4), xp_text, fill=t["sub"], font=font_small)
    pct_bbox = draw.textbbox((0, 0), pct_text, font=font_small)
    pct_w = pct_bbox[2] - pct_bbox[0]
    draw.text((bar_x + bar_w - pct_w, bar_y + BAR_HEIGHT + 4), pct_text, fill=t["accent"], font=font_small)

    # ── Stats row ──
    stat_y = bar_y + BAR_HEIGHT + 32
    stats = [
        ("\U0001f4b0", f"{coins:,}", "coins"),
        ("\U0001f4ac", f"{messages:,}", "msgs"),
        ("\U0001f3a4", f"{voice_minutes:,}", "min"),
    ]
    stat_x = bar_x
    col_w = bar_w // 3
    for emoji, value, label in stats:
        # stat value
        draw.text((stat_x + 4, stat_y), value, fill=t["text"], font=font_stat)
        val_bbox = draw.textbbox((0, 0), value, font=font_stat)
        val_w = val_bbox[2] - val_bbox[0]
        draw.text((stat_x + val_w + 8, stat_y + 2), label, fill=t["sub"], font=font_small)
        stat_x += col_w

    # ── Badges row ──
    if badges:
        badge_y = stat_y + 35
        badge_emojis = {
            "Rising Star": "\u2b50", "Iroha Fan": "\U0001f496",
            "Regular": "\U0001f3b5", "Diva": "\U0001f451", "God Mode": "\u26a1",
        }
        badge_x = bar_x
        for b in badges[:6]:
            badge_label = f" {b}"
            # badge pill background
            pill_bbox = draw.textbbox((0, 0), badge_label, font=font_small)
            pill_w = pill_bbox[2] - pill_bbox[0] + 16
            pill_h = 24
            pill = rounded_rect(pill_w, pill_h, 12, (*t["accent"], 50))
            card.alpha_composite(pill, (badge_x, badge_y))
            draw = ImageDraw.Draw(card)  # refresh draw after composite
            draw.text((badge_x + 8, badge_y + 3), badge_label, fill=t["accent"], font=font_small)
            badge_x += pill_w + 8

    # ── Export ──
    buf = io.BytesIO()
    card.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def draw_rank_card(
    username: str,
    avatar_bytes: Optional[bytes],
    level: int,
    rank: int,
    xp_progress: int,
    xp_required: int,
    messages: int,
    voice_minutes: int,
    theme: str = DEFAULT_THEME,
) -> io.BytesIO:
    t = THEMES.get(theme, THEMES[DEFAULT_THEME])

    W, H = 800, 200
    PADDING = 20
    AVATAR_SIZE = 80

    card = fast_gradient(W, H, t["bg1"], t["bg2"])
    panel = rounded_rect(W - PADDING * 2, H - PADDING * 2, 16, (0, 0, 0, 80))
    card.alpha_composite(panel, (PADDING, PADDING))

    draw = ImageDraw.Draw(card)

    # Avatar
    ax, ay = PADDING + 20, PADDING + 20
    glow = Image.new("RGBA", (AVATAR_SIZE + 6, AVATAR_SIZE + 6), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((0, 0, AVATAR_SIZE + 5, AVATAR_SIZE + 5), fill=(*t["accent"], 100))
    card.alpha_composite(glow, (ax - 3, ay - 3))

    if avatar_bytes:
        try:
            av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            card.alpha_composite(circular_crop(av, AVATAR_SIZE), (ax, ay))
        except Exception:
            draw.ellipse((ax, ay, ax + AVATAR_SIZE, ay + AVATAR_SIZE), fill=(*t["accent"], 180))
    else:
        draw.ellipse((ax, ay, ax + AVATAR_SIZE, ay + AVATAR_SIZE), fill=(*t["accent"], 180))

    # Name + rank
    tx = ax + AVATAR_SIZE + 20
    font_name = get_font(24, bold=True)
    font_small = get_font(14)
    font_rank = get_font(18, bold=True)
    draw.text((tx, ay + 4), username.lower(), fill=t["text"], font=font_name)

    # Rank badge
    rank_text = f"#{rank}" if rank > 0 else ""
    if rank_text:
        rx = W - PADDING - 25
        rbbox = draw.textbbox((0, 0), rank_text, font=get_font(32, bold=True))
        rw = rbbox[2] - rbbox[0]
        draw.text((rx - rw, ay), rank_text, fill=t["accent"], font=get_font(32, bold=True))

    # Level + stats
    draw.text((tx, ay + 30), f"level {level}  \u2022  {messages:,} msgs  \u2022  {voice_minutes:,} min voice", fill=t["sub"], font=font_small)

    # Progress bar
    bar_x = tx
    bar_y = ay + 52
    bar_w = W - bar_x - PADDING - 25
    progress = xp_progress / max(xp_required, 1)
    bar = draw_progress_bar(bar_w, 14, progress, (255, 255, 255, 30), t["bar"])
    card.alpha_composite(bar, (bar_x, bar_y))
    draw = ImageDraw.Draw(card)

    xp_text = f"{xp_progress:,} / {xp_required:,} xp ({progress * 100:.0f}%)"
    draw.text((bar_x, bar_y + 18), xp_text, fill=t["sub"], font=font_small)

    buf = io.BytesIO()
    card.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
