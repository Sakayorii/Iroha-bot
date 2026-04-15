from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, List, Optional, Tuple

import discord


class Colors:
    SUCCESS = discord.Color.green()
    ERROR = discord.Color.red()
    INFO = discord.Color.blue()
    SPECIAL = discord.Color.gold()
    NEUTRAL = discord.Color.greyple()


def make_embed(
    title: str = "",
    description: str = "",
    color: discord.Color = Colors.INFO,
    thumbnail_url: Optional[str] = None,
    footer: str = "iroha",
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=footer)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    return embed


def progress_bar(current: int | float, maximum: int | float, length: int = 10) -> str:
    if maximum <= 0:
        return "\u2591" * length + " 0%"
    ratio = max(0.0, min(1.0, current / maximum))
    filled = round(ratio * length)
    bar = "\u2588" * filled + "\u2591" * (length - filled)
    return f"{bar} {ratio * 100:.0f}%"


def format_duration(ms: int) -> str:
    seconds = ms // 1000
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def medal_prefix(index: int) -> str:
    medals = {0: "\U0001f947", 1: "\U0001f948", 2: "\U0001f949"}
    return medals.get(index, f"{index + 1}.")


def paginate_embed_list(
    items: List[Any],
    per_page: int,
    page: int,
    title: str,
    color: discord.Color,
    formatter_fn: Callable[[int, Any], str],
    thumbnail_url: Optional[str] = None,
) -> Tuple[discord.Embed, int]:
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    chunk = items[start : start + per_page]

    lines = [formatter_fn(start + i, item) for i, item in enumerate(chunk)]
    description = "\n".join(lines) if lines else "nothing here."

    embed = make_embed(
        title=title,
        description=description,
        color=color,
        thumbnail_url=thumbnail_url,
    )
    embed.set_footer(text=f"page {page}/{total_pages} \u2022 iroha")
    return embed, total_pages
