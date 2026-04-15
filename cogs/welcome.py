from __future__ import annotations

import logging

import discord
from discord.ext import commands

from db import get_guild_config
from utils.guards import is_owner
from utils.embed_utils import make_embed, Colors


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if is_owner(member.id):
            return
        cfg = await get_guild_config(member.guild.id)
        if not cfg.get("welcome_enabled"):
            return
        channel_id = cfg.get("welcome_channel_id")
        if not channel_id:
            return
        channel = member.guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            return
        msg = (cfg.get("welcome_message") or "welcome {user} to {server}!").format(
            user=member.mention, server=member.guild.name
        )
        embed = make_embed(title="welcome!", description=msg, color=Colors.SUCCESS, thumbnail_url=member.display_avatar.url)
        embed.add_field(name="member #", value=str(member.guild.member_count or 0), inline=True)
        embed.add_field(name="created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
        await channel.send(embed=embed)

        auto_role_id = cfg.get("auto_role_id")
        if auto_role_id:
            role = member.guild.get_role(int(auto_role_id))
            if role:
                try:
                    await member.add_roles(role, reason="auto role")
                except Exception:
                    logging.exception("failed to assign auto role to member %s", member.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if is_owner(member.id):
            return
        cfg = await get_guild_config(member.guild.id)
        if not cfg.get("goodbye_enabled"):
            return
        channel_id = cfg.get("goodbye_channel_id")
        if not channel_id:
            return
        channel = member.guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            return
        msg = (cfg.get("goodbye_message") or "goodbye {user}.").format(user=member.name, server=member.guild.name)
        embed = make_embed(title="goodbye", description=msg, color=Colors.NEUTRAL, thumbnail_url=member.display_avatar.url)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if before.premium_since == after.premium_since or after.premium_since is None:
            return
        if is_owner(after.id):
            return
        cfg = await get_guild_config(after.guild.id)
        if not cfg.get("boost_enabled"):
            return
        channel_id = cfg.get("welcome_channel_id") or cfg.get("log_channel_id")
        if not channel_id:
            return
        channel = after.guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            return
        msg = (cfg.get("boost_message") or "thanks for boosting, {user}!").format(user=after.mention, server=after.guild.name)
        embed = make_embed(title="\U0001f4a0 server boost!", description=msg, color=Colors.SPECIAL, thumbnail_url=after.display_avatar.url)
        embed.add_field(name="total boosts", value=str(after.guild.premium_subscription_count or 0), inline=True)
        await channel.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot))
