from __future__ import annotations

import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import MAX_MENTIONS
from db import (
    add_warning,
    clear_warnings,
    get_guild_config,
    get_warnings,
    add_blocked_word,
    remove_blocked_word,
    list_blocked_words,
)
from utils.guards import bot_ratio_exceeded, is_owner
from utils.checks import is_moderator
from utils.logging_utils import send_log


INVITE_RE = re.compile(r"(discord\.gg/|discord\.com/invite/)", re.IGNORECASE)
LINK_RE = re.compile(r"https?://", re.IGNORECASE)
NSFW_WORDS = {"nsfw", "porn", "hentai", "sex", "nude"}


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.message_timestamps: Dict[int, Dict[int, Deque[float]]] = defaultdict(lambda: defaultdict(deque))
        self.message_content: Dict[int, Dict[int, Deque[str]]] = defaultdict(lambda: defaultdict(deque))
        self.join_times: Dict[int, Deque[float]] = defaultdict(deque)

    @property
    def _bot_id(self) -> int:
        return self._bot_id

    async def _can_moderate(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False
        if await is_moderator(interaction.user):
            return True
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return False

    async def _timeout_member(self, member: discord.Member, minutes: int, reason: str) -> None:
        try:
            until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            await member.timeout(until, reason=reason)
        except Exception:
            logging.exception("failed to timeout member %s", member.id)

    async def _send_log_if_visible(self, guild_id: int, actor_id: int | None, content: str) -> None:
        if is_owner(actor_id):
            return
        await send_log(self.bot, guild_id, content=content)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if is_owner(member.id):
            return
        cfg = await get_guild_config(member.guild.id)
        if bot_ratio_exceeded(member.guild, cfg):
            await self._send_log_if_visible(member.guild.id, member.id, "Bot ratio guard: bots exceed humans.")
        if not cfg.get("anti_raid_enabled"):
            return
        now = datetime.now(timezone.utc).timestamp()
        bucket = self.join_times[member.guild.id]
        bucket.append(now)
        window = int(cfg.get("anti_raid_window") or 10)
        threshold = int(cfg.get("anti_raid_threshold") or 6)
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= threshold:
            await self._timeout_member(member, 10, "Anti-raid protection")
            await self._send_log_if_visible(member.guild.id, member.id, f"Anti-raid: timed out {member.mention}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if is_owner(member.id):
            return
        cfg = await get_guild_config(member.guild.id)
        if bot_ratio_exceeded(member.guild, cfg):
            await self._send_log_if_visible(member.guild.id, member.id, "Bot ratio guard: bots exceed humans.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        if is_owner(message.author.id):
            return
        cfg = await get_guild_config(message.guild.id)
        if (
            not cfg.get("anti_spam_enabled")
            and not cfg.get("anti_invite_enabled")
            and not cfg.get("anti_link_enabled")
            and not cfg.get("anti_nsfw_enabled")
        ):
            return

        if isinstance(message.author, discord.Member):
            if await is_moderator(message.author):
                return

        max_mentions = int(cfg.get("max_mentions") or MAX_MENTIONS)
        if max_mentions > 0 and len(message.mentions) >= max_mentions:
            try:
                await message.delete()
            except Exception:
                logging.exception("failed to delete mass mention message %s", message.id)
            await self._timeout_member(message.author, 5, "Mass mention spam")
            await add_warning(message.guild.id, message.author.id, self._bot_id, "Mass mention spam")
            return

        content_lower = (message.content or "").lower()

        if content_lower:
            blocked = await list_blocked_words(message.guild.id)
            for word in blocked:
                if word.lower() in content_lower:
                    try:
                        await message.delete()
                    except Exception:
                        logging.exception("failed to delete blocked word message %s", message.id)
                    await add_warning(message.guild.id, message.author.id, self._bot_id, f"Blocked word: {word}")
                    return

        if cfg.get("anti_invite_enabled") and INVITE_RE.search(content_lower):
            try:
                await message.delete()
            except Exception:
                logging.exception("failed to delete invite link message %s", message.id)
            await add_warning(message.guild.id, message.author.id, self._bot_id, "Invite link")
            return

        if cfg.get("anti_link_enabled") and LINK_RE.search(content_lower):
            try:
                await message.delete()
            except Exception:
                logging.exception("failed to delete link message %s", message.id)
            await add_warning(message.guild.id, message.author.id, self._bot_id, "Link not allowed")
            return

        if cfg.get("anti_nsfw_enabled") and isinstance(message.channel, discord.TextChannel) and not message.channel.is_nsfw():
            if any(word in content_lower for word in NSFW_WORDS):
                try:
                    await message.delete()
                except Exception:
                    logging.exception("failed to delete nsfw message %s", message.id)
                await add_warning(message.guild.id, message.author.id, self._bot_id, "NSFW content")
                return

        if cfg.get("anti_spam_enabled"):
            now = datetime.now(timezone.utc).timestamp()
            bucket = self.message_timestamps[message.guild.id][message.author.id]
            bucket.append(now)
            interval = int(cfg.get("anti_spam_interval") or 8)
            rate = int(cfg.get("anti_spam_rate") or 6)
            while bucket and now - bucket[0] > interval:
                bucket.popleft()
            if len(bucket) > rate:
                try:
                    await message.delete()
                except Exception:
                    logging.exception("failed to delete spam message %s", message.id)
                await self._timeout_member(message.author, 5, "Spam detected")
                await add_warning(message.guild.id, message.author.id, self._bot_id, "Spam detected")
                return

            content_bucket = self.message_content[message.guild.id][message.author.id]
            content_bucket.append(content_lower)
            while len(content_bucket) > 3:
                content_bucket.popleft()
            if len(content_bucket) == 3 and len(set(content_bucket)) == 1:
                try:
                    await message.delete()
                except Exception:
                    logging.exception("failed to delete duplicate spam message %s", message.id)
                await self._timeout_member(message.author, 5, "Duplicate spam")
                await add_warning(message.guild.id, message.author.id, self._bot_id, "Duplicate spam")
                return

    @app_commands.command(name="warn", description="Warn a user.")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None) -> None:
        if not await self._can_moderate(interaction):
            return
        reason = reason or "No reason provided."
        await add_warning(interaction.guild.id, member.id, interaction.user.id, reason)
        await interaction.response.send_message(f"Warned {member.mention}: {reason}", ephemeral=True)
        await self._send_log_if_visible(interaction.guild.id, interaction.user.id, f"Warn: {member} by {interaction.user} - {reason}")

    @app_commands.command(name="warnings", description="Show a user's warnings.")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if not await self._can_moderate(interaction):
            return
        records = await get_warnings(interaction.guild.id, member.id)
        if not records:
            await interaction.response.send_message("No warnings found.", ephemeral=True)
            return
        lines = [f"{r['id']}: {r['reason']} ({r['created_at']})" for r in records[:10]]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="clearwarnings", description="Clear a user's warnings.")
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if not await self._can_moderate(interaction):
            return
        await clear_warnings(interaction.guild.id, member.id)
        await interaction.response.send_message(f"Warnings cleared for {member.mention}.", ephemeral=True)
        await self._send_log_if_visible(interaction.guild.id, interaction.user.id, f"Warnings cleared for {member} by {interaction.user}")

    @app_commands.command(name="timeout", description="Timeout a user.")
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: Optional[str] = None) -> None:
        if not await self._can_moderate(interaction):
            return
        await self._timeout_member(member, minutes, reason or "Timeout")
        await interaction.response.send_message(f"Timed out {member.mention} for {minutes} minutes.", ephemeral=True)
        await self._send_log_if_visible(interaction.guild.id, interaction.user.id, f"Timeout: {member} by {interaction.user} for {minutes}m")

    @app_commands.command(name="kick", description="Kick a user.")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None) -> None:
        if not await self._can_moderate(interaction):
            return
        try:
            await member.kick(reason=reason)
        except Exception:
            await interaction.response.send_message("Failed to kick user.", ephemeral=True)
            return
        await interaction.response.send_message(f"Kicked {member.mention}.", ephemeral=True)
        await self._send_log_if_visible(interaction.guild.id, interaction.user.id, f"Kick: {member} by {interaction.user}")

    @app_commands.command(name="ban", description="Ban a user.")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None) -> None:
        if not await self._can_moderate(interaction):
            return
        try:
            await member.ban(reason=reason)
        except Exception:
            await interaction.response.send_message("Failed to ban user.", ephemeral=True)
            return
        await interaction.response.send_message(f"Banned {member.mention}.", ephemeral=True)
        await self._send_log_if_visible(interaction.guild.id, interaction.user.id, f"Ban: {member} by {interaction.user}")

    @app_commands.command(name="unban", description="Unban a user by ID.")
    async def unban(self, interaction: discord.Interaction, user_id: str) -> None:
        if not await self._can_moderate(interaction):
            return
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
        except Exception:
            await interaction.response.send_message("Failed to unban user.", ephemeral=True)
            return
        await interaction.response.send_message(f"Unbanned {user_id}.", ephemeral=True)
        await self._send_log_if_visible(interaction.guild.id, interaction.user.id, f"Unban: {user_id} by {interaction.user}")

    @app_commands.command(name="purge", description="Purge messages.")
    async def purge(self, interaction: discord.Interaction, amount: int) -> None:
        if not await self._can_moderate(interaction):
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        deleted = await interaction.channel.purge(limit=min(amount, 100))
        await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)
        await self._send_log_if_visible(interaction.guild.id, interaction.user.id, f"Purge: {len(deleted)} messages by {interaction.user}")

    @app_commands.command(name="filter_add", description="Add a blocked word.")
    async def filter_add(self, interaction: discord.Interaction, word: str) -> None:
        if not await self._can_moderate(interaction):
            return
        await add_blocked_word(interaction.guild.id, word)
        await interaction.response.send_message(f"Blocked word added: {word}", ephemeral=True)

    @app_commands.command(name="filter_remove", description="Remove a blocked word.")
    async def filter_remove(self, interaction: discord.Interaction, word: str) -> None:
        if not await self._can_moderate(interaction):
            return
        await remove_blocked_word(interaction.guild.id, word)
        await interaction.response.send_message(f"Blocked word removed: {word}", ephemeral=True)

    @app_commands.command(name="filter_list", description="List blocked words.")
    async def filter_list(self, interaction: discord.Interaction) -> None:
        if not await self._can_moderate(interaction):
            return
        words = await list_blocked_words(interaction.guild.id)
        if not words:
            await interaction.response.send_message("No blocked words.", ephemeral=True)
            return
        await interaction.response.send_message(", ".join(words[:50]), ephemeral=True)


    @app_commands.command(name="purge", description="Delete messages (works for >14 days too).")
    async def purge(self, interaction: discord.Interaction, amount: int) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not await is_moderator(interaction.user):
            await interaction.response.send_message("no permission.", ephemeral=True)
            return
        if amount < 1 or amount > 500:
            await interaction.response.send_message("1-500.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        deleted = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)

        # try bulk delete first for recent messages
        recent = []
        old = []
        async for msg in channel.history(limit=amount):
            if msg.created_at > cutoff:
                recent.append(msg)
            else:
                old.append(msg)

        # bulk delete recent (<14 days)
        if recent:
            try:
                for i in range(0, len(recent), 100):
                    batch = recent[i:i+100]
                    await channel.delete_messages(batch)
                    deleted += len(batch)
            except Exception:
                # fallback to individual delete
                for msg in recent:
                    try:
                        await msg.delete()
                        deleted += 1
                    except Exception:
                        pass

        # individual delete old (>14 days)
        for msg in old:
            try:
                await msg.delete()
                deleted += 1
            except Exception:
                pass

        from utils.embed_utils import make_embed, Colors
        await interaction.followup.send(
            embed=make_embed(description=f"\U0001f5d1 deleted {deleted} messages.", color=Colors.SUCCESS),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog(bot))
