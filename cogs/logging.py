from __future__ import annotations

import discord
from discord.ext import commands

from db import get_guild_config
from utils.guards import is_owner
from utils.logging_utils import send_log


class LoggingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if is_owner(member.id):
            return
        cfg = await get_guild_config(member.guild.id)
        if not cfg.get("logging_enabled"):
            return
        embed = discord.Embed(
            title="Member Joined",
            description=f"{member.mention} ({member.id})",
            color=discord.Color.green(),
        )
        await send_log(self.bot, member.guild.id, embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if is_owner(member.id):
            return
        cfg = await get_guild_config(member.guild.id)
        if not cfg.get("logging_enabled"):
            return
        embed = discord.Embed(
            title="Member Left",
            description=f"{member} ({member.id})",
            color=discord.Color.orange(),
        )
        await send_log(self.bot, member.guild.id, embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if not message.guild:
            return
        author = getattr(message, "author", None)
        if author and is_owner(getattr(author, "id", None)):
            return
        cfg = await get_guild_config(message.guild.id)
        if not cfg.get("logging_enabled"):
            return
        embed = discord.Embed(
            title="Message Deleted",
            description=f"Channel: {message.channel.mention}\nAuthor: {message.author.mention}\nContent: {message.content}",
            color=discord.Color.red(),
        )
        await send_log(self.bot, message.guild.id, embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if not before.guild or before.content == after.content:
            return
        if is_owner(getattr(before.author, "id", None)):
            return
        cfg = await get_guild_config(before.guild.id)
        if not cfg.get("logging_enabled"):
            return
        embed = discord.Embed(
            title="Message Edited",
            description=f"Channel: {before.channel.mention}\nAuthor: {before.author.mention}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Before", value=before.content or "None", inline=False)
        embed.add_field(name="After", value=after.content or "None", inline=False)
        await send_log(self.bot, before.guild.id, embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if not member.guild:
            return
        if is_owner(member.id):
            return
        cfg = await get_guild_config(member.guild.id)
        if not cfg.get("logging_enabled"):
            return
        if before.channel != after.channel:
            if after.channel:
                action = f"joined {after.channel.name}"
            elif before.channel:
                action = f"left {before.channel.name}"
            else:
                action = "changed voice state"
            embed = discord.Embed(
                title="Voice Update",
                description=f"{member.mention} {action}",
                color=discord.Color.teal(),
            )
            await send_log(self.bot, member.guild.id, embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LoggingCog(bot))
