from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

import discord
from discord.ext import commands
from discord import app_commands

from config import DISCORD_TOKEN, LOG_LEVEL, DATA_DIR, CACHE_DIR
from db import init_db, close_pool
from utils.ai_client import AIClient
from utils.guards import is_owner


COGS = [
    "cogs.setup",
    "cogs.presence",
    "cogs.logging",
    "cogs.welcome",
    "cogs.moderation",
    "cogs.verification",
    "cogs.music",
    "cogs.ai_chat",
    "cogs.levels",
    "cogs.economy",
    "cogs.games",
    "cogs.utility",
    "cogs.giveaway",
    "cogs.extras",
    "cogs.tickets",
    "cogs.roles",
    "cogs.polls",
    "cogs.profile",
    "cogs.links",
    "cogs.owner_admin",
]


class RateLimitCommandTree(app_commands.CommandTree):
    def __init__(self, client: commands.Bot) -> None:
        super().__init__(client)
        self._user_buckets: dict[int, deque[float]] = defaultdict(deque)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.type is discord.InteractionType.autocomplete:
            return True
        if interaction.guild is None:
            try:
                message = "This bot can only be used in servers, not in DMs."
                if not interaction.response.is_done():
                    await interaction.response.send_message(message, ephemeral=True)
                else:
                    await interaction.followup.send(message, ephemeral=True)
            except Exception:
                logging.debug("failed to send dm-only error message", exc_info=True)
            return False
        user = interaction.user
        if user is None:
            return True
        if is_owner(user.id):
            return True
        now = time.monotonic()
        bucket = self._user_buckets[user.id]
        while bucket and now - bucket[0] > 5.0:
            bucket.popleft()
        if len(bucket) >= 3:
            try:
                message = "You're using commands too quickly (3 commands/5s). Please wait a moment."
                if not interaction.response.is_done():
                    await interaction.response.send_message(message, ephemeral=True)
                else:
                    await interaction.followup.send(message, ephemeral=True)
            except Exception:
                logging.debug("failed to send rate limit message", exc_info=True)
            return False
        bucket.append(now)
        return True


class IrohaBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents, tree_cls=RateLimitCommandTree)
        self.ai_client = AIClient()

    async def setup_hook(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        await init_db()
        for ext in COGS:
            try:
                await self.load_extension(ext)
            except Exception as exc:
                logging.exception("Failed to load %s: %s", ext, exc)
        try:
            await self.tree.sync()
        except Exception as exc:
            logging.exception("Command sync failed: %s", exc)

    async def on_ready(self) -> None:
        logging.info("Logged in as %s (ID: %s)", self.user, self.user.id if self.user else "unknown")


def main() -> None:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is missing")
    bot = IrohaBot()
    try:
        bot.run(DISCORD_TOKEN)
    finally:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        loop.run_until_complete(close_pool())


if __name__ == "__main__":
    main()