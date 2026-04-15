from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.embed_utils import make_embed, Colors


class ExtrasCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.started_at = datetime.now(timezone.utc)

    @app_commands.command(name="ping", description="Check bot latency.")
    async def ping(self, interaction: discord.Interaction) -> None:
        ms = int(self.bot.latency * 1000)
        color = Colors.SUCCESS if ms < 200 else Colors.ERROR
        await interaction.response.send_message(
            embed=make_embed(title="\U0001f3d3 pong!", description=f"**{ms}ms**", color=color),
            ephemeral=True,
        )

    @app_commands.command(name="avatar", description="Show a user's avatar.")
    async def avatar(self, interaction: discord.Interaction, member: Optional[discord.Member] = None) -> None:
        target = member or interaction.user
        if not target:
            return
        embed = make_embed(title=f"{target.display_name}'s avatar", color=Colors.INFO)
        embed.set_image(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="serverinfo", description="Show server info.")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        g = interaction.guild
        embed = make_embed(
            title=g.name,
            color=Colors.INFO,
            thumbnail_url=g.icon.url if g.icon else None,
        )
        embed.add_field(name="id", value=str(g.id), inline=True)
        embed.add_field(name="owner", value=str(g.owner) if g.owner else "unknown", inline=True)
        embed.add_field(name="members", value=str(g.member_count or 0), inline=True)
        embed.add_field(name="\U0001f4ac text", value=str(len(g.text_channels)), inline=True)
        embed.add_field(name="\U0001f3a4 voice", value=str(len(g.voice_channels)), inline=True)
        embed.add_field(name="\U0001f3ad roles", value=str(len(g.roles)), inline=True)
        embed.add_field(name="\U0001f4a0 boosts", value=f"{g.premium_subscription_count or 0} (tier {g.premium_tier})", inline=True)
        embed.add_field(name="created", value=g.created_at.strftime("%Y-%m-%d"), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="userinfo", description="Show user info.")
    async def userinfo(self, interaction: discord.Interaction, member: Optional[discord.Member] = None) -> None:
        if not interaction.guild:
            return
        target = member or interaction.user
        if not isinstance(target, discord.Member):
            return
        embed = make_embed(
            title=str(target),
            color=Colors.INFO,
            thumbnail_url=target.display_avatar.url,
        )
        embed.add_field(name="id", value=str(target.id), inline=True)
        top_role = target.top_role
        if top_role and top_role.name != "@everyone":
            embed.add_field(name="top role", value=top_role.mention, inline=True)
        embed.add_field(name="joined", value=target.joined_at.strftime("%Y-%m-%d") if target.joined_at else "unknown", inline=True)
        embed.add_field(name="created", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="roles", value=str(len(target.roles) - 1), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="uptime", description="Show bot uptime.")
    async def uptime(self, interaction: discord.Interaction) -> None:
        delta = datetime.now(timezone.utc) - self.started_at
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        await interaction.response.send_message(
            embed=make_embed(
                title="\u23f1 uptime",
                description=f"**{days}d {hours}h {minutes}m {seconds}s**",
                color=Colors.INFO,
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ExtrasCog(bot))
