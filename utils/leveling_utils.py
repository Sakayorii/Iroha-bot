from __future__ import annotations

import math


def xp_for_level(level: int) -> int:
    if level <= 1:
        return 0
    return 100 * (level - 1) * (level - 1)


def level_from_xp(xp: int) -> int:
    if xp <= 0:
        return 1
    return int(math.sqrt(xp / 100)) + 1


def progress_to_next_level(xp: int) -> tuple[int, int]:
    level = level_from_xp(xp)
    current_floor = xp_for_level(level)
    next_floor = xp_for_level(level + 1)
    return xp - current_floor, max(1, next_floor - current_floor)
