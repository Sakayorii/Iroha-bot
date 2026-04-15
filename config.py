from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
CACHE_DIR = Path(os.getenv("CACHE_DIR", DATA_DIR / "cache"))
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "bot.db"))

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
GOD_MODE_ENABLED = os.getenv("GOD_MODE_ENABLED", "1") == "1"
BOT_VERSION = os.getenv("BOT_VERSION", "iroha-1.0.0").strip()

PRESENCE_STATUS = os.getenv("PRESENCE_STATUS", "dnd").strip().lower()
PRESENCE_ACTIVITY_TYPE = os.getenv("PRESENCE_ACTIVITY_TYPE", "playing").strip().lower()
PRESENCE_ACTIVITY_TEXT = os.getenv("PRESENCE_ACTIVITY_TEXT", "being iroha").strip()
PRESENCE_STREAM_URL = os.getenv("PRESENCE_STREAM_URL", "").strip()
PRESENCE_ROTATION_ENABLED = os.getenv("PRESENCE_ROTATION_ENABLED", "1") == "1"
PRESENCE_ROTATION_INTERVAL = int(os.getenv("PRESENCE_ROTATION_INTERVAL", "5"))

AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1").strip()
AI_MODEL = os.getenv("AI_MODEL", "llama-3.3-70b-versatile").strip()
AI_VISION_MODEL = os.getenv("AI_VISION_MODEL", "llama-3.2-90b-vision-preview").strip()


CACHE_TTL_MINUTES = int(os.getenv("CACHE_TTL_MINUTES", "1440"))
CACHE_MAX_GB = float(os.getenv("CACHE_MAX_GB", "10"))
MUSIC_QUALITY = os.getenv("MUSIC_QUALITY", "bestaudio")
MUSIC_MAX_QUEUE = int(os.getenv("MUSIC_MAX_QUEUE", "100"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

DEFAULT_LOCALE = os.getenv("DEFAULT_LOCALE", "en").strip()
MAX_AI_HISTORY = int(os.getenv("MAX_AI_HISTORY", "8"))
AI_COOLDOWN_SECONDS = int(os.getenv("AI_COOLDOWN_SECONDS", "8"))

VERIFY_CODE_TTL_MINUTES = int(os.getenv("VERIFY_CODE_TTL_MINUTES", "10"))

ANTI_SPAM_ENABLED = os.getenv("ANTI_SPAM_ENABLED", "1") == "1"
ANTI_SPAM_RATE = int(os.getenv("ANTI_SPAM_RATE", "6"))
ANTI_SPAM_INTERVAL = int(os.getenv("ANTI_SPAM_INTERVAL", "8"))
MAX_MENTIONS = int(os.getenv("MAX_MENTIONS", "5"))

ANTI_RAID_ENABLED = os.getenv("ANTI_RAID_ENABLED", "1") == "1"
ANTI_RAID_THRESHOLD = int(os.getenv("ANTI_RAID_THRESHOLD", "6"))
ANTI_RAID_WINDOW = int(os.getenv("ANTI_RAID_WINDOW", "10"))

ANTI_INVITE_ENABLED = os.getenv("ANTI_INVITE_ENABLED", "1") == "1"
ANTI_LINK_ENABLED = os.getenv("ANTI_LINK_ENABLED", "0") == "1"
ANTI_NSFW_ENABLED = os.getenv("ANTI_NSFW_ENABLED", "1") == "1"

TICKET_CATEGORY_NAME = os.getenv("TICKET_CATEGORY_NAME", "Iroha Tickets")

XP_PER_MESSAGE_MIN = int(os.getenv("XP_PER_MESSAGE_MIN", "10"))
XP_PER_MESSAGE_MAX = int(os.getenv("XP_PER_MESSAGE_MAX", "20"))
XP_COOLDOWN_SECONDS = int(os.getenv("XP_COOLDOWN_SECONDS", "45"))
DAILY_REWARD = int(os.getenv("DAILY_REWARD", "250"))
FISH_REWARD = int(os.getenv("FISH_REWARD", "20"))
POKEMON_REWARD = int(os.getenv("POKEMON_REWARD", "30"))
VOICE_XP_PER_MIN = int(os.getenv("VOICE_XP_PER_MIN", "2"))

DAILY_TASK_MESSAGES = int(os.getenv("DAILY_TASK_MESSAGES", "30"))
DAILY_TASK_VOICE_MINUTES = int(os.getenv("DAILY_TASK_VOICE_MINUTES", "15"))
DAILY_TASK_GAMES = int(os.getenv("DAILY_TASK_GAMES", "2"))

BOT_RATIO_GUARD_ENABLED = os.getenv("BOT_RATIO_GUARD_ENABLED", "1") == "1"
BOT_RATIO_MAX = float(os.getenv("BOT_RATIO_MAX", "0.6"))
