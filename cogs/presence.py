from __future__ import annotations

import logging

import discord
from discord.ext import commands, tasks

from config import (
    PRESENCE_STATUS,
    PRESENCE_ACTIVITY_TYPE,
    PRESENCE_ACTIVITY_TEXT,
    PRESENCE_STREAM_URL,
    PRESENCE_ROTATION_ENABLED,
)


STATUS_ROTATION_SECONDS = 5

GAME_STATUS_MESSAGES = [
    "Honkai: Star Rail",
    "Zenless Zone Zero",
    "Genshin Impact",
    "Wuthering Waves",
    "Arknight: Endfield",
    "Hatsune Miku: Colorful Stage!",
    "osu!",
    "osu!taiko",
    "osu!mania",
    "Beat Saber",
    "Cytus",
    "Cytus II",
    "Deemo",
    "Deemo II",
    "VOEZ",
    "Arcaea",
    "Lanota",
    "Muse Dash",
    "Phigros",
    "Rizline",
    "Dynamix",
    "Tone Sphere",
    "Groove Coaster",
    "Project DIVA Mega Mix+",
    "Hatsune Miku: Project DIVA Future Tone",
    "Hatsune Miku: Project DIVA X",
    "DJMAX Respect V",
    "EZ2ON REBOOT : R",
    "Sound Voltex Exceed Gear",
    "beatmania IIDX",
    "pop'n music",
    "jubeat",
    "DanceDanceRevolution",
    "Pump It Up: Phoenix",
    "maimai DX",
    "CHUNITHM",
    "Taiko no Tatsujin",
    "Rhythm Doctor",
    "Rhythm Heaven Fever",
    "Rhythm Heaven Megamix",
    "A Dance of Fire and Ice",
    "Spin Rhythm XD",
    "Trombone Champ",
    "Melatonin",
    "Hi-Fi RUSH",
    "Crypt of the NecroDancer",
    "BPM: Bullets Per Minute",
    "Kingdom Hearts: Melody of Memory",
    "Theatrhythm Final Bar Line",
    "Superbeat: XONiC",
    "Pistol Whip",
    "Sixtar Gate: STARTRAIL",
]


def _status_from_config() -> discord.Status:
    mapping = {
        "online": discord.Status.online,
        "idle": discord.Status.idle,
        "dnd": discord.Status.dnd,
        "invisible": discord.Status.invisible,
    }
    return mapping.get(PRESENCE_STATUS, discord.Status.dnd)


def _static_activity() -> discord.BaseActivity | None:
    if not PRESENCE_ACTIVITY_TEXT:
        return None
    if PRESENCE_ACTIVITY_TYPE == "streaming" and PRESENCE_STREAM_URL:
        return discord.Streaming(name=PRESENCE_ACTIVITY_TEXT, url=PRESENCE_STREAM_URL)
    type_map = {
        "playing": discord.ActivityType.playing,
        "listening": discord.ActivityType.listening,
        "watching": discord.ActivityType.watching,
        "competing": discord.ActivityType.competing,
        "custom": discord.ActivityType.custom,
    }
    activity_type = type_map.get(PRESENCE_ACTIVITY_TYPE, discord.ActivityType.playing)
    if activity_type == discord.ActivityType.custom:
        return discord.CustomActivity(name=PRESENCE_ACTIVITY_TEXT)
    return discord.Activity(type=activity_type, name=PRESENCE_ACTIVITY_TEXT)


class PresenceCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._index = 0

    async def cog_load(self) -> None:
        if PRESENCE_ROTATION_ENABLED:
            self.rotate_status.start()
        else:
            await self._set_static_presence()

    async def cog_unload(self) -> None:
        if PRESENCE_ROTATION_ENABLED:
            self.rotate_status.cancel()

    async def _set_static_presence(self) -> None:
        await self.bot.wait_until_ready()
        try:
            await self.bot.change_presence(status=_status_from_config(), activity=_static_activity())
        except Exception:
            logging.exception("failed to set static presence")

    @tasks.loop(seconds=STATUS_ROTATION_SECONDS)
    async def rotate_status(self) -> None:
        await self.bot.wait_until_ready()
        message = GAME_STATUS_MESSAGES[self._index % len(GAME_STATUS_MESSAGES)]
        self._index += 1
        status = _status_from_config()
        try:
            activity = discord.Game(name=message)
            await self.bot.change_presence(status=status, activity=activity)
        except Exception:
            try:
                activity = discord.Activity(type=discord.ActivityType.playing, name=message)
                await self.bot.change_presence(status=status, activity=activity)
            except Exception:
                logging.exception("failed to rotate presence")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PresenceCog(bot))
