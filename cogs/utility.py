from __future__ import annotations

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from db import (
    get_guild_config,
    create_reminder,
    get_due_reminders,
    delete_reminder,
    set_birthday,
    list_birthdays_for_date,
    create_event,
    list_upcoming_events,
    delete_event,
    set_afk_status,
    get_afk_status,
    get_afk_statuses,
    clear_afk_status,
)
from utils.time_utils import parse_duration, format_duration
from utils.checks import is_moderator
from utils.guards import module_enabled


class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.reminder_loop.start()
        self.birthday_loop.start()
        self._last_birthday_date: Optional[str] = None

    async def cog_unload(self) -> None:
        self.reminder_loop.cancel()
        self.birthday_loop.cancel()

    def _format_afk_since(self, since_at: str) -> str:
        try:
            since_dt = datetime.fromisoformat(since_at)
            return discord.utils.format_dt(since_dt, style="R")
        except Exception:
            return "some time ago"

    @tasks.loop(seconds=30)
    async def reminder_loop(self) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        due = await get_due_reminders(now_iso)
        for reminder in due:
            channel = self.bot.get_channel(int(reminder["channel_id"]))
            if not isinstance(channel, discord.TextChannel):
                await delete_reminder(reminder["id"])
                continue
            try:
                await channel.send(f"<@{reminder['user_id']}> Reminder: {reminder['message']}")
            except Exception:
                logging.debug("failed to send reminder message", exc_info=True)
            await delete_reminder(reminder["id"])

    @tasks.loop(minutes=60)
    async def birthday_loop(self) -> None:
        today = datetime.now(timezone.utc).strftime("%m-%d")
        if self._last_birthday_date == today:
            return
        self._last_birthday_date = today
        month = int(today.split("-")[0])
        day = int(today.split("-")[1])
        for guild in self.bot.guilds:
            cfg = await get_guild_config(guild.id)
            channel_id = cfg.get("welcome_channel_id") or cfg.get("log_channel_id")
            if not channel_id:
                continue
            channel = guild.get_channel(int(channel_id))
            if not isinstance(channel, discord.TextChannel):
                continue
            users = await list_birthdays_for_date(guild.id, month, day)
            for user_id in users:
                await channel.send(f"Happy birthday <@{user_id}>! 🎉")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        author_afk = await get_afk_status(message.guild.id, message.author.id)
        if author_afk:
            was_cleared = await clear_afk_status(message.guild.id, message.author.id)
            if was_cleared:
                reason = author_afk.get("reason") or "AFK"
                since_text = self._format_afk_since(str(author_afk.get("since_at") or ""))
                await message.reply(
                    f"Welcome back, AFK removed. Previous reason: {reason} ({since_text}).",
                    mention_author=False,
                    delete_after=20,
                )
        if not message.mentions:
            return
        mentioned_ids = list({member.id for member in message.mentions if not member.bot and member.id != message.author.id})
        if not mentioned_ids:
            return
        afk_map = await get_afk_statuses(message.guild.id, mentioned_ids)
        if not afk_map:
            return
        lines = []
        for member in message.mentions:
            if member.id not in afk_map:
                continue
            afk_data = afk_map[member.id]
            reason = str(afk_data.get("reason") or "AFK")
            since_text = self._format_afk_since(str(afk_data.get("since_at") or ""))
            lines.append(f"{member.mention} is AFK: {reason} ({since_text})")
            if len(lines) >= 5:
                break
        if lines:
            await message.reply("\n".join(lines), mention_author=False, delete_after=20)

    @app_commands.command(name="remind", description="Set a reminder (e.g. 10m, 2h, 1d).")
    async def remind(self, interaction: discord.Interaction, duration: str, message: str) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "reminders_enabled", interaction.user.id):
            await interaction.response.send_message("Reminders are disabled.", ephemeral=True)
            return
        try:
            seconds = parse_duration(duration)
        except Exception:
            await interaction.response.send_message("Invalid duration.", ephemeral=True)
            return
        remind_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        await create_reminder(interaction.user.id, interaction.guild.id, interaction.channel_id, message, remind_at.isoformat())
        await interaction.response.send_message(f"Reminder set for {format_duration(seconds)}.", ephemeral=True)

    @app_commands.command(name="birthday", description="Set your birthday (MM-DD).")
    async def birthday(self, interaction: discord.Interaction, date: str) -> None:
        if not interaction.guild:
            return
        try:
            month, day = date.split("-")
            month_i = int(month)
            day_i = int(day)
        except Exception:
            await interaction.response.send_message("Use MM-DD format.", ephemeral=True)
            return
        await set_birthday(interaction.guild.id, interaction.user.id, month_i, day_i)
        await interaction.response.send_message("Birthday saved.", ephemeral=True)

    @app_commands.command(name="event_create", description="Create an event (YYYY-MM-DD HH:MM UTC).")
    async def event_create(self, interaction: discord.Interaction, name: str, when: str) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "reminders_enabled", interaction.user.id):
            await interaction.response.send_message("Events are disabled.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not await is_moderator(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        try:
            event_time = datetime.strptime(when, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except Exception:
            await interaction.response.send_message("Invalid date format.", ephemeral=True)
            return
        event_id = await create_event(interaction.guild.id, interaction.channel_id, name, event_time.isoformat(), interaction.user.id)
        await interaction.response.send_message(f"Event created with ID {event_id}.", ephemeral=True)

    @app_commands.command(name="event_list", description="List upcoming events.")
    async def event_list(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "reminders_enabled", interaction.user.id):
            await interaction.response.send_message("Events are disabled.", ephemeral=True)
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        events = await list_upcoming_events(interaction.guild.id, now_iso, 10)
        if not events:
            await interaction.response.send_message("No upcoming events.", ephemeral=True)
            return
        lines = [f"{e['id']} - {e['name']} at {e['event_time']}" for e in events]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="event_delete", description="Delete an event by ID.")
    async def event_delete(self, interaction: discord.Interaction, event_id: int) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "reminders_enabled", interaction.user.id):
            await interaction.response.send_message("Events are disabled.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not await is_moderator(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        await delete_event(event_id)
        await interaction.response.send_message("Event deleted.", ephemeral=True)

    @app_commands.command(name="afk", description="Set your AFK status.")
    async def afk(self, interaction: discord.Interaction, reason: str = "AFK") -> None:
        if not interaction.guild:
            return
        final_reason = reason.strip() or "AFK"
        if len(final_reason) > 120:
            await interaction.response.send_message("AFK reason must be 120 characters or fewer.", ephemeral=True)
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        await set_afk_status(interaction.guild.id, interaction.user.id, final_reason, now_iso)
        await interaction.response.send_message(f"AFK enabled: {final_reason}", ephemeral=True)

    @app_commands.command(name="unafk", description="Disable your AFK status.")
    async def unafk(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        removed = await clear_afk_status(interaction.guild.id, interaction.user.id)
        if removed:
            await interaction.response.send_message("AFK disabled.", ephemeral=True)
            return
        await interaction.response.send_message("You are not AFK.", ephemeral=True)

    @app_commands.command(name="choose", description="Choose one option from a list separated by |.")
    async def choose(self, interaction: discord.Interaction, options: str) -> None:
        items = [item.strip() for item in options.split("|") if item.strip()]
        if len(items) < 2:
            await interaction.response.send_message("Provide at least two options separated by |.", ephemeral=True)
            return
        picked = random.choice(items)
        await interaction.response.send_message(f"I choose: {picked}", ephemeral=True)

    @app_commands.command(name="roll", description="Roll dice.")
    async def roll(
        self,
        interaction: discord.Interaction,
        sides: app_commands.Range[int, 2, 1000] = 6,
        count: app_commands.Range[int, 1, 20] = 1,
    ) -> None:
        results = [random.randint(1, sides) for _ in range(count)]
        total = sum(results)
        joined = ", ".join(str(v) for v in results)
        await interaction.response.send_message(
            f"Rolled {count}d{sides}: {joined} | Total: {total}",
            ephemeral=True,
        )

    @app_commands.command(name="coinflip", description="Flip a coin.")
    async def coinflip(self, interaction: discord.Interaction) -> None:
        side = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(f"Coinflip: {side}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilityCog(bot))
