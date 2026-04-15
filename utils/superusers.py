from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Set

from config import DATA_DIR, OWNER_ID, GOD_MODE_ENABLED


SUPERUSER_FILE = Path(DATA_DIR) / "superusers.json"
_SUPERUSERS: Set[int] | None = None


def is_primary_owner(user_id: int | None) -> bool:
    return bool(GOD_MODE_ENABLED and OWNER_ID > 0 and user_id == OWNER_ID)


def _load_superusers() -> Set[int]:
    global _SUPERUSERS
    if _SUPERUSERS is not None:
        return _SUPERUSERS
    loaded: Set[int] = set()
    try:
        if SUPERUSER_FILE.exists():
            raw = json.loads(SUPERUSER_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for item in raw:
                    try:
                        user_id = int(item)
                    except Exception:
                        continue
                    if user_id > 0 and user_id != OWNER_ID:
                        loaded.add(user_id)
    except Exception:
        loaded = set()
    _SUPERUSERS = loaded
    return _SUPERUSERS


def _save_superusers() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    user_ids = sorted(_load_superusers())
    SUPERUSER_FILE.write_text(json.dumps(user_ids), encoding="utf-8")


def is_superuser(user_id: int | None) -> bool:
    if not GOD_MODE_ENABLED or not user_id:
        return False
    if is_primary_owner(user_id):
        return True
    return user_id in _load_superusers()


def list_superusers() -> List[int]:
    return sorted(_load_superusers())


def add_superuser(user_id: int) -> bool:
    if user_id <= 0 or user_id == OWNER_ID:
        return False
    superusers = _load_superusers()
    if user_id in superusers:
        return False
    superusers.add(user_id)
    _save_superusers()
    return True


def remove_superuser(user_id: int) -> bool:
    superusers = _load_superusers()
    if user_id not in superusers:
        return False
    superusers.remove(user_id)
    _save_superusers()
    return True
