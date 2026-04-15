from __future__ import annotations

import re
from datetime import timedelta

DURATION_RE = re.compile(r"^(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")


def parse_duration(text: str) -> int:
    text = text.strip().lower()
    match = DURATION_RE.match(text)
    if not match:
        raise ValueError("Invalid duration format. Use like 10m, 2h, 1d, 30s, or 1h30m")
    days, hours, minutes, seconds = match.groups(default="0")
    total = (
        int(days) * 86400
        + int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
    )
    if total <= 0:
        raise ValueError("Duration must be greater than 0")
    return total


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    parts = []
    td = timedelta(seconds=seconds)
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return " ".join(parts)

