from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from db import get_balance, get_leveling, get_badges, get_user_profile, get_user_items
from utils.leveling_utils import progress_to_next_level
from utils.card_drawer import draw_profile_card


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="profile", description="Show a user's profile card.")
    @app_commands.describe(theme="card theme: midnight, sunset, ocean, forest, sakura")
    async def profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
        theme: str = "midnight",
    ) -> None:
        if not interaction.guild:
            return
        target = member or interaction.user
        if not isinstance(target, discord.Member):
            return

        await interaction.response.defer(ephemeral=True)

        balance, _ = await get_balance(interaction.guild.id, target.id)
        leveling = await get_leveling(interaction.guild.id, target.id)
        badges = await get_badges(interaction.guild.id, target.id)
        prof = await get_user_profile(interaction.guild.id, target.id)
        items = await get_user_items(interaction.guild.id, target.id)

        level = int(leveling["level"])
        xp = int(leveling["xp"])
        progress, required = progress_to_next_level(xp)
        msg_count = int(leveling["message_count"])
        voice_min = int(leveling["voice_seconds"]) // 60

        # download avatar
        avatar_bytes = None
        try:
            avatar_bytes = await target.display_avatar.with_size(256).read()
        except Exception:
            pass

        # generate card in thread pool
        buf = await asyncio.to_thread(
            draw_profile_card,
            username=target.display_name,
            avatar_bytes=avatar_bytes,
            level=level,
            xp_progress=progress,
            xp_required=required,
            coins=balance,
            messages=msg_count,
            voice_minutes=voice_min,
            badges=badges,
            title=prof.get("title"),
            theme=theme if theme in ("midnight", "sunset", "ocean", "forest", "sakura") else "midnight",
        )

        file = discord.File(buf, filename="profile.png")
        await interaction.followup.send(file=file)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfileCog(bot))
