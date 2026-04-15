from __future__ import annotations

import asyncio
import json
import aiosqlite
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from config import (
    DB_PATH,
    DEFAULT_LOCALE,
    OWNER_ID,
    ANTI_SPAM_ENABLED,
    ANTI_SPAM_RATE,
    ANTI_SPAM_INTERVAL,
    ANTI_RAID_ENABLED,
    ANTI_RAID_THRESHOLD,
    ANTI_RAID_WINDOW,
    CACHE_TTL_MINUTES,
    CACHE_MAX_GB,
    ANTI_INVITE_ENABLED,
    ANTI_LINK_ENABLED,
    ANTI_NSFW_ENABLED,
    MAX_MENTIONS,
    BOT_RATIO_GUARD_ENABLED,
    BOT_RATIO_MAX,
)
from utils.superusers import is_superuser, is_primary_owner, list_superusers

_pool: list[aiosqlite.Connection] = []
_pool_size: int = 5
_pool_lock = asyncio.Lock()


@asynccontextmanager
async def _get_db() -> AsyncIterator[aiosqlite.Connection]:
    conn: aiosqlite.Connection | None = None
    async with _pool_lock:
        if _pool:
            conn = _pool.pop()
    if conn is None:
        conn = await aiosqlite.connect(DB_PATH)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        async with _pool_lock:
            if len(_pool) < _pool_size:
                _pool.append(conn)
            else:
                await conn.close()


async def close_pool() -> None:
    async with _pool_lock:
        for conn in _pool:
            await conn.close()
        _pool.clear()

CREATE_SQL = ""
CREATE_SQL += """
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id INTEGER PRIMARY KEY,
    log_channel_id INTEGER,
    welcome_channel_id INTEGER,
    goodbye_channel_id INTEGER,
    ai_channel_id INTEGER,
    music_channel_id INTEGER,
    mod_role_id INTEGER,
    auto_role_id INTEGER,
    verify_channel_id INTEGER,
    verify_role_id INTEGER,
    verify_message_id INTEGER,
    verify_enabled INTEGER,
    giveaway_channel_id INTEGER,
    giveaway_enabled INTEGER,
    locale TEXT,
    ai_enabled INTEGER,
    music_enabled INTEGER,
    leveling_enabled INTEGER,
    economy_enabled INTEGER,
    games_enabled INTEGER,
    tickets_enabled INTEGER,
    roles_enabled INTEGER,
    reminders_enabled INTEGER,
    polls_enabled INTEGER,
    logging_enabled INTEGER,
    welcome_enabled INTEGER,
    goodbye_enabled INTEGER,
    boost_enabled INTEGER,
    anti_spam_enabled INTEGER,
    anti_spam_rate INTEGER,
    anti_spam_interval INTEGER,
    anti_raid_enabled INTEGER,
    anti_raid_threshold INTEGER,
    anti_raid_window INTEGER,
    anti_invite_enabled INTEGER,
    anti_link_enabled INTEGER,
    anti_nsfw_enabled INTEGER,
    max_mentions INTEGER,
    bot_ratio_guard_enabled INTEGER,
    bot_ratio_max REAL,
    cache_ttl_minutes INTEGER,
    cache_max_gb REAL,
    welcome_message TEXT,
    goodbye_message TEXT,
    boost_message TEXT
);

CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocked_words (
    guild_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS economy (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    balance INTEGER NOT NULL DEFAULT 0,
    last_daily TEXT,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS user_profile (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    title TEXT,
    frame TEXT,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS user_items (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, item_id)
);

CREATE TABLE IF NOT EXISTS leveling (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    last_xp_at TEXT,
    message_count INTEGER NOT NULL DEFAULT 0,
    voice_seconds INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS badges (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    badge TEXT NOT NULL,
    PRIMARY KEY (guild_id, user_id, badge)
);

CREATE TABLE IF NOT EXISTS daily_tasks (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    task_type TEXT NOT NULL,
    target INTEGER NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    claimed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, date, task_type)
);
"""

CREATE_SQL += """
CREATE TABLE IF NOT EXISTS fishing_inventory (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, item_name)
);

CREATE TABLE IF NOT EXISTS pokemon_collection (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    pokemon_name TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, pokemon_name)
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    guild_id INTEGER,
    channel_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    remind_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS afk_status (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT,
    since_at TEXT NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS music_cache (
    video_id TEXT NOT NULL,
    quality TEXT NOT NULL,
    title TEXT,
    duration INTEGER,
    filepath TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    last_played_at TEXT NOT NULL,
    PRIMARY KEY (video_id, quality)
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    opener_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    closed_at TEXT
);
"""

CREATE_SQL += """
CREATE TABLE IF NOT EXISTS role_menus (
    guild_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    title TEXT,
    min_values INTEGER NOT NULL DEFAULT 0,
    max_values INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (message_id)
);

CREATE TABLE IF NOT EXISTS role_menu_items (
    message_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    label TEXT,
    emoji TEXT,
    PRIMARY KEY (message_id, role_id)
);

CREATE TABLE IF NOT EXISTS polls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    options_json TEXT NOT NULL,
    anonymous INTEGER NOT NULL DEFAULT 0,
    ends_at TEXT,
    created_at TEXT NOT NULL,
    created_by INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS poll_votes (
    poll_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    option_index INTEGER NOT NULL,
    PRIMARY KEY (poll_id, user_id)
);

CREATE TABLE IF NOT EXISTS birthdays (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    event_time TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verify_codes (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS giveaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    prize TEXT NOT NULL,
    winner_count INTEGER NOT NULL,
    ends_at TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    ended_at TEXT,
    winners_json TEXT
);

CREATE TABLE IF NOT EXISTS giveaway_entries (
    giveaway_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (giveaway_id, user_id)
);
"""

DEFAULT_CONFIG = {
    "log_channel_id": None,
    "welcome_channel_id": None,
    "goodbye_channel_id": None,
    "ai_channel_id": None,
    "music_channel_id": None,
    "mod_role_id": None,
    "auto_role_id": None,
    "verify_channel_id": None,
    "verify_role_id": None,
    "verify_message_id": None,
    "verify_enabled": 1,
    "giveaway_channel_id": None,
    "giveaway_enabled": 1,
    "locale": DEFAULT_LOCALE,
    "ai_enabled": 1,
    "music_enabled": 1,
    "leveling_enabled": 1,
    "economy_enabled": 1,
    "games_enabled": 1,
    "tickets_enabled": 1,
    "roles_enabled": 1,
    "reminders_enabled": 1,
    "polls_enabled": 1,
    "logging_enabled": 1,
    "welcome_enabled": 1,
    "goodbye_enabled": 1,
    "boost_enabled": 1,
    "anti_spam_enabled": 1 if ANTI_SPAM_ENABLED else 0,
    "anti_spam_rate": ANTI_SPAM_RATE,
    "anti_spam_interval": ANTI_SPAM_INTERVAL,
    "anti_raid_enabled": 1 if ANTI_RAID_ENABLED else 0,
    "anti_raid_threshold": ANTI_RAID_THRESHOLD,
    "anti_raid_window": ANTI_RAID_WINDOW,
    "anti_invite_enabled": 1 if ANTI_INVITE_ENABLED else 0,
    "anti_link_enabled": 1 if ANTI_LINK_ENABLED else 0,
    "anti_nsfw_enabled": 1 if ANTI_NSFW_ENABLED else 0,
    "max_mentions": MAX_MENTIONS,
    "bot_ratio_guard_enabled": 1 if BOT_RATIO_GUARD_ENABLED else 0,
    "bot_ratio_max": BOT_RATIO_MAX,
    "cache_ttl_minutes": CACHE_TTL_MINUTES,
    "cache_max_gb": CACHE_MAX_GB,
    "welcome_message": "Welcome {user} to {server}!",
    "goodbye_message": "Goodbye {user}.",
    "boost_message": "Thanks for boosting the server, {user}!",
}

GUILD_CONFIG_COLUMNS = [
    ("log_channel_id", "INTEGER", None),
    ("welcome_channel_id", "INTEGER", None),
    ("goodbye_channel_id", "INTEGER", None),
    ("ai_channel_id", "INTEGER", None),
    ("music_channel_id", "INTEGER", None),
    ("mod_role_id", "INTEGER", None),
    ("auto_role_id", "INTEGER", None),
    ("verify_channel_id", "INTEGER", None),
    ("verify_role_id", "INTEGER", None),
    ("verify_message_id", "INTEGER", None),
    ("verify_enabled", "INTEGER", 1),
    ("giveaway_channel_id", "INTEGER", None),
    ("giveaway_enabled", "INTEGER", 1),
    ("locale", "TEXT", DEFAULT_LOCALE),
    ("ai_enabled", "INTEGER", 1),
    ("music_enabled", "INTEGER", 1),
    ("leveling_enabled", "INTEGER", 1),
    ("economy_enabled", "INTEGER", 1),
    ("games_enabled", "INTEGER", 1),
    ("tickets_enabled", "INTEGER", 1),
    ("roles_enabled", "INTEGER", 1),
    ("reminders_enabled", "INTEGER", 1),
    ("polls_enabled", "INTEGER", 1),
    ("logging_enabled", "INTEGER", 1),
    ("welcome_enabled", "INTEGER", 1),
    ("goodbye_enabled", "INTEGER", 1),
    ("boost_enabled", "INTEGER", 1),
    ("anti_spam_enabled", "INTEGER", 1 if ANTI_SPAM_ENABLED else 0),
    ("anti_spam_rate", "INTEGER", ANTI_SPAM_RATE),
    ("anti_spam_interval", "INTEGER", ANTI_SPAM_INTERVAL),
    ("anti_raid_enabled", "INTEGER", 1 if ANTI_RAID_ENABLED else 0),
    ("anti_raid_threshold", "INTEGER", ANTI_RAID_THRESHOLD),
    ("anti_raid_window", "INTEGER", ANTI_RAID_WINDOW),
    ("anti_invite_enabled", "INTEGER", 1 if ANTI_INVITE_ENABLED else 0),
    ("anti_link_enabled", "INTEGER", 1 if ANTI_LINK_ENABLED else 0),
    ("anti_nsfw_enabled", "INTEGER", 1 if ANTI_NSFW_ENABLED else 0),
    ("max_mentions", "INTEGER", MAX_MENTIONS),
    ("bot_ratio_guard_enabled", "INTEGER", 1 if BOT_RATIO_GUARD_ENABLED else 0),
    ("bot_ratio_max", "REAL", BOT_RATIO_MAX),
    ("cache_ttl_minutes", "INTEGER", CACHE_TTL_MINUTES),
    ("cache_max_gb", "REAL", CACHE_MAX_GB),
    ("welcome_message", "TEXT", "Welcome {user} to {server}!"),
    ("goodbye_message", "TEXT", "Goodbye {user}."),
    ("boost_message", "TEXT", "Thanks for boosting the server, {user}!"),
]

GOD_XP = 10**18
GOD_LEVEL = int((GOD_XP // 100) ** 0.5) + 1
GOD_COINS = 10**18
GOD_MESSAGE_COUNT = 10**12
GOD_VOICE_SECONDS = 10**12
GOD_ITEM_COUNT = 999999
GOD_USER_ITEM_IDS = ("iroha_frame", "star_title", "fan_title")
GOD_FISH_ITEMS = ("Mystic Koi", "Golden Fish", "Iroha Bass")
GOD_POKEMON = ("Pikachu", "Eevee", "Bulbasaur", "Charmander", "Squirtle", "Jigglypuff")
GOD_BADGES = ("Rising Star", "Iroha Fan", "Regular", "Diva", "God Mode")


def _is_owner_god(user_id: int | None) -> bool:
    return is_superuser(user_id)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sql_default(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return f"DEFAULT {1 if value else 0}"
    if isinstance(value, (int, float)):
        return f"DEFAULT {value}"
    escaped = str(value).replace("'", "''")
    return f"DEFAULT '{escaped}'"


async def _fetchone(db: aiosqlite.Connection, sql: str, params: Tuple[Any, ...] = ()) -> Any:
    cursor = await db.execute(sql, params)
    try:
        return await cursor.fetchone()
    finally:
        await cursor.close()


async def _fetchall(db: aiosqlite.Connection, sql: str, params: Tuple[Any, ...] = ()) -> List[Any]:
    cursor = await db.execute(sql, params)
    try:
        return await cursor.fetchall()
    finally:
        await cursor.close()


async def _ensure_columns(db: aiosqlite.Connection, table: str, columns: List[Tuple[str, str, Any]]) -> None:
    rows = await _fetchall(db, f"PRAGMA table_info({table})")
    existing = {row[1] for row in rows}
    for name, col_type, default in columns:
        if name in existing:
            continue
        default_sql = _sql_default(default)
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type} {default_sql}")


async def init_db() -> None:
    async with _get_db() as db:
        await db.executescript(CREATE_SQL)
        await _ensure_columns(db, "guild_config", GUILD_CONFIG_COLUMNS)
        await db.commit()


async def get_guild_config(guild_id: int) -> Dict[str, Any]:
    async with _get_db() as db:

        row = await _fetchone(db, 
            "SELECT * FROM guild_config WHERE guild_id = ?",
            (guild_id,),
        )
        if row is None:
            await _insert_default_config(db, guild_id)
            await db.commit()
            row = await _fetchone(db, 
                "SELECT * FROM guild_config WHERE guild_id = ?",
                (guild_id,),
            )
        return dict(row)


async def _insert_default_config(db: aiosqlite.Connection, guild_id: int) -> None:
    columns = ",".join(["guild_id"] + list(DEFAULT_CONFIG.keys()))
    placeholders = ",".join(["?"] * (1 + len(DEFAULT_CONFIG)))
    values = [guild_id] + list(DEFAULT_CONFIG.values())
    await db.execute(
        f"INSERT OR IGNORE INTO guild_config ({columns}) VALUES ({placeholders})",
        values,
    )


async def update_guild_config(guild_id: int, **kwargs: Any) -> None:
    if not kwargs:
        return
    _valid_columns = set(DEFAULT_CONFIG.keys())
    _safe = {k: v for k, v in kwargs.items() if k in _valid_columns}
    if not _safe:
        return
    fields = ",".join([f"{k} = ?" for k in _safe.keys()])
    values = list(_safe.values()) + [guild_id]
    async with _get_db() as db:
        await _insert_default_config(db, guild_id)
        await db.execute(f"UPDATE guild_config SET {fields} WHERE guild_id = ?", values)
        await db.commit()


async def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, moderator_id, reason, _utcnow()),
        )
        await db.commit()


async def get_warnings(guild_id: int, user_id: int) -> List[Dict[str, Any]]:
    if _is_owner_god(user_id):
        return []
    async with _get_db() as db:

        rows = await _fetchall(db, 
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC",
            (guild_id, user_id),
        )
        return [dict(r) for r in rows]


async def clear_warnings(guild_id: int, user_id: int) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        await db.commit()


async def add_blocked_word(guild_id: int, word: str) -> None:
    async with _get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO blocked_words (guild_id, word) VALUES (?, ?)",
            (guild_id, word.lower()),
        )
        await db.commit()


async def remove_blocked_word(guild_id: int, word: str) -> None:
    async with _get_db() as db:
        await db.execute(
            "DELETE FROM blocked_words WHERE guild_id = ? AND word = ?",
            (guild_id, word.lower()),
        )
        await db.commit()


async def list_blocked_words(guild_id: int) -> List[str]:
    async with _get_db() as db:
        rows = await _fetchall(db, 
            "SELECT word FROM blocked_words WHERE guild_id = ? ORDER BY word ASC",
            (guild_id,),
        )
        return [r[0] for r in rows]


async def get_balance(guild_id: int, user_id: int) -> Tuple[int, Optional[str]]:
    if _is_owner_god(user_id):
        return GOD_COINS, None
    async with _get_db() as db:
        row = await _fetchone(db, 
            "SELECT balance, last_daily FROM economy WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        if row is None:
            await db.execute(
                "INSERT INTO economy (guild_id, user_id, balance) VALUES (?, ?, 0)",
                (guild_id, user_id),
            )
            await db.commit()
            return 0, None
        return row[0], row[1]


async def update_balance(guild_id: int, user_id: int, delta: int) -> int:
    if _is_owner_god(user_id):
        return GOD_COINS
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO economy (guild_id, user_id, balance) VALUES (?, ?, 0) ON CONFLICT(guild_id, user_id) DO NOTHING",
            (guild_id, user_id),
        )
        await db.execute(
            "UPDATE economy SET balance = balance + ? WHERE guild_id = ? AND user_id = ?",
            (delta, guild_id, user_id),
        )
        await db.commit()
        row = await _fetchone(db, 
            "SELECT balance FROM economy WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return row[0] if row else 0


async def set_balance(guild_id: int, user_id: int, amount: int) -> int:
    if _is_owner_god(user_id):
        return GOD_COINS
    amount = max(0, int(amount))
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO economy (guild_id, user_id, balance) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET balance=excluded.balance",
            (guild_id, user_id, amount),
        )
        await db.commit()
        return amount


async def set_last_daily(guild_id: int, user_id: int, iso_time: str) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "UPDATE economy SET last_daily = ? WHERE guild_id = ? AND user_id = ?",
            (iso_time, guild_id, user_id),
        )
        await db.commit()


async def upsert_user_profile(guild_id: int, user_id: int, title: Optional[str], frame: Optional[str]) -> None:
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO user_profile (guild_id, user_id, title, frame) VALUES (?, ?, ?, ?)\n"
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET title=excluded.title, frame=excluded.frame",
            (guild_id, user_id, title, frame),
        )
        await db.commit()


async def get_user_profile(guild_id: int, user_id: int) -> Dict[str, Any]:
    async with _get_db() as db:

        row = await _fetchone(db, 
            "SELECT title, frame FROM user_profile WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return dict(row) if row else {"title": None, "frame": None}


async def add_user_item(guild_id: int, user_id: int, item_id: str, count: int = 1) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO user_items (guild_id, user_id, item_id, count) VALUES (?, ?, ?, ?)\n"
            "ON CONFLICT(guild_id, user_id, item_id) DO UPDATE SET count = count + ?",
            (guild_id, user_id, item_id, count, count),
        )
        await db.commit()


async def get_user_items(guild_id: int, user_id: int) -> List[Dict[str, Any]]:
    if _is_owner_god(user_id):
        return [{"item_id": item_id, "count": GOD_ITEM_COUNT} for item_id in GOD_USER_ITEM_IDS]
    async with _get_db() as db:

        rows = await _fetchall(db, 
            "SELECT item_id, count FROM user_items WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return [dict(r) for r in rows]


async def get_leveling(guild_id: int, user_id: int) -> Dict[str, Any]:
    if _is_owner_god(user_id):
        return {
            "xp": GOD_XP,
            "level": GOD_LEVEL,
            "last_xp_at": None,
            "message_count": GOD_MESSAGE_COUNT,
            "voice_seconds": GOD_VOICE_SECONDS,
        }
    async with _get_db() as db:

        row = await _fetchone(db, 
            "SELECT xp, level, last_xp_at, message_count, voice_seconds FROM leveling WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        if row is None:
            await db.execute(
                "INSERT INTO leveling (guild_id, user_id, xp, level) VALUES (?, ?, 0, 1)",
                (guild_id, user_id),
            )
            await db.commit()
            return {"xp": 0, "level": 1, "last_xp_at": None, "message_count": 0, "voice_seconds": 0}
        return dict(row)


async def set_leveling(guild_id: int, user_id: int, xp: int, level: int, last_xp_at: Optional[str]) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO leveling (guild_id, user_id, xp, level, last_xp_at) VALUES (?, ?, ?, ?, ?)\n"
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp=excluded.xp, level=excluded.level, last_xp_at=excluded.last_xp_at",
            (guild_id, user_id, xp, level, last_xp_at),
        )
        await db.commit()


async def increment_message_count(guild_id: int, user_id: int, count: int = 1) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO leveling (guild_id, user_id, xp, level, message_count) VALUES (?, ?, 0, 1, 0)\n"
            "ON CONFLICT(guild_id, user_id) DO NOTHING",
            (guild_id, user_id),
        )
        await db.execute(
            "UPDATE leveling SET message_count = message_count + ? WHERE guild_id = ? AND user_id = ?",
            (count, guild_id, user_id),
        )
        await db.commit()


async def increment_voice_seconds(guild_id: int, user_id: int, seconds: int) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO leveling (guild_id, user_id, xp, level, voice_seconds) VALUES (?, ?, 0, 1, 0)\n"
            "ON CONFLICT(guild_id, user_id) DO NOTHING",
            (guild_id, user_id),
        )
        await db.execute(
            "UPDATE leveling SET voice_seconds = voice_seconds + ? WHERE guild_id = ? AND user_id = ?",
            (seconds, guild_id, user_id),
        )
        await db.commit()


async def get_leaderboard(guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []
    async with _get_db() as db:

        rows = await _fetchall(db, 
            "SELECT user_id, xp, level, message_count, voice_seconds FROM leveling WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
            (guild_id, limit),
        )
        data = [dict(r) for r in rows]
    privileged_ids: List[int] = []
    if is_primary_owner(OWNER_ID):
        privileged_ids.append(OWNER_ID)
    for user_id in list_superusers():
        if user_id not in privileged_ids:
            privileged_ids.append(user_id)
    if privileged_ids:
        blocked = set(privileged_ids)
        data = [row for row in data if int(row.get("user_id", 0)) not in blocked]
        for user_id in reversed(privileged_ids):
            data.insert(
                0,
                {
                    "user_id": user_id,
                    "xp": GOD_XP,
                    "level": GOD_LEVEL,
                    "message_count": GOD_MESSAGE_COUNT,
                    "voice_seconds": GOD_VOICE_SECONDS,
                },
            )
        return data[:limit]
    return data


async def add_badge(guild_id: int, user_id: int, badge: str) -> None:
    async with _get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO badges (guild_id, user_id, badge) VALUES (?, ?, ?)",
            (guild_id, user_id, badge),
        )
        await db.commit()


async def get_badges(guild_id: int, user_id: int) -> List[str]:
    if _is_owner_god(user_id):
        return list(GOD_BADGES)
    async with _get_db() as db:
        rows = await _fetchall(db, 
            "SELECT badge FROM badges WHERE guild_id = ? AND user_id = ? ORDER BY badge ASC",
            (guild_id, user_id),
        )
        return [r[0] for r in rows]


async def upsert_daily_task(
    guild_id: int,
    user_id: int,
    date: str,
    task_type: str,
    target: int,
    progress: int,
    claimed: int,
) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO daily_tasks (guild_id, user_id, date, task_type, target, progress, claimed) VALUES (?, ?, ?, ?, ?, ?, ?)\n"
            "ON CONFLICT(guild_id, user_id, date, task_type) DO UPDATE SET target=excluded.target, progress=excluded.progress, claimed=excluded.claimed",
            (guild_id, user_id, date, task_type, target, progress, claimed),
        )
        await db.commit()


async def get_daily_tasks(guild_id: int, user_id: int, date: str) -> List[Dict[str, Any]]:
    if _is_owner_god(user_id):
        return [
            {"task_type": "messages", "target": 1, "progress": 1, "claimed": 1},
            {"task_type": "voice_minutes", "target": 1, "progress": 1, "claimed": 1},
            {"task_type": "games", "target": 1, "progress": 1, "claimed": 1},
        ]
    async with _get_db() as db:

        rows = await _fetchall(db, 
            "SELECT task_type, target, progress, claimed FROM daily_tasks WHERE guild_id = ? AND user_id = ? AND date = ?",
            (guild_id, user_id, date),
        )
        return [dict(r) for r in rows]


async def update_daily_progress(guild_id: int, user_id: int, date: str, task_type: str, delta: int) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "UPDATE daily_tasks SET progress = progress + ? WHERE guild_id = ? AND user_id = ? AND date = ? AND task_type = ?",
            (delta, guild_id, user_id, date, task_type),
        )
        await db.commit()


async def claim_daily(guild_id: int, user_id: int, date: str) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "UPDATE daily_tasks SET claimed = 1 WHERE guild_id = ? AND user_id = ? AND date = ?",
            (guild_id, user_id, date),
        )
        await db.commit()


async def add_inventory_item(guild_id: int, user_id: int, item_name: str, count: int = 1) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO fishing_inventory (guild_id, user_id, item_name, count) VALUES (?, ?, ?, ?)\n"
            "ON CONFLICT(guild_id, user_id, item_name) DO UPDATE SET count = count + ?",
            (guild_id, user_id, item_name, count, count),
        )
        await db.commit()


async def get_inventory(guild_id: int, user_id: int) -> List[Dict[str, Any]]:
    if _is_owner_god(user_id):
        return [{"item_name": item_name, "count": GOD_ITEM_COUNT} for item_name in GOD_FISH_ITEMS]
    async with _get_db() as db:

        rows = await _fetchall(db, 
            "SELECT item_name, count FROM fishing_inventory WHERE guild_id = ? AND user_id = ? ORDER BY count DESC",
            (guild_id, user_id),
        )
        return [dict(r) for r in rows]


async def add_pokemon(guild_id: int, user_id: int, pokemon_name: str, count: int = 1) -> None:
    if _is_owner_god(user_id):
        return
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO pokemon_collection (guild_id, user_id, pokemon_name, count) VALUES (?, ?, ?, ?)\n"
            "ON CONFLICT(guild_id, user_id, pokemon_name) DO UPDATE SET count = count + ?",
            (guild_id, user_id, pokemon_name, count, count),
        )
        await db.commit()


async def get_pokemon_collection(guild_id: int, user_id: int) -> List[Dict[str, Any]]:
    if _is_owner_god(user_id):
        return [{"pokemon_name": pokemon_name, "count": GOD_ITEM_COUNT} for pokemon_name in GOD_POKEMON]
    async with _get_db() as db:

        rows = await _fetchall(db, 
            "SELECT pokemon_name, count FROM pokemon_collection WHERE guild_id = ? AND user_id = ? ORDER BY count DESC",
            (guild_id, user_id),
        )
        return [dict(r) for r in rows]


async def create_reminder(user_id: int, guild_id: Optional[int], channel_id: int, message: str, remind_at: str) -> None:
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO reminders (user_id, guild_id, channel_id, message, remind_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, guild_id, channel_id, message, remind_at, _utcnow()),
        )
        await db.commit()


async def get_due_reminders(now_iso: str) -> List[Dict[str, Any]]:
    async with _get_db() as db:

        rows = await _fetchall(db, 
            "SELECT * FROM reminders WHERE remind_at <= ? ORDER BY remind_at ASC",
            (now_iso,),
        )
        return [dict(r) for r in rows]


async def delete_reminder(reminder_id: int) -> None:
    async with _get_db() as db:
        await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        await db.commit()


async def set_afk_status(guild_id: int, user_id: int, reason: str, since_at: str) -> None:
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO afk_status (guild_id, user_id, reason, since_at) VALUES (?, ?, ?, ?)\n"
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET reason=excluded.reason, since_at=excluded.since_at",
            (guild_id, user_id, reason, since_at),
        )
        await db.commit()


async def get_afk_status(guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    async with _get_db() as db:

        row = await _fetchone(
            db,
            "SELECT guild_id, user_id, reason, since_at FROM afk_status WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return dict(row) if row else None


async def get_afk_statuses(guild_id: int, user_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    if not user_ids:
        return {}
    placeholders = ",".join(["?"] * len(user_ids))
    params: Tuple[Any, ...] = (guild_id, *user_ids)
    async with _get_db() as db:

        rows = await _fetchall(
            db,
            f"SELECT user_id, reason, since_at FROM afk_status WHERE guild_id = ? AND user_id IN ({placeholders})",
            params,
        )
        return {int(row["user_id"]): dict(row) for row in rows}


async def clear_afk_status(guild_id: int, user_id: int) -> bool:
    async with _get_db() as db:
        cursor = await db.execute(
            "DELETE FROM afk_status WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def upsert_music_cache(
    video_id: str,
    quality: str,
    title: str,
    duration: Optional[int],
    filepath: str,
    size_bytes: int,
    last_played_at: str,
) -> None:
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO music_cache (video_id, quality, title, duration, filepath, size_bytes, last_played_at)\n"
            "VALUES (?, ?, ?, ?, ?, ?, ?)\n"
            "ON CONFLICT(video_id, quality) DO UPDATE SET title=excluded.title, duration=excluded.duration, filepath=excluded.filepath, size_bytes=excluded.size_bytes, last_played_at=excluded.last_played_at",
            (video_id, quality, title, duration, filepath, size_bytes, last_played_at),
        )
        await db.commit()


async def get_music_cache(video_id: str, quality: str) -> Optional[Dict[str, Any]]:
    async with _get_db() as db:

        row = await _fetchone(db, 
            "SELECT * FROM music_cache WHERE video_id = ? AND quality = ?",
            (video_id, quality),
        )
        return dict(row) if row else None


async def touch_music_cache(video_id: str, quality: str, last_played_at: str) -> None:
    async with _get_db() as db:
        await db.execute(
            "UPDATE music_cache SET last_played_at = ? WHERE video_id = ? AND quality = ?",
            (last_played_at, video_id, quality),
        )
        await db.commit()


async def list_music_cache() -> List[Dict[str, Any]]:
    async with _get_db() as db:

        rows = await _fetchall(db, "SELECT * FROM music_cache")
        return [dict(r) for r in rows]


async def delete_music_cache(video_id: str, quality: str) -> None:
    async with _get_db() as db:
        await db.execute(
            "DELETE FROM music_cache WHERE video_id = ? AND quality = ?",
            (video_id, quality),
        )
        await db.commit()


async def create_ticket(guild_id: int, channel_id: int, opener_id: int) -> int:
    async with _get_db() as db:
        cursor = await db.execute(
            "INSERT INTO tickets (guild_id, channel_id, opener_id, status, created_at) VALUES (?, ?, ?, 'open', ?)",
            (guild_id, channel_id, opener_id, _utcnow()),
        )
        await db.commit()
        return cursor.lastrowid


async def close_ticket(channel_id: int) -> None:
    async with _get_db() as db:
        await db.execute(
            "UPDATE tickets SET status='closed', closed_at=? WHERE channel_id = ?",
            (_utcnow(), channel_id),
        )
        await db.commit()


async def create_role_menu(
    guild_id: int,
    message_id: int,
    channel_id: int,
    title: str,
    min_values: int,
    max_values: int,
) -> None:
    async with _get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO role_menus (guild_id, message_id, channel_id, title, min_values, max_values) VALUES (?, ?, ?, ?, ?, ?)",
            (guild_id, message_id, channel_id, title, min_values, max_values),
        )
        await db.commit()


async def add_role_menu_item(message_id: int, role_id: int, label: str, emoji: Optional[str]) -> None:
    async with _get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO role_menu_items (message_id, role_id, label, emoji) VALUES (?, ?, ?, ?)",
            (message_id, role_id, label, emoji),
        )
        await db.commit()


async def get_role_menu(message_id: int) -> Optional[Dict[str, Any]]:
    async with _get_db() as db:

        row = await _fetchone(db, 
            "SELECT * FROM role_menus WHERE message_id = ?",
            (message_id,),
        )
        return dict(row) if row else None


async def list_role_menu_items(message_id: int) -> List[Dict[str, Any]]:
    async with _get_db() as db:

        rows = await _fetchall(db, 
            "SELECT role_id, label, emoji FROM role_menu_items WHERE message_id = ?",
            (message_id,),
        )
        return [dict(r) for r in rows]


async def list_all_role_menus() -> List[Dict[str, Any]]:
    async with _get_db() as db:

        rows = await _fetchall(db, "SELECT * FROM role_menus")
        return [dict(r) for r in rows]


async def create_poll(
    guild_id: int,
    channel_id: int,
    message_id: int,
    question: str,
    options_json: str,
    anonymous: int,
    ends_at: Optional[str],
    created_by: int,
) -> int:
    async with _get_db() as db:
        cursor = await db.execute(
            "INSERT INTO polls (guild_id, channel_id, message_id, question, options_json, anonymous, ends_at, created_at, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (guild_id, channel_id, message_id, question, options_json, anonymous, ends_at, _utcnow(), created_by),
        )
        await db.commit()
        return cursor.lastrowid


async def get_poll(poll_id: int) -> Optional[Dict[str, Any]]:
    async with _get_db() as db:

        row = await _fetchone(db, 
            "SELECT * FROM polls WHERE id = ?",
            (poll_id,),
        )
        return dict(row) if row else None


async def get_poll_by_message(message_id: int) -> Optional[Dict[str, Any]]:
    async with _get_db() as db:

        row = await _fetchone(db, 
            "SELECT * FROM polls WHERE message_id = ?",
            (message_id,),
        )
        return dict(row) if row else None


async def list_due_polls(now_iso: str) -> List[Dict[str, Any]]:
    async with _get_db() as db:

        rows = await _fetchall(db, 
            "SELECT * FROM polls WHERE ends_at IS NOT NULL AND ends_at <= ?",
            (now_iso,),
        )
        return [dict(r) for r in rows]


async def list_open_polls(now_iso: str) -> List[Dict[str, Any]]:
    async with _get_db() as db:

        rows = await _fetchall(db, 
            "SELECT * FROM polls WHERE ends_at IS NULL OR ends_at > ?",
            (now_iso,),
        )
        return [dict(r) for r in rows]


async def delete_poll(poll_id: int) -> None:
    async with _get_db() as db:
        await db.execute("DELETE FROM polls WHERE id = ?", (poll_id,))
        await db.execute("DELETE FROM poll_votes WHERE poll_id = ?", (poll_id,))
        await db.commit()


async def vote_poll(poll_id: int, user_id: int, option_index: int) -> None:
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO poll_votes (poll_id, user_id, option_index) VALUES (?, ?, ?)\n"
            "ON CONFLICT(poll_id, user_id) DO UPDATE SET option_index=excluded.option_index",
            (poll_id, user_id, option_index),
        )
        await db.commit()


async def get_poll_counts(poll_id: int, option_count: int) -> List[int]:
    async with _get_db() as db:
        rows = await _fetchall(db, 
            "SELECT option_index, COUNT(*) FROM poll_votes WHERE poll_id = ? GROUP BY option_index",
            (poll_id,),
        )
        counts = [0] * option_count
        for idx, cnt in rows:
            if 0 <= idx < option_count:
                counts[idx] = cnt
        return counts


async def set_birthday(guild_id: int, user_id: int, month: int, day: int) -> None:
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError(f"Invalid birthday: month={month}, day={day}")
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO birthdays (guild_id, user_id, month, day) VALUES (?, ?, ?, ?)\n"
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET month=excluded.month, day=excluded.day",
            (guild_id, user_id, month, day),
        )
        await db.commit()


async def list_birthdays_for_date(guild_id: int, month: int, day: int) -> List[int]:
    async with _get_db() as db:
        rows = await _fetchall(db, 
            "SELECT user_id FROM birthdays WHERE guild_id = ? AND month = ? AND day = ?",
            (guild_id, month, day),
        )
        return [r[0] for r in rows]


async def create_event(guild_id: int, channel_id: int, name: str, event_time: str, created_by: int) -> int:
    async with _get_db() as db:
        cursor = await db.execute(
            "INSERT INTO events (guild_id, channel_id, name, event_time, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (guild_id, channel_id, name, event_time, created_by, _utcnow()),
        )
        await db.commit()
        return cursor.lastrowid


async def list_upcoming_events(guild_id: int, now_iso: str, limit: int = 10) -> List[Dict[str, Any]]:
    async with _get_db() as db:

        rows = await _fetchall(db, 
            "SELECT id, channel_id, name, event_time FROM events WHERE guild_id = ? AND event_time >= ? ORDER BY event_time ASC LIMIT ?",
            (guild_id, now_iso, limit),
        )
        return [dict(r) for r in rows]


async def delete_event(event_id: int) -> None:
    async with _get_db() as db:
        await db.execute("DELETE FROM events WHERE id = ?", (event_id,))
        await db.commit()


async def set_verify_code(guild_id: int, user_id: int, code: str, expires_at: str) -> None:
    async with _get_db() as db:
        await db.execute(
            "INSERT INTO verify_codes (guild_id, user_id, code, expires_at, created_at) VALUES (?, ?, ?, ?, ?)\n"
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET code=excluded.code, expires_at=excluded.expires_at, created_at=excluded.created_at",
            (guild_id, user_id, code, expires_at, _utcnow()),
        )
        await db.commit()


async def get_verify_code(guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    async with _get_db() as db:

        row = await _fetchone(
            db,
            "SELECT code, expires_at, created_at FROM verify_codes WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return dict(row) if row else None


async def delete_verify_code(guild_id: int, user_id: int) -> None:
    async with _get_db() as db:
        await db.execute(
            "DELETE FROM verify_codes WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        await db.commit()


async def delete_expired_verify_codes(now_iso: str) -> None:
    async with _get_db() as db:
        await db.execute(
            "DELETE FROM verify_codes WHERE expires_at <= ?",
            (now_iso,),
        )
        await db.commit()


async def create_giveaway(
    guild_id: int,
    channel_id: int,
    message_id: int,
    prize: str,
    winner_count: int,
    ends_at: str,
    created_by: int,
) -> int:
    async with _get_db() as db:
        cursor = await db.execute(
            "INSERT INTO giveaways (guild_id, channel_id, message_id, prize, winner_count, ends_at, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (guild_id, channel_id, message_id, prize, winner_count, ends_at, created_by, _utcnow()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_giveaway(giveaway_id: int) -> Optional[Dict[str, Any]]:
    async with _get_db() as db:

        row = await _fetchone(db, "SELECT * FROM giveaways WHERE id = ?", (giveaway_id,))
        return dict(row) if row else None


async def get_giveaway_by_message(message_id: int) -> Optional[Dict[str, Any]]:
    async with _get_db() as db:

        row = await _fetchone(db, "SELECT * FROM giveaways WHERE message_id = ?", (message_id,))
        return dict(row) if row else None


async def list_open_giveaways(now_iso: str) -> List[Dict[str, Any]]:
    async with _get_db() as db:

        rows = await _fetchall(
            db,
            "SELECT * FROM giveaways WHERE ended_at IS NULL AND ends_at > ?",
            (now_iso,),
        )
        return [dict(r) for r in rows]


async def list_due_giveaways(now_iso: str) -> List[Dict[str, Any]]:
    async with _get_db() as db:

        rows = await _fetchall(
            db,
            "SELECT * FROM giveaways WHERE ended_at IS NULL AND ends_at <= ?",
            (now_iso,),
        )
        return [dict(r) for r in rows]


async def close_giveaway(giveaway_id: int, winners: List[int], ended_at: str) -> None:
    winners_json = json.dumps(winners)
    async with _get_db() as db:
        await db.execute(
            "UPDATE giveaways SET ended_at = ?, winners_json = ? WHERE id = ?",
            (ended_at, winners_json, giveaway_id),
        )
        await db.commit()


async def add_giveaway_entry(giveaway_id: int, user_id: int) -> bool:
    async with _get_db() as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO giveaway_entries (giveaway_id, user_id) VALUES (?, ?)",
            (giveaway_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def remove_giveaway_entry(giveaway_id: int, user_id: int) -> bool:
    async with _get_db() as db:
        cursor = await db.execute(
            "DELETE FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ?",
            (giveaway_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def list_giveaway_entries(giveaway_id: int) -> List[int]:
    async with _get_db() as db:
        rows = await _fetchall(
            db,
            "SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?",
            (giveaway_id,),
        )
        return [r[0] for r in rows]


async def delete_giveaway_entries(giveaway_id: int) -> None:
    async with _get_db() as db:
        await db.execute(
            "DELETE FROM giveaway_entries WHERE giveaway_id = ?",
            (giveaway_id,),
        )
        await db.commit()
