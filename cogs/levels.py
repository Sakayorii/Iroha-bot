from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Dict

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    XP_PER_MESSAGE_MIN,
    XP_PER_MESSAGE_MAX,
    XP_COOLDOWN_SECONDS,
    VOICE_XP_PER_MIN,
    DAILY_TASK_MESSAGES,
    DAILY_TASK_VOICE_MINUTES,
    DAILY_TASK_GAMES,
)
from db import (
    get_guild_config,
    get_leveling,
    set_leveling,
    get_leaderboard,
    increment_message_count,
    increment_voice_seconds,
    add_badge,
    get_badges,
    get_daily_tasks,
    upsert_daily_task,
    update_daily_progress,
)
from utils.leveling_utils import level_from_xp, progress_to_next_level
from utils.guards import bot_ratio_exceeded, module_enabled, is_owner

BADGE_MILESTONES: dict[int, str] = {5: "Rising Star", 10: "Iroha Fan", 20: "Regular", 30: "Diva"}


def _date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class LevelsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.last_xp: Dict[int, Dict[int, float]] = {}
        self.voice_sessions: Dict[int, Dict[int, float]] = {}

    def _cooldown_ok(self, guild_id: int, user_id: int) -> bool:
        if guild_id not in self.last_xp:
            self.last_xp[guild_id] = {}
        now = datetime.now(timezone.utc).timestamp()
        last = self.last_xp[guild_id].get(user_id, 0.0)
        if now - last < XP_COOLDOWN_SECONDS:
            return False
        self.last_xp[guild_id][user_id] = now
        return True

    async def _ensure_daily_tasks(self, guild_id: int, user_id: int) -> None:
        date = _date_str()
        tasks = await get_daily_tasks(guild_id, user_id, date)
        if tasks:
            return
        await upsert_daily_task(guild_id, user_id, date, "messages", DAILY_TASK_MESSAGES, 0, 0)
        await upsert_daily_task(guild_id, user_id, date, "voice_minutes", DAILY_TASK_VOICE_MINUTES, 0, 0)
        await upsert_daily_task(guild_id, user_id, date, "games", DAILY_TASK_GAMES, 0, 0)

    async def _check_badges(self, guild_id: int, user_id: int, level: int) -> None:
        if level in BADGE_MILESTONES:
            await add_badge(guild_id, user_id, BADGE_MILESTONES[level])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        if is_owner(message.author.id):
            return
        cfg = await get_guild_config(message.guild.id)
        if not module_enabled(cfg, "leveling_enabled", message.author.id):
            return
        if bot_ratio_exceeded(message.guild, cfg, message.author.id):
            return
        await increment_message_count(message.guild.id, message.author.id, 1)
        await self._ensure_daily_tasks(message.guild.id, message.author.id)
        await update_daily_progress(message.guild.id, message.author.id, _date_str(), "messages", 1)
        if not self._cooldown_ok(message.guild.id, message.author.id):
            return
        data = await get_leveling(message.guild.id, message.author.id)
        xp_gain = random.randint(XP_PER_MESSAGE_MIN, XP_PER_MESSAGE_MAX)
        new_xp = int(data["xp"]) + xp_gain
        new_level = level_from_xp(new_xp)
        await set_leveling(message.guild.id, message.author.id, new_xp, new_level, datetime.now(timezone.utc).isoformat())
        if new_level > int(data["level"]):
            await self._check_badges(message.guild.id, message.author.id, new_level)
            try:
                from utils.embed_utils import make_embed, Colors
                badge_name = BADGE_MILESTONES.get(new_level)
                desc = f"{message.author.mention} reached **level {new_level}**!"
                if badge_name:
                    desc += f"\n\U0001f3c5 new badge: **{badge_name}**"
                embed = make_embed(
                    title="\u2b06 level up!",
                    description=desc,
                    color=Colors.SPECIAL,
                    thumbnail_url=message.author.display_avatar.url,
                )
                await message.channel.send(embed=embed)
            except Exception:
                logging.debug("failed to send level up message", exc_info=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if not member.guild or member.bot:
            return
        if is_owner(member.id):
            guild_sessions = self.voice_sessions.get(member.guild.id)
            if guild_sessions and member.id in guild_sessions:
                guild_sessions.pop(member.id, None)
            return
        cfg = await get_guild_config(member.guild.id)
        if not module_enabled(cfg, "leveling_enabled", member.id):
            return
        if bot_ratio_exceeded(member.guild, cfg, member.id):
            return
        guild_id = member.guild.id
        if guild_id not in self.voice_sessions:
            self.voice_sessions[guild_id] = {}
        if before.channel is None and after.channel is not None:
            self.voice_sessions[guild_id][member.id] = datetime.now(timezone.utc).timestamp()
            return
        if before.channel is not None and after.channel is None:
            start = self.voice_sessions[guild_id].pop(member.id, None)
            if not start:
                return
            seconds = int(datetime.now(timezone.utc).timestamp() - start)
            if seconds <= 0:
                return
            await increment_voice_seconds(guild_id, member.id, seconds)
            await self._ensure_daily_tasks(guild_id, member.id)
            minutes = max(1, seconds // 60)
            await update_daily_progress(guild_id, member.id, _date_str(), "voice_minutes", minutes)
            data = await get_leveling(guild_id, member.id)
            new_xp = int(data["xp"]) + minutes * VOICE_XP_PER_MIN
            new_level = level_from_xp(new_xp)
            await set_leveling(guild_id, member.id, new_xp, new_level, datetime.now(timezone.utc).isoformat())
        if before.channel is not None and after.channel is not None and before.channel != after.channel:
            guild_sessions = self.voice_sessions.get(guild_id, {})
            start = guild_sessions.get(member.id)
            if start:
                seconds = int(datetime.now(timezone.utc).timestamp() - start)
                if seconds > 0:
                    await increment_voice_seconds(guild_id, member.id, seconds)
            self.voice_sessions[guild_id][member.id] = datetime.now(timezone.utc).timestamp()

    @app_commands.command(name="rank", description="Show your rank.")
    @app_commands.describe(theme="card theme: midnight, sunset, ocean, forest, sakura")
    async def rank(self, interaction: discord.Interaction, member: discord.Member | None = None, theme: str = "midnight") -> None:
        if not interaction.guild:
            return
        target = member or interaction.user
        if not isinstance(target, discord.Member):
            return
        await interaction.response.defer(ephemeral=True)
        import asyncio
        from utils.card_drawer import draw_rank_card

        data = await get_leveling(interaction.guild.id, target.id)
        level = int(data["level"])
        progress, required = progress_to_next_level(int(data["xp"]))

        # compute rank position
        leaders = await get_leaderboard(interaction.guild.id, 100)
        rank_pos = 0
        for idx, entry in enumerate(leaders):
            if int(entry["user_id"]) == target.id:
                rank_pos = idx + 1
                break

        avatar_bytes = None
        try:
            avatar_bytes = await target.display_avatar.with_size(256).read()
        except Exception:
            pass

        buf = await asyncio.to_thread(
            draw_rank_card,
            username=target.display_name,
            avatar_bytes=avatar_bytes,
            level=level,
            rank=rank_pos,
            xp_progress=progress,
            xp_required=required,
            messages=int(data["message_count"]),
            voice_minutes=int(data["voice_seconds"]) // 60,
            theme=theme if theme in ("midnight", "sunset", "ocean", "forest", "sakura") else "midnight",
        )
        file = discord.File(buf, filename="rank.png")
        await interaction.followup.send(file=file)

    @app_commands.command(name="leaderboard", description="Show the XP leaderboard.")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        from utils.embed_utils import Colors, medal_prefix
        from utils.view_utils import PaginatorView
        leaders = await get_leaderboard(interaction.guild.id, 100)
        if not leaders:
            from utils.embed_utils import make_embed
            await interaction.response.send_message(
                embed=make_embed(title="leaderboard", description="no data yet.", color=Colors.NEUTRAL),
                ephemeral=True,
            )
            return
        guild = interaction.guild

        def fmt(idx: int, entry: dict) -> str:
            user = guild.get_member(int(entry["user_id"]))
            name = user.display_name if user else str(entry["user_id"])
            return f"{medal_prefix(idx)} **{name}** \u2014 level {entry['level']} ({int(entry['xp']):,} xp)"

        view = PaginatorView(
            items=leaders, per_page=10, title="\U0001f3c6 leaderboard",
            color=Colors.SPECIAL, formatter_fn=fmt,
            author_id=interaction.user.id,
        )
        await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LevelsCog(bot))
