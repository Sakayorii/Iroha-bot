from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import discord
from discord import app_commands
from discord.ext import commands

from db import get_leveling, set_leveling, set_balance
from utils.leveling_utils import level_from_xp, xp_for_level
from utils.superusers import is_primary_owner, add_superuser, remove_superuser, list_superusers


class OwnerAdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _owner_only(self, interaction: discord.Interaction) -> bool:
        if not is_primary_owner(interaction.user.id):
            await interaction.response.send_message("Only OWNER_ID can use this command.", ephemeral=True)
            return False
        if not interaction.guild:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return False
        return True

    @app_commands.command(name="owner_setxp", description="OWNER_ID only: set a user's XP.")
    async def owner_setxp(self, interaction: discord.Interaction, member: discord.Member, xp: int) -> None:
        if not await self._owner_only(interaction):
            return
        xp_value = max(0, int(xp))
        level_value = level_from_xp(xp_value)
        now_iso = datetime.now(timezone.utc).isoformat()
        await get_leveling(interaction.guild.id, member.id)
        await set_leveling(interaction.guild.id, member.id, xp_value, level_value, now_iso)
        await interaction.response.send_message(
            f"Updated {member.mention}: XP={xp_value}, Level={level_value}.",
            ephemeral=True,
        )

    @app_commands.command(name="owner_setlevel", description="OWNER_ID only: set a user's level.")
    async def owner_setlevel(self, interaction: discord.Interaction, member: discord.Member, level: int) -> None:
        if not await self._owner_only(interaction):
            return
        level_value = max(1, int(level))
        xp_value = xp_for_level(level_value)
        now_iso = datetime.now(timezone.utc).isoformat()
        await get_leveling(interaction.guild.id, member.id)
        await set_leveling(interaction.guild.id, member.id, xp_value, level_value, now_iso)
        await interaction.response.send_message(
            f"Updated {member.mention}: Level={level_value}, XP floor={xp_value}.",
            ephemeral=True,
        )

    @app_commands.command(name="owner_setcoins", description="OWNER_ID only: set a user's coin balance.")
    async def owner_setcoins(self, interaction: discord.Interaction, member: discord.Member, coins: int) -> None:
        if not await self._owner_only(interaction):
            return
        amount = max(0, int(coins))
        result = await set_balance(interaction.guild.id, member.id, amount)
        await interaction.response.send_message(
            f"Updated {member.mention}: coins={result}.",
            ephemeral=True,
        )

    @app_commands.command(name="owner_addsuperuser", description="OWNER_ID only: add a co-owner superuser.")
    async def owner_addsuperuser(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if not await self._owner_only(interaction):
            return
        if add_superuser(member.id):
            await interaction.response.send_message(f"Added {member.mention} as superuser.", ephemeral=True)
            return
        await interaction.response.send_message("Cannot add this user as superuser.", ephemeral=True)

    @app_commands.command(name="owner_removesuperuser", description="OWNER_ID only: remove a co-owner superuser.")
    async def owner_removesuperuser(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if not await self._owner_only(interaction):
            return
        if remove_superuser(member.id):
            await interaction.response.send_message(f"Removed {member.mention} from superusers.", ephemeral=True)
            return
        await interaction.response.send_message("This user is not a superuser.", ephemeral=True)

    @app_commands.command(name="owner_listsuperusers", description="OWNER_ID only: list all co-owner superusers.")
    async def owner_listsuperusers(self, interaction: discord.Interaction) -> None:
        if not await self._owner_only(interaction):
            return
        ids: List[int] = list_superusers()
        if not ids:
            await interaction.response.send_message("No superusers configured.", ephemeral=True)
            return
        lines = []
        for user_id in ids:
            member = interaction.guild.get_member(user_id)
            if member:
                lines.append(f"{member.display_name} ({user_id})")
            else:
                lines.append(str(user_id))
        await interaction.response.send_message("Superusers:\n" + "\n".join(lines), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OwnerAdminCog(bot))
